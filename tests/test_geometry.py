"""Test bounding-box geometry calculations and edge cases."""

import pytest

from visual_verifier.metrics import (
    calculate_intersection_area,
    calculate_intersection_box,
    calculate_iou,
    calculate_target_coverage_ratio,
    calculate_union_area,
    clip_box_to_frame,
    intersection_area,
)
from visual_verifier.models import BoundingBox

EXPECTED_INTERSECTION_AREA_INT = 25
EXPECTED_UNION_AREA_INT = 175
EXPECTED_IOU_FLOAT = 25 / 175
EXPECTED_TARGET_COVERAGE_FLOAT = 0.25


def test_overlapping_boxes_produce_expected_geometry() -> None:
    """Confirm overlap, union, IoU, and target coverage calculations."""

    first_box_obj = BoundingBox(0, 0, 10, 10)
    second_box_obj = BoundingBox(5, 5, 15, 15)

    intersection_box_obj = calculate_intersection_box(
        first_box_obj,
        second_box_obj,
    )

    assert intersection_box_obj == BoundingBox(5, 5, 10, 10)
    assert (
        calculate_intersection_area(first_box_obj, second_box_obj)
        == EXPECTED_INTERSECTION_AREA_INT
    )
    assert (
        intersection_area(first_box_obj, second_box_obj)
        == EXPECTED_INTERSECTION_AREA_INT
    )
    assert (
        calculate_union_area(first_box_obj, second_box_obj)
        == EXPECTED_UNION_AREA_INT
    )
    assert calculate_iou(
        first_box_obj,
        second_box_obj,
    ) == pytest.approx(EXPECTED_IOU_FLOAT)
    assert calculate_target_coverage_ratio(
        first_box_obj,
        second_box_obj,
    ) == pytest.approx(EXPECTED_TARGET_COVERAGE_FLOAT)


def test_disjoint_boxes_produce_zero_shared_metrics() -> None:
    """Confirm non-overlapping boxes have no intersection or coverage."""

    first_box_obj = BoundingBox(0, 0, 10, 10)
    second_box_obj = BoundingBox(20, 20, 30, 30)

    assert (
        calculate_intersection_area(
            first_box_obj,
            second_box_obj,
        )
        == 0
    )
    assert calculate_iou(first_box_obj, second_box_obj) == 0.0
    assert (
        calculate_target_coverage_ratio(
            first_box_obj,
            second_box_obj,
        )
        == 0.0
    )


def test_zero_area_boxes_produce_zero_ratios() -> None:
    """Confirm degenerate boxes do not cause division-by-zero errors."""

    zero_area_box_obj = BoundingBox(5, 5, 5, 10)
    valid_box_obj = BoundingBox(0, 0, 10, 10)

    assert calculate_iou(zero_area_box_obj, valid_box_obj) == 0.0
    assert (
        calculate_target_coverage_ratio(
            zero_area_box_obj,
            valid_box_obj,
        )
        == 0.0
    )


def test_clip_box_to_frame_constrains_every_coordinate() -> None:
    """Confirm clipping keeps coordinates inside the frame boundary."""

    out_of_bounds_box_obj = BoundingBox(-10, -5, 120, 90)

    clipped_box_obj = clip_box_to_frame(
        out_of_bounds_box_obj,
        frame_width_int=100,
        frame_height_int=80,
    )

    assert clipped_box_obj == BoundingBox(0, 0, 100, 80)


@pytest.mark.parametrize(
    ("frame_width_int", "frame_height_int"),
    [
        (-1, 80),
        (100, -1),
    ],
)
def test_clip_box_rejects_negative_frame_dimensions(
    frame_width_int: int,
    frame_height_int: int,
) -> None:
    """Confirm invalid frame dimensions raise a clear error."""

    bounding_box_obj = BoundingBox(0, 0, 10, 10)

    with pytest.raises(ValueError):
        clip_box_to_frame(
            bounding_box_obj,
            frame_width_int=frame_width_int,
            frame_height_int=frame_height_int,
        )
