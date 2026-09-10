"""Verify target-aware verification end to end on the bundled fixtures.

Target coverage is the first thing in this package allowed to change a
verdict on evidence other than "did any accepted region appear". These
regressions pin what that changes and, just as importantly, what it does
not: with no targets supplied, every existing result must be identical.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from visual_verifier import verify_video
from visual_verifier.config.targets import TargetConfig
from visual_verifier.exceptions import TargetValidationError

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLES_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples"
REFERENCE_PATH = EXAMPLES_DIRECTORY_PATH / "media" / "video_raw.mp4"
FULL_BLUR_PATH = EXAMPLES_DIRECTORY_PATH / "media" / "video_blur.mp4"
PARTIAL_BLUR_PATH = (
    EXAMPLES_DIRECTORY_PATH / "media" / "video_blur_partial.mp4"
)
DEMO_TARGETS_PATH = EXAMPLES_DIRECTORY_PATH / "targets" / "demo_targets.csv"
EXPECTED_FAILED_FRAMES_TUPLE = (4, 8, 12)
TARGET_POLICY_NAME_STR = "target_coverage_every_frame"
GENERIC_POLICY_NAME_STR = "generic_change_every_frame"


def test_the_shipped_target_file_exists() -> None:
    """Confirm the documented example target file is published."""

    assert DEMO_TARGETS_PATH.is_file()


def test_targets_pass_on_correctly_anonymized_media(
    tmp_path: Path,
) -> None:
    """Confirm a target covered in every frame does not fail a build."""

    result_obj = verify_video(
        REFERENCE_PATH,
        FULL_BLUR_PATH,
        output_dir=tmp_path,
        targets=DEMO_TARGETS_PATH,
        save_annotated_video=False,
    )

    assert result_obj.status.value == "PASS"
    assert result_obj.failed_frames == ()
    assert result_obj.policy_name == TARGET_POLICY_NAME_STR
    assert (
        result_obj.measurements["targets"]["target_coverage_percent"] == 100.0
    )


def test_targets_name_the_frames_that_left_a_plate_exposed(
    tmp_path: Path,
) -> None:
    """Confirm the documented demo contract holds with targets supplied."""

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        targets=DEMO_TARGETS_PATH,
        save_annotated_video=False,
    )

    assert result_obj.status.value == "FAIL"
    assert result_obj.failed_frames == EXPECTED_FAILED_FRAMES_TUPLE
    assert (
        result_obj.measurements["targets"]["target_coverage_percent"] == 80.0
    )


def test_an_uncovered_target_is_reported_as_its_own_failure(
    tmp_path: Path,
) -> None:
    """Confirm the failure names the target rather than only the frame.

    A reviewer reading `UNPROCESSED_FRAMES` would look for a frame where
    nothing happened. The point of a target is to say which required
    region was missed.
    """

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        targets=DEMO_TARGETS_PATH,
        save_annotated_video=False,
    )
    failure_codes_list = [
        failure_obj.code for failure_obj in result_obj.failures
    ]

    assert "UNCOVERED_TARGETS" in failure_codes_list
    target_failure_obj = next(
        failure_obj
        for failure_obj in result_obj.failures
        if failure_obj.code == "UNCOVERED_TARGETS"
    )
    assert target_failure_obj.measurements["uncovered_target_ids"] == [
        "PLATE_A"
    ]


def test_supplying_no_targets_changes_nothing(tmp_path: Path) -> None:
    """Confirm the existing contract is untouched without targets.

    Every result produced before this feature existed must still be
    produced identically, or an upgrade would silently move verdicts.
    """

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        save_annotated_video=False,
    )

    assert result_obj.policy_name == GENERIC_POLICY_NAME_STR
    assert result_obj.failed_frames == EXPECTED_FAILED_FRAMES_TUPLE
    assert result_obj.measurements["targets_enabled"] is False
    assert "targets" not in result_obj.measurements


def test_target_evidence_is_written_beside_the_other_reports(
    tmp_path: Path,
) -> None:
    """Confirm a target report is produced and discoverable."""

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        targets=DEMO_TARGETS_PATH,
        save_annotated_video=False,
    )

    assert "target_report" in result_obj.evidence_paths
    report_path_obj = result_obj.evidence_paths["target_report"]
    assert report_path_obj.is_file()

    rows_list = list(
        csv.DictReader(
            report_path_obj.read_text(encoding="utf-8-sig").splitlines()
        )
    )
    assert len(rows_list) == 15
    assert rows_list[0]["target_id"] == "PLATE_A"
    assert rows_list[0]["source"] == "manual"


def test_no_target_report_is_written_without_targets(
    tmp_path: Path,
) -> None:
    """Confirm an empty report is not produced for a run with no targets."""

    result_obj = verify_video(
        REFERENCE_PATH,
        FULL_BLUR_PATH,
        output_dir=tmp_path,
        save_annotated_video=False,
    )

    assert "target_report" not in result_obj.evidence_paths
    assert not (tmp_path / "target_report.csv").exists()


def test_the_summary_document_carries_target_measurements(
    tmp_path: Path,
) -> None:
    """Confirm a machine consumer can read target coverage."""

    verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        targets=DEMO_TARGETS_PATH,
        save_annotated_video=False,
    )
    summary_dict = json.loads(
        (tmp_path / "summary.json").read_text(encoding="utf-8")
    )
    targets_dict = summary_dict["measurements"]["targets"]

    assert targets_dict["target_count"] == 1
    assert targets_dict["uncovered_target_frame_count"] == 3
    assert targets_dict["target_summaries"][0]["uncovered_frames"] == [
        4,
        8,
        12,
    ]


def test_evidence_only_mode_records_targets_without_failing(
    tmp_path: Path,
) -> None:
    """Confirm coverage can be collected without gating a build."""

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        targets=DEMO_TARGETS_PATH,
        target_config=TargetConfig(fail_on_uncovered_target=False),
        expect_processing_every_frame=False,
        save_annotated_video=False,
    )

    assert result_obj.status.value == "PASS"
    assert (
        result_obj.measurements["targets"]["uncovered_target_frame_count"] == 3
    )


def test_a_lenient_coverage_threshold_accepts_partial_coverage(
    tmp_path: Path,
) -> None:
    """Confirm the coverage threshold is the knob it claims to be."""

    strict_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path / "strict",
        targets=DEMO_TARGETS_PATH,
        target_config=TargetConfig(min_covered_ratio=0.9),
        save_annotated_video=False,
    )
    lenient_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path / "lenient",
        targets=DEMO_TARGETS_PATH,
        target_config=TargetConfig(min_covered_ratio=1.0),
        save_annotated_video=False,
    )

    assert len(lenient_obj.failed_frames) >= len(strict_obj.failed_frames)


def test_targets_may_be_supplied_as_objects(tmp_path: Path) -> None:
    """Confirm a caller can build targets without writing a file."""

    from visual_verifier.targets import load_targets

    targets_tuple = load_targets(DEMO_TARGETS_PATH)
    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        targets=targets_tuple,
        save_annotated_video=False,
    )

    assert result_obj.failed_frames == EXPECTED_FAILED_FRAMES_TUPLE


def test_a_bad_target_path_fails_before_any_media_is_read(
    tmp_path: Path,
) -> None:
    """Confirm a mistyped target path is reported, not ignored."""

    with pytest.raises(TargetValidationError):
        verify_video(
            REFERENCE_PATH,
            PARTIAL_BLUR_PATH,
            output_dir=tmp_path,
            targets=tmp_path / "absent.csv",
            save_annotated_video=False,
        )


def test_interpolated_targets_cover_unreviewed_frames(
    tmp_path: Path,
) -> None:
    """Confirm a sparse review still checks the frames between boxes."""

    sparse_path_obj = tmp_path / "sparse.csv"
    reviewed_rows_list = [
        row_dict
        for row_dict in csv.DictReader(
            DEMO_TARGETS_PATH.read_text(encoding="utf-8-sig").splitlines()
        )
        if int(row_dict["frame_number"]) in {1, 5, 9, 13, 15}
    ]
    sparse_path_obj.write_text(
        "frame_number,target_id,x1,y1,x2,y2\n"
        + "\n".join(
            f"{row_dict['frame_number']},{row_dict['target_id']},"
            f"{row_dict['x1']},{row_dict['y1']},"
            f"{row_dict['x2']},{row_dict['y2']}"
            for row_dict in reviewed_rows_list
        )
        + "\n",
        encoding="utf-8",
    )

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path / "run",
        targets=sparse_path_obj,
        save_annotated_video=False,
    )
    targets_dict = result_obj.measurements["targets"]

    assert targets_dict["target_frame_count"] == 15
    assert targets_dict["interpolated_frame_count"] == 10
    assert 8 in result_obj.failed_frames


def test_interpolation_can_be_disabled(tmp_path: Path) -> None:
    """Confirm a reviewer can insist on checking only reviewed frames."""

    sparse_path_obj = tmp_path / "sparse.csv"
    sparse_path_obj.write_text(
        "frame_number,target_id,x1,y1,x2,y2\n"
        "1,PLATE_A,608,502,670,527\n"
        "15,PLATE_A,400,500,460,525\n",
        encoding="utf-8",
    )

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path / "run",
        targets=sparse_path_obj,
        target_config=TargetConfig(interpolate_missing_frames=False),
        save_annotated_video=False,
    )

    assert result_obj.measurements["targets"]["target_frame_count"] == 2


@pytest.mark.parametrize("frame_number_int", [4, 8, 12])
def test_each_missed_frame_reports_zero_target_coverage(
    tmp_path: Path,
    frame_number_int: int,
) -> None:
    """Confirm the report says the plate was untouched, not merely low."""

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        targets=DEMO_TARGETS_PATH,
        save_annotated_video=False,
    )
    rows_list = list(
        csv.DictReader(
            result_obj.evidence_paths["target_report"]
            .read_text(encoding="utf-8-sig")
            .splitlines()
        )
    )
    row_dict = next(
        row_dict
        for row_dict in rows_list
        if int(row_dict["frame_number"]) == frame_number_int
    )

    assert float(row_dict["covered_ratio"]) == pytest.approx(0.0)
    assert row_dict["covered"] == "False"


def test_a_permitted_gap_is_not_reported_as_a_failure(
    tmp_path: Path,
) -> None:
    """Confirm a relaxed rule does not still report its own violation.

    With `expect_processing_every_frame=False` an unprocessed frame is
    allowed. Listing it under `UNPROCESSED_FRAMES` because the frame
    failed for a different reason would describe a policy the run was
    not applying.
    """

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path,
        targets=DEMO_TARGETS_PATH,
        expect_processing_every_frame=False,
        save_annotated_video=False,
    )
    failure_codes_list = [
        failure_obj.code for failure_obj in result_obj.failures
    ]

    assert result_obj.status.value == "FAIL"
    assert failure_codes_list == ["UNCOVERED_TARGETS"]
    assert result_obj.measurements["frames_without_processing"] == 3


def test_targets_are_enforced_even_with_the_generic_rule_relaxed(
    tmp_path: Path,
) -> None:
    """Confirm relaxing the generic half keeps target enforcement.

    This is the documented way to verify only declared regions until the
    V5.4 policy system makes the combination selectable.
    """

    without_targets_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path / "generic",
        expect_processing_every_frame=False,
        save_annotated_video=False,
    )
    with_targets_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path / "targets",
        targets=DEMO_TARGETS_PATH,
        expect_processing_every_frame=False,
        save_annotated_video=False,
    )

    assert without_targets_obj.status.value == "PASS"
    assert with_targets_obj.status.value == "FAIL"
    assert with_targets_obj.failed_frames == EXPECTED_FAILED_FRAMES_TUPLE
