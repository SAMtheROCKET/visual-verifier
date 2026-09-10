"""Keep the published documentation honest about the real program.

A CLI reference page is the easiest documentation to let rot: an option is
added, the page is not touched, and the site quietly starts lying. These
checks compare the published pages against the actual argument parser and
the actual navigation, so drift fails the build instead of the user.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from visual_verifier.cli import build_parser

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
DOCS_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "docs"
CLI_PAGE_PATH = DOCS_DIRECTORY_PATH / "cli.md"
MKDOCS_CONFIG_PATH = REPOSITORY_ROOT_PATH / "mkdocs.yml"
NAV_ENTRY_PATTERN = re.compile(r":\s*([A-Za-z0-9_./-]+\.md)\s*$", re.MULTILINE)
IGNORED_OPTIONS_FROZENSET = frozenset({"-h", "--help"})


def _documented_option_strings() -> set[str]:
    """Return every long option mentioned in the CLI reference page.

    Returns:
        Option strings such as ``--min-severity`` found on the page.
    """

    page_text = CLI_PAGE_PATH.read_text(encoding="utf-8")
    documented_options_set = set(re.findall(r"`(--[a-z0-9-]+)", page_text))
    return documented_options_set - IGNORED_OPTIONS_FROZENSET


def _parser_option_strings() -> set[str]:
    """Return every long option the installed program actually accepts.

    Returns:
        Option strings from the root parser and every subcommand.
    """

    root_parser_obj = build_parser()
    collected_options_set: set[str] = set()
    parsers_list: list[argparse.ArgumentParser] = [root_parser_obj]

    for action_obj in root_parser_obj._actions:
        if isinstance(action_obj, argparse._SubParsersAction):
            parsers_list.extend(action_obj.choices.values())

    for parser_obj in parsers_list:
        for action_obj in parser_obj._actions:
            for option_text in action_obj.option_strings:
                if option_text.startswith("--"):
                    collected_options_set.add(option_text)

    return collected_options_set - IGNORED_OPTIONS_FROZENSET


def test_every_option_is_documented() -> None:
    """Confirm no command-line option is missing from the CLI page."""

    undocumented_options_list = sorted(
        _parser_option_strings() - _documented_option_strings()
    )

    assert not undocumented_options_list, (
        f"docs/cli.md does not mention {undocumented_options_list}"
    )


def test_no_documented_option_was_removed() -> None:
    """Confirm the CLI page does not advertise options that were deleted."""

    stale_options_list = sorted(
        _documented_option_strings() - _parser_option_strings()
    )

    assert not stale_options_list, (
        f"docs/cli.md still documents removed options {stale_options_list}"
    )


def test_every_command_is_documented() -> None:
    """Confirm every subcommand has a section on the CLI page."""

    page_text = CLI_PAGE_PATH.read_text(encoding="utf-8")
    root_parser_obj = build_parser()
    subparser_actions_list = [
        action_obj
        for action_obj in root_parser_obj._actions
        if isinstance(action_obj, argparse._SubParsersAction)
    ]

    assert subparser_actions_list
    for command_name_str in subparser_actions_list[0].choices:
        assert f"## {command_name_str}" in page_text, command_name_str


@pytest.mark.parametrize(
    "documented_page_str",
    sorted(
        set(
            NAV_ENTRY_PATTERN.findall(
                MKDOCS_CONFIG_PATH.read_text(encoding="utf-8")
            )
        )
    ),
)
def test_every_navigation_target_exists(documented_page_str: str) -> None:
    """Confirm no site navigation entry points at a missing page."""

    assert (DOCS_DIRECTORY_PATH / documented_page_str).is_file()


def test_navigation_covers_every_published_page() -> None:
    """Confirm no documentation page is orphaned from the site nav.

    An unlinked page is invisible to readers and to search engines, which
    defeats the point of publishing it.
    """

    navigation_pages_frozenset = frozenset(
        NAV_ENTRY_PATTERN.findall(
            MKDOCS_CONFIG_PATH.read_text(encoding="utf-8")
        )
    )
    published_pages_frozenset = frozenset(
        str(path_obj.relative_to(DOCS_DIRECTORY_PATH).as_posix())
        for path_obj in DOCS_DIRECTORY_PATH.rglob("*.md")
        if "audits" not in path_obj.parts
    )
    orphaned_pages_list = sorted(
        published_pages_frozenset - navigation_pages_frozenset
    )

    assert not orphaned_pages_list, (
        f"pages missing from mkdocs.yml nav: {orphaned_pages_list}"
    )
