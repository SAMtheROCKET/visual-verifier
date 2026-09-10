"""Render verification results as readable console summaries.

The renderer only reads a finished :class:`VerificationResult`, so the
command-line interface, tests, and future integrations share one
human-facing presentation without re-deriving any measurement. Paths are
shortened against the working directory for readability; nothing else in
the output depends on the environment.

This text is for humans and is not a stable interface. Callers that parse
results must use ``--json`` or the generated reports.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from visual_verifier.models import VerificationResult

LABEL_WIDTH_INT = 27
SECTION_UNDERLINE_TEXT = "-"
TITLE_TEXT = "Visual Verifier result"
MAX_LISTED_FAILED_FRAMES_INT = 24
PERCENT_MEASUREMENT_SUFFIX_TEXT = "_percent"

MEASUREMENT_LABELS_TUPLE: tuple[tuple[str, str], ...] = (
    ("frames_checked", "Frames checked"),
    ("frames_with_processing", "Frames with processing"),
    ("frames_without_processing", "Frames without processing"),
    ("processing_coverage_percent", "Processing coverage"),
    ("accepted_region_count", "Accepted regions"),
    ("rejected_region_count", "Rejected regions"),
)
TRACKING_LABELS_TUPLE: tuple[tuple[str, str], ...] = (
    ("track_count", "Tracks"),
    ("observation_count", "Track observations"),
    ("event_count", "Track events"),
    ("tracks_with_gaps", "Tracks with gaps"),
    ("mean_continuity_ratio", "Mean continuity ratio"),
)
TARGET_LABELS_TUPLE: tuple[tuple[str, str], ...] = (
    ("target_count", "Targets"),
    ("target_frame_count", "Target frames checked"),
    ("covered_target_frame_count", "Target frames covered"),
    ("uncovered_target_frame_count", "Target frames uncovered"),
    ("target_coverage_percent", "Target coverage"),
    ("interpolated_frame_count", "Interpolated target boxes"),
)


def format_verification_summary(result_obj: VerificationResult) -> str:
    """Render one verification result as a readable console report.

    Args:
        result_obj: Completed image or video verification result.

    Returns:
        Multi-line report containing status, measurements, temporal
        evidence, policy failures, and generated evidence paths.
    """

    summary_lines_list: list[str] = [
        TITLE_TEXT,
        "=" * len(TITLE_TEXT),
    ]
    summary_lines_list.extend(_format_identity_lines(result_obj))
    summary_lines_list.extend(
        _format_section(
            "Measurements",
            _format_labelled_lines(
                result_obj.measurements,
                MEASUREMENT_LABELS_TUPLE,
            ),
        )
    )
    summary_lines_list.extend(_format_tracking_section(result_obj))
    summary_lines_list.extend(_format_target_section(result_obj))
    summary_lines_list.extend(_format_failure_section(result_obj))
    summary_lines_list.extend(_format_evidence_section(result_obj))
    return "\n".join(summary_lines_list)


def _format_identity_lines(
    result_obj: VerificationResult,
) -> list[str]:
    """Return status, policy, and input-path lines for one result."""

    return [
        _format_labelled_line("Status", result_obj.status.value),
        _format_labelled_line("Policy", result_obj.policy_name),
        _format_labelled_line(
            "Reference",
            _format_display_path(result_obj.reference_path),
        ),
        _format_labelled_line(
            "Candidate",
            _format_display_path(result_obj.candidate_path),
        ),
    ]


def _format_display_path(path_obj: Path) -> str:
    """Return a path relative to the working directory when possible.

    Args:
        path_obj: Absolute or relative filesystem path to display.

    Returns:
        Short relative path when the file sits under the working
        directory, and the original path otherwise.
    """

    try:
        return str(path_obj.relative_to(Path.cwd()))
    except (OSError, ValueError):
        return str(path_obj)


def _format_tracking_section(
    result_obj: VerificationResult,
) -> list[str]:
    """Return the temporal tracking section when tracking evidence exists."""

    tracking_value_obj = result_obj.measurements.get("tracking")
    if not isinstance(tracking_value_obj, Mapping):
        return []
    return _format_section(
        "Temporal tracking",
        _format_labelled_lines(
            tracking_value_obj,
            TRACKING_LABELS_TUPLE,
        ),
    )


def _format_target_section(
    result_obj: VerificationResult,
) -> list[str]:
    """Return the target coverage section when targets were supplied.

    Args:
        result_obj: Completed verification result.

    Returns:
        Section lines, or an empty list when no targets were used.
    """

    target_value_obj = result_obj.measurements.get("targets")
    if not isinstance(target_value_obj, Mapping):
        return []
    return _format_section(
        "Target coverage",
        _format_labelled_lines(target_value_obj, TARGET_LABELS_TUPLE),
    )


def _format_failure_section(
    result_obj: VerificationResult,
) -> list[str]:
    """Return policy failure codes and the failed-frame list."""

    failure_lines_list = [
        f"{failure_obj.code}: {failure_obj.message}"
        for failure_obj in result_obj.failures
    ]
    if result_obj.failed_frames:
        failure_lines_list.append(
            _format_labelled_line(
                "Failed frames",
                _format_failed_frames(result_obj.failed_frames),
            )
        )
    return _format_section("Failures", failure_lines_list)


def _format_evidence_section(
    result_obj: VerificationResult,
) -> list[str]:
    """Return the generated evidence paths in stable name order."""

    evidence_lines_list = [
        _format_labelled_line(
            evidence_name_str,
            _format_display_path(evidence_path_obj),
        )
        for evidence_name_str, evidence_path_obj in sorted(
            result_obj.evidence_paths.items()
        )
    ]
    return _format_section("Evidence", evidence_lines_list)


def _format_section(
    section_title_str: str,
    body_lines_list: list[str],
) -> list[str]:
    """Return one titled section, or nothing when the body is empty."""

    if not body_lines_list:
        return []
    return [
        "",
        section_title_str,
        SECTION_UNDERLINE_TEXT * len(section_title_str),
        *body_lines_list,
    ]


def _format_labelled_lines(
    values_mapping: Mapping[str, object],
    labels_tuple: tuple[tuple[str, str], ...],
) -> list[str]:
    """Return aligned lines for every known and present measurement."""

    labelled_lines_list: list[str] = []
    for measurement_key_str, label_str in labels_tuple:
        if measurement_key_str not in values_mapping:
            continue
        labelled_lines_list.append(
            _format_labelled_line(
                label_str,
                _format_measurement_value(
                    measurement_key_str,
                    values_mapping[measurement_key_str],
                ),
            )
        )
    return labelled_lines_list


def _format_labelled_line(label_str: str, value_str: str) -> str:
    """Return one aligned ``label: value`` console line."""

    return f"{label_str + ':':<{LABEL_WIDTH_INT}}{value_str}"


def _format_measurement_value(
    measurement_key_str: str,
    value_obj: object,
) -> str:
    """Return a display value, adding a percent sign where appropriate."""

    if measurement_key_str.endswith(PERCENT_MEASUREMENT_SUFFIX_TEXT):
        return f"{value_obj}%"
    return str(value_obj)


def _format_failed_frames(
    failed_frames_sequence: Sequence[int],
) -> str:
    """Return a truncated, comma-separated list of failed frame numbers."""

    listed_frames_list = list(failed_frames_sequence)
    if len(listed_frames_list) <= MAX_LISTED_FAILED_FRAMES_INT:
        return ", ".join(str(frame_int) for frame_int in listed_frames_list)
    shown_frames_list = listed_frames_list[:MAX_LISTED_FAILED_FRAMES_INT]
    remaining_count_int = len(listed_frames_list) - len(shown_frames_list)
    shown_frames_text = ", ".join(
        str(frame_int) for frame_int in shown_frames_list
    )
    return f"{shown_frames_text} (+{remaining_count_int} more)"


__all__ = [
    "format_verification_summary",
]
