"""Calculate bounding-box geometry for visual verification workflows."""

from __future__ import annotations

from visual_verifier.models import BoundingBox


def _validate_frame_dimensions(
    frame_width_int: int,
    frame_height_int: int,
) -> None:
    """Validate that frame dimensions are non-negative.

    Args:
        frame_width_int: Frame width in pixels.
        frame_height_int: Frame height in pixels.

    Raises:
        ValueError: If either frame dimension is negative.
    """

    if frame_width_int < 0:
        raise ValueError("Frame width cannot be negative.")

    if frame_height_int < 0:
        raise ValueError("Frame height cannot be negative.")


def clip_box_to_frame(
    bounding_box_obj: BoundingBox,
    frame_width_int: int,
    frame_height_int: int,
) -> BoundingBox:
    """Clip a bounding box to valid frame boundaries.

    Args:
        bounding_box_obj: Bounding box to constrain.
        frame_width_int: Frame width in pixels.
        frame_height_int: Frame height in pixels.

    Returns:
        A bounding box whose coordinates lie inside the frame.

    Raises:
        ValueError: If either frame dimension is negative.
    """

    _validate_frame_dimensions(
        frame_width_int=frame_width_int,
        frame_height_int=frame_height_int,
    )

    return BoundingBox(
        x1=max(0, min(frame_width_int, bounding_box_obj.x1)),
        y1=max(0, min(frame_height_int, bounding_box_obj.y1)),
        x2=max(0, min(frame_width_int, bounding_box_obj.x2)),
        y2=max(0, min(frame_height_int, bounding_box_obj.y2)),
    )


def calculate_intersection_box(
    first_box_obj: BoundingBox,
    second_box_obj: BoundingBox,
) -> BoundingBox:
    """Calculate the overlapping box shared by two bounding boxes.

    Args:
        first_box_obj: First bounding box.
        second_box_obj: Second bounding box.

    Returns:
        The overlapping bounding box. A non-overlap produces zero area.
    """

    return BoundingBox(
        x1=max(first_box_obj.x1, second_box_obj.x1),
        y1=max(first_box_obj.y1, second_box_obj.y1),
        x2=min(first_box_obj.x2, second_box_obj.x2),
        y2=min(first_box_obj.y2, second_box_obj.y2),
    )


def calculate_intersection_area(
    first_box_obj: BoundingBox,
    second_box_obj: BoundingBox,
) -> int:
    """Calculate the shared pixel area of two bounding boxes.

    Args:
        first_box_obj: First bounding box.
        second_box_obj: Second bounding box.

    Returns:
        Shared area in pixels, or zero when the boxes do not overlap.
    """

    intersection_box_obj = calculate_intersection_box(
        first_box_obj=first_box_obj,
        second_box_obj=second_box_obj,
    )
    return intersection_box_obj.area


def intersection_area(
    first_box_obj: BoundingBox,
    second_box_obj: BoundingBox,
) -> int:
    """Return the shared area while preserving the legacy public name.

    Args:
        first_box_obj: First bounding box.
        second_box_obj: Second bounding box.

    Returns:
        Shared area in pixels.

    Warning:
        Prefer ``calculate_intersection_area`` in new package code.
    """

    return calculate_intersection_area(
        first_box_obj=first_box_obj,
        second_box_obj=second_box_obj,
    )


def calculate_union_area(
    first_box_obj: BoundingBox,
    second_box_obj: BoundingBox,
) -> int:
    """Calculate the combined unique area of two bounding boxes.

    Args:
        first_box_obj: First bounding box.
        second_box_obj: Second bounding box.

    Returns:
        Union area in pixels.
    """

    intersection_area_int = calculate_intersection_area(
        first_box_obj=first_box_obj,
        second_box_obj=second_box_obj,
    )
    return first_box_obj.area + second_box_obj.area - intersection_area_int


def calculate_iou(
    first_box_obj: BoundingBox,
    second_box_obj: BoundingBox,
) -> float:
    """Calculate intersection over union for two bounding boxes.

    Args:
        first_box_obj: First bounding box.
        second_box_obj: Second bounding box.

    Returns:
        Intersection-over-union ratio in the inclusive range [0, 1].
    """

    intersection_area_int = calculate_intersection_area(
        first_box_obj=first_box_obj,
        second_box_obj=second_box_obj,
    )
    union_area_int = calculate_union_area(
        first_box_obj=first_box_obj,
        second_box_obj=second_box_obj,
    )

    if union_area_int <= 0:
        return 0.0

    return intersection_area_int / union_area_int


def calculate_target_coverage_ratio(
    target_box_obj: BoundingBox,
    processed_box_obj: BoundingBox,
) -> float:
    """Calculate the fraction of a target covered by processing.

    Args:
        target_box_obj: Region expected to receive processing.
        processed_box_obj: Region where processing was detected.

    Returns:
        Covered fraction of the target in the inclusive range [0, 1].
    """

    if target_box_obj.area <= 0:
        return 0.0

    intersection_area_int = calculate_intersection_area(
        first_box_obj=target_box_obj,
        second_box_obj=processed_box_obj,
    )
    return intersection_area_int / target_box_obj.area


__all__ = [
    "calculate_intersection_area",
    "calculate_intersection_box",
    "calculate_iou",
    "calculate_target_coverage_ratio",
    "calculate_union_area",
    "clip_box_to_frame",
    "intersection_area",
]
