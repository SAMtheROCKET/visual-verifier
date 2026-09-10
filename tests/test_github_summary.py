"""Protect the job summary the GitHub Action publishes.

The renderer runs inside `action.yml`, where a defect surfaces as a broken
or misleading summary on somebody else's pull request rather than as a
failing test here. It reads only `summary.json`, so these checks pin both
the rendering rules and the schema fields the action depends on.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from visual_verifier import verify_video

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLES_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples"
RENDERER_SCRIPT_PATH = (
    REPOSITORY_ROOT_PATH / "scripts" / "render_github_summary.py"
)


def _load_renderer_module() -> ModuleType:
    """Import the job summary renderer script as a module.

    Returns:
        The imported ``render_github_summary`` module.
    """

    module_spec = importlib.util.spec_from_file_location(
        "render_github_summary", RENDERER_SCRIPT_PATH
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    renderer_module = importlib.util.module_from_spec(module_spec)
    sys.modules["render_github_summary"] = renderer_module
    module_spec.loader.exec_module(renderer_module)
    return renderer_module


RENDERER_MODULE = _load_renderer_module()


def _build_summary(
    status_str: str,
    failed_frames_list: list[int],
    frames_checked_int: int = 15,
) -> dict[str, Any]:
    """Return a minimal verification document for rendering tests.

    Args:
        status_str: Verification status such as ``PASS`` or ``FAIL``.
        failed_frames_list: Frame numbers without accepted processing.
        frames_checked_int: Number of synchronized frames compared.

    Returns:
        Mapping shaped like the documented ``summary.json`` document.
    """

    processed_int = frames_checked_int - len(failed_frames_list)
    coverage_float = round(processed_int / frames_checked_int * 100.0, 2)
    return {
        "status": status_str,
        "policy_name": "every_frame_processed",
        "failed_frames": failed_frames_list,
        "measurements": {
            "frames_checked": frames_checked_int,
            "processing_coverage_percent": coverage_float,
        },
        "evidence_paths": {},
    }


def test_passing_run_reports_every_frame() -> None:
    """Confirm a clean pass states the number of protected frames."""

    rendered_str = RENDERER_MODULE.render_summary(_build_summary("PASS", []))

    assert "Visual Verifier" in rendered_str
    assert "PASS" in rendered_str
    assert "**15 frames**" in rendered_str
    assert "100" in rendered_str


def test_failing_run_counts_the_gaps() -> None:
    """Confirm a failing run names how many gaps were found."""

    rendered_str = RENDERER_MODULE.render_summary(
        _build_summary("FAIL", [4, 8, 12])
    )

    assert "FAIL" in rendered_str
    assert "**3 processing gaps found**" in rendered_str
    assert "4, 8, 12" in rendered_str


def test_single_gap_uses_singular_wording() -> None:
    """Confirm one unprotected frame is not reported as ``1 gaps``."""

    rendered_str = RENDERER_MODULE.render_summary(_build_summary("FAIL", [7]))

    assert "**1 processing gap found**" in rendered_str
    assert "gaps found" not in rendered_str


def test_incomplete_run_avoids_claiming_a_verdict() -> None:
    """Confirm an errored run neither passes nor lists phantom gaps."""

    rendered_str = RENDERER_MODULE.render_summary(_build_summary("ERROR", []))

    assert "Verification could not be completed." in rendered_str
    assert "processing gap" not in rendered_str


def test_scope_note_is_attached_only_to_a_pass() -> None:
    """Confirm the honest-scope caveat qualifies passing runs only."""

    passing_str = RENDERER_MODULE.render_summary(_build_summary("PASS", []))
    failing_str = RENDERER_MODULE.render_summary(_build_summary("FAIL", [4]))

    assert "does not prove" in passing_str
    assert "does not prove" not in failing_str


def test_timeline_marks_each_unprotected_frame() -> None:
    """Confirm short runs render one cell per frame, failures included."""

    rendered_str = RENDERER_MODULE.render_summary(
        _build_summary("FAIL", [4, 8, 12])
    )

    assert rendered_str.count(RENDERER_MODULE.FAIL_CELL_TEXT) == 3
    assert rendered_str.count(RENDERER_MODULE.PASS_CELL_TEXT) == 12
    assert "Each cell covers" not in rendered_str


def test_timeline_buckets_long_videos() -> None:
    """Confirm a long run stays readable and declares its bucket size."""

    frames_checked_int = 6000
    rendered_str = RENDERER_MODULE.render_summary(
        _build_summary("FAIL", [5999], frames_checked_int)
    )

    cell_count_int = rendered_str.count(
        RENDERER_MODULE.PASS_CELL_TEXT
    ) + rendered_str.count(RENDERER_MODULE.FAIL_CELL_TEXT)

    assert cell_count_int <= RENDERER_MODULE.MAX_TIMELINE_CELLS_INT
    assert rendered_str.count(RENDERER_MODULE.FAIL_CELL_TEXT) == 1
    assert "Each cell covers 100 frames." in rendered_str


def test_timeline_is_omitted_when_nothing_was_checked() -> None:
    """Confirm an empty run renders no misleading all-green strip."""

    summary_dict = _build_summary("ERROR", [])
    summary_dict["measurements"]["frames_checked"] = 0

    rendered_str = RENDERER_MODULE.render_summary(summary_dict)

    assert "Frame timeline" not in rendered_str
    assert RENDERER_MODULE.PASS_CELL_TEXT not in rendered_str


def test_long_failed_frame_lists_are_truncated() -> None:
    """Confirm a wall of frame numbers cannot swamp the summary table."""

    failed_frames_list = list(range(1, 51))
    rendered_str = RENDERER_MODULE.render_summary(
        _build_summary("FAIL", failed_frames_list, 200)
    )

    assert "(+20 more)" in rendered_str
    assert ", 31," not in rendered_str


def test_track_table_reports_continuity_and_longest_gap() -> None:
    """Confirm tracked regions render with their continuity evidence."""

    summary_dict = _build_summary("FAIL", [4])
    summary_dict["measurements"]["tracking"] = {
        "track_summaries": [
            {
                "track_label": "T001",
                "first_frame": 1,
                "last_frame": 15,
                "continuity_ratio": 0.8,
                "gap_count": 1,
                "longest_gap_frames": 3,
                "recovery_count": 1,
            }
        ]
    }

    rendered_str = RENDERER_MODULE.render_summary(summary_dict)

    assert "Tracked regions (1)" in rendered_str
    assert "`T001`" in rendered_str
    assert "80%" in rendered_str
    assert "| Longest gap | 3 frames |" in rendered_str


def test_single_frame_gap_uses_singular_wording() -> None:
    """Confirm the shortest possible gap is not reported as ``1 frames``."""

    summary_dict = _build_summary("FAIL", [4])
    summary_dict["measurements"]["tracking"] = {
        "track_summaries": [
            {
                "track_label": "T001",
                "first_frame": 1,
                "last_frame": 15,
                "continuity_ratio": 0.93,
                "gap_count": 1,
                "longest_gap_frames": 1,
                "recovery_count": 1,
            }
        ]
    }

    rendered_str = RENDERER_MODULE.render_summary(summary_dict)

    assert "| Longest gap | 1 frame |" in rendered_str


def test_track_table_is_truncated_and_declares_the_omission() -> None:
    """Confirm a crowded scene lists a bounded number of tracks."""

    limit_int = RENDERER_MODULE.MAX_LISTED_TRACKS_INT
    summary_dict = _build_summary("FAIL", [4])
    summary_dict["measurements"]["tracking"] = {
        "track_summaries": [
            {
                "track_label": f"T{track_index_int:03d}",
                "first_frame": 1,
                "last_frame": 15,
                "continuity_ratio": 1.0,
                "gap_count": 0,
                "longest_gap_frames": 0,
                "recovery_count": 0,
            }
            for track_index_int in range(1, limit_int + 4)
        ]
    }

    rendered_str = RENDERER_MODULE.render_summary(summary_dict)

    assert f"Tracked regions ({limit_int + 3})" in rendered_str
    assert "_3 further tracks omitted._" in rendered_str
    assert f"`T{limit_int:03d}`" in rendered_str
    assert f"`T{limit_int + 1:03d}`" not in rendered_str


def test_track_table_is_omitted_without_tracking() -> None:
    """Confirm a run made with ``--no-tracking`` renders no empty table."""

    rendered_str = RENDERER_MODULE.render_summary(_build_summary("FAIL", [4]))

    assert "Tracked regions" not in rendered_str


def test_evidence_line_points_at_the_html_report() -> None:
    """Confirm reviewers are directed to the report they can open."""

    summary_dict = _build_summary("FAIL", [4])
    summary_dict["evidence_paths"] = {"html_report": "out/index.html"}

    rendered_str = RENDERER_MODULE.render_summary(summary_dict, "out")

    assert "`out`" in rendered_str
    assert "`index.html`" in rendered_str


def test_evidence_line_is_omitted_without_any_evidence() -> None:
    """Confirm a run that wrote no files advertises no evidence path."""

    rendered_str = RENDERER_MODULE.render_summary(_build_summary("FAIL", [4]))

    assert "Evidence written to" not in rendered_str


def test_main_renders_a_document_from_disk(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm the command-line entry point prints the rendered summary."""

    summary_path_obj = tmp_path / "summary.json"
    summary_path_obj.write_text(
        json.dumps(_build_summary("FAIL", [4, 8, 12])), encoding="utf-8"
    )

    exit_code_int = RENDERER_MODULE.main([str(summary_path_obj), "evidence"])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 0
    assert "**3 processing gaps found**" in captured_output_obj.out


def test_main_reports_a_missing_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm a missing summary fails loudly instead of printing noise."""

    exit_code_int = RENDERER_MODULE.main([str(tmp_path / "absent.json")])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 1
    assert "Could not read" in captured_output_obj.err


def test_main_reports_an_unparsable_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm a truncated summary is reported rather than half rendered."""

    summary_path_obj = tmp_path / "summary.json"
    summary_path_obj.write_text('{"status": ', encoding="utf-8")

    exit_code_int = RENDERER_MODULE.main([str(summary_path_obj)])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 1
    assert "Could not read" in captured_output_obj.err


def test_main_requires_a_summary_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm the entry point explains its own usage."""

    exit_code_int = RENDERER_MODULE.main([])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 1
    assert "Usage:" in captured_output_obj.err


def test_rendering_survives_a_legacy_console_encoding(
    tmp_path: Path,
) -> None:
    """Confirm status icons do not crash a non-UTF-8 standard output.

    A Windows runner pipes standard output using the legacy code page,
    which cannot encode the emoji this summary is built from. The
    renderer must write UTF-8 regardless of that default.
    """

    summary_path_obj = tmp_path / "summary.json"
    summary_path_obj.write_text(
        json.dumps(_build_summary("FAIL", [4])), encoding="utf-8"
    )
    legacy_environment_dict = dict(os.environ)
    legacy_environment_dict["PYTHONIOENCODING"] = "cp1252"

    completed_process_obj = subprocess.run(
        [sys.executable, str(RENDERER_SCRIPT_PATH), str(summary_path_obj)],
        capture_output=True,
        env=legacy_environment_dict,
        check=False,
    )

    assert completed_process_obj.returncode == 0, (
        completed_process_obj.stderr.decode("utf-8", "replace")
    )
    assert RENDERER_MODULE.FAIL_CELL_TEXT in (
        completed_process_obj.stdout.decode("utf-8")
    )


def test_rendering_a_real_verification_run(tmp_path: Path) -> None:
    """Confirm the renderer matches a genuine ``summary.json`` document.

    The renderer reads the documented machine-readable output rather than
    the result object, so a schema change must fail here instead of on a
    user's pull request.
    """

    result_obj = verify_video(
        EXAMPLES_DIRECTORY_PATH / "media" / "video_raw.mp4",
        EXAMPLES_DIRECTORY_PATH / "media" / "video_blur_partial.mp4",
        output_dir=tmp_path / "evidence",
        save_annotated_video=False,
    )
    summary_path_obj = tmp_path / "evidence" / "summary.json"
    summary_dict = json.loads(summary_path_obj.read_text(encoding="utf-8"))

    rendered_str = RENDERER_MODULE.render_summary(summary_dict, "evidence")

    assert result_obj.status.value == "FAIL"
    assert "**3 processing gaps found**" in rendered_str
    assert "4, 8, 12" in rendered_str
    assert f"`{result_obj.policy_name}`" in rendered_str
    assert rendered_str.count(RENDERER_MODULE.FAIL_CELL_TEXT) == 3
    assert "Evidence written to `evidence`." in rendered_str
