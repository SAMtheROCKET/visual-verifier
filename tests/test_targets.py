"""Protect target loading, interpolation, and coverage measurement.

Targets are the one input this package cannot check against the media. A
row silently dropped, a box silently widened, or an interpolated box
silently presented as reviewed would all mean a region nobody verified
being reported as verified. Every one of those is a test here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from visual_verifier.config.targets import TargetConfig
from visual_verifier.exceptions import (
    ConfigurationError,
    TargetValidationError,
)
from visual_verifier.models import BoundingBox, RegionMeasurement
from visual_verifier.targets import (
    Target,
    TargetSource,
    group_targets_by_frame,
    interpolate_targets,
    load_targets,
    measure_frame_targets,
    summarize_targets,
)

TARGET_HEADER_TEXT = "frame_number,target_id,target_type,x1,y1,x2,y2"


def _write_targets(tmp_path: Path, body_text: str) -> Path:
    """Write a target file and return its path.

    Args:
        tmp_path: Directory to write into.
        body_text: Rows following the standard header.

    Returns:
        Path to the written file.
    """

    targets_path_obj = tmp_path / "targets.csv"
    targets_path_obj.write_text(
        f"{TARGET_HEADER_TEXT}\n{body_text}\n", encoding="utf-8"
    )
    return targets_path_obj


def _region(
    box_obj: BoundingBox,
    *,
    accepted_bool: bool = True,
) -> RegionMeasurement:
    """Return a region measurement carrying only what coverage reads.

    Args:
        box_obj: Region geometry.
        accepted_bool: Whether the region passed detection filtering.

    Returns:
        A region measurement usable by coverage.
    """

    return RegionMeasurement(
        box=box_obj,
        changed_pixels=100,
        changed_ratio=0.5,
        mean_diff=40.0,
        max_diff=90.0,
        laplacian_reference=100.0,
        laplacian_candidate=10.0,
        sharpness_percentage_candidate_vs_reference=10.0,
        edge_change_ratio=0.9,
        severity_score=60.0,
        severity_label="high",
        accepted=accepted_bool,
    )


def test_a_minimal_target_file_loads(tmp_path: Path) -> None:
    """Confirm the documented minimum columns are enough."""

    targets_path_obj = tmp_path / "targets.csv"
    targets_path_obj.write_text(
        "frame_number,target_id,x1,y1,x2,y2\n1,PLATE_A,10,20,50,60\n",
        encoding="utf-8",
    )

    targets_tuple = load_targets(targets_path_obj)

    assert len(targets_tuple) == 1
    assert targets_tuple[0].target_id == "PLATE_A"
    assert targets_tuple[0].box == BoundingBox(x1=10, y1=20, x2=50, y2=60)
    assert targets_tuple[0].required
    assert targets_tuple[0].source is TargetSource.MANUAL


def test_targets_are_ordered_by_frame_then_identifier(
    tmp_path: Path,
) -> None:
    """Confirm loading imposes a stable order regardless of file order."""

    targets_path_obj = _write_targets(
        tmp_path,
        "2,PLATE_B,plate,10,10,30,30\n"
        "1,PLATE_B,plate,10,10,30,30\n"
        "1,PLATE_A,plate,10,10,30,30",
    )

    targets_tuple = load_targets(targets_path_obj)

    assert [
        (target_obj.frame_number, target_obj.target_id)
        for target_obj in targets_tuple
    ] == [(1, "PLATE_A"), (1, "PLATE_B"), (2, "PLATE_B")]


def test_a_missing_column_is_rejected(tmp_path: Path) -> None:
    """Confirm an incomplete header fails instead of loading partially."""

    targets_path_obj = tmp_path / "targets.csv"
    targets_path_obj.write_text(
        "frame_number,target_id,x1,y1\n1,PLATE_A,10,20\n", encoding="utf-8"
    )

    with pytest.raises(TargetValidationError) as error_info:
        load_targets(targets_path_obj)

    assert "missing_columns" in error_info.value.context_dict


def test_a_missing_file_is_rejected(tmp_path: Path) -> None:
    """Confirm a mistyped path fails loudly rather than verifying nothing."""

    with pytest.raises(TargetValidationError):
        load_targets(tmp_path / "absent.csv")


@pytest.mark.parametrize(
    "row_text",
    [
        "0,PLATE_A,plate,10,10,30,30",
        "1,,plate,10,10,30,30",
        "1,PLATE_A,plate,30,10,10,30",
        "1,PLATE_A,plate,10,30,30,10",
        "1,PLATE_A,plate,-5,10,30,30",
        "1,PLATE_A,plate,ten,10,30,30",
        "one,PLATE_A,plate,10,10,30,30",
    ],
)
def test_an_invalid_row_is_rejected(
    tmp_path: Path,
    row_text: str,
) -> None:
    """Confirm every documented coordinate rule is enforced."""

    with pytest.raises(TargetValidationError):
        load_targets(_write_targets(tmp_path, row_text))


def test_the_offending_line_is_named(tmp_path: Path) -> None:
    """Confirm an error points at the row a reviewer has to fix."""

    targets_path_obj = _write_targets(
        tmp_path,
        "1,PLATE_A,plate,10,10,30,30\n2,PLATE_A,plate,30,10,10,30",
    )

    with pytest.raises(TargetValidationError) as error_info:
        load_targets(targets_path_obj)

    assert error_info.value.context_dict["line_number"] == 3


def test_a_duplicated_target_in_one_frame_is_rejected(
    tmp_path: Path,
) -> None:
    """Confirm an ambiguous declaration cannot be measured silently."""

    targets_path_obj = _write_targets(
        tmp_path,
        "1,PLATE_A,plate,10,10,30,30\n1,PLATE_A,plate,40,40,60,60",
    )

    with pytest.raises(TargetValidationError) as error_info:
        load_targets(targets_path_obj)

    assert error_info.value.context_dict["target_id"] == "PLATE_A"


@pytest.mark.parametrize(
    ("required_text", "expected_bool"),
    [("true", True), ("false", False), ("1", True), ("0", False), ("", True)],
)
def test_the_required_flag_is_parsed(
    tmp_path: Path,
    required_text: str,
    expected_bool: bool,
) -> None:
    """Confirm an optional target can be declared without failing a build."""

    targets_path_obj = tmp_path / "targets.csv"
    targets_path_obj.write_text(
        "frame_number,target_id,x1,y1,x2,y2,required\n"
        f"1,PLATE_A,10,10,30,30,{required_text}\n",
        encoding="utf-8",
    )

    assert load_targets(targets_path_obj)[0].required is expected_bool


def test_an_unknown_required_value_is_rejected(tmp_path: Path) -> None:
    """Confirm an ambiguous flag is not quietly treated as true."""

    targets_path_obj = tmp_path / "targets.csv"
    targets_path_obj.write_text(
        "frame_number,target_id,x1,y1,x2,y2,required\n"
        "1,PLATE_A,10,10,30,30,maybe\n",
        encoding="utf-8",
    )

    with pytest.raises(TargetValidationError):
        load_targets(targets_path_obj)


def test_an_unknown_source_is_rejected(tmp_path: Path) -> None:
    """Confirm provenance cannot be invented by a typo."""

    targets_path_obj = tmp_path / "targets.csv"
    targets_path_obj.write_text(
        "frame_number,target_id,x1,y1,x2,y2,source\n"
        "1,PLATE_A,10,10,30,30,guessed\n",
        encoding="utf-8",
    )

    with pytest.raises(TargetValidationError):
        load_targets(targets_path_obj)


def test_only_a_manual_box_counts_as_reviewed() -> None:
    """Confirm provenance distinguishes a human from a machine."""

    assert TargetSource.MANUAL.is_reviewed
    assert not TargetSource.INTERPOLATED.is_reviewed
    assert not TargetSource.DETECTOR.is_reviewed


def _target(frame_number_int: int, left_int: int) -> Target:
    """Return a simple target at one horizontal position.

    Args:
        frame_number_int: Frame the target applies to.
        left_int: Left coordinate of a 20x20 box.

    Returns:
        The target.
    """

    return Target(
        frame_number=frame_number_int,
        target_id="PLATE_A",
        box=BoundingBox(x1=left_int, y1=0, x2=left_int + 20, y2=20),
    )


def test_a_gap_between_reviewed_boxes_is_filled() -> None:
    """Confirm interpolation places boxes along the reviewed path."""

    filled_tuple = interpolate_targets(
        (_target(1, 0), _target(5, 40)), max_gap_int=5
    )

    assert [target_obj.frame_number for target_obj in filled_tuple] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert [target_obj.box.x1 for target_obj in filled_tuple] == [
        0,
        10,
        20,
        30,
        40,
    ]


def test_interpolated_boxes_are_marked_as_such() -> None:
    """Confirm a generated box can never pass as a reviewed one.

    A report that showed both identically would let a reviewer trust a
    box no human ever looked at.
    """

    filled_tuple = interpolate_targets(
        (_target(1, 0), _target(4, 30)), max_gap_int=5
    )

    reviewed_frames = [
        target_obj.frame_number
        for target_obj in filled_tuple
        if target_obj.source is TargetSource.MANUAL
    ]
    generated_frames = [
        target_obj.frame_number
        for target_obj in filled_tuple
        if target_obj.source is TargetSource.INTERPOLATED
    ]

    assert reviewed_frames == [1, 4]
    assert generated_frames == [2, 3]


def test_a_gap_longer_than_the_limit_is_left_empty() -> None:
    """Confirm a target that left the scene is not invented back into it."""

    filled_tuple = interpolate_targets(
        (_target(1, 0), _target(20, 200)), max_gap_int=5
    )

    assert [target_obj.frame_number for target_obj in filled_tuple] == [1, 20]


def test_interpolation_can_be_switched_off() -> None:
    """Confirm a zero gap limit generates nothing."""

    filled_tuple = interpolate_targets(
        (_target(1, 0), _target(5, 40)), max_gap_int=0
    )

    assert len(filled_tuple) == 2


def test_interpolation_keeps_identities_separate() -> None:
    """Confirm two targets are never interpolated into one another."""

    first_obj = Target(
        frame_number=1,
        target_id="PLATE_A",
        box=BoundingBox(x1=0, y1=0, x2=20, y2=20),
    )
    second_obj = Target(
        frame_number=3,
        target_id="PLATE_B",
        box=BoundingBox(x1=200, y1=0, x2=220, y2=20),
    )

    filled_tuple = interpolate_targets((first_obj, second_obj), max_gap_int=5)

    assert len(filled_tuple) == 2


def test_an_optional_endpoint_makes_the_gap_optional() -> None:
    """Confirm interpolation never strengthens a requirement."""

    start_obj = Target(
        frame_number=1,
        target_id="PLATE_A",
        box=BoundingBox(x1=0, y1=0, x2=20, y2=20),
        required=True,
    )
    end_obj = Target(
        frame_number=3,
        target_id="PLATE_A",
        box=BoundingBox(x1=20, y1=0, x2=40, y2=20),
        required=False,
    )

    filled_tuple = interpolate_targets((start_obj, end_obj), max_gap_int=5)
    generated_obj = next(
        target_obj
        for target_obj in filled_tuple
        if target_obj.source is TargetSource.INTERPOLATED
    )

    assert not generated_obj.required


def test_a_fully_covered_target_passes() -> None:
    """Confirm a region covering the whole target counts as covered."""

    coverages_tuple = measure_frame_targets(
        (_target(1, 0),),
        (_region(BoundingBox(x1=0, y1=0, x2=20, y2=20)),),
        min_covered_ratio=0.9,
    )

    assert coverages_tuple[0].covered_ratio == pytest.approx(1.0)
    assert coverages_tuple[0].covered
    assert not coverages_tuple[0].is_failure


def test_a_half_covered_target_fails() -> None:
    """Confirm partial coverage is a failure, which is the point."""

    coverages_tuple = measure_frame_targets(
        (_target(1, 0),),
        (_region(BoundingBox(x1=0, y1=0, x2=10, y2=20)),),
        min_covered_ratio=0.9,
    )

    assert coverages_tuple[0].covered_ratio == pytest.approx(0.5)
    assert not coverages_tuple[0].covered
    assert coverages_tuple[0].is_failure


def test_an_untouched_target_reports_zero_coverage() -> None:
    """Confirm a region elsewhere in the frame covers nothing."""

    coverages_tuple = measure_frame_targets(
        (_target(1, 0),),
        (_region(BoundingBox(x1=100, y1=100, x2=140, y2=140)),),
        min_covered_ratio=0.9,
    )

    assert coverages_tuple[0].covered_ratio == pytest.approx(0.0)
    assert coverages_tuple[0].contributing_region_count == 0


def test_coverage_unions_overlapping_regions() -> None:
    """Confirm two overlapping regions are not double counted.

    Summing areas would report more than 100% coverage and could pass a
    target that was never fully covered.
    """

    coverages_tuple = measure_frame_targets(
        (_target(1, 0),),
        (
            _region(BoundingBox(x1=0, y1=0, x2=15, y2=20)),
            _region(BoundingBox(x1=10, y1=0, x2=20, y2=20)),
        ),
        min_covered_ratio=0.9,
    )

    assert coverages_tuple[0].covered_ratio == pytest.approx(1.0)
    assert coverages_tuple[0].contributing_region_count == 2


def test_two_partial_regions_can_together_cover_a_target() -> None:
    """Confirm coverage is a union rather than the best single region."""

    coverages_tuple = measure_frame_targets(
        (_target(1, 0),),
        (
            _region(BoundingBox(x1=0, y1=0, x2=10, y2=20)),
            _region(BoundingBox(x1=10, y1=0, x2=20, y2=20)),
        ),
        min_covered_ratio=0.9,
    )

    assert coverages_tuple[0].covered_ratio == pytest.approx(1.0)


def test_a_rejected_region_does_not_cover_a_target() -> None:
    """Confirm processing that failed detection filtering does not count."""

    coverages_tuple = measure_frame_targets(
        (_target(1, 0),),
        (_region(BoundingBox(x1=0, y1=0, x2=20, y2=20), accepted_bool=False),),
        min_covered_ratio=0.9,
    )

    assert coverages_tuple[0].covered_ratio == pytest.approx(0.0)


def test_an_optional_target_never_fails_verification() -> None:
    """Confirm a target marked optional is measured but not enforced."""

    optional_obj = Target(
        frame_number=1,
        target_id="SIGN",
        box=BoundingBox(x1=0, y1=0, x2=20, y2=20),
        required=False,
    )

    coverages_tuple = measure_frame_targets(
        (optional_obj,), (), min_covered_ratio=0.9
    )

    assert not coverages_tuple[0].covered
    assert not coverages_tuple[0].is_failure


def test_summaries_report_continuity_and_provenance() -> None:
    """Confirm a summary carries the frames and the interpolated count."""

    coverages_tuple = (
        *measure_frame_targets(
            (_target(1, 0),),
            (_region(BoundingBox(x1=0, y1=0, x2=20, y2=20)),),
            min_covered_ratio=0.9,
        ),
        *measure_frame_targets(
            (
                Target(
                    frame_number=2,
                    target_id="PLATE_A",
                    box=BoundingBox(x1=0, y1=0, x2=20, y2=20),
                    source=TargetSource.INTERPOLATED,
                ),
            ),
            (),
            min_covered_ratio=0.9,
        ),
    )

    summaries_tuple = summarize_targets(coverages_tuple)

    assert len(summaries_tuple) == 1
    summary_obj = summaries_tuple[0]
    assert summary_obj.frame_count == 2
    assert summary_obj.covered_frame_count == 1
    assert summary_obj.uncovered_frames == (2,)
    assert summary_obj.interpolated_frame_count == 1
    assert summary_obj.coverage_ratio == pytest.approx(0.5)


def test_targets_are_indexed_by_frame() -> None:
    """Confirm frame lookup groups every target of that frame."""

    by_frame_dict = group_targets_by_frame(
        (_target(1, 0), _target(2, 10), _target(2, 40))
    )

    assert len(by_frame_dict[1]) == 1
    assert len(by_frame_dict[2]) == 2
    assert 3 not in by_frame_dict


@pytest.mark.parametrize("ratio_float", [0.0, -0.1, 1.5])
def test_an_impossible_coverage_ratio_is_rejected(
    ratio_float: float,
) -> None:
    """Confirm a threshold that can never be met is refused."""

    with pytest.raises(ConfigurationError):
        TargetConfig(min_covered_ratio=ratio_float)


@pytest.mark.parametrize("gap_int", [-1, 100_000])
def test_an_implausible_interpolation_gap_is_rejected(
    gap_int: int,
) -> None:
    """Confirm a gap that would fabricate evidence is refused."""

    with pytest.raises(ConfigurationError):
        TargetConfig(max_interpolation_gap=gap_int)
