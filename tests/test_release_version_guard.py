"""Protect the release guard that ties the Git tag to declared versions.

The guard runs once, in the release workflow, on a tag push that publishes
permanently to PyPI. That is the worst possible place to discover it is
broken, so its behaviour is exercised here instead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

import visual_verifier

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
GUARD_SCRIPT_PATH = (
    REPOSITORY_ROOT_PATH / "scripts" / "check_release_version.py"
)


def _load_guard_module() -> ModuleType:
    """Import the release guard script as a module.

    Returns:
        The imported ``check_release_version`` module.
    """

    module_spec = importlib.util.spec_from_file_location(
        "check_release_version", GUARD_SCRIPT_PATH
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    guard_module = importlib.util.module_from_spec(module_spec)
    sys.modules["check_release_version"] = guard_module
    module_spec.loader.exec_module(guard_module)
    return guard_module


GUARD_MODULE = _load_guard_module()


def test_matching_tag_is_accepted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm the current version passes its own release guard."""

    exit_code_int = GUARD_MODULE.main([f"v{visual_verifier.__version__}"])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 0
    assert visual_verifier.__version__ in captured_output_obj.out


def test_mismatched_tag_is_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm a tag that disagrees with the package fails the release."""

    exit_code_int = GUARD_MODULE.main(["v99.99.99"])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 1
    assert "Release version mismatch" in captured_output_obj.err
    assert "the package reports" in captured_output_obj.err
    assert "CITATION.cff reports" in captured_output_obj.err


def test_missing_tag_is_rejected(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirm the guard refuses to pass when no tag can be resolved."""

    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    exit_code_int = GUARD_MODULE.main([])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 1
    assert "No tag supplied" in captured_output_obj.err


def test_tag_is_resolved_from_the_ci_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirm the workflow can rely on ``GITHUB_REF_NAME`` alone."""

    monkeypatch.setenv("GITHUB_REF_NAME", "v1.2.3")

    assert GUARD_MODULE._resolve_tag_name([]) == "v1.2.3"
    assert GUARD_MODULE._resolve_tag_name(["v4.5.6"]) == "v4.5.6"


def test_citation_version_is_actually_read() -> None:
    """Confirm the guard reads a real version out of ``CITATION.cff``."""

    assert GUARD_MODULE._read_citation_version() == (
        visual_verifier.__version__
    )
