"""Fail the build when the documentation site would load third-party code.

Visual Verifier tells people their media never leaves their machine. A
documentation site that pulls a web font or an analytics script from
someone else's server undercuts that on the very page making the promise,
and it happens by accident: one theme option flipped, one embed pasted in.

Hyperlinks are fine. This checks only resources the browser fetches on its
own: scripts, stylesheets, fonts, images, frames, and preloads.

    uv run python scripts/check_site_privacy.py site
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_SITE_DIRECTORY_NAME_STR = "site"
LOADED_RESOURCE_PATTERN = re.compile(
    r"""(?:src|srcset|data-src|poster)\s*=\s*["'](https?://[^"']+)""",
    re.IGNORECASE,
)
STYLESHEET_PATTERN = re.compile(
    r"""<link\b[^>]*\bhref\s*=\s*["'](https?://[^"']+)[^>]*>""",
    re.IGNORECASE,
)
LINK_RELATION_PATTERN = re.compile(
    r"""\brel\s*=\s*["']([^"']+)""",
    re.IGNORECASE,
)
FETCHING_RELATIONS_FROZENSET = frozenset(
    {
        "stylesheet",
        "preload",
        "prefetch",
        "preconnect",
        "dns-prefetch",
        "modulepreload",
    }
)
CSS_IMPORT_PATTERN = re.compile(
    r"""(?:@import\s+|url\()\s*["']?(https?://[^"')]+)""",
    re.IGNORECASE,
)


def main(argv: list[str] | None = None) -> int:
    """Scan a built site and report every third-party resource load.

    Args:
        argv: Optional argument vector. The first entry is the site
            directory. Defaults to ``site``.

    Returns:
        Process exit code. ``0`` when the site is self-hosted, ``1`` when
        it would fetch a resource from another origin or the directory is
        missing.
    """

    arguments_list = sys.argv[1:] if argv is None else argv
    site_path_obj = Path(
        arguments_list[0]
        if arguments_list
        else DEFAULT_SITE_DIRECTORY_NAME_STR
    )
    if not site_path_obj.is_dir():
        print(f"Site directory not found: {site_path_obj}", file=sys.stderr)
        return 1

    findings_list = _find_external_resources(site_path_obj)
    if findings_list:
        print("Third-party resource loads found:", file=sys.stderr)
        for file_name_str, url_str in findings_list:
            print(f"  {file_name_str}: {url_str}", file=sys.stderr)
        return 1

    scanned_count_int = len(list(site_path_obj.rglob("*.html")))
    print(
        f"No third-party resource loads in {scanned_count_int} pages. "
        "The documentation site is self-hosted."
    )
    return 0


def _find_external_resources(
    site_path_obj: Path,
) -> list[tuple[str, str]]:
    """Return every externally fetched resource in a built site.

    Args:
        site_path_obj: Directory containing the built site.

    Returns:
        Pairs of relative file name and offending absolute URL.
    """

    findings_list: list[tuple[str, str]] = []

    for page_path_obj in sorted(site_path_obj.rglob("*.html")):
        page_text = page_path_obj.read_text(encoding="utf-8", errors="ignore")
        relative_name_str = str(
            page_path_obj.relative_to(site_path_obj).as_posix()
        )
        for url_str in _external_urls_in_markup(page_text):
            findings_list.append((relative_name_str, url_str))

    for style_path_obj in sorted(site_path_obj.rglob("*.css")):
        style_text = style_path_obj.read_text(
            encoding="utf-8", errors="ignore"
        )
        relative_name_str = str(
            style_path_obj.relative_to(site_path_obj).as_posix()
        )
        for url_str in CSS_IMPORT_PATTERN.findall(style_text):
            findings_list.append((relative_name_str, url_str))

    return findings_list


def _external_urls_in_markup(page_text: str) -> list[str]:
    """Return absolute URLs one page would fetch without user action.

    Args:
        page_text: Rendered HTML of a single page.

    Returns:
        Absolute URLs loaded as scripts, styles, fonts, media, or hints.
    """

    external_urls_list: list[str] = list(
        LOADED_RESOURCE_PATTERN.findall(page_text)
    )

    for link_match_obj in re.finditer(
        r"<link\b[^>]*>", page_text, re.IGNORECASE
    ):
        link_text = link_match_obj.group(0)
        relation_match_obj = LINK_RELATION_PATTERN.search(link_text)
        if relation_match_obj is None:
            continue
        relations_frozenset = frozenset(
            relation_match_obj.group(1).lower().split()
        )
        if not relations_frozenset & FETCHING_RELATIONS_FROZENSET:
            continue
        href_match_obj = STYLESHEET_PATTERN.match(link_text)
        if href_match_obj is not None:
            external_urls_list.append(href_match_obj.group(1))

    return external_urls_list


if __name__ == "__main__":
    raise SystemExit(main())
