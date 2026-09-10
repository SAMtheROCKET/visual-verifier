"""Measure how much of each target accepted processing actually covered.

Coverage is computed as the union of every accepted region overlapping a
target, not the best single region. A pipeline that blurs a face in two
overlapping passes has covered it once, and counting only the larger
pass would under-report real coverage.

The union is measured on a mask the size of the target box, so cost
scales with the target rather than with the frame.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence

import numpy as np

from visual_verifier.metrics.geometry import calculate_intersection_box
from visual_verifier.models import BoundingBox, RegionMeasurement
from visual_verifier.targets.models import (
    Target,
    TargetCoverage,
    TargetSource,
    TargetSummary,
)


def measure_frame_targets(
    frame_targets_sequence: Sequence[Target],
    accepted_regions_sequence: Sequence[RegionMeasurement],
    *,
    min_covered_ratio: float,
) -> tuple[TargetCoverage, ...]:
    """Measure coverage of every target in one frame.

    Args:
        frame_targets_sequence: Targets declared for this frame.
        accepted_regions_sequence: Accepted processing regions detected
            in this frame.
        min_covered_ratio: Fraction of a target that must be covered.

    Returns:
        One coverage measurement per target, in the given order.
    """

    accepted_boxes_list = [
        region_obj.box
        for region_obj in accepted_regions_sequence
        if region_obj.accepted
    ]
    return tuple(
        _measure_one_target(target_obj, accepted_boxes_list, min_covered_ratio)
        for target_obj in frame_targets_sequence
    )


def _measure_one_target(
    target_obj: Target,
    accepted_boxes_list: Sequence[BoundingBox],
    min_covered_ratio: float,
) -> TargetCoverage:
    """Measure how much of one target was covered.

    Args:
        target_obj: Target being measured.
        accepted_boxes_list: Accepted region boxes in the same frame.
        min_covered_ratio: Fraction that must be covered.

    Returns:
        The coverage measurement.
    """

    overlapping_boxes_list = [
        intersection_box
        for accepted_box_obj in accepted_boxes_list
        if (
            intersection_box := calculate_intersection_box(
                target_obj.box, accepted_box_obj
            )
        ).is_valid
    ]
    covered_ratio_float = _union_coverage_ratio(
        target_obj.box, overlapping_boxes_list
    )
    return TargetCoverage(
        target=target_obj,
        covered_ratio=covered_ratio_float,
        covered=covered_ratio_float >= min_covered_ratio,
        contributing_region_count=len(overlapping_boxes_list),
    )


def _union_coverage_ratio(
    target_box_obj: BoundingBox,
    overlapping_boxes_list: Sequence[BoundingBox],
) -> float:
    """Return the fraction of a target covered by a union of boxes.

    Args:
        target_box_obj: Target region.
        overlapping_boxes_list: Boxes already clipped to the target.

    Returns:
        Covered fraction in the inclusive range 0 to 1.
    """

    if target_box_obj.area <= 0:
        return 0.0
    if not overlapping_boxes_list:
        return 0.0

    coverage_mask = np.zeros(
        (target_box_obj.height, target_box_obj.width), dtype=bool
    )
    for box_obj in overlapping_boxes_list:
        coverage_mask[
            box_obj.y1 - target_box_obj.y1 : box_obj.y2 - target_box_obj.y1,
            box_obj.x1 - target_box_obj.x1 : box_obj.x2 - target_box_obj.x1,
        ] = True

    return float(np.count_nonzero(coverage_mask)) / target_box_obj.area


def summarize_targets(
    coverages_iterable: Iterable[TargetCoverage],
) -> tuple[TargetSummary, ...]:
    """Summarize per-frame coverage into one row per target identifier.

    Args:
        coverages_iterable: Every per-frame coverage measurement.

    Returns:
        One summary per target identifier, ordered by identifier.
    """

    by_identifier_dict: dict[str, list[TargetCoverage]] = defaultdict(list)
    for coverage_obj in coverages_iterable:
        by_identifier_dict[coverage_obj.target.target_id].append(coverage_obj)

    return tuple(
        _summarize_one_target(target_id_str, coverages_list)
        for target_id_str, coverages_list in sorted(by_identifier_dict.items())
    )


def _summarize_one_target(
    target_id_str: str,
    coverages_list: list[TargetCoverage],
) -> TargetSummary:
    """Summarize one target identifier across every frame.

    Args:
        target_id_str: Identifier being summarized.
        coverages_list: Measurements for that identifier.

    Returns:
        The summary row.
    """

    frames_list = [
        coverage_obj.target.frame_number for coverage_obj in coverages_list
    ]
    uncovered_list = [
        coverage_obj.target.frame_number
        for coverage_obj in coverages_list
        if not coverage_obj.covered
    ]
    interpolated_int = sum(
        1
        for coverage_obj in coverages_list
        if coverage_obj.target.source is TargetSource.INTERPOLATED
    )
    mean_ratio_float = sum(
        coverage_obj.covered_ratio for coverage_obj in coverages_list
    ) / len(coverages_list)

    return TargetSummary(
        target_id=target_id_str,
        target_type=coverages_list[0].target.target_type,
        first_frame=min(frames_list),
        last_frame=max(frames_list),
        frame_count=len(coverages_list),
        covered_frame_count=len(coverages_list) - len(uncovered_list),
        uncovered_frames=tuple(sorted(uncovered_list)),
        mean_covered_ratio=mean_ratio_float,
        interpolated_frame_count=interpolated_int,
        required=any(
            coverage_obj.target.required for coverage_obj in coverages_list
        ),
    )


def group_targets_by_frame(
    targets_tuple: tuple[Target, ...],
) -> dict[int, tuple[Target, ...]]:
    """Index targets by the frame they apply to.

    Args:
        targets_tuple: Every declared and interpolated target.

    Returns:
        Mapping of frame number to that frame's targets.
    """

    by_frame_dict: dict[int, list[Target]] = defaultdict(list)
    for target_obj in targets_tuple:
        by_frame_dict[target_obj.frame_number].append(target_obj)
    return {
        frame_number_int: tuple(targets_list)
        for frame_number_int, targets_list in by_frame_dict.items()
    }


__all__ = [
    "group_targets_by_frame",
    "measure_frame_targets",
    "summarize_targets",
]
