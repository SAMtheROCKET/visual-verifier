"""Rewrite the README's asset links to absolute URLs for PyPI.

`README.md` uses repository-relative image paths, because those are what
render in a local editor preview and in GitHub's repository view. PyPI
does not resolve relative paths, so a release built straight from that
file would show three broken images on the project page.

This script produces the absolute-URL form, and the release workflow runs
it immediately before building. Keeping the relative form in the
repository and converting at release time is the only arrangement where
every reader sees the images: editors and GitHub from the relative paths,
PyPI from the converted ones.

    uv run python scripts/build_pypi_readme.py --check
    uv run python scripts/build_pypi_readme.py --ref v0.3.0
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
README_PATH = REPOSITORY_ROOT_PATH / "README.md"
RAW_URL_PREFIX_TEXT = (
    "https://raw.githubusercontent.com/SAMtheROCKET/visual-verifier"
)
ASSET_DIRECTORY_NAME_TEXT = "docs/assets/"
DEFAULT_REF_TEXT = "main"
RELATIVE_LINK_PATTERN = re.compile(
    r"""(src=["']|\]\()(docs/assets/[^"')\s]+)"""
)


def build_parser() -> argparse.ArgumentParser:
    """Return the command-line parser.

    Returns:
        Parser accepting the Git ref and a check-only mode.
    """

    parser_obj = argparse.ArgumentParser(
        prog="build_pypi_readme.py",
        description=(
            "Rewrite relative README asset links to absolute raw URLs so "
            "the PyPI project page can render them."
        ),
    )
    parser_obj.add_argument(
        "--ref",
        metavar="REF",
        default=DEFAULT_REF_TEXT,
        help=(
            "Git ref the absolute URLs point at, usually the release tag "
            f"(default: {DEFAULT_REF_TEXT})."
        ),
    )
    parser_obj.add_argument(
        "--check",
        action="store_true",
        help=(
            "Report what would change and exit non-zero if any relative "
            "asset link is missing from disk. Writes nothing."
        ),
    )
    return parser_obj


def main(argv: list[str] | None = None) -> int:
    """Rewrite the README, or report what a rewrite would do.

    Args:
        argv: Optional argument vector.

    Returns:
        Process exit code. ``1`` when a linked asset does not exist.
    """

    arguments_obj = build_parser().parse_args(argv)
    readme_text = README_PATH.read_text(encoding="utf-8")
    relative_links_list = find_relative_asset_links(readme_text)

    missing_list = [
        link_str
        for link_str in relative_links_list
        if not (REPOSITORY_ROOT_PATH / link_str).is_file()
    ]
    if missing_list:
        print(
            f"README links to missing assets: {missing_list}",
            file=sys.stderr,
        )
        return 1

    if arguments_obj.check:
        print(
            f"{len(relative_links_list)} relative asset links resolve on "
            "disk and would become absolute for PyPI."
        )
        return 0

    README_PATH.write_text(
        rewrite_asset_links(readme_text, arguments_obj.ref),
        encoding="utf-8",
    )
    print(
        f"Rewrote {len(relative_links_list)} asset links to "
        f"{RAW_URL_PREFIX_TEXT}/{arguments_obj.ref}/"
    )
    return 0


def find_relative_asset_links(readme_text: str) -> list[str]:
    """Return every repository-relative asset path the README links to.

    Args:
        readme_text: README contents.

    Returns:
        Relative paths such as ``docs/assets/demo.gif``, in order.
    """

    return [
        match_obj.group(2)
        for match_obj in RELATIVE_LINK_PATTERN.finditer(readme_text)
    ]


def rewrite_asset_links(readme_text: str, ref_text: str) -> str:
    """Return the README with relative asset links made absolute.

    Args:
        readme_text: README contents.
        ref_text: Git ref the absolute URLs point at.

    Returns:
        The rewritten document.
    """

    def _replace(match_obj: re.Match[str]) -> str:
        return (
            f"{match_obj.group(1)}{RAW_URL_PREFIX_TEXT}/{ref_text}/"
            f"{match_obj.group(2)}"
        )

    return RELATIVE_LINK_PATTERN.sub(_replace, readme_text)


if __name__ == "__main__":
    raise SystemExit(main())
