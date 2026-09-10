"""Keep the published GitHub Action honest about what it accepts.

`action.yml` is consumed by other people's workflows, so a renamed input
or an undocumented output breaks builds this repository never runs. The
manifest is read as text rather than parsed, because a YAML library is not
a test dependency and the shape checked here is deliberately flat.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import visual_verifier

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
ACTION_MANIFEST_PATH = REPOSITORY_ROOT_PATH / "action.yml"
CI_PAGE_PATH = REPOSITORY_ROOT_PATH / "docs" / "ci.md"
ACTION_PAGE_PATH = REPOSITORY_ROOT_PATH / "docs" / "github_action.md"
README_PATH = REPOSITORY_ROOT_PATH / "README.md"
RENDERER_SCRIPT_PATH = (
    REPOSITORY_ROOT_PATH / "scripts" / "render_github_summary.py"
)
WORKFLOW_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / ".github" / "workflows"
TOP_LEVEL_KEY_PATTERN = re.compile(r"^[a-z]", re.MULTILINE)
DECLARED_NAME_PATTERN = re.compile(r"^ {2}([a-z][a-z0-9-]*):$")
DOCUMENTED_FIELD_PATTERN = re.compile(r"^\| `([a-z][a-z0-9-]*)`", re.MULTILINE)
ACTION_REFERENCE_PATTERN = re.compile(r"SAMtheROCKET/visual-verifier@(\S+)")
REQUIRED_INPUTS_FROZENSET = frozenset({"reference", "candidate"})
DOCUMENTED_PAGE_PATHS_TUPLE = (
    CI_PAGE_PATH,
    ACTION_PAGE_PATH,
    README_PATH,
)

MANIFEST_TEXT = ACTION_MANIFEST_PATH.read_text(encoding="utf-8")
CI_PAGE_TEXT = CI_PAGE_PATH.read_text(encoding="utf-8")
ACTION_PAGE_TEXT = ACTION_PAGE_PATH.read_text(encoding="utf-8")


def _section_text(section_name_str: str) -> str:
    """Return the body of one top-level manifest section.

    Args:
        section_name_str: Top-level key such as ``inputs`` or ``outputs``.

    Returns:
        The indented lines belonging to that section.
    """

    start_match = re.search(
        rf"^{section_name_str}:$", MANIFEST_TEXT, re.MULTILINE
    )
    assert start_match is not None, section_name_str

    remainder_str = MANIFEST_TEXT[start_match.end() :]
    end_match = TOP_LEVEL_KEY_PATTERN.search(remainder_str)
    if end_match is None:
        return remainder_str
    return remainder_str[: end_match.start()]


def _declared_blocks(section_name_str: str) -> dict[str, str]:
    """Split one manifest section into its declared entries.

    Args:
        section_name_str: Top-level key such as ``inputs`` or ``outputs``.

    Returns:
        Mapping of declared name to the raw lines describing it.
    """

    blocks_dict: dict[str, list[str]] = {}
    current_name_str = ""

    for line_str in _section_text(section_name_str).splitlines():
        name_match = DECLARED_NAME_PATTERN.match(line_str)
        if name_match is not None:
            current_name_str = name_match.group(1)
            blocks_dict[current_name_str] = []
        elif current_name_str:
            blocks_dict[current_name_str].append(line_str)

    return {
        name_str: "\n".join(lines_list)
        for name_str, lines_list in blocks_dict.items()
    }


INPUT_BLOCKS_DICT = _declared_blocks("inputs")
OUTPUT_BLOCKS_DICT = _declared_blocks("outputs")


def test_the_action_is_a_composite_action() -> None:
    """Confirm the manifest still runs as a composite action."""

    assert "using: composite" in MANIFEST_TEXT
    assert INPUT_BLOCKS_DICT
    assert OUTPUT_BLOCKS_DICT


def test_the_renderer_the_action_invokes_exists() -> None:
    """Confirm the manifest does not call a script that was moved."""

    assert "scripts/render_github_summary.py" in MANIFEST_TEXT
    assert RENDERER_SCRIPT_PATH.is_file()


def test_only_the_two_media_paths_are_required() -> None:
    """Confirm the action stays usable with two arguments."""

    required_names_frozenset = frozenset(
        name_str
        for name_str, block_str in INPUT_BLOCKS_DICT.items()
        if "required: true" in block_str
    )

    assert required_names_frozenset == REQUIRED_INPUTS_FROZENSET


def test_every_optional_input_has_a_default() -> None:
    """Confirm an optional input cannot arrive as an empty expression."""

    missing_defaults_list = sorted(
        name_str
        for name_str, block_str in INPUT_BLOCKS_DICT.items()
        if name_str not in REQUIRED_INPUTS_FROZENSET
        and "default:" not in block_str
    )

    assert not missing_defaults_list, missing_defaults_list


def test_gating_is_the_default() -> None:
    """Confirm a silent, non-gating default cannot creep in.

    An anonymization check that reports gaps without failing the job is
    worse than no check, because the badge still looks green.
    """

    assert 'default: "true"' in INPUT_BLOCKS_DICT["fail-on-gap"]


def test_evidence_is_uploaded_by_default() -> None:
    """Confirm the evidence survives the run that needed it most."""

    assert 'default: "true"' in INPUT_BLOCKS_DICT["upload-evidence"]


@pytest.mark.parametrize("input_name_str", sorted(INPUT_BLOCKS_DICT))
def test_every_input_is_documented(input_name_str: str) -> None:
    """Confirm the page documents every input the action accepts."""

    assert f"`{input_name_str}`" in ACTION_PAGE_TEXT, input_name_str


@pytest.mark.parametrize("output_name_str", sorted(OUTPUT_BLOCKS_DICT))
def test_every_output_is_documented(output_name_str: str) -> None:
    """Confirm the page documents every output the action publishes."""

    assert f"`{output_name_str}`" in ACTION_PAGE_TEXT, output_name_str


@pytest.mark.parametrize(
    "page_path_obj",
    DOCUMENTED_PAGE_PATHS_TUPLE,
    ids=lambda path_obj: path_obj.name,
)
def test_documented_action_tag_matches_the_package_version(
    page_path_obj: Path,
) -> None:
    """Confirm the documentation advertises the tag being released.

    Every example tells a reader to pin the action, so a stale tag here
    silently sends them to an older verifier than the one documented.
    """

    page_text = page_path_obj.read_text(encoding="utf-8")
    referenced_tags_frozenset = frozenset(
        ACTION_REFERENCE_PATTERN.findall(page_text)
    )
    expected_tag_str = f"v{visual_verifier.__version__}"

    assert referenced_tags_frozenset, page_path_obj.name
    assert referenced_tags_frozenset == {expected_tag_str}


def test_the_action_is_exercised_by_a_workflow() -> None:
    """Confirm the action is proven on a runner before anyone else uses it.

    The composite steps are shell, so nothing else in the suite can catch
    a broken one. A workflow that runs the local action does.
    """

    workflow_texts_list = [
        path_obj.read_text(encoding="utf-8")
        for path_obj in WORKFLOW_DIRECTORY_PATH.glob("*.yml")
    ]

    assert any(
        "uses: ./" in workflow_text_str
        for workflow_text_str in workflow_texts_list
    )


def test_no_documented_field_was_removed() -> None:
    """Confirm the page does not advertise a deleted input or output."""

    documented_names_frozenset = frozenset(
        DOCUMENTED_FIELD_PATTERN.findall(ACTION_PAGE_TEXT)
    )
    known_names_frozenset = frozenset(INPUT_BLOCKS_DICT) | frozenset(
        OUTPUT_BLOCKS_DICT
    )
    stale_names_list = sorted(
        documented_names_frozenset - known_names_frozenset
    )

    assert not stale_names_list, (
        f"github_action.md documents removed fields {stale_names_list}"
    )


def test_the_action_is_exercised_on_the_minimum_python() -> None:
    """Confirm the composite wrapper is run on the oldest supported Python.

    Every other self-test step pins 3.12, so 3.12-only syntax in the
    wrapper's inline Python would pass CI while breaking the 3.10 users
    the package still advertises support for.
    """

    minimum_version_str = _minimum_supported_python()
    workflow_texts_list = [
        path_obj.read_text(encoding="utf-8")
        for path_obj in WORKFLOW_DIRECTORY_PATH.glob("*.yml")
    ]

    assert any(
        "uses: ./" in workflow_text_str
        and f'python-version: "{minimum_version_str}"' in workflow_text_str
        for workflow_text_str in workflow_texts_list
    ), (
        f"a workflow must run the local action with python-version "
        f'"{minimum_version_str}", the minimum in pyproject.toml'
    )


def _minimum_supported_python() -> str:
    """Return the lowest Python version the package claims to support.

    Returns:
        A version such as ``3.10``, read from ``requires-python``.
    """

    pyproject_text = (REPOSITORY_ROOT_PATH / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    match_obj = re.search(
        r'requires-python\s*=\s*"[><=]*\s*(\d+\.\d+)', pyproject_text
    )
    assert match_obj is not None, "requires-python not found"
    return match_obj.group(1)
