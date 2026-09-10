"""Protect deterministic V5.2 tracking behavior on example videos."""

import csv
from pathlib import Path

from visual_verifier import verify_video

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
MEDIA_PATH = REPOSITORY_ROOT_PATH / "examples" / "media"
REFERENCE_PATH = MEDIA_PATH / "video_raw.mp4"
FULL_BLUR_PATH = MEDIA_PATH / "video_blur.mp4"
PARTIAL_BLUR_PATH = MEDIA_PATH / "video_blur_partial.mp4"
TRACK_REPORT_NAMES_FROZENSET = frozenset(
    {
        "track_report",
        "track_observation_report",
        "track_event_report",
    }
)


def test_full_blur_tracking_is_deterministic(tmp_path: Path) -> None:
    """Confirm the fixture produces the established full-blur tracks."""

    result_obj = verify_video(
        REFERENCE_PATH,
        FULL_BLUR_PATH,
        output_dir=tmp_path / "full",
        save_annotated_video=False,
    )
    tracking_dict = result_obj.measurements["tracking"]

    assert result_obj.passed
    assert tracking_dict["track_count"] == 19
    assert tracking_dict["observation_count"] == 41
    assert tracking_dict["tracks_with_gaps"] == 0
    first_summary_dict = tracking_dict["track_summaries"][0]
    assert first_summary_dict["track_label"] == "T001"
    assert first_summary_dict["observation_count"] == 15
    assert first_summary_dict["continuity_ratio"] == 1.0
    assert frozenset(result_obj.evidence_paths) >= TRACK_REPORT_NAMES_FROZENSET


def test_partial_blur_primary_track_preserves_failed_frame_gaps(
    tmp_path: Path,
) -> None:
    """Confirm temporal gaps align with frames 4, 8, and 12."""

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path / "partial",
        save_annotated_video=False,
    )
    tracking_dict = result_obj.measurements["tracking"]
    primary_summary_dict = tracking_dict["track_summaries"][0]

    assert result_obj.failed_frames == (4, 8, 12)
    assert tracking_dict["track_count"] == 15
    assert tracking_dict["tracks_with_gaps"] == 1
    assert primary_summary_dict["track_label"] == "T001"
    assert primary_summary_dict["missing_frames"] == [4, 8, 12]
    assert primary_summary_dict["continuity_ratio"] == 0.8
    assert primary_summary_dict["recovery_count"] == 3

    track_report_path_obj = result_obj.evidence_paths["track_report"]
    with track_report_path_obj.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as report_file_obj:
        rows_list = list(csv.DictReader(report_file_obj))
    assert rows_list[0]["track_label"] == "T001"
    assert rows_list[0]["missing_frames"] == "4|8|12"


def test_tracking_can_be_disabled_without_changing_verification(
    tmp_path: Path,
) -> None:
    """Confirm opt-out removes tracking evidence but preserves failures."""

    result_obj = verify_video(
        REFERENCE_PATH,
        PARTIAL_BLUR_PATH,
        output_dir=tmp_path / "disabled",
        save_annotated_video=False,
        enable_tracking=False,
    )

    assert result_obj.failed_frames == (4, 8, 12)
    assert result_obj.measurements["tracking_enabled"] is False
    assert "tracking" not in result_obj.measurements
    assert TRACK_REPORT_NAMES_FROZENSET.isdisjoint(result_obj.evidence_paths)
