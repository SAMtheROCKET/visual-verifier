"""Protect the established example-video verification contract."""

import csv
from pathlib import Path

import pytest

from visual_verifier import verify_video
from visual_verifier.exceptions import VerificationFailedError

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLE_MEDIA_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples" / "media"
REFERENCE_VIDEO_PATH = EXAMPLE_MEDIA_DIRECTORY_PATH / "video_raw.mp4"
FULL_BLUR_VIDEO_PATH = EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur.mp4"
PARTIAL_BLUR_VIDEO_PATH = (
    EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur_partial.mp4"
)
EXPECTED_FRAME_COUNT_INT = 15
EXPECTED_PARTIAL_FAILED_FRAMES_TUPLE = (4, 8, 12)
EXPECTED_PARTIAL_COVERAGE_FLOAT = 80.0
EXPECTED_REPORT_NAMES_FROZENSET = frozenset(
    {
        "frame_report",
        "html_report",
        "region_report",
        "rejected_region_report",
        "summary_json",
        "track_report",
        "track_observation_report",
        "track_event_report",
    }
)


def test_full_blur_video_passes_every_frame(tmp_path: Path) -> None:
    """Confirm the fully processed example satisfies the policy."""

    result_obj = verify_video(
        REFERENCE_VIDEO_PATH,
        FULL_BLUR_VIDEO_PATH,
        output_dir=tmp_path / "full_blur",
        save_annotated_video=False,
    )

    assert result_obj.passed
    assert result_obj.failed_frames == ()
    assert result_obj.failures == ()
    assert result_obj.measurements["frames_checked"] == (
        EXPECTED_FRAME_COUNT_INT
    )
    assert result_obj.measurements["processing_coverage_percent"] == 100.0
    assert (
        frozenset(result_obj.evidence_paths) == EXPECTED_REPORT_NAMES_FROZENSET
    )


def test_partial_blur_fails_on_exact_expected_frames(
    tmp_path: Path,
) -> None:
    """Confirm the partial example fails only on frames 4, 8, and 12."""

    result_obj = verify_video(
        REFERENCE_VIDEO_PATH,
        PARTIAL_BLUR_VIDEO_PATH,
        output_dir=tmp_path / "partial_blur",
        save_annotated_video=False,
    )

    assert result_obj.failed
    assert result_obj.failed_frames == EXPECTED_PARTIAL_FAILED_FRAMES_TUPLE
    assert len(result_obj.failures) == 1
    assert result_obj.failures[0].code == "UNPROCESSED_FRAMES"
    assert result_obj.measurements["processing_coverage_percent"] == (
        EXPECTED_PARTIAL_COVERAGE_FLOAT
    )

    with pytest.raises(VerificationFailedError):
        result_obj.raise_for_failure()


def test_optional_processing_allows_partial_blur_video(
    tmp_path: Path,
) -> None:
    """Confirm optional per-frame processing converts the result to PASS."""

    result_obj = verify_video(
        REFERENCE_VIDEO_PATH,
        PARTIAL_BLUR_VIDEO_PATH,
        output_dir=tmp_path / "partial_allowed",
        expect_processing_every_frame=False,
        save_annotated_video=False,
    )

    assert result_obj.passed
    assert result_obj.failed_frames == ()
    assert result_obj.failures == ()
    assert result_obj.measurements["processing_coverage_percent"] == (
        EXPECTED_PARTIAL_COVERAGE_FLOAT
    )


def test_partial_blur_frame_report_marks_expected_failures(
    tmp_path: Path,
) -> None:
    """Confirm tabular evidence records the same failed frame contract."""

    result_obj = verify_video(
        REFERENCE_VIDEO_PATH,
        PARTIAL_BLUR_VIDEO_PATH,
        output_dir=tmp_path / "partial_report",
        save_annotated_video=False,
    )
    frame_report_path_obj = result_obj.evidence_paths["frame_report"]

    with frame_report_path_obj.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as report_file_obj:
        report_rows_list = list(csv.DictReader(report_file_obj))

    failed_frames_list: list[int] = []
    for report_row_dict in report_rows_list:
        if report_row_dict["frame_status"] != "FAIL":
            continue
        frame_number_text = report_row_dict["frame_number"]
        assert frame_number_text is not None
        failed_frames_list.append(int(frame_number_text))

    assert len(report_rows_list) == EXPECTED_FRAME_COUNT_INT
    assert tuple(failed_frames_list) == (EXPECTED_PARTIAL_FAILED_FRAMES_TUPLE)
