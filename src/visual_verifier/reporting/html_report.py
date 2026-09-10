"""Render a self-contained HTML evidence report.

CSV and JSON are the right machine-readable outputs, but they are hard to
forward to a reviewer who does not know the schemas. This module renders
one `index.html` that opens in any browser and answers the only question
that matters at a glance: which frames were left unprotected.

The page references nothing external. No CDN, no web font, no linked
image. Thumbnails are embedded as data URIs, so the file can be attached
to a ticket and opened offline, and opening it cannot signal to anyone
that the report exists. That is the same local-only guarantee the package
itself makes.

The output is deterministic: it carries no timestamp and no random ids,
so two runs over the same media produce byte-identical documents.
"""

from __future__ import annotations

import base64
import html
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from visual_verifier.exceptions import ReportWriteError
from visual_verifier.models import (
    FrameVerification,
    VerificationResult,
)
from visual_verifier.type_aliases import PathInput

HTML_REPORT_FILENAME_STR = "index.html"
TIMELINE_MAX_CELLS_INT = 600
MAX_EVIDENCE_CARDS_INT = 24
REPORT_TITLE_TEXT = "Visual Verifier report"

STATUS_TONE_MAPPING: Mapping[str, str] = {
    "PASS": "pass",
    "FAIL": "fail",
    "ERROR": "fail",
}


@dataclass(frozen=True, slots=True)
class FrameThumbnail:
    """Hold JPEG evidence for one frame of interest.

    Attributes:
        frame_number: One-based frame number.
        reference_jpeg_bytes: Encoded original frame.
        candidate_jpeg_bytes: Encoded processed candidate frame.
    """

    frame_number: int
    reference_jpeg_bytes: bytes
    candidate_jpeg_bytes: bytes


def write_html_report(
    result_obj: VerificationResult,
    frame_results_sequence: Sequence[FrameVerification],
    thumbnails_sequence: Sequence[FrameThumbnail],
    output_path_input: PathInput,
) -> Path:
    """Write one self-contained HTML evidence report.

    Args:
        result_obj: Completed verification result.
        frame_results_sequence: Per-frame verification evidence.
        thumbnails_sequence: Encoded evidence for failing frames.
        output_path_input: Destination path for the HTML document.

    Returns:
        Path to the written report.

    Raises:
        ReportWriteError: When the document cannot be written.
    """

    output_path_obj = Path(output_path_input).expanduser()
    document_text = render_html_report(
        result_obj,
        frame_results_sequence,
        thumbnails_sequence,
    )
    try:
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        output_path_obj.write_text(document_text, encoding="utf-8")
    except OSError as error_obj:
        raise ReportWriteError(
            "Could not write the HTML evidence report.",
            context_mapping={
                "output_path": str(output_path_obj),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj
    return output_path_obj


def render_html_report(
    result_obj: VerificationResult,
    frame_results_sequence: Sequence[FrameVerification],
    thumbnails_sequence: Sequence[FrameThumbnail],
) -> str:
    """Render the complete evidence document as HTML text.

    Args:
        result_obj: Completed verification result.
        frame_results_sequence: Per-frame verification evidence.
        thumbnails_sequence: Encoded evidence for failing frames.

    Returns:
        Deterministic, self-contained HTML document.
    """

    sections_list = [
        _render_header(result_obj),
        _render_statistics(result_obj, frame_results_sequence),
        _render_timeline(frame_results_sequence, result_obj),
        _render_evidence_cards(thumbnails_sequence),
        _render_tracks(result_obj),
        _render_footer(result_obj),
    ]
    return _HTML_SHELL_TEXT.format(
        title=html.escape(REPORT_TITLE_TEXT),
        styles=_REPORT_STYLE_TEXT,
        body="\n".join(section for section in sections_list if section),
        script=_REPORT_SCRIPT_TEXT,
    )


def _render_header(result_obj: VerificationResult) -> str:
    """Render the status banner and the compared media paths."""

    status_text = result_obj.status.value
    tone_text = STATUS_TONE_MAPPING.get(status_text, "fail")
    return (
        '<header class="header">'
        f'<div class="badge {tone_text}">{html.escape(status_text)}</div>'
        f"<h1>{html.escape(REPORT_TITLE_TEXT)}</h1>"
        '<dl class="paths">'
        "<dt>Policy</dt>"
        f"<dd>{html.escape(result_obj.policy_name)}</dd>"
        "<dt>Reference</dt>"
        f"<dd>{html.escape(str(result_obj.reference_path))}</dd>"
        "<dt>Candidate</dt>"
        f"<dd>{html.escape(str(result_obj.candidate_path))}</dd>"
        "</dl></header>"
    )


def _render_statistics(
    result_obj: VerificationResult,
    frame_results_sequence: Sequence[FrameVerification],
) -> str:
    """Render the headline measurement tiles."""

    measurements_mapping = result_obj.measurements
    tiles_list: list[tuple[str, str]] = [
        ("Frames checked", str(len(frame_results_sequence))),
        (
            "Processing coverage",
            f"{measurements_mapping.get('processing_coverage_percent', 0)}%",
        ),
        ("Frames unprotected", str(len(result_obj.failed_frames))),
    ]
    tracking_mapping = measurements_mapping.get("tracking")
    if isinstance(tracking_mapping, Mapping):
        tiles_list.append(
            ("Tracks", str(tracking_mapping.get("track_count", 0)))
        )
        tiles_list.append(
            (
                "Longest gap",
                f"{_longest_gap_frames(tracking_mapping)} frames",
            )
        )
    tile_html_list = [
        f'<div class="tile"><span class="tile-value">{html.escape(value)}'
        f'</span><span class="tile-label">{html.escape(label)}</span></div>'
        for label, value in tiles_list
    ]
    return f'<section class="tiles">{"".join(tile_html_list)}</section>'


def _longest_gap_frames(tracking_mapping: Mapping[str, object]) -> int:
    """Return the longest gap observed across every completed track."""

    summaries_object = tracking_mapping.get("track_summaries")
    if not isinstance(summaries_object, Sequence):
        return 0
    longest_gap_int = 0
    for summary_object in summaries_object:
        if not isinstance(summary_object, Mapping):
            continue
        gap_value = summary_object.get("longest_gap_frames", 0)
        if isinstance(gap_value, int):
            longest_gap_int = max(longest_gap_int, gap_value)
    return longest_gap_int


def _render_timeline(
    frame_results_sequence: Sequence[FrameVerification],
    result_obj: VerificationResult,
) -> str:
    """Render one cell per frame, or per bucket for long media."""

    if not frame_results_sequence:
        return ""
    failed_frames_frozenset = frozenset(result_obj.failed_frames)
    bucket_size_int = max(
        1,
        -(-len(frame_results_sequence) // TIMELINE_MAX_CELLS_INT),
    )
    cells_list = _build_timeline_cells(
        frame_results_sequence,
        failed_frames_frozenset,
        bucket_size_int,
    )
    note_text = ""
    if bucket_size_int > 1:
        note_text = (
            f'<p class="note">Condensed: each cell covers '
            f"{bucket_size_int} frames and is marked unprotected when any "
            "frame inside it failed.</p>"
        )
    return (
        '<section class="panel"><h2>Frame timeline</h2>'
        f'<div class="timeline">{"".join(cells_list)}</div>'
        f"{note_text}"
        '<p class="legend"><span class="swatch pass"></span> processed'
        '<span class="swatch fail"></span> unprotected</p>'
        "</section>"
    )


def _build_timeline_cells(
    frame_results_sequence: Sequence[FrameVerification],
    failed_frames_frozenset: frozenset[int],
    bucket_size_int: int,
) -> list[str]:
    """Return the rendered timeline cells for every frame or bucket."""

    cells_list: list[str] = []
    for bucket_start_int in range(
        0, len(frame_results_sequence), bucket_size_int
    ):
        bucket_slice = frame_results_sequence[
            bucket_start_int : bucket_start_int + bucket_size_int
        ]
        bucket_frames_list = [
            frame_obj.frame_number for frame_obj in bucket_slice
        ]
        failed_in_bucket_list = [
            frame_number_int
            for frame_number_int in bucket_frames_list
            if frame_number_int in failed_frames_frozenset
        ]
        tone_text = "fail" if failed_in_bucket_list else "pass"
        label_text = _timeline_cell_label(
            bucket_frames_list, failed_in_bucket_list
        )
        anchor_text = ""
        if failed_in_bucket_list:
            anchor_text = f' href="#frame-{failed_in_bucket_list[0]}"'
        cells_list.append(
            f'<a class="cell {tone_text}"{anchor_text} '
            f'title="{html.escape(label_text)}"></a>'
        )
    return cells_list


def _timeline_cell_label(
    bucket_frames_list: list[int],
    failed_in_bucket_list: list[int],
) -> str:
    """Return the hover label describing one timeline cell."""

    if len(bucket_frames_list) == 1:
        state_text = "unprotected" if failed_in_bucket_list else "processed"
        return f"Frame {bucket_frames_list[0]}: {state_text}"
    span_text = f"Frames {bucket_frames_list[0]}-{bucket_frames_list[-1]}"
    if not failed_in_bucket_list:
        return f"{span_text}: processed"
    return f"{span_text}: {len(failed_in_bucket_list)} unprotected"


def _render_evidence_cards(
    thumbnails_sequence: Sequence[FrameThumbnail],
) -> str:
    """Render a before/after comparison for each captured failing frame."""

    if not thumbnails_sequence:
        return ""
    shown_thumbnails_list = list(thumbnails_sequence)[:MAX_EVIDENCE_CARDS_INT]
    omitted_count_int = len(thumbnails_sequence) - len(shown_thumbnails_list)
    cards_list = [
        _render_evidence_card(thumbnail_obj)
        for thumbnail_obj in shown_thumbnails_list
    ]
    note_text = ""
    if omitted_count_int > 0:
        note_text = (
            f'<p class="note">{omitted_count_int} further unprotected '
            "frames are listed in <code>frame_report.csv</code>.</p>"
        )
    return (
        '<section class="panel"><h2>Unprotected frames</h2>'
        '<p class="note">Drag each slider to wipe between the original and '
        "the processed candidate.</p>"
        f"{''.join(cards_list)}{note_text}</section>"
    )


def _render_evidence_card(thumbnail_obj: FrameThumbnail) -> str:
    """Render one before/after wipe comparison for a failing frame."""

    frame_number_int = thumbnail_obj.frame_number
    reference_uri = _data_uri(thumbnail_obj.reference_jpeg_bytes)
    candidate_uri = _data_uri(thumbnail_obj.candidate_jpeg_bytes)
    return (
        f'<figure class="card" id="frame-{frame_number_int}">'
        f"<figcaption>Frame {frame_number_int}"
        '<span class="pill fail">no processing detected</span>'
        "</figcaption>"
        '<div class="wipe">'
        f'<img class="under" src="{candidate_uri}" alt="Processed '
        f'candidate, frame {frame_number_int}">'
        f'<div class="over"><img src="{reference_uri}" alt="Original '
        f'reference, frame {frame_number_int}"></div>'
        '<input class="slider" type="range" min="0" max="100" value="50" '
        f'aria-label="Compare frame {frame_number_int}">'
        '<span class="tag left">original</span>'
        '<span class="tag right">candidate</span>'
        "</div></figure>"
    )


def _render_tracks(result_obj: VerificationResult) -> str:
    """Render the per-track continuity table when tracking evidence exists."""

    tracking_mapping = result_obj.measurements.get("tracking")
    if not isinstance(tracking_mapping, Mapping):
        return ""
    summaries_object = tracking_mapping.get("track_summaries")
    if not isinstance(summaries_object, Sequence) or not summaries_object:
        return ""
    rows_list = [
        _render_track_row(summary_object)
        for summary_object in summaries_object
        if isinstance(summary_object, Mapping)
    ]
    return (
        '<section class="panel"><h2>Tracked regions</h2>'
        "<table><thead><tr><th>Track</th><th>Frames</th>"
        "<th>Continuity</th><th>Gaps</th><th>Recoveries</th>"
        "<th>Missing frames</th></tr></thead>"
        f"<tbody>{''.join(rows_list)}</tbody></table>"
        '<p class="note">A track is a persistent changed region. It is not '
        "proof that a particular face, plate, or person was processed.</p>"
        "</section>"
    )


def _render_track_row(summary_mapping: Mapping[str, object]) -> str:
    """Render one row of the tracked-region table."""

    missing_object = summary_mapping.get("missing_frames")
    missing_text = "none"
    if isinstance(missing_object, Sequence) and missing_object:
        missing_text = ", ".join(str(value) for value in missing_object)
    continuity_object = summary_mapping.get("continuity_ratio", 0)
    continuity_float = (
        float(continuity_object)
        if isinstance(continuity_object, (int, float))
        else 0.0
    )
    tone_text = "fail" if continuity_float < 1.0 else "pass"
    return (
        f"<tr><td><code>{_cell(summary_mapping, 'track_label')}</code></td>"
        f"<td>{_cell(summary_mapping, 'first_frame')}"
        f"-{_cell(summary_mapping, 'last_frame')}</td>"
        f'<td class="{tone_text}">{continuity_float:.0%}</td>'
        f"<td>{_cell(summary_mapping, 'gap_count')}</td>"
        f"<td>{_cell(summary_mapping, 'recovery_count')}</td>"
        f"<td>{html.escape(missing_text)}</td></tr>"
    )


def _cell(mapping_obj: Mapping[str, object], key_str: str) -> str:
    """Return one escaped table cell value."""

    return html.escape(str(mapping_obj.get(key_str, "")))


def _render_footer(result_obj: VerificationResult) -> str:
    """Render the reproduction command and the honest-scope note."""

    command_text = (
        "visual-verifier video \\\n"
        f"    --reference {result_obj.reference_path} \\\n"
        f"    --candidate {result_obj.candidate_path} \\\n"
        "    --output ."
    )
    failed_frames_text = json.dumps(list(result_obj.failed_frames))
    return (
        '<section class="panel"><h2>Reproduce this report</h2>'
        f"<pre>{html.escape(command_text)}</pre>"
        f"<p>Failed frames: <code>{html.escape(failed_frames_text)}</code>. "
        "Machine-readable evidence is in <code>summary.json</code> and the "
        "CSV reports beside this file.</p>"
        '<p class="note">A <strong>PASS</strong> means accepted visual '
        "change was detected in every checked frame under the configured "
        "thresholds. It is not a certificate of anonymization, and it does "
        "not prove that a particular required object was transformed. "
        "This report was generated locally; nothing was uploaded.</p>"
        "</section>"
    )


def _data_uri(image_bytes: bytes) -> str:
    """Return one base64 JPEG data URI for embedding in the document."""

    encoded_text = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded_text}"


_REPORT_STYLE_TEXT = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; padding: 32px 20px 64px; font: 15px/1.55 ui-sans-serif,
  system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  background: #f6f7f9; color: #1d2025; }
main { max-width: 960px; margin: 0 auto; }
h1 { font-size: 26px; margin: 12px 0 18px; }
h2 { font-size: 17px; margin: 0 0 14px; }
.header { margin-bottom: 22px; }
.badge { display: inline-block; padding: 5px 14px; border-radius: 999px;
  font-weight: 700; letter-spacing: .07em; font-size: 13px; color: #fff; }
.badge.pass { background: #2f855a; } .badge.fail { background: #c0392b; }
.paths { display: grid; grid-template-columns: 128px 1fr; gap: 4px 14px;
  margin: 0; font-size: 13px; }
.paths dt { color: #667; } .paths dd { margin: 0; word-break: break-all; }
.tiles { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 22px; }
.tile { flex: 1 1 150px; background: #fff; border: 1px solid #e3e6ea;
  border-radius: 10px; padding: 14px 16px; }
.tile-value { display: block; font-size: 24px; font-weight: 650; }
.tile-label { display: block; font-size: 12px; color: #667;
  text-transform: uppercase; letter-spacing: .05em; margin-top: 2px; }
.panel { background: #fff; border: 1px solid #e3e6ea; border-radius: 10px;
  padding: 18px 20px; margin-bottom: 20px; }
.timeline { display: flex; gap: 2px; height: 42px; }
.cell { flex: 1 1 0; border-radius: 3px; min-width: 2px;
  text-decoration: none; }
.cell.pass { background: #57b894; } .cell.fail { background: #d95448; }
.legend { font-size: 12px; color: #667; margin: 10px 0 0; }
.swatch { display: inline-block; width: 11px; height: 11px; border-radius: 3px;
  margin: 0 6px 0 14px; vertical-align: -1px; }
.swatch.pass { background: #57b894; margin-left: 0; }
.swatch.fail { background: #d95448; }
.note { font-size: 12.5px; color: #667; margin: 12px 0 0; }
.card { margin: 0 0 22px; }
figcaption { font-weight: 620; margin-bottom: 8px; }
.pill { display: inline-block; margin-left: 10px; padding: 2px 9px;
  border-radius: 999px; font-size: 11.5px; font-weight: 600; color: #fff; }
.pill.fail { background: #c0392b; }
.wipe { position: relative; overflow: hidden; border-radius: 8px;
  background: #000; line-height: 0; }
.wipe img { width: 100%; display: block; }
.wipe .over { position: absolute; inset: 0; width: 50%; overflow: hidden;
  border-right: 2px solid #fff; }
.wipe .over img { width: auto; height: 100%; max-width: none; }
.slider { position: absolute; inset: auto 0 10px; width: 94%; margin: 0 3%;
  cursor: ew-resize; }
.tag { position: absolute; top: 8px; padding: 2px 8px;
  border-radius: 4px; background: rgba(0,0,0,.62); color: #fff;
  font-size: 11px; line-height: 1.6; }
.tag.left { left: 8px; } .tag.right { right: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th, td { text-align: left; padding: 7px 10px;
  border-bottom: 1px solid #edeff2; }
th { font-size: 11.5px; text-transform: uppercase; letter-spacing: .05em;
  color: #667; }
td.pass { color: #2f855a; font-weight: 600; }
td.fail { color: #c0392b; font-weight: 600; }
pre { background: #f3f4f6; border: 1px solid #e3e6ea; border-radius: 8px;
  padding: 12px 14px; overflow-x: auto; font-size: 13px; }
code { background: #f3f4f6; padding: 1px 5px; border-radius: 4px;
  font-size: 12.5px; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e6e8ea; }
  .tile, .panel { background: #1c1f24; border-color: #2b2f36; }
  .paths dt, .tile-label, .legend, .note, th { color: #98a0aa; }
  pre, code { background: #23272e; border-color: #2b2f36; }
  th, td { border-bottom-color: #262a30; }
}
"""

_REPORT_SCRIPT_TEXT = """
for (const wipe of document.querySelectorAll('.wipe')) {
  const slider = wipe.querySelector('.slider');
  const over = wipe.querySelector('.over');
  const sync = () => {
    over.style.width = slider.value + '%';
    const img = over.querySelector('img');
    if (img) { img.style.width = wipe.clientWidth + 'px'; }
  };
  slider.addEventListener('input', sync);
  window.addEventListener('resize', sync);
  if (wipe.querySelector('.under').complete) { sync(); }
  else { wipe.querySelector('.under').addEventListener('load', sync); }
}
"""

_HTML_SHELL_TEXT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{title}</title>
<style>{styles}</style>
</head>
<body>
<main>
{body}
</main>
<script>{script}</script>
</body>
</html>
"""


__all__ = [
    "HTML_REPORT_FILENAME_STR",
    "FrameThumbnail",
    "render_html_report",
    "write_html_report",
]
