"""Protect the zero-clone demonstration a new user runs first.

`visual-verifier demo` is the first thing most people will run after
installing. If it does not reproduce the documented failure, the project
loses the reader in the first sixty seconds, so its contract is pinned
here as tightly as the bundled-fixture contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from visual_verifier.cli import EXIT_SUCCESS_INT, main
from visual_verifier.demo import (
    UNPROCESSED_FRAMES_TUPLE,
    run_demonstration,
)

EXPECTED_COVERAGE_PERCENT_FLOAT = 80.0
EXPECTED_FRAME_COUNT_INT = 15


def test_demonstration_reproduces_the_documented_failure(
    tmp_path: Path,
) -> None:
    """Confirm the generated sample fails on exactly the sown frames."""

    demonstration_obj = run_demonstration(tmp_path / "demo")
    result_obj = demonstration_obj.verification_result

    assert demonstration_obj.behaved_as_documented
    assert result_obj.failed
    assert result_obj.failed_frames == UNPROCESSED_FRAMES_TUPLE
    assert result_obj.measurements["frames_checked"] == (
        EXPECTED_FRAME_COUNT_INT
    )
    assert result_obj.measurements["processing_coverage_percent"] == (
        EXPECTED_COVERAGE_PERCENT_FLOAT
    )


def test_demonstration_is_deterministic(tmp_path: Path) -> None:
    """Confirm two runs produce byte-identical generated media.

    A demonstration that drifts between runs cannot be quoted in
    documentation, so determinism is part of its contract.
    """

    first_obj = run_demonstration(tmp_path / "first")
    second_obj = run_demonstration(tmp_path / "second")

    assert (
        first_obj.reference_path.read_bytes()
        == second_obj.reference_path.read_bytes()
    )
    assert (
        first_obj.candidate_path.read_bytes()
        == second_obj.candidate_path.read_bytes()
    )
    assert (
        first_obj.verification_result.failed_frames
        == second_obj.verification_result.failed_frames
    )


def test_demonstration_writes_the_full_evidence_set(
    tmp_path: Path,
) -> None:
    """Confirm a new user immediately has real evidence to inspect."""

    demonstration_obj = run_demonstration(tmp_path / "demo")
    written_names_frozenset = frozenset(
        path_obj.name
        for path_obj in demonstration_obj.report_directory.iterdir()
    )

    assert "summary.json" in written_names_frozenset
    assert "annotated_video.mp4" in written_names_frozenset
    assert "track_report.csv" in written_names_frozenset

    summary_dict = json.loads(
        (demonstration_obj.report_directory / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary_dict["status"] == "FAIL"
    assert summary_dict["failed_frames"] == list(UNPROCESSED_FRAMES_TUPLE)


def test_demo_command_succeeds_and_explains_itself(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Confirm the command exits zero and teaches the real command.

    The demonstration succeeded at demonstrating, so it exits ``0`` even
    though the verification it ran reports ``FAIL``.
    """

    exit_code_int = main(["demo", "--output", str(tmp_path / "demo")])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == EXIT_SUCCESS_INT
    assert "Visual Verifier demonstration" in captured_output_obj.out
    assert "nothing leaves this machine" in captured_output_obj.out
    assert "FAIL" in captured_output_obj.out
    assert "4, 8, 12" in captured_output_obj.out
    assert "behaved as documented" in captured_output_obj.out
    assert "Reproduce it yourself" in captured_output_obj.out
    assert "visual-verifier video" in captured_output_obj.out


def test_demo_command_reports_an_unexpected_result(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Confirm a demonstration that drifts fails loudly rather than lying."""

    real_run_demonstration = run_demonstration

    def _drifted_demonstration(output_dir: object) -> object:
        """Return a demonstration whose expectations no longer match."""

        demonstration_obj = real_run_demonstration(output_dir)  # type: ignore[arg-type]
        object.__setattr__(
            demonstration_obj,
            "expected_unprocessed_frames",
            (1, 2, 3),
        )
        return demonstration_obj

    monkeypatch.setattr(
        "visual_verifier.cli.run_demonstration",
        _drifted_demonstration,
    )
    exit_code_int = main(["demo", "--output", str(tmp_path / "demo")])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 1
    assert "did not reproduce" in captured_output_obj.err
