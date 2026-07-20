"""Calculate deterministic pixel differences between aligned images."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from visual_verifier.exceptions import MediaCompatibilityError
from visual_verifier.type_aliases import ImageArray, MaskArray

SUPPORTED_IMAGE_DIMENSIONS_TUPLE = (2, 3)
GRAYSCALE_CHANNEL_COUNT_INT = 1
BGR_CHANNEL_COUNT_INT = 3
BGRA_CHANNEL_COUNT_INT = 4
MINIMUM_PIXEL_THRESHOLD_INT = 0
MAXIMUM_PIXEL_THRESHOLD_INT = 255


@dataclass(frozen=True, slots=True)
class PixelDifferenceStatistics:
    """Store pixel-difference measurements for one aligned region.

    Attributes:
        changed_pixels: Number of pixels exceeding the threshold.
        changed_ratio: Fraction of pixels exceeding the threshold.
        mean_difference: Mean absolute grayscale difference.
        maximum_difference: Maximum absolute grayscale difference.
    """

    changed_pixels: int
    changed_ratio: float
    mean_difference: float
    maximum_difference: float

    def to_dict(self) -> dict[str, int | float]:
        """Return a machine-readable statistics representation.

        Returns:
            Dictionary containing every pixel-difference measurement.
        """

        return {
            "changed_pixels": self.changed_pixels,
            "changed_ratio": self.changed_ratio,
            "mean_difference": self.mean_difference,
            "maximum_difference": self.maximum_difference,
        }


def _normalize_uint8_array(
    source_array_ndarray: NDArray[Any],
) -> ImageArray:
    """Return a contiguous unsigned 8-bit copy or view of an array.

    Args:
        source_array_ndarray: Numeric array produced by NumPy or OpenCV.

    Returns:
        Contiguous array with an unsigned 8-bit data type.
    """

    contiguous_array_ndarray = np.ascontiguousarray(
        source_array_ndarray,
    )
    return contiguous_array_ndarray.astype(
        np.uint8,
        copy=False,
    )


def _raise_for_invalid_image_array(
    image_ndarray: ImageArray,
    image_role_str: str,
) -> None:
    """Validate one image array before pixel operations.

    Args:
        image_ndarray: Image array to validate.
        image_role_str: Human-readable role such as reference or candidate.

    Raises:
        MediaCompatibilityError: When the array is empty or unsupported.
    """

    if image_ndarray.size == 0:
        raise MediaCompatibilityError(
            f"The {image_role_str} image array is empty.",
            context_mapping={"image_role": image_role_str},
        )
    if image_ndarray.ndim not in SUPPORTED_IMAGE_DIMENSIONS_TUPLE:
        raise MediaCompatibilityError(
            f"The {image_role_str} image dimensions are unsupported.",
            context_mapping={
                "image_role": image_role_str,
                "dimensions": image_ndarray.ndim,
            },
        )


def _raise_for_incompatible_spatial_shapes(
    reference_image_ndarray: ImageArray,
    candidate_image_ndarray: ImageArray,
) -> None:
    """Validate equal spatial dimensions for an aligned image pair.

    Args:
        reference_image_ndarray: Reference image or video frame.
        candidate_image_ndarray: Candidate image or video frame.

    Raises:
        MediaCompatibilityError: When height or width values differ.
    """

    reference_shape_tuple = reference_image_ndarray.shape[:2]
    candidate_shape_tuple = candidate_image_ndarray.shape[:2]

    if reference_shape_tuple == candidate_shape_tuple:
        return
    raise MediaCompatibilityError(
        "Reference and candidate image dimensions do not match.",
        context_mapping={
            "reference_shape": reference_shape_tuple,
            "candidate_shape": candidate_shape_tuple,
        },
    )


def _raise_for_invalid_threshold(
    difference_threshold_int: int,
) -> None:
    """Validate an unsigned 8-bit pixel-difference threshold.

    Args:
        difference_threshold_int: Inclusive threshold comparison value.

    Raises:
        ValueError: When the threshold is outside the 0 to 255 range.
    """

    threshold_is_valid_bool = (
        MINIMUM_PIXEL_THRESHOLD_INT
        <= difference_threshold_int
        <= MAXIMUM_PIXEL_THRESHOLD_INT
    )
    if not threshold_is_valid_bool:
        raise ValueError("difference_threshold_int must be between 0 and 255.")


def convert_image_to_grayscale(
    image_ndarray: ImageArray,
    *,
    image_role_str: str = "input",
) -> ImageArray:
    """Convert a supported image array into unsigned 8-bit grayscale.

    Args:
        image_ndarray: Grayscale, BGR, or BGRA image array.
        image_role_str: Human-readable role used in error diagnostics.

    Returns:
        Two-dimensional unsigned 8-bit grayscale image.

    Raises:
        MediaCompatibilityError: When the channel layout is unsupported.
    """

    _raise_for_invalid_image_array(image_ndarray, image_role_str)
    if image_ndarray.ndim == 2:
        return _normalize_uint8_array(image_ndarray)

    channel_count_int = int(image_ndarray.shape[2])
    if channel_count_int == GRAYSCALE_CHANNEL_COUNT_INT:
        single_channel_ndarray = image_ndarray[:, :, 0]
        return _normalize_uint8_array(single_channel_ndarray)
    if channel_count_int == BGR_CHANNEL_COUNT_INT:
        bgr_grayscale_ndarray = cv2.cvtColor(
            image_ndarray,
            cv2.COLOR_BGR2GRAY,
        )
        return _normalize_uint8_array(bgr_grayscale_ndarray)
    if channel_count_int == BGRA_CHANNEL_COUNT_INT:
        bgra_grayscale_ndarray = cv2.cvtColor(
            image_ndarray,
            cv2.COLOR_BGRA2GRAY,
        )
        return _normalize_uint8_array(bgra_grayscale_ndarray)

    raise MediaCompatibilityError(
        f"The {image_role_str} image channel count is unsupported.",
        context_mapping={
            "image_role": image_role_str,
            "channel_count": channel_count_int,
        },
    )


def calculate_grayscale_difference(
    reference_image_ndarray: ImageArray,
    candidate_image_ndarray: ImageArray,
) -> ImageArray:
    """Calculate absolute grayscale difference for an aligned image pair.

    Args:
        reference_image_ndarray: Reference image or video frame.
        candidate_image_ndarray: Candidate image or video frame.

    Returns:
        Unsigned 8-bit absolute grayscale difference image.

    Raises:
        MediaCompatibilityError: When spatial dimensions are incompatible.
    """

    _raise_for_invalid_image_array(
        reference_image_ndarray,
        "reference",
    )
    _raise_for_invalid_image_array(
        candidate_image_ndarray,
        "candidate",
    )
    _raise_for_incompatible_spatial_shapes(
        reference_image_ndarray,
        candidate_image_ndarray,
    )
    reference_grayscale_ndarray = convert_image_to_grayscale(
        reference_image_ndarray,
        image_role_str="reference",
    )
    candidate_grayscale_ndarray = convert_image_to_grayscale(
        candidate_image_ndarray,
        image_role_str="candidate",
    )
    difference_ndarray = cv2.absdiff(
        reference_grayscale_ndarray,
        candidate_grayscale_ndarray,
    )
    return _normalize_uint8_array(difference_ndarray)


def create_changed_pixel_mask(
    difference_ndarray: ImageArray,
    difference_threshold_int: int,
) -> MaskArray:
    """Create a binary mask for pixels exceeding a difference threshold.

    Args:
        difference_ndarray: Two-dimensional grayscale difference image.
        difference_threshold_int: Strict changed-pixel threshold.

    Returns:
        Binary unsigned 8-bit mask containing values 0 and 255.

    Raises:
        MediaCompatibilityError: When the difference array is not grayscale.
        ValueError: When the threshold is outside the 0 to 255 range.
    """

    _raise_for_invalid_image_array(difference_ndarray, "difference")
    _raise_for_invalid_threshold(difference_threshold_int)
    if difference_ndarray.ndim != 2:
        raise MediaCompatibilityError(
            "The difference array must be two-dimensional grayscale.",
            context_mapping={"dimensions": difference_ndarray.ndim},
        )
    changed_mask_bool_ndarray = difference_ndarray > difference_threshold_int
    changed_mask_uint8_ndarray = changed_mask_bool_ndarray.astype(
        np.uint8,
        copy=False,
    )
    scaled_mask_ndarray = np.multiply(
        changed_mask_uint8_ndarray,
        np.uint8(MAXIMUM_PIXEL_THRESHOLD_INT),
        dtype=np.uint8,
    )
    return _normalize_uint8_array(scaled_mask_ndarray)


def calculate_pixel_difference_statistics(
    difference_ndarray: ImageArray,
    difference_threshold_int: int,
) -> PixelDifferenceStatistics:
    """Calculate thresholded and continuous pixel-difference statistics.

    Args:
        difference_ndarray: Two-dimensional grayscale difference image.
        difference_threshold_int: Strict changed-pixel threshold.

    Returns:
        Immutable pixel-difference statistics.

    Raises:
        MediaCompatibilityError: When the difference array is invalid.
        ValueError: When the threshold is outside the 0 to 255 range.
    """

    changed_mask_ndarray = create_changed_pixel_mask(
        difference_ndarray,
        difference_threshold_int,
    )
    changed_pixels_int = int(np.count_nonzero(changed_mask_ndarray))
    total_pixels_int = int(difference_ndarray.size)
    changed_ratio_float = (
        changed_pixels_int / total_pixels_int if total_pixels_int > 0 else 0.0
    )
    return PixelDifferenceStatistics(
        changed_pixels=changed_pixels_int,
        changed_ratio=float(changed_ratio_float),
        mean_difference=float(np.mean(difference_ndarray)),
        maximum_difference=float(np.max(difference_ndarray)),
    )


def grayscale_difference(
    reference: ImageArray,
    candidate: ImageArray,
) -> ImageArray:
    """Return absolute grayscale difference using the legacy API name.

    Args:
        reference: Reference image or video frame.
        candidate: Candidate image or video frame.

    Returns:
        Unsigned 8-bit absolute grayscale difference image.

    Warning:
        New package code should call ``calculate_grayscale_difference``.
    """

    return calculate_grayscale_difference(reference, candidate)


__all__ = [
    "PixelDifferenceStatistics",
    "calculate_grayscale_difference",
    "calculate_pixel_difference_statistics",
    "convert_image_to_grayscale",
    "create_changed_pixel_mask",
    "grayscale_difference",
]
