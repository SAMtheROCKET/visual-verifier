"""Normalize image geometry for deterministic media comparison."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from visual_verifier.exceptions import MediaCompatibilityError
from visual_verifier.type_aliases import ImageArray

DEFAULT_RESIZE_INTERPOLATION_INT = cv2.INTER_LINEAR
MINIMUM_SPATIAL_DIMENSION_INT = 1
SUPPORTED_IMAGE_DIMENSIONS_TUPLE = (2, 3)


def _normalize_uint8_array(
    source_array_ndarray: NDArray[Any],
) -> ImageArray:
    """Return a contiguous unsigned 8-bit image array.

    Args:
        source_array_ndarray: Numeric image array produced by NumPy or
            OpenCV.

    Returns:
        Contiguous image array with an unsigned 8-bit data type.
    """

    contiguous_array_ndarray = np.ascontiguousarray(
        source_array_ndarray,
    )
    return contiguous_array_ndarray.astype(
        np.uint8,
        copy=False,
    )


def _raise_for_invalid_image(
    image_ndarray: ImageArray,
    image_role_str: str,
) -> None:
    """Validate one image before geometric normalization.

    Args:
        image_ndarray: Image or video-frame array to validate.
        image_role_str: Human-readable role used in diagnostics.

    Raises:
        MediaCompatibilityError: When the image is empty, has unsupported
            dimensions, or has invalid spatial dimensions.
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

    image_height_int, image_width_int = image_ndarray.shape[:2]
    spatial_dimensions_are_valid_bool = (
        image_height_int >= MINIMUM_SPATIAL_DIMENSION_INT
        and image_width_int >= MINIMUM_SPATIAL_DIMENSION_INT
    )
    if not spatial_dimensions_are_valid_bool:
        raise MediaCompatibilityError(
            f"The {image_role_str} image dimensions are invalid.",
            context_mapping={
                "image_role": image_role_str,
                "height": image_height_int,
                "width": image_width_int,
            },
        )


def _raise_for_invalid_target_dimensions(
    target_width_int: int,
    target_height_int: int,
) -> None:
    """Validate requested OpenCV resize dimensions.

    Args:
        target_width_int: Required output width in pixels.
        target_height_int: Required output height in pixels.

    Raises:
        ValueError: When either target dimension is less than one pixel.
    """

    dimensions_are_valid_bool = (
        target_width_int >= MINIMUM_SPATIAL_DIMENSION_INT
        and target_height_int >= MINIMUM_SPATIAL_DIMENSION_INT
    )
    if not dimensions_are_valid_bool:
        raise ValueError(
            "Target width and height must both be at least one pixel."
        )


def get_spatial_dimensions(
    image_ndarray: ImageArray,
    *,
    image_role_str: str = "input",
) -> tuple[int, int]:
    """Return image width and height in OpenCV order.

    Args:
        image_ndarray: Image or video-frame array to inspect.
        image_role_str: Human-readable role used in diagnostics.

    Returns:
        Two-item tuple containing width and height in pixels.

    Raises:
        MediaCompatibilityError: When the image array is invalid.
    """

    _raise_for_invalid_image(image_ndarray, image_role_str)
    image_height_int, image_width_int = image_ndarray.shape[:2]
    return int(image_width_int), int(image_height_int)


def have_matching_spatial_dimensions(
    reference_image_ndarray: ImageArray,
    candidate_image_ndarray: ImageArray,
) -> bool:
    """Return whether two images have identical width and height.

    Args:
        reference_image_ndarray: Reference image or video frame.
        candidate_image_ndarray: Candidate image or video frame.

    Returns:
        ``True`` when both spatial dimensions match, otherwise ``False``.

    Raises:
        MediaCompatibilityError: When either image array is invalid.
    """

    reference_dimensions_tuple = get_spatial_dimensions(
        reference_image_ndarray,
        image_role_str="reference",
    )
    candidate_dimensions_tuple = get_spatial_dimensions(
        candidate_image_ndarray,
        image_role_str="candidate",
    )
    return reference_dimensions_tuple == candidate_dimensions_tuple


def resize_image(
    image_ndarray: ImageArray,
    *,
    target_width_int: int,
    target_height_int: int,
    interpolation_int: int = DEFAULT_RESIZE_INTERPOLATION_INT,
) -> ImageArray:
    """Resize one image to explicit spatial dimensions.

    Args:
        image_ndarray: Image or video frame to resize.
        target_width_int: Required output width in pixels.
        target_height_int: Required output height in pixels.
        interpolation_int: OpenCV interpolation constant.

    Returns:
        Contiguous unsigned 8-bit resized image.

    Raises:
        MediaCompatibilityError: When the source image is invalid.
        ValueError: When either target dimension is invalid.
    """

    _raise_for_invalid_image(image_ndarray, "input")
    _raise_for_invalid_target_dimensions(
        target_width_int,
        target_height_int,
    )
    resized_image_ndarray = cv2.resize(
        image_ndarray,
        (target_width_int, target_height_int),
        interpolation=interpolation_int,
    )
    return _normalize_uint8_array(resized_image_ndarray)


def resize_candidate_to_reference(
    reference: ImageArray,
    candidate: ImageArray,
) -> ImageArray:
    """Resize a candidate image to reference spatial dimensions.

    This compatibility function preserves the existing public API. Channel
    counts are intentionally left unchanged because later metric functions
    normalize supported grayscale, BGR, and BGRA inputs independently.

    Args:
        reference: Reference image or video frame defining output size.
        candidate: Candidate image or video frame to normalize.

    Returns:
        Original candidate when dimensions already match, otherwise a
        resized unsigned 8-bit candidate image.

    Raises:
        MediaCompatibilityError: When either image array is invalid.
    """

    dimensions_match_bool = have_matching_spatial_dimensions(
        reference,
        candidate,
    )
    if dimensions_match_bool:
        return candidate

    reference_width_int, reference_height_int = get_spatial_dimensions(
        reference,
        image_role_str="reference",
    )
    return resize_image(
        candidate,
        target_width_int=reference_width_int,
        target_height_int=reference_height_int,
    )


__all__ = [
    "DEFAULT_RESIZE_INTERPOLATION_INT",
    "get_spatial_dimensions",
    "have_matching_spatial_dimensions",
    "resize_candidate_to_reference",
    "resize_image",
]
