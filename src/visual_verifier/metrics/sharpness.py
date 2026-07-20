"""Calculate deterministic image sharpness and edge-detail metrics."""

from __future__ import annotations

from dataclasses import dataclass

import cv2

from visual_verifier.metrics.pixel import convert_image_to_grayscale
from visual_verifier.type_aliases import ImageArray

SHARPNESS_EPSILON_FLOAT = 1.0e-9
PERCENT_SCALE_FLOAT = 100.0


@dataclass(frozen=True, slots=True)
class SharpnessStatistics:
    """Store comparative sharpness measurements for an aligned image pair.

    Attributes:
        reference_variance: Reference-image Laplacian variance.
        candidate_variance: Candidate-image Laplacian variance.
        candidate_percentage: Candidate sharpness relative to reference.
        relative_change: Signed fractional change from reference sharpness.
    """

    reference_variance: float
    candidate_variance: float
    candidate_percentage: float
    relative_change: float

    @property
    def candidate_is_sharper(self) -> bool:
        """Return whether the candidate has greater Laplacian variance.

        Returns:
            True when candidate variance exceeds reference variance.
        """

        return self.candidate_variance > self.reference_variance

    def to_dict(self) -> dict[str, float | bool]:
        """Return a machine-readable representation.

        Returns:
            Dictionary containing all comparative sharpness metrics.
        """

        return {
            "reference_variance": self.reference_variance,
            "candidate_variance": self.candidate_variance,
            "candidate_percentage": self.candidate_percentage,
            "relative_change": self.relative_change,
            "candidate_is_sharper": self.candidate_is_sharper,
        }


def calculate_laplacian_variance(
    image_ndarray: ImageArray | None,
) -> float:
    """Measure image edge detail using Laplacian variance.

    Args:
        image_ndarray: Grayscale, BGR, or BGRA image or cropped region.

    Returns:
        Non-negative Laplacian variance. Empty or missing images return zero.

    Raises:
        MediaCompatibilityError: When the image layout is unsupported.

    Warning:
        High-frequency noise can increase this metric even when perceptual
        image quality has not improved.
    """

    if image_ndarray is None or image_ndarray.size == 0:
        return 0.0

    grayscale_image_ndarray = convert_image_to_grayscale(
        image_ndarray,
        image_role_str="sharpness input",
    )
    laplacian_ndarray = cv2.Laplacian(
        grayscale_image_ndarray,
        cv2.CV_64F,
    )
    return max(0.0, float(laplacian_ndarray.var()))


def calculate_candidate_sharpness_percentage(
    reference_variance_float: float,
    candidate_variance_float: float,
    *,
    epsilon_float: float = SHARPNESS_EPSILON_FLOAT,
) -> float:
    """Calculate candidate sharpness as a percentage of reference.

    Args:
        reference_variance_float: Reference Laplacian variance.
        candidate_variance_float: Candidate Laplacian variance.
        epsilon_float: Minimum usable reference variance.

    Returns:
        Candidate-to-reference percentage, or positive infinity when the
        reference variance is effectively zero.

    Raises:
        ValueError: When any variance or epsilon value is negative.
    """

    _raise_for_invalid_sharpness_values(
        reference_variance_float,
        candidate_variance_float,
        epsilon_float,
    )
    if reference_variance_float <= epsilon_float:
        return float("inf")
    return (
        candidate_variance_float
        * PERCENT_SCALE_FLOAT
        / reference_variance_float
    )


def calculate_relative_sharpness_change(
    reference_variance_float: float,
    candidate_variance_float: float,
    *,
    epsilon_float: float = SHARPNESS_EPSILON_FLOAT,
) -> float:
    """Calculate signed fractional sharpness change from reference.

    Args:
        reference_variance_float: Reference Laplacian variance.
        candidate_variance_float: Candidate Laplacian variance.
        epsilon_float: Minimum usable reference variance.

    Returns:
        Signed fractional change. Positive values indicate greater candidate
        variance. Zero is returned for an effectively flat reference.

    Raises:
        ValueError: When any variance or epsilon value is negative.
    """

    _raise_for_invalid_sharpness_values(
        reference_variance_float,
        candidate_variance_float,
        epsilon_float,
    )
    if reference_variance_float <= epsilon_float:
        return 0.0
    return (
        candidate_variance_float - reference_variance_float
    ) / reference_variance_float


def calculate_sharpness_statistics(
    reference_image_ndarray: ImageArray | None,
    candidate_image_ndarray: ImageArray | None,
) -> SharpnessStatistics:
    """Calculate comparative sharpness metrics for an image pair.

    Args:
        reference_image_ndarray: Reference image or cropped region.
        candidate_image_ndarray: Processed candidate image or cropped region.

    Returns:
        Immutable comparative sharpness statistics.

    Raises:
        MediaCompatibilityError: When either image layout is unsupported.
    """

    reference_variance_float = calculate_laplacian_variance(
        reference_image_ndarray,
    )
    candidate_variance_float = calculate_laplacian_variance(
        candidate_image_ndarray,
    )
    candidate_percentage_float = calculate_candidate_sharpness_percentage(
        reference_variance_float,
        candidate_variance_float,
    )
    relative_change_float = calculate_relative_sharpness_change(
        reference_variance_float,
        candidate_variance_float,
    )
    return SharpnessStatistics(
        reference_variance=reference_variance_float,
        candidate_variance=candidate_variance_float,
        candidate_percentage=candidate_percentage_float,
        relative_change=relative_change_float,
    )


def _raise_for_invalid_sharpness_values(
    reference_variance_float: float,
    candidate_variance_float: float,
    epsilon_float: float,
) -> None:
    """Validate numerical values used by comparative sharpness metrics.

    Args:
        reference_variance_float: Reference Laplacian variance.
        candidate_variance_float: Candidate Laplacian variance.
        epsilon_float: Minimum usable reference variance.

    Raises:
        ValueError: When any supplied value is negative.
    """

    values_are_valid_bool = (
        reference_variance_float >= 0.0
        and candidate_variance_float >= 0.0
        and epsilon_float >= 0.0
    )
    if not values_are_valid_bool:
        raise ValueError(
            "Sharpness variances and epsilon_float must be non-negative."
        )


def laplacian_variance(image: ImageArray | None) -> float:
    """Measure edge detail using the legacy public function name.

    Args:
        image: Grayscale, BGR, or BGRA image or cropped region.

    Returns:
        Non-negative Laplacian variance.

    Raises:
        MediaCompatibilityError: When the image layout is unsupported.
    """

    return calculate_laplacian_variance(image)


__all__ = [
    "SHARPNESS_EPSILON_FLOAT",
    "SharpnessStatistics",
    "calculate_candidate_sharpness_percentage",
    "calculate_laplacian_variance",
    "calculate_relative_sharpness_change",
    "calculate_sharpness_statistics",
    "laplacian_variance",
]
