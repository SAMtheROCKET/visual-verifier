"""Prove that the package never reaches the network.

"Runs locally, your media is never uploaded" is a privacy claim, and a
privacy claim asserted only in a README is worth nothing. These checks
parse the shipped package and fail if any module gains the ability to
open a socket, so the claim stays true by construction.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "src" / "visual_verifier"
NETWORK_MODULE_PREFIXES_FROZENSET = frozenset(
    {
        "aiohttp",
        "asyncio",
        "boto3",
        "ftplib",
        "http",
        "httpx",
        "imaplib",
        "poplib",
        "requests",
        "smtplib",
        "socket",
        "socketserver",
        "ssl",
        "telnetlib",
        "urllib",
        "urllib3",
        "webbrowser",
        "websockets",
        "xmlrpc",
    }
)
NETWORK_CALL_NAMES_FROZENSET = frozenset(
    {
        "urlopen",
        "urlretrieve",
        "socket",
        "create_connection",
    }
)

PACKAGE_MODULE_PATHS_LIST = sorted(PACKAGE_DIRECTORY_PATH.rglob("*.py"))
PACKAGE_MODULE_IDS_LIST = [
    str(path_obj.relative_to(PACKAGE_DIRECTORY_PATH).as_posix())
    for path_obj in PACKAGE_MODULE_PATHS_LIST
]


def _imported_root_modules(module_path_obj: Path) -> set[str]:
    """Return the root name of every module imported by one file.

    Args:
        module_path_obj: Python module to parse.

    Returns:
        Root module names, so ``urllib.request`` yields ``urllib``.
    """

    module_tree = ast.parse(module_path_obj.read_text(encoding="utf-8"))
    imported_roots_set: set[str] = set()

    for node_obj in ast.walk(module_tree):
        if isinstance(node_obj, ast.Import):
            for alias_obj in node_obj.names:
                imported_roots_set.add(alias_obj.name.split(".")[0])
        elif isinstance(node_obj, ast.ImportFrom) and node_obj.module:
            imported_roots_set.add(node_obj.module.split(".")[0])

    return imported_roots_set


def test_package_modules_were_discovered() -> None:
    """Confirm the scan actually found the shipped package modules."""

    assert len(PACKAGE_MODULE_PATHS_LIST) > 20
    assert "api.py" in PACKAGE_MODULE_IDS_LIST
    assert "demo.py" in PACKAGE_MODULE_IDS_LIST


@pytest.mark.parametrize(
    "module_path_obj",
    PACKAGE_MODULE_PATHS_LIST,
    ids=PACKAGE_MODULE_IDS_LIST,
)
def test_no_module_imports_a_networking_library(
    module_path_obj: Path,
) -> None:
    """Confirm no shipped module can open a network connection."""

    offending_modules_frozenset = (
        _imported_root_modules(module_path_obj)
        & NETWORK_MODULE_PREFIXES_FROZENSET
    )

    assert not offending_modules_frozenset, (
        f"{module_path_obj.name} imports "
        f"{sorted(offending_modules_frozenset)}, which would break the "
        "documented guarantee that Visual Verifier runs locally"
    )


@pytest.mark.parametrize(
    "module_path_obj",
    PACKAGE_MODULE_PATHS_LIST,
    ids=PACKAGE_MODULE_IDS_LIST,
)
def test_no_module_calls_a_networking_function(
    module_path_obj: Path,
) -> None:
    """Confirm no module calls a known network entry point by name."""

    module_tree = ast.parse(module_path_obj.read_text(encoding="utf-8"))
    called_names_list: list[str] = []

    for node_obj in ast.walk(module_tree):
        if not isinstance(node_obj, ast.Call):
            continue
        function_obj = node_obj.func
        if isinstance(function_obj, ast.Name):
            called_names_list.append(function_obj.id)
        elif isinstance(function_obj, ast.Attribute):
            called_names_list.append(function_obj.attr)

    offending_calls_frozenset = (
        frozenset(called_names_list) & NETWORK_CALL_NAMES_FROZENSET
    )

    assert not offending_calls_frozenset, (
        f"{module_path_obj.name} calls {sorted(offending_calls_frozenset)}"
    )


def test_runtime_dependencies_are_offline_libraries() -> None:
    """Confirm no networking library became a runtime dependency."""

    pyproject_text = (REPOSITORY_ROOT_PATH / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    dependencies_block = pyproject_text.split("dependencies = [", 1)[1]
    dependencies_block = dependencies_block.split("]", 1)[0].lower()

    for network_name_str in ("requests", "httpx", "aiohttp", "urllib3"):
        assert network_name_str not in dependencies_block
