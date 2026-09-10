"""Protect the human-readable console summary rendering."""

from __future__ import annotations

from pathlib import Path

from visual_verifier import (
    VerificationFailure,
    VerificationResult,
    VerificationStatus,
)
from visual_verifier.reporting.console import format_verification_summary


def _build_result(
    *,
    status_enum: VerificationStatus,
    failed_frames_tuple: tuple[int, ...] = (),
    measurements_dict: dict[str, object] | None = None,
) -> VerificationResult:
    """Return a synthetic verification result for rendering tests.

    Args:
        status_enum: Verification status to render.
        failed_frames_tuple: Frames reported as policy violations.
        measurements_dict: Optional measurement payload.

    Returns:
        Immutable result carrying the requested evidence.
    """

    return VerificationResult(
        status=status_enum,
        reference_path=Path("reference.mp4"),
        candidate_path=Path("candidate.mp4"),
        policy_name="generic_change_every_frame",
        failed_frames=failed_frames_tuple,
        measurements=measurements_dict or {},
    )


def test_summary_reports_status_policy_and_inputs() -> None:
    """Confirm the header always identifies the run and its inputs."""

    summary_text = format_verification_summary(
        _build_result(status_enum=VerificationStatus.PASS),
    )

    assert "Status:" in summary_text
    assert "PASS" in summary_text
    assert "generic_change_every_frame" in summary_text
    assert "reference.mp4" in summary_text
    assert "candidate.mp4" in summary_text


def test_empty_sections_are_omitted() -> None:
    """Confirm a clean pass does not print empty evidence sections."""

    summary_text = format_verification_summary(
        _build_result(status_enum=VerificationStatus.PASS),
    )

    assert "Measurements" not in summary_text
    assert "Temporal tracking" not in summary_text
    assert "Failures" not in summary_text
    assert "Evidence" not in summary_text


def test_percentage_measurements_render_with_a_percent_sign() -> None:
    """Confirm coverage is displayed as a percentage, not a bare number."""

    summary_text = format_verification_summary(
        _build_result(
            status_enum=VerificationStatus.FAIL,
            measurements_dict={
                "frames_checked": 15,
                "processing_coverage_percent": 80.0,
            },
        ),
    )

    assert "Processing coverage:" in summary_text
    assert "80.0%" in summary_text


def test_tracking_section_appears_only_with_tracking_evidence() -> None:
    """Confirm temporal metrics render when tracking measurements exist."""

    summary_text = format_verification_summary(
        _build_result(
            status_enum=VerificationStatus.PASS,
            measurements_dict={
                "tracking": {
                    "track_count": 19,
                    "observation_count": 41,
                    "tracks_with_gaps": 0,
                }
            },
        ),
    )

    assert "Temporal tracking" in summary_text
    assert "Tracks:" in summary_text
    assert "19" in summary_text


def test_failure_section_lists_codes_and_failed_frames() -> None:
    """Confirm policy failures render with their stable failure codes."""

    result_obj = VerificationResult(
        status=VerificationStatus.FAIL,
        reference_path=Path("reference.mp4"),
        candidate_path=Path("candidate.mp4"),
        policy_name="generic_change_every_frame",
        failures=(
            VerificationFailure(
                code="UNPROCESSED_FRAMES",
                message="No accepted processing was detected.",
            ),
        ),
        failed_frames=(4, 8, 12),
    )
    summary_text = format_verification_summary(result_obj)

    assert "UNPROCESSED_FRAMES" in summary_text
    assert "4, 8, 12" in summary_text


def test_long_failed_frame_lists_are_truncated() -> None:
    """Confirm large failure sets stay readable in a terminal."""

    summary_text = format_verification_summary(
        _build_result(
            status_enum=VerificationStatus.FAIL,
            failed_frames_tuple=tuple(range(1, 101)),
        ),
    )

    assert "(+76 more)" in summary_text
