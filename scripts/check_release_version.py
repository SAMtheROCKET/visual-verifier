"""Assert that a release tag agrees with every declared version.

`tests/test_package_smoke.py` already ties the package version to the
packaging and citation metadata. Nothing tied the Git tag to any of them,
so `v0.2.1` could be pushed while the package still reported `0.2.0` and
the release would publish the wrong version under the right name.

Run before tagging, or let the release workflow run it for you:

    uv run python scripts/check_release_version.py v0.2.0
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import visual_verifier

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
CITATION_FILE_PATH = REPOSITORY_ROOT_PATH / "CITATION.cff"
CITATION_VERSION_PATTERN = re.compile(r"^version:\s*(\S+)\s*$", re.MULTILINE)
TAG_PREFIX_TEXT = "v"


def main(argv: list[str] | None = None) -> int:
    """Compare the release tag with the package and citation versions.

    Args:
        argv: Optional argument vector. The first entry is the tag name.
            Falls back to ``GITHUB_REF_NAME`` when omitted.

    Returns:
        Process exit code. ``0`` when every version agrees, ``1`` when a
        tag was not supplied or any declared version disagrees.
    """

    arguments_list = sys.argv[1:] if argv is None else argv
    tag_name_str = _resolve_tag_name(arguments_list)
    if tag_name_str is None:
        print(
            "No tag supplied. Pass one as an argument or set GITHUB_REF_NAME.",
            file=sys.stderr,
        )
        return 1

    expected_version_str = tag_name_str.removeprefix(TAG_PREFIX_TEXT)
    problems_list = _find_version_problems(
        tag_name_str,
        expected_version_str,
    )
    if problems_list:
        print("Release version mismatch:", file=sys.stderr)
        for problem_str in problems_list:
            print(f"  {problem_str}", file=sys.stderr)
        return 1

    print(f"Tag, package, and citation all agree on {expected_version_str}.")
    return 0


def _resolve_tag_name(arguments_list: list[str]) -> str | None:
    """Return the tag name from arguments or the CI environment.

    Args:
        arguments_list: Command-line arguments without the program name.

    Returns:
        Tag name, or ``None`` when no tag could be determined.
    """

    if arguments_list:
        return arguments_list[0]
    return os.environ.get("GITHUB_REF_NAME") or None


def _find_version_problems(
    tag_name_str: str,
    expected_version_str: str,
) -> list[str]:
    """Return one readable message per disagreeing version source.

    Args:
        tag_name_str: Release tag being validated.
        expected_version_str: Version implied by the tag.

    Returns:
        Empty list when every source agrees.
    """

    problems_list: list[str] = []
    package_version_str = visual_verifier.__version__
    citation_version_str = _read_citation_version()

    if package_version_str != expected_version_str:
        problems_list.append(
            f"tag {tag_name_str} implies {expected_version_str!r} but the "
            f"package reports {package_version_str!r}"
        )
    if citation_version_str != expected_version_str:
        problems_list.append(
            f"tag {tag_name_str} implies {expected_version_str!r} but "
            f"CITATION.cff reports {citation_version_str!r}"
        )
    return problems_list


def _read_citation_version() -> str | None:
    """Return the version declared in ``CITATION.cff``.

    Returns:
        Declared version, or ``None`` when the field is absent.
    """

    citation_text = CITATION_FILE_PATH.read_text(encoding="utf-8")
    version_match_obj = CITATION_VERSION_PATTERN.search(citation_text)
    if version_match_obj is None:
        return None
    return version_match_obj.group(1)


if __name__ == "__main__":
    raise SystemExit(main())
