"""Protect the documented command-line contract and exit codes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from visual_verifier import __version__
from visual_verifier.cli import (
    EXIT_EXECUTION_ERROR_INT,
    EXIT_SUCCESS_INT,
    EXIT_VERIFICATION_FAILED_INT,
    build_parser,
    main,
)

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLE_MEDIA_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples" / "media"
REFERENCE_VIDEO_PATH = EXAMPLE_MEDIA_DIRECTORY_PATH / "video_raw.mp4"
FULL_BLUR_VIDEO_PATH = EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur.mp4"
PARTIAL_BLUR_VIDEO_PATH = (
    EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur_partial.mp4"
)
EXPECTED_VIDEO_REPORT_NAMES_FROZENSET = frozenset(
    {
        "frame_report.csv",
        "index.html",
        "region_report.csv",
        "rejected_region_report.csv",
        "summary.json",
        "track_report.csv",
        "track_observation_report.csv",
        "track_event_report.csv",
    }
)


@pytest.fixture
def identical_image_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Write two identical images that contain no processing evidence.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Reference and candidate image paths holding the same pixels.
    """

    image_ndarray = np.full((64, 64, 3), 128, dtype=np.uint8)
    reference_path_obj = tmp_path / "reference.png"
    candidate_path_obj = tmp_path / "candidate.png"
    cv2.imwrite(str(reference_path_obj), image_ndarray)
    cv2.imwrite(str(candidate_path_obj), image_ndarray)
    return reference_path_obj, candidate_path_obj


def _video_arguments(candidate_path_obj: Path) -> list[str]:
    """Return a minimal video command for one candidate fixture.

    Args:
        candidate_path_obj: Processed candidate video to verify.

    Returns:
        Argument vector that writes no annotated video evidence.
    """

    return [
        "video",
        "--reference",
        str(REFERENCE_VIDEO_PATH),
        "--candidate",
        str(candidate_path_obj),
        "--no-annotated-video",
    ]


def _collect_parsers() -> list[argparse.ArgumentParser]:
    """Return the root parser and every registered subcommand parser.

    Returns:
        Parsers covering the complete documented command surface.
    """

    root_parser_obj = build_parser()
    collected_parsers_list = [root_parser_obj]

    for action_obj in root_parser_obj._actions:
        if isinstance(action_obj, argparse._SubParsersAction):
            collected_parsers_list.extend(action_obj.choices.values())

    return collected_parsers_list


def test_doctor_reports_a_degraded_environment_without_a_codec(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirm a missing encoder is reported without failing the check.

    Verification itself never needs an encoder, so an OpenCV build that
    cannot write annotated evidence is degraded rather than broken.
    """

    monkeypatch.setattr(
        "visual_verifier.cli.find_supported_codec",
        lambda: None,
    )
    exit_code_int = main(["doctor"])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == EXIT_SUCCESS_INT
    assert "Video codec:     unavailable" in captured_output_obj.out
    assert "Environment status: DEGRADED" in captured_output_obj.out


def test_version_flag_reports_the_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm the root parser prints the installed version and exits."""

    with pytest.raises(SystemExit) as exit_info_obj:
        main(["--version"])
    captured_output_obj = capsys.readouterr()

    assert exit_info_obj.value.code == 0
    assert __version__ in captured_output_obj.out


def test_every_command_and_option_documents_itself() -> None:
    """Confirm no command-line option ships without help text."""

    collected_parsers_list = _collect_parsers()

    assert len(collected_parsers_list) == 6
    for parser_obj in collected_parsers_list:
        for action_obj in parser_obj._actions:
            assert action_obj.help, f"{parser_obj.prog}: {action_obj.dest}"


def test_passing_video_returns_the_success_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm a passing verification exits with code zero."""

    exit_code_int = main(_video_arguments(FULL_BLUR_VIDEO_PATH))
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == EXIT_SUCCESS_INT
    assert "Status:" in captured_output_obj.out
    assert "PASS" in captured_output_obj.out


def test_failing_video_returns_the_verification_failed_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm a failed verification exits with the documented code two."""

    exit_code_int = main(_video_arguments(PARTIAL_BLUR_VIDEO_PATH))
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == EXIT_VERIFICATION_FAILED_INT
    assert "FAIL" in captured_output_obj.out
    assert "4, 8, 12" in captured_output_obj.out


def test_json_output_is_machine_readable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm the JSON mode emits one parseable verification document."""

    exit_code_int = main(
        [*_video_arguments(PARTIAL_BLUR_VIDEO_PATH), "--json"],
    )
    captured_output_obj = capsys.readouterr()
    payload_dict = json.loads(captured_output_obj.out)

    assert exit_code_int == EXIT_VERIFICATION_FAILED_INT
    assert payload_dict["status"] == "FAIL"
    assert payload_dict["failed_frames"] == [4, 8, 12]
    assert payload_dict["policy_name"] == "generic_change_every_frame"


def test_quiet_mode_prints_nothing_and_keeps_the_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm quiet mode reports only through the process exit code."""

    exit_code_int = main(
        [*_video_arguments(PARTIAL_BLUR_VIDEO_PATH), "--quiet"],
    )
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == EXIT_VERIFICATION_FAILED_INT
    assert captured_output_obj.out == ""


def test_video_command_writes_every_documented_report(
    tmp_path: Path,
) -> None:
    """Confirm the output directory receives the documented evidence set."""

    output_directory_path_obj = tmp_path / "evidence"
    exit_code_int = main(
        [
            *_video_arguments(PARTIAL_BLUR_VIDEO_PATH),
            "--output",
            str(output_directory_path_obj),
            "--quiet",
        ],
    )
    written_names_frozenset = frozenset(
        path_obj.name for path_obj in output_directory_path_obj.iterdir()
    )

    assert exit_code_int == EXIT_VERIFICATION_FAILED_INT
    assert written_names_frozenset == EXPECTED_VIDEO_REPORT_NAMES_FROZENSET


def test_disabled_tracking_omits_temporal_reports(
    tmp_path: Path,
) -> None:
    """Confirm disabling tracking removes only the temporal evidence."""

    output_directory_path_obj = tmp_path / "no_tracking"
    exit_code_int = main(
        [
            *_video_arguments(FULL_BLUR_VIDEO_PATH),
            "--output",
            str(output_directory_path_obj),
            "--no-tracking",
            "--quiet",
        ],
    )
    written_names_frozenset = frozenset(
        path_obj.name for path_obj in output_directory_path_obj.iterdir()
    )

    assert exit_code_int == EXIT_SUCCESS_INT
    assert "track_report.csv" not in written_names_frozenset
    assert "frame_report.csv" in written_names_frozenset


def test_inspect_command_prints_normalized_metadata(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm media inspection emits parseable normalized metadata."""

    exit_code_int = main(["inspect", str(REFERENCE_VIDEO_PATH)])
    captured_output_obj = capsys.readouterr()
    metadata_dict = json.loads(captured_output_obj.out)

    assert exit_code_int == EXIT_SUCCESS_INT
    assert metadata_dict["media_type"] == "video"
    assert metadata_dict["frame_count"] == 15
    assert metadata_dict["width"] == 1280


def test_missing_media_reports_a_structured_error(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Confirm unreadable media exits with code one and a stable code."""

    exit_code_int = main(
        [
            "video",
            "--reference",
            str(tmp_path / "absent_reference.mp4"),
            "--candidate",
            str(FULL_BLUR_VIDEO_PATH),
            "--no-annotated-video",
        ],
    )
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == EXIT_EXECUTION_ERROR_INT
    assert "ERROR [MEDIA_READ_ERROR]" in captured_output_obj.err
    assert captured_output_obj.out == ""


def test_invalid_threshold_reports_a_configuration_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm rejected thresholds surface as configuration errors."""

    exit_code_int = main(
        [*_video_arguments(FULL_BLUR_VIDEO_PATH), "--tracking-iou", "1.5"],
    )
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == EXIT_EXECUTION_ERROR_INT
    assert "ERROR [CONFIGURATION_ERROR]" in captured_output_obj.err
    assert "association_iou_threshold" in captured_output_obj.err


def test_image_command_detects_an_unprocessed_candidate(
    capsys: pytest.CaptureFixture[str],
    identical_image_pair: tuple[Path, Path],
) -> None:
    """Confirm identical images fail when processing is expected."""

    reference_path_obj, candidate_path_obj = identical_image_pair
    exit_code_int = main(
        [
            "image",
            "--reference",
            str(reference_path_obj),
            "--candidate",
            str(candidate_path_obj),
        ],
    )
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == EXIT_VERIFICATION_FAILED_INT
    assert "FAIL" in captured_output_obj.out


def test_image_command_can_allow_missing_processing(
    identical_image_pair: tuple[Path, Path],
) -> None:
    """Confirm the optional-processing flag converts the result to PASS."""

    reference_path_obj, candidate_path_obj = identical_image_pair
    exit_code_int = main(
        [
            "image",
            "--reference",
            str(reference_path_obj),
            "--candidate",
            str(candidate_path_obj),
            "--allow-no-processing",
            "--quiet",
        ],
    )

    assert exit_code_int == EXIT_SUCCESS_INT


def test_json_output_matches_the_written_summary_report(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Confirm `--json` and `summary.json` carry the same document.

    The readable summary became the default output in place of JSON, so
    the machine-readable path must remain a complete, exact substitute.
    """

    output_directory_path_obj = tmp_path / "json_parity"
    main(
        [
            *_video_arguments(PARTIAL_BLUR_VIDEO_PATH),
            "--output",
            str(output_directory_path_obj),
            "--json",
        ],
    )
    captured_output_obj = capsys.readouterr()
    printed_payload_dict = json.loads(captured_output_obj.out)
    written_payload_dict = json.loads(
        (output_directory_path_obj / "summary.json").read_text(
            encoding="utf-8"
        )
    )

    assert printed_payload_dict["status"] == written_payload_dict["status"]
    assert (
        printed_payload_dict["failed_frames"]
        == written_payload_dict["failed_frames"]
    )
    assert (
        printed_payload_dict["measurements"]
        == written_payload_dict["measurements"]
    )
    assert printed_payload_dict["failures"] == written_payload_dict["failures"]
    assert set(printed_payload_dict) == set(written_payload_dict)
