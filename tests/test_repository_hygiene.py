"""Protect repository hygiene guarantees that reviewers cannot see.

A stray control character inside a fenced command block is invisible in a
rendered document but silently corrupts every copied command. These checks
run with the normal suite so the defect cannot return unnoticed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
ARCHIVE_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "archive"
CHECKED_SUFFIXES_FROZENSET = frozenset(
    {
        ".cff",
        ".json",
        ".md",
        ".ps1",
        ".py",
        ".sh",
        ".toml",
        ".yaml",
        ".yml",
    }
)
SKIPPED_DIRECTORY_NAMES_FROZENSET = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "outputs",
        "site",
        "venv",
    }
)
FORBIDDEN_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MAXIMUM_FUNCTION_LINES_INT = 50
MAXIMUM_ENTRY_POINT_LINES_INT = 100
ENTRY_POINT_NAMES_FROZENSET = frozenset({"main"})


def _iter_checked_files() -> list[Path]:
    """Return every text file that repository hygiene rules apply to.

    Returns:
        Sorted repository files with a checked suffix, excluding generated
        directories, virtual environments, and the read-only archive.
    """

    checked_paths_list: list[Path] = []

    for candidate_path_obj in REPOSITORY_ROOT_PATH.rglob("*"):
        if candidate_path_obj.suffix not in CHECKED_SUFFIXES_FROZENSET:
            continue
        if not candidate_path_obj.is_file():
            continue
        relative_parts_frozenset = frozenset(
            candidate_path_obj.relative_to(REPOSITORY_ROOT_PATH).parts
        )
        if relative_parts_frozenset & SKIPPED_DIRECTORY_NAMES_FROZENSET:
            continue
        checked_paths_list.append(candidate_path_obj)

    return sorted(checked_paths_list)


CHECKED_FILE_PATHS_LIST = _iter_checked_files()
CHECKED_FILE_IDS_LIST = [
    str(path_obj.relative_to(REPOSITORY_ROOT_PATH).as_posix())
    for path_obj in CHECKED_FILE_PATHS_LIST
]


def test_hygiene_checks_cover_the_repository() -> None:
    """Confirm the file discovery walk found the documented text files."""

    assert "README.md" in CHECKED_FILE_IDS_LIST
    assert "pyproject.toml" in CHECKED_FILE_IDS_LIST
    assert len(CHECKED_FILE_PATHS_LIST) > 40


@pytest.mark.parametrize(
    "checked_path_obj",
    CHECKED_FILE_PATHS_LIST,
    ids=CHECKED_FILE_IDS_LIST,
)
def test_text_files_contain_no_stray_control_characters(
    checked_path_obj: Path,
) -> None:
    """Confirm no text file hides a control character in a command block."""

    file_text = checked_path_obj.read_text(encoding="utf-8")
    control_match_obj = FORBIDDEN_CONTROL_PATTERN.search(file_text)
    failure_message_str = ""
    if control_match_obj is not None:
        failure_message_str = (
            f"{checked_path_obj.name} contains control character "
            f"{control_match_obj.group()!r} at offset "
            f"{control_match_obj.start()}"
        )

    assert control_match_obj is None, failure_message_str


def test_archive_is_never_imported_by_active_code() -> None:
    """Confirm the read-only archive stays out of the runtime package."""

    package_directory_path = REPOSITORY_ROOT_PATH / "src" / "visual_verifier"

    for module_path_obj in package_directory_path.rglob("*.py"):
        module_text = module_path_obj.read_text(encoding="utf-8")
        assert "archive" not in module_text, module_path_obj.name


def test_archive_directory_remains_present_and_read_only_in_intent() -> None:
    """Confirm historical prototypes are retained as plain text only."""

    archived_paths_list = sorted(ARCHIVE_DIRECTORY_PATH.rglob("*.*"))

    assert archived_paths_list
    for archived_path_obj in archived_paths_list:
        assert archived_path_obj.suffix == ".txt"


def _iter_python_files() -> list[Path]:
    """Return every first-party Python file governed by the style rules.

    Returns:
        Sorted package, test, and script modules, excluding the read-only
        archive and every generated directory.
    """

    return [
        path_obj
        for path_obj in _iter_checked_files()
        if path_obj.suffix == ".py"
    ]


def _measure_function_lengths(
    module_path_obj: Path,
) -> list[tuple[str, int, int]]:
    """Return the physical length of every function in one module.

    Args:
        module_path_obj: Python module to parse.

    Returns:
        Name, measured length, and applicable limit for each function.
    """

    module_tree = ast.parse(module_path_obj.read_text(encoding="utf-8"))
    measured_functions_list: list[tuple[str, int, int]] = []

    for node_obj in ast.walk(module_tree):
        if not isinstance(node_obj, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start_line_int = min(
            [node_obj.lineno]
            + [
                decorator_obj.lineno
                for decorator_obj in node_obj.decorator_list
            ]
        )
        end_line_int = node_obj.end_lineno or start_line_int
        limit_int = (
            MAXIMUM_ENTRY_POINT_LINES_INT
            if node_obj.name in ENTRY_POINT_NAMES_FROZENSET
            else MAXIMUM_FUNCTION_LINES_INT
        )
        measured_functions_list.append(
            (node_obj.name, end_line_int - start_line_int + 1, limit_int)
        )

    return measured_functions_list


@pytest.mark.parametrize(
    "module_path_obj",
    _iter_python_files(),
    ids=[
        str(path_obj.relative_to(REPOSITORY_ROOT_PATH).as_posix())
        for path_obj in _iter_python_files()
    ],
)
def test_functions_respect_the_documented_length_limit(
    module_path_obj: Path,
) -> None:
    """Confirm no function exceeds the length rule in ``AGENTS.md``.

    Rules 6 and 7 cap functions at 50 physical lines and entry points at
    100. Documenting a rule does not keep it, so it is measured here.
    """

    oversized_functions_list = [
        f"{function_name_str} is {measured_length_int} lines "
        f"(limit {limit_int})"
        for function_name_str, measured_length_int, limit_int in (
            _measure_function_lengths(module_path_obj)
        )
        if measured_length_int > limit_int
    ]

    assert not oversized_functions_list, "; ".join(oversized_functions_list)
