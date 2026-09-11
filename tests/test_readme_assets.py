"""Keep the README's images working for every reader.

Three audiences render this file and they do not agree. An editor
preview and GitHub's repository view resolve repository-relative paths.
PyPI resolves neither, and shows a broken image for each one.

The repository therefore keeps the relative form, and the release
workflow converts it. Both halves of that arrangement are checked here,
because a broken image on a project page is the kind of defect nobody
notices until a stranger does.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
README_PATH = REPOSITORY_ROOT_PATH / "README.md"
PYPI_README_PATH = REPOSITORY_ROOT_PATH / "PYPI_README.md"
PYPROJECT_PATH = REPOSITORY_ROOT_PATH / "pyproject.toml"
BUILDER_SCRIPT_PATH = REPOSITORY_ROOT_PATH / "scripts" / "build_pypi_readme.py"
RELEASE_WORKFLOW_PATH = (
    REPOSITORY_ROOT_PATH / ".github" / "workflows" / "release.yml"
)
ABSOLUTE_ASSET_PATTERN = re.compile(
    r"raw\.githubusercontent\.com/[^\"')\s]*docs/assets/"
)


def _load_builder_module() -> ModuleType:
    """Import the README rewriter as a module.

    Returns:
        The imported ``build_pypi_readme`` module.
    """

    module_spec = importlib.util.spec_from_file_location(
        "build_pypi_readme", BUILDER_SCRIPT_PATH
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    builder_module = importlib.util.module_from_spec(module_spec)
    sys.modules["build_pypi_readme"] = builder_module
    module_spec.loader.exec_module(builder_module)
    return builder_module


BUILDER_MODULE = _load_builder_module()
README_TEXT = README_PATH.read_text(encoding="utf-8")
RELATIVE_LINKS_LIST = BUILDER_MODULE.find_relative_asset_links(README_TEXT)


def test_the_readme_actually_shows_images() -> None:
    """Confirm the README still carries its demonstration assets."""

    assert RELATIVE_LINKS_LIST


@pytest.mark.parametrize("relative_link_str", RELATIVE_LINKS_LIST)
def test_every_linked_asset_exists(relative_link_str: str) -> None:
    """Confirm no image link points at a file that is not there.

    A path that resolves nowhere renders as alt text, which is exactly
    how a missing asset hides in plain sight.
    """

    assert (REPOSITORY_ROOT_PATH / relative_link_str).is_file()


def test_asset_links_stay_relative_in_the_repository() -> None:
    """Confirm no asset link was hard-coded back to an absolute URL.

    An absolute URL renders nothing until that exact ref exists on the
    remote, so it breaks the editor preview and every fresh clone.
    """

    absolute_list = ABSOLUTE_ASSET_PATTERN.findall(README_TEXT)

    assert not absolute_list, (
        "README asset links must stay relative; the release workflow "
        f"makes them absolute. Found {absolute_list}"
    )


def test_the_rewriter_converts_every_link() -> None:
    """Confirm the release conversion leaves nothing relative behind."""

    rewritten_text = BUILDER_MODULE.rewrite_asset_links(README_TEXT, "v9.9.9")

    assert not BUILDER_MODULE.find_relative_asset_links(rewritten_text)
    assert rewritten_text.count("/v9.9.9/docs/assets/") == len(
        RELATIVE_LINKS_LIST
    )


def test_the_rewriter_preserves_everything_else() -> None:
    """Confirm conversion touches the links and nothing more."""

    rewritten_text = BUILDER_MODULE.rewrite_asset_links(README_TEXT, "v9.9.9")

    assert len(rewritten_text) > len(README_TEXT)
    assert "# Visual Verifier" in rewritten_text
    assert "pip install visual-verifier" in rewritten_text


def test_the_rewriter_is_idempotent() -> None:
    """Confirm running the conversion twice does not double a prefix."""

    once_text = BUILDER_MODULE.rewrite_asset_links(README_TEXT, "v9.9.9")
    twice_text = BUILDER_MODULE.rewrite_asset_links(once_text, "v9.9.9")

    assert once_text == twice_text


def test_a_missing_asset_fails_the_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirm the release check refuses a README with a dead link."""

    broken_path_obj = tmp_path / "README.md"
    broken_path_obj.write_text(
        '<img src="docs/assets/absent.png">\n', encoding="utf-8"
    )
    monkeypatch.setattr(BUILDER_MODULE, "README_PATH", broken_path_obj)
    monkeypatch.setattr(BUILDER_MODULE, "REPOSITORY_ROOT_PATH", tmp_path)

    assert BUILDER_MODULE.main(["--check"]) == 1


def test_the_release_workflow_runs_the_conversion() -> None:
    """Confirm PyPI cannot be published from the relative form.

    Without this step the project page would ship broken images, which
    is the failure the relative form deliberately trades for.
    """

    workflow_text = RELEASE_WORKFLOW_PATH.read_text(encoding="utf-8")
    conversion_index = workflow_text.find("build_pypi_readme.py")
    build_index = workflow_text.find("python -m build")

    assert conversion_index != -1, "release workflow must convert links"
    assert build_index != -1
    assert conversion_index < build_index, (
        "the conversion must run before the distributions are built"
    )


def test_the_packaged_readme_is_the_compact_one() -> None:
    """Confirm PyPI ships the short page, not the full repository README.

    The repository README is long on purpose. A PyPI project page that
    long buries the install command below several screens of detail.
    """

    pyproject_text = PYPROJECT_PATH.read_text(encoding="utf-8")

    assert 'readme = "PYPI_README.md"' in pyproject_text
    assert PYPI_README_PATH.is_file()
    assert len(PYPI_README_PATH.read_text(encoding="utf-8")) < len(
        README_PATH.read_text(encoding="utf-8")
    )


def test_the_rewriter_targets_whatever_packaging_ships() -> None:
    """Confirm the rewriter follows pyproject rather than a fixed name.

    If the two ever disagree, the release would build a page whose image
    links were never converted, and PyPI would show broken images.
    """

    assert BUILDER_MODULE.README_PATH.name == "PYPI_README.md"


@pytest.mark.parametrize(
    "readme_path_obj",
    [README_PATH, PYPI_README_PATH],
    ids=lambda path_obj: path_obj.name,
)
def test_both_readmes_keep_relative_asset_links(
    readme_path_obj: Path,
) -> None:
    """Confirm neither README hard-codes an absolute asset URL.

    An absolute URL renders nothing until that exact ref exists on the
    remote, which breaks editor previews and fresh clones.
    """

    readme_text = readme_path_obj.read_text(encoding="utf-8")

    assert not ABSOLUTE_ASSET_PATTERN.findall(readme_text)


@pytest.mark.parametrize(
    "readme_path_obj",
    [README_PATH, PYPI_README_PATH],
    ids=lambda path_obj: path_obj.name,
)
def test_both_readmes_link_only_to_existing_assets(
    readme_path_obj: Path,
) -> None:
    """Confirm every image in either README resolves on disk."""

    readme_text = readme_path_obj.read_text(encoding="utf-8")

    for relative_link_str in BUILDER_MODULE.find_relative_asset_links(
        readme_text
    ):
        assert (REPOSITORY_ROOT_PATH / relative_link_str).is_file(), (
            relative_link_str
        )


def test_the_packaged_readme_states_the_honest_scope() -> None:
    """Confirm compressing the page did not drop the caveat.

    The shortest surface is the one most likely to lose the limits, and
    the one most people read.
    """

    pypi_text = " ".join(PYPI_README_PATH.read_text(encoding="utf-8").split())

    assert "not a certificate of anonymization" in pypi_text
    assert "Coverage is geometric" in pypi_text
    assert "not an anonymizer" in pypi_text
