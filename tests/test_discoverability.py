"""Keep the documentation site findable by people, crawlers, and agents.

None of this changes what the tool does, which is exactly why it rots
quietly. A broken sitemap reference or a social card that stopped being
generated produces no error anywhere; the only symptom is a launch link
rendering as a bare URL, noticed after it has already been shared.

These checks are deliberately about presence and correctness of the
declarations, not about search ranking, which no test can assert.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
DOCS_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "docs"
MKDOCS_CONFIG_PATH = REPOSITORY_ROOT_PATH / "mkdocs.yml"
ROBOTS_PATH = DOCS_DIRECTORY_PATH / "robots.txt"
LLMS_PATH = DOCS_DIRECTORY_PATH / "llms.txt"
SOCIAL_CARD_PATH = DOCS_DIRECTORY_PATH / "assets" / "social_card.png"
THEME_OVERRIDE_PATH = REPOSITORY_ROOT_PATH / "overrides" / "main.html"
SITE_URL_TEXT = "https://samtherocket.github.io/visual-verifier/"
SOCIAL_CARD_WIDTH_INT = 1200
SOCIAL_CARD_HEIGHT_INT = 630
PNG_DIMENSION_OFFSET_INT = 16


def test_robots_points_crawlers_at_the_sitemap() -> None:
    """Confirm a crawler can discover every page from the entry point."""

    robots_text = ROBOTS_PATH.read_text(encoding="utf-8")

    assert "User-agent: *" in robots_text
    assert "Allow: /" in robots_text
    assert f"Sitemap: {SITE_URL_TEXT}sitemap.xml" in robots_text


def test_llms_file_describes_the_project_to_an_agent() -> None:
    """Confirm the agent-readable summary carries the essentials.

    An agent reading this file should learn what the tool is, that it is
    not an anonymizer, and how to install it, without fetching anything
    else.
    """

    llms_text = LLMS_PATH.read_text(encoding="utf-8")

    assert llms_text.startswith("# Visual Verifier")
    assert "> " in llms_text
    assert "pip install visual-verifier" in llms_text
    assert "not an anonymizer" in llms_text


def test_llms_links_are_absolute_and_on_the_site() -> None:
    """Confirm every link an agent follows actually resolves.

    A relative link in this file is useless: it is read out of context,
    often without the site around it.
    """

    llms_text = LLMS_PATH.read_text(encoding="utf-8")
    link_targets_list = re.findall(r"\]\(([^)]+)\)", llms_text)

    assert link_targets_list
    assert all(
        target_str.startswith("https://") for target_str in link_targets_list
    ), [t for t in link_targets_list if not t.startswith("https://")]


@pytest.mark.parametrize(
    "page_slug_str",
    [
        "getting_started",
        "anonymization_qa",
        "target_annotation",
        "github_action",
        "benchmarks",
        "cli",
        "python_api",
        "limitations",
    ],
)
def test_every_linked_documentation_page_exists(page_slug_str: str) -> None:
    """Confirm the agent index does not advertise a page that was renamed."""

    llms_text = LLMS_PATH.read_text(encoding="utf-8")

    assert f"{SITE_URL_TEXT}{page_slug_str}/" in llms_text
    assert (DOCS_DIRECTORY_PATH / f"{page_slug_str}.md").is_file()


def test_the_social_card_exists_at_the_required_size() -> None:
    """Confirm the shared-link preview image is present and correct.

    Every platform expects 1200x630. A wrong size is cropped badly
    rather than rejected, so nothing warns you.
    """

    assert SOCIAL_CARD_PATH.is_file()

    header_bytes = SOCIAL_CARD_PATH.read_bytes()[:32]
    width_int = int.from_bytes(
        header_bytes[PNG_DIMENSION_OFFSET_INT : PNG_DIMENSION_OFFSET_INT + 4],
        "big",
    )
    height_int = int.from_bytes(
        header_bytes[
            PNG_DIMENSION_OFFSET_INT + 4 : PNG_DIMENSION_OFFSET_INT + 8
        ],
        "big",
    )

    assert (width_int, height_int) == (
        SOCIAL_CARD_WIDTH_INT,
        SOCIAL_CARD_HEIGHT_INT,
    )


def test_social_metadata_is_declared() -> None:
    """Confirm a shared link renders as a card rather than a bare URL."""

    override_text = THEME_OVERRIDE_PATH.read_text(encoding="utf-8")

    for property_str in (
        "og:title",
        "og:description",
        "og:image",
        "og:url",
        "twitter:card",
        "twitter:image",
    ):
        assert property_str in override_text, property_str


def test_social_metadata_survives_a_missing_page_object() -> None:
    """Confirm the override guards `page`, which 404.html renders without.

    An unguarded `page.meta` access fails the whole documentation build,
    producing a site directory with no HTML in it at all.
    """

    override_text = THEME_OVERRIDE_PATH.read_text(encoding="utf-8")

    assert "{% if page %}" in override_text
    assert "namespace(" in override_text


def test_the_theme_override_is_wired_into_the_config() -> None:
    """Confirm the metadata block is actually used by the build."""

    config_text = MKDOCS_CONFIG_PATH.read_text(encoding="utf-8")

    assert "custom_dir: overrides" in config_text


def test_the_home_page_title_is_descriptive() -> None:
    """Confirm the most heavily weighted tag is not just a product name.

    A bare "Visual Verifier" tells a searcher nothing about what the
    project does.
    """

    home_text = (DOCS_DIRECTORY_PATH / "README.md").read_text(encoding="utf-8")

    assert home_text.startswith("---")
    assert "title: Anonymization QA for Images & Videos" in home_text
    assert "description:" in home_text


def test_the_category_statement_is_stated_prominently() -> None:
    """Confirm both READMEs say what the tool is, not only what it does.

    The distinctive claim is the role: most tools transform media, this
    one independently tests whether the transformation happened. That
    positioning is easy to lose during an edit.

    Whitespace is normalized first, because the prose is hard-wrapped
    and a phrase may straddle a line break.
    """

    for readme_path_obj in (
        REPOSITORY_ROOT_PATH / "README.md",
        DOCS_DIRECTORY_PATH / "README.md",
    ):
        readme_text = " ".join(
            readme_path_obj.read_text(encoding="utf-8").split()
        )
        assert "The missing test after visual processing" in readme_text, (
            readme_path_obj.name
        )
        assert "not an anonymizer" in readme_text, readme_path_obj.name


MARKETPLACE_URL_TEXT = "https://github.com/marketplace/actions/visual-verifier"


@pytest.mark.parametrize(
    "relative_path_str",
    [
        "README.md",
        "docs/github_action.md",
        "docs/ci.md",
        "docs/llms.txt",
    ],
)
def test_the_marketplace_listing_is_linked(relative_path_str: str) -> None:
    """Confirm every surface that mentions the action points at its listing.

    The Marketplace is a discovery surface of its own and a trust signal
    for a CI action. A listing nothing links to is one nobody finds.
    """

    file_text = (REPOSITORY_ROOT_PATH / relative_path_str).read_text(
        encoding="utf-8"
    )

    assert MARKETPLACE_URL_TEXT in file_text


def test_the_action_declares_marketplace_branding() -> None:
    """Confirm the listing has an icon and colour rather than defaults.

    GitHub requires branding for a Marketplace listing, and a missing
    icon is only visible once the listing is already public.
    """

    action_text = (REPOSITORY_ROOT_PATH / "action.yml").read_text(
        encoding="utf-8"
    )

    assert "branding:" in action_text
    assert "icon:" in action_text
    assert "color:" in action_text
