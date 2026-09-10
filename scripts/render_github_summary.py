"""Render a verification result as a GitHub job summary.

The GitHub Action writes this into `$GITHUB_STEP_SUMMARY`, and optionally
into a pull-request comment. It reads only `summary.json`, which is the
documented machine-readable output, so it stays correct as long as that
schema does.

    uv run python scripts/render_github_summary.py summary.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MAX_TIMELINE_CELLS_INT = 60
MAX_LISTED_FRAMES_INT = 30
MAX_LISTED_TRACKS_INT = 15
MAX_LISTED_TARGETS_INT = 15
UNPROCESSED_CODE_TEXT = "UNPROCESSED_FRAMES"
UNCOVERED_TARGETS_CODE_TEXT = "UNCOVERED_TARGETS"
PASS_CELL_TEXT = "\N{LARGE GREEN CIRCLE}"
FAIL_CELL_TEXT = "\N{LARGE RED CIRCLE}"
STATUS_ICON_MAPPING = {
    "PASS": "\N{WHITE HEAVY CHECK MARK}",
    "FAIL": "\N{CROSS MARK}",
    "ERROR": "\N{WARNING SIGN}",
}


def main(argv: list[str] | None = None) -> int:
    """Print a job summary for one verification result document.

    Args:
        argv: Optional argument vector. The first entry is the path to
            ``summary.json``.

    Returns:
        Process exit code. ``0`` on success, ``1`` when the document is
        missing or cannot be parsed.
    """

    _use_utf8_output()

    arguments_list = sys.argv[1:] if argv is None else argv
    if not arguments_list:
        print("Usage: render_github_summary.py SUMMARY_JSON", file=sys.stderr)
        return 1

    summary_path_obj = Path(arguments_list[0])
    try:
        summary_dict = json.loads(summary_path_obj.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error_obj:
        print(
            f"Could not read {summary_path_obj}: {error_obj}",
            file=sys.stderr,
        )
        return 1

    evidence_hint_str = arguments_list[1] if len(arguments_list) > 1 else ""
    print(render_summary(summary_dict, evidence_hint_str))
    return 0


def _use_utf8_output() -> None:
    """Force UTF-8 on standard output before any status icon is written.

    The summary is built from emoji, and a Windows runner defaults its
    pipe encoding to the legacy code page. Without this the renderer
    raises ``UnicodeEncodeError`` instead of producing a summary.
    """

    reconfigure_callable = getattr(sys.stdout, "reconfigure", None)
    if reconfigure_callable is None:
        return
    reconfigure_callable(encoding="utf-8")


def render_summary(
    summary_dict: dict[str, Any],
    evidence_hint_str: str = "",
) -> str:
    """Render one verification document as GitHub-flavoured markdown.

    Args:
        summary_dict: Parsed ``summary.json`` document.
        evidence_hint_str: Optional path shown as the evidence location.

    Returns:
        Markdown suitable for a job summary or a pull-request comment.
    """

    blocks_list = [
        _render_headline(summary_dict),
        _render_measurements(summary_dict),
        _render_timeline(summary_dict),
        _render_targets(summary_dict),
        _render_tracks(summary_dict),
        _render_evidence(summary_dict, evidence_hint_str),
        _render_scope_note(summary_dict),
    ]
    return "\n\n".join(block for block in blocks_list if block)


def _render_headline(summary_dict: dict[str, Any]) -> str:
    """Render the status heading and the one-line verdict."""

    status_str = str(summary_dict.get("status", "ERROR"))
    icon_str = STATUS_ICON_MAPPING.get(status_str, "\N{WARNING SIGN}")
    failed_frames_list = list(summary_dict.get("failed_frames") or [])
    measurements_dict = summary_dict.get("measurements") or {}
    frames_checked_int = int(measurements_dict.get("frames_checked", 0) or 0)

    heading_str = f"## {icon_str} Visual Verifier — {status_str}"
    if status_str == "PASS":
        return (
            f"{heading_str}\n\n"
            f"Accepted visual processing was detected in every one of "
            f"**{frames_checked_int} frames**."
        )
    if not failed_frames_list:
        return f"{heading_str}\n\nVerification could not be completed."
    return (
        f"{heading_str}\n\n"
        f"**{len(failed_frames_list)} of {frames_checked_int} frames "
        f"failed.** {_failure_reason(summary_dict)}"
    )


def _failure_reason(summary_dict: dict[str, Any]) -> str:
    """Describe which of the two failure modes applied.

    A target-aware run can fail a frame that was processed, just
    not where it mattered. Reporting that as a processing gap
    would send a reviewer looking for the wrong thing.

    Args:
        summary_dict: Parsed ``summary.json`` document.

    Returns:
        A sentence naming the reasons, or an empty string.
    """

    reasons_list: list[str] = []
    for failure_obj in summary_dict.get("failures") or []:
        if not isinstance(failure_obj, dict):
            continue
        code_str = str(failure_obj.get("code", ""))
        if code_str == UNPROCESSED_CODE_TEXT:
            reasons_list.append("no accepted processing")
        elif code_str == UNCOVERED_TARGETS_CODE_TEXT:
            reasons_list.append("a required target left uncovered")
    if not reasons_list:
        return ""
    return "Cause: " + " and ".join(reasons_list) + "."


def _render_measurements(summary_dict: dict[str, Any]) -> str:
    """Render the headline measurement table."""

    measurements_dict = summary_dict.get("measurements") or {}
    failed_frames_list = list(summary_dict.get("failed_frames") or [])
    rows_list: list[tuple[str, str]] = [
        ("Policy", f"`{summary_dict.get('policy_name', 'unknown')}`"),
        ("Frames checked", str(measurements_dict.get("frames_checked", 0))),
        (
            "Processing coverage",
            f"{measurements_dict.get('processing_coverage_percent', 0)}%",
        ),
        ("Frames unprotected", str(len(failed_frames_list))),
    ]
    targets_dict = measurements_dict.get("targets")
    if isinstance(targets_dict, dict):
        rows_list.append(
            (
                "Target coverage",
                f"{targets_dict.get('target_coverage_percent', 0)}%",
            )
        )
        rows_list.append(
            (
                "Target frames uncovered",
                str(targets_dict.get("uncovered_target_frame_count", 0)),
            )
        )
    if failed_frames_list:
        rows_list.append(
            ("Failed frames", f"`{_format_frames(failed_frames_list)}`")
        )
    longest_gap_int = _longest_gap(summary_dict)
    if longest_gap_int:
        frame_word_str = "frame" if longest_gap_int == 1 else "frames"
        rows_list.append(
            ("Longest gap", f"{longest_gap_int} {frame_word_str}")
        )

    table_lines_list = ["| Measurement | Value |", "| --- | --- |"]
    table_lines_list.extend(
        f"| {label_str} | {value_str} |" for label_str, value_str in rows_list
    )
    return "\n".join(table_lines_list)


def _render_timeline(summary_dict: dict[str, Any]) -> str:
    """Render a compact per-frame or bucketed status strip."""

    measurements_dict = summary_dict.get("measurements") or {}
    frames_checked_int = int(measurements_dict.get("frames_checked", 0) or 0)
    if frames_checked_int <= 0:
        return ""

    failed_frames_frozenset = frozenset(
        summary_dict.get("failed_frames") or []
    )
    bucket_size_int = max(1, -(-frames_checked_int // MAX_TIMELINE_CELLS_INT))
    cells_list: list[str] = []
    for bucket_start_int in range(1, frames_checked_int + 1, bucket_size_int):
        bucket_frames_range = range(
            bucket_start_int,
            min(bucket_start_int + bucket_size_int, frames_checked_int + 1),
        )
        has_failure_bool = any(
            frame_int in failed_frames_frozenset
            for frame_int in bucket_frames_range
        )
        cells_list.append(
            FAIL_CELL_TEXT if has_failure_bool else PASS_CELL_TEXT
        )

    note_str = ""
    if bucket_size_int > 1:
        note_str = f"\n\n_Each cell covers {bucket_size_int} frames._"
    return f"### Frame timeline\n\n{''.join(cells_list)}{note_str}"


def _render_targets(summary_dict: dict[str, Any]) -> str:
    """Render reviewed-target coverage when targets were supplied.

    Args:
        summary_dict: Parsed ``summary.json`` document.

    Returns:
        The markdown section, or an empty string without targets.
    """

    summaries_list = _target_summaries(summary_dict)
    if not summaries_list:
        return ""

    shown_list = summaries_list[:MAX_LISTED_TARGETS_INT]
    lines_list = [
        "### Required targets",
        "",
        "| Target | Type | Frames | Covered | Interpolated | Result |",
        "| --- | --- | --- | ---: | ---: | :-: |",
    ]
    for summary_obj in shown_list:
        uncovered_list = list(summary_obj.get("uncovered_frames") or [])
        required_bool = bool(summary_obj.get("required", True))
        passed_bool = not uncovered_list or not required_bool
        lines_list.append(
            f"| `{summary_obj.get('target_id', '')}` "
            f"| {summary_obj.get('target_type', '')} "
            f"| {summary_obj.get('first_frame', '')}"
            f"-{summary_obj.get('last_frame', '')} "
            f"| {summary_obj.get('covered_frame_count', 0)}"
            f"/{summary_obj.get('frame_count', 0)} "
            f"| {summary_obj.get('interpolated_frame_count', 0)} "
            f"| {'PASS' if passed_bool else 'FAIL'} |"
        )
    omitted_int = len(summaries_list) - len(shown_list)
    if omitted_int > 0:
        lines_list.append(f"\n_{omitted_int} further targets omitted._")

    lines_list.extend(_uncovered_frame_lines(summaries_list))
    return "\n".join(lines_list)


def _uncovered_frame_lines(
    summaries_list: list[dict[str, Any]],
) -> list[str]:
    """Return the line naming every frame a required target was missed in.

    Args:
        summaries_list: Target summaries declared by the run.

    Returns:
        Zero or two lines, so the caller can extend unconditionally.
    """

    failed_frames_list = sorted(
        {
            frame_int
            for summary_obj in summaries_list
            for frame_int in (summary_obj.get("uncovered_frames") or [])
            if summary_obj.get("required", True)
        }
    )
    if not failed_frames_list:
        return []
    return [
        "",
        f"Uncovered target frames: `{_format_frames(failed_frames_list)}`",
    ]


def _target_summaries(summary_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the target summary mappings, or an empty list.

    Args:
        summary_dict: Parsed ``summary.json`` document.

    Returns:
        Target summaries declared by the run.
    """

    measurements_dict = summary_dict.get("measurements") or {}
    targets_dict = measurements_dict.get("targets") or {}
    summaries_object = targets_dict.get("target_summaries") or []
    if not isinstance(summaries_object, list):
        return []
    return [item for item in summaries_object if isinstance(item, dict)]


def _render_tracks(summary_dict: dict[str, Any]) -> str:
    """Render tracked-region continuity inside a collapsed block."""

    summaries_list = _track_summaries(summary_dict)
    if not summaries_list:
        return ""

    shown_list = summaries_list[:MAX_LISTED_TRACKS_INT]
    table_lines_list = [
        "| Track | Frames | Continuity | Gaps | Recoveries |",
        "| --- | --- | --- | --- | --- |",
    ]
    for summary_obj in shown_list:
        continuity_float = float(summary_obj.get("continuity_ratio", 0) or 0)
        table_lines_list.append(
            f"| `{summary_obj.get('track_label', '')}` "
            f"| {summary_obj.get('first_frame', '')}"
            f"-{summary_obj.get('last_frame', '')} "
            f"| {continuity_float:.0%} "
            f"| {summary_obj.get('gap_count', 0)} "
            f"| {summary_obj.get('recovery_count', 0)} |"
        )
    omitted_int = len(summaries_list) - len(shown_list)
    if omitted_int > 0:
        table_lines_list.append(f"\n_{omitted_int} further tracks omitted._")

    body_str = "\n".join(table_lines_list)
    return (
        f"<details>\n<summary>Tracked regions "
        f"({len(summaries_list)})</summary>\n\n{body_str}\n\n</details>"
    )


def _render_evidence(
    summary_dict: dict[str, Any],
    evidence_hint_str: str,
) -> str:
    """Render where the generated evidence can be found."""

    evidence_paths_dict = summary_dict.get("evidence_paths") or {}
    if not evidence_paths_dict and not evidence_hint_str:
        return ""
    location_str = evidence_hint_str or "the evidence directory"
    if "html_report" not in evidence_paths_dict:
        return f"Evidence written to `{location_str}`."
    return (
        f"Evidence written to `{location_str}`. Open **`index.html`** for "
        "a frame timeline and a before/after comparison of every "
        "unprotected frame."
    )


def _render_scope_note(summary_dict: dict[str, Any]) -> str:
    """Render the honest-scope caveat for a passing result."""

    if str(summary_dict.get("status")) != "PASS":
        return ""
    if _target_summaries(summary_dict):
        return (
            "> A `PASS` means every reviewed target was covered by "
            "accepted processing in every frame it was declared on. "
            "Coverage is geometric: it does not prove the region became "
            "unreadable to a human."
        )
    return (
        "> A `PASS` means accepted visual change was detected in every "
        "checked frame under the configured thresholds. It does not prove "
        "that a particular required object was transformed."
    )


def _format_frames(failed_frames_list: list[Any]) -> str:
    """Return a truncated, comma-separated failed-frame list."""

    if len(failed_frames_list) <= MAX_LISTED_FRAMES_INT:
        return ", ".join(str(frame_obj) for frame_obj in failed_frames_list)
    shown_list = failed_frames_list[:MAX_LISTED_FRAMES_INT]
    remaining_int = len(failed_frames_list) - len(shown_list)
    shown_str = ", ".join(str(frame_obj) for frame_obj in shown_list)
    return f"{shown_str} (+{remaining_int} more)"


def _track_summaries(summary_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the track summary mappings, or an empty list."""

    measurements_dict = summary_dict.get("measurements") or {}
    tracking_dict = measurements_dict.get("tracking") or {}
    summaries_object = tracking_dict.get("track_summaries") or []
    if not isinstance(summaries_object, list):
        return []
    return [item for item in summaries_object if isinstance(item, dict)]


def _longest_gap(summary_dict: dict[str, Any]) -> int:
    """Return the longest gap across every completed track."""

    longest_int = 0
    for summary_obj in _track_summaries(summary_dict):
        gap_value = summary_obj.get("longest_gap_frames", 0)
        if isinstance(gap_value, int):
            longest_int = max(longest_int, gap_value)
    return longest_int


if __name__ == "__main__":
    raise SystemExit(main())
