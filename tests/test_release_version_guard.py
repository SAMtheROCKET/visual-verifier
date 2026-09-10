"""Protect the release guard that ties the Git tag to declared versions.

The guard runs once, in the release workflow, on a tag push that publishes
permanently to PyPI. That is the worst possible place to discover it is
broken, so its behaviour is exercised here instead.
"""

from __future__ import annotations

import importlib.util
import re
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


VERSION_ADVERTISING_PATHS_TUPLE = (
    Path(".github") / "ISSUE_TEMPLATE" / "bug_report.yml",
    Path(".github") / "DISCUSSION_TEMPLATE" / "q-a.yml",
    Path("SECURITY.md"),
)
STALE_VERSION_PATTERN = re.compile(r"`?(\d+\.\d+\.\d+)(?![a-z0-9.])`?")


@pytest.mark.parametrize(
    "relative_path_obj",
    VERSION_ADVERTISING_PATHS_TUPLE,
    ids=lambda path_obj: path_obj.name,
)
def test_advertised_versions_match_the_package(
    relative_path_obj: Path,
) -> None:
    """Confirm no community file advertises a superseded version.

    A bug template asking for the version and suggesting a release two
    behind teaches every reporter to file stale information, and a
    security policy naming an unsupported version is worse than silent.
    Release versions with a suffix, such as ``0.2.0a0``, are historical
    entries and are left alone.
    """

    file_text = (REPOSITORY_ROOT_PATH / relative_path_obj).read_text(
        encoding="utf-8"
    )
    advertised_frozenset = frozenset(STALE_VERSION_PATTERN.findall(file_text))
    unexpected_list = sorted(
        advertised_frozenset - {visual_verifier.__version__}
    )

    assert not unexpected_list, (
        f"{relative_path_obj.as_posix()} advertises "
        f"{unexpected_list}, but the package is "
        f"{visual_verifier.__version__}"
    )


def test_no_maintainer_machine_is_named_in_a_template() -> None:
    """Confirm no template example identifies a specific machine.

    An OS build number copied from a maintainer's own `doctor` output
    is both needlessly identifying and misleading as an example.
    """

    template_directory_path = REPOSITORY_ROOT_PATH / ".github"
    build_number_pattern = re.compile(r"10\.0\.\d{5}")

    offending_list = [
        path_obj.relative_to(REPOSITORY_ROOT_PATH).as_posix()
        for path_obj in template_directory_path.rglob("*.yml")
        if build_number_pattern.search(path_obj.read_text(encoding="utf-8"))
    ]

    assert not offending_list, offending_list
