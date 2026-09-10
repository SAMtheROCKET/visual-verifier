"""Global-metric baselines the benchmark compares against.

These are the checks teams actually reach for first: average the pixel
difference between two frames, or compute PSNR or SSIM, then threshold
it. They are implemented here rather than imported so the benchmark has
no dependency the package does not already carry, and so the comparison
cannot be accused of using a deliberately weakened version.

Each baseline returns one score per frame. A higher score always means
"more likely to have been left unprotected", so scoring can treat every
baseline identically.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from visual_verifier.type_aliases import ImageArray

SSIM_WINDOW_SIZE_INT = 11
SSIM_SIGMA_FLOAT = 1.5
SSIM_C1_FLOAT = (0.01 * 255.0) ** 2
SSIM_C2_FLOAT = (0.03 * 255.0) ** 2
MAXIMUM_PIXEL_VALUE_FLOAT = 255.0
PERFECT_PSNR_FLOAT = 100.0

FrameScorer = Callable[[ImageArray, ImageArray], float]


@dataclass(frozen=True, slots=True)
class Baseline:
    """One global-metric method under test.

    Attributes:
        name_str: Display name used in the published table.
        description_str: How the method decides a frame is unprotected.
        scorer: Callable returning a per-frame exposure score.
    """

    name_str: str
    description_str: str
    scorer: FrameScorer


def mean_absolute_difference_score(
    reference_ndarray: ImageArray,
    candidate_ndarray: ImageArray,
) -> float:
    """Return an exposure score from the mean absolute pixel difference.

    Args:
        reference_ndarray: Reference frame.
        candidate_ndarray: Candidate frame.

    Returns:
        Negated mean absolute difference, so a frame that barely changed
        scores high, matching the shared "higher means exposed" contract.
    """

    difference_ndarray = cv2.absdiff(reference_ndarray, candidate_ndarray)
    return -float(np.mean(difference_ndarray))


def peak_signal_noise_ratio_score(
    reference_ndarray: ImageArray,
    candidate_ndarray: ImageArray,
) -> float:
    """Return an exposure score from PSNR.

    Args:
        reference_ndarray: Reference frame.
        candidate_ndarray: Candidate frame.

    Returns:
        PSNR in decibels. A high value means the frames are nearly
        identical, which is what an unprotected frame looks like.
    """

    difference_ndarray = reference_ndarray.astype(
        np.float64
    ) - candidate_ndarray.astype(np.float64)
    mean_squared_error_float = float(np.mean(difference_ndarray**2))
    if mean_squared_error_float <= 0.0:
        return PERFECT_PSNR_FLOAT
    return float(
        10.0
        * np.log10(MAXIMUM_PIXEL_VALUE_FLOAT**2 / mean_squared_error_float)
    )


def structural_similarity_score(
    reference_ndarray: ImageArray,
    candidate_ndarray: ImageArray,
) -> float:
    """Return an exposure score from mean SSIM.

    Args:
        reference_ndarray: Reference frame.
        candidate_ndarray: Candidate frame.

    Returns:
        Mean SSIM over the frame. A high value means the frames are
        structurally alike, which is what an unprotected frame looks
        like.
    """

    reference_gray_ndarray = _to_grayscale_float(reference_ndarray)
    candidate_gray_ndarray = _to_grayscale_float(candidate_ndarray)
    return float(
        np.mean(
            _structural_similarity_map(
                reference_gray_ndarray, candidate_gray_ndarray
            )
        )
    )


def _to_grayscale_float(frame_ndarray: ImageArray) -> np.ndarray:
    """Return one frame as a single-channel float array.

    Args:
        frame_ndarray: Frame to convert.

    Returns:
        Grayscale frame as float64.
    """

    if frame_ndarray.ndim == 2:
        return frame_ndarray.astype(np.float64)
    return cv2.cvtColor(frame_ndarray, cv2.COLOR_BGR2GRAY).astype(np.float64)


def _structural_similarity_map(
    reference_ndarray: np.ndarray,
    candidate_ndarray: np.ndarray,
) -> np.ndarray:
    """Return the per-pixel SSIM map of two grayscale frames.

    This is the standard Gaussian-weighted formulation from Wang et al.
    with an 11x11 window and sigma 1.5.

    Args:
        reference_ndarray: Grayscale reference frame.
        candidate_ndarray: Grayscale candidate frame.

    Returns:
        The SSIM map.
    """

    reference_mean = _windowed_mean(reference_ndarray)
    candidate_mean = _windowed_mean(candidate_ndarray)
    reference_mean_squared = reference_mean**2
    candidate_mean_squared = candidate_mean**2
    mean_product = reference_mean * candidate_mean

    reference_variance = (
        _windowed_mean(reference_ndarray**2) - reference_mean_squared
    )
    candidate_variance = (
        _windowed_mean(candidate_ndarray**2) - candidate_mean_squared
    )
    covariance = (
        _windowed_mean(reference_ndarray * candidate_ndarray) - mean_product
    )

    numerator_ndarray = (2.0 * mean_product + SSIM_C1_FLOAT) * (
        2.0 * covariance + SSIM_C2_FLOAT
    )
    denominator_ndarray = (
        reference_mean_squared + candidate_mean_squared + SSIM_C1_FLOAT
    ) * (reference_variance + candidate_variance + SSIM_C2_FLOAT)
    return numerator_ndarray / denominator_ndarray


def _windowed_mean(values_ndarray: np.ndarray) -> np.ndarray:
    """Return the Gaussian-weighted local mean of one array.

    Args:
        values_ndarray: Array to smooth.

    Returns:
        The locally averaged array.
    """

    return cv2.GaussianBlur(
        values_ndarray,
        (SSIM_WINDOW_SIZE_INT, SSIM_WINDOW_SIZE_INT),
        SSIM_SIGMA_FLOAT,
    )


BASELINES_TUPLE: tuple[Baseline, ...] = (
    Baseline(
        name_str="Mean pixel difference",
        description_str="Flag a frame when the average change is small.",
        scorer=mean_absolute_difference_score,
    ),
    Baseline(
        name_str="PSNR threshold",
        description_str="Flag a frame when PSNR against the source is high.",
        scorer=peak_signal_noise_ratio_score,
    ),
    Baseline(
        name_str="SSIM threshold",
        description_str="Flag a frame when structural similarity is high.",
        scorer=structural_similarity_score,
    ),
)


def score_sequence(
    reference_path: Path,
    candidate_path: Path,
    baseline_obj: Baseline,
) -> list[float]:
    """Score every synchronized frame of one sequence.

    Args:
        reference_path: Reference clip.
        candidate_path: Candidate clip.
        baseline_obj: Method to score with.

    Returns:
        One exposure score per synchronized frame, in frame order.
    """

    return [
        baseline_obj.scorer(reference_ndarray, candidate_ndarray)
        for reference_ndarray, candidate_ndarray in _iter_frame_pairs(
            reference_path, candidate_path
        )
    ]


def _iter_frame_pairs(
    reference_path: Path,
    candidate_path: Path,
) -> Iterator[tuple[ImageArray, ImageArray]]:
    """Yield synchronized frame pairs from two clips.

    Args:
        reference_path: Reference clip.
        candidate_path: Candidate clip.

    Yields:
        Pairs of frames until either clip is exhausted.
    """

    reference_capture = cv2.VideoCapture(str(reference_path))
    candidate_capture = cv2.VideoCapture(str(candidate_path))
    try:
        while True:
            reference_ok_bool, reference_ndarray = reference_capture.read()
            candidate_ok_bool, candidate_ndarray = candidate_capture.read()
            if not reference_ok_bool or not candidate_ok_bool:
                return
            yield reference_ndarray, candidate_ndarray
    finally:
        reference_capture.release()
        candidate_capture.release()
