"""Protect the self-contained HTML evidence report.

The report exists to be forwarded: attached to a ticket, emailed to a
reviewer, opened on a machine that has never heard of this project. Three
properties make that safe, and each is pinned here.

- It references nothing external, so it renders offline and opening it
  cannot signal to anyone that the report exists.
- It embeds its own thumbnails, so it survives being moved.
- It is deterministic, so two runs over the same media are comparable.
"""

from __future__ import annotations

import base64
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from visual_verifier import verify_video
from visual_verifier.reporting.html_report import (
    FrameThumbnail,
    render_html_report,
)

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLE_MEDIA_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples" / "media"
REFERENCE_VIDEO_PATH = EXAMPLE_MEDIA_DIRECTORY_PATH / "video_raw.mp4"
PARTIAL_BLUR_VIDEO_PATH = (
    EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur_partial.mp4"
)
EXTERNAL_REFERENCE_PATTERN = re.compile(r'(?:src|href)="(?!#|data:)([^"]+)"')
JPEG_MAGIC_BYTES = b"\xff\xd8"


class _DocumentInspector(HTMLParser):
    """Collect the structural facts the report contract depends on."""

    def __init__(self) -> None:
        """Initialize empty structural counters."""

        super().__init__()
        self.class_names_list: list[str] = []
        self.image_sources_list: list[str] = []
        self.element_ids_list: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Record classes, image sources, and element identifiers."""

        attributes_dict = dict(attrs)
        class_value = attributes_dict.get("class")
        if class_value:
            self.class_names_list.append(class_value)
        identifier_value = attributes_dict.get("id")
        if identifier_value:
            self.element_ids_list.append(identifier_value)
        if tag == "img":
            self.image_sources_list.append(attributes_dict.get("src") or "")


@pytest.fixture(scope="module")
def partial_blur_report(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Return the HTML report for the partially blurred fixture.

    Args:
        tmp_path_factory: Pytest-provided temporary directory factory.

    Returns:
        Rendered HTML document text.
    """

    output_path_obj = tmp_path_factory.mktemp("html_report")
    result_obj = verify_video(
        REFERENCE_VIDEO_PATH,
        PARTIAL_BLUR_VIDEO_PATH,
        output_dir=output_path_obj,
        save_annotated_video=False,
    )
    return result_obj.evidence_paths["html_report"].read_text(encoding="utf-8")


def _inspect(document_text: str) -> _DocumentInspector:
    """Parse one document and return its structural facts."""

    inspector_obj = _DocumentInspector()
    inspector_obj.feed(document_text)
    return inspector_obj


def test_report_references_nothing_external(
    partial_blur_report: str,
) -> None:
    """Confirm the document loads no remote resource of any kind.

    A single CDN link would leak the fact that a privacy report was
    opened, and would break the report on an air-gapped machine.
    """

    external_references_list = EXTERNAL_REFERENCE_PATTERN.findall(
        partial_blur_report
    )

    assert external_references_list == []
    assert "http://" not in partial_blur_report
    assert "https://" not in partial_blur_report


def test_report_embeds_valid_jpeg_evidence(
    partial_blur_report: str,
) -> None:
    """Confirm every image is an embedded, decodable JPEG."""

    inspector_obj = _inspect(partial_blur_report)

    assert inspector_obj.image_sources_list
    for source_text in inspector_obj.image_sources_list:
        assert source_text.startswith("data:image/jpeg;base64,")
        decoded_bytes = base64.b64decode(source_text.split(",", 1)[1])
        assert decoded_bytes.startswith(JPEG_MAGIC_BYTES)


def test_report_timeline_matches_the_verification(
    partial_blur_report: str,
) -> None:
    """Confirm the timeline shows 12 processed and 3 unprotected frames."""

    inspector_obj = _inspect(partial_blur_report)
    passed_cells_int = inspector_obj.class_names_list.count("cell pass")
    failed_cells_int = inspector_obj.class_names_list.count("cell fail")

    assert passed_cells_int == 12
    assert failed_cells_int == 3


def test_report_links_every_failure_to_its_evidence(
    partial_blur_report: str,
) -> None:
    """Confirm each failing timeline cell anchors to a real card."""

    anchor_frames_frozenset = frozenset(
        re.findall(r'href="#frame-(\d+)"', partial_blur_report)
    )
    identifier_frames_frozenset = frozenset(
        re.findall(r'id="frame-(\d+)"', partial_blur_report)
    )

    assert anchor_frames_frozenset == frozenset({"4", "8", "12"})
    assert anchor_frames_frozenset <= identifier_frames_frozenset


def test_report_states_the_limits_of_a_pass(
    partial_blur_report: str,
) -> None:
    """Confirm the honest-scope note travels with the document.

    The report is designed to be forwarded to people who never read the
    documentation, so it has to carry its own caveat.
    """

    assert "not a certificate of anonymization" in partial_blur_report
    assert "generated locally" in partial_blur_report


def test_report_is_deterministic(tmp_path: Path) -> None:
    """Confirm two runs over the same media produce identical documents."""

    documents_list: list[str] = []
    for run_name_str in ("first", "second"):
        result_obj = verify_video(
            REFERENCE_VIDEO_PATH,
            PARTIAL_BLUR_VIDEO_PATH,
            output_dir=tmp_path / run_name_str,
            save_annotated_video=False,
        )
        documents_list.append(
            result_obj.evidence_paths["html_report"]
            .read_text(encoding="utf-8")
            .replace(run_name_str, "RUN")
        )

    assert documents_list[0] == documents_list[1]


def test_report_can_be_disabled(tmp_path: Path) -> None:
    """Confirm the HTML report is optional for pipelines that skip it."""

    result_obj = verify_video(
        REFERENCE_VIDEO_PATH,
        PARTIAL_BLUR_VIDEO_PATH,
        output_dir=tmp_path / "no_html",
        save_annotated_video=False,
        save_html_report=False,
    )

    assert "html_report" not in result_obj.evidence_paths
    assert not (tmp_path / "no_html" / "index.html").exists()


def test_summary_json_lists_the_html_report(tmp_path: Path) -> None:
    """Confirm machine consumers can discover the human report.

    ``summary.json`` is the documented entry point, so it has to name
    every file written beside it.
    """

    result_obj = verify_video(
        REFERENCE_VIDEO_PATH,
        PARTIAL_BLUR_VIDEO_PATH,
        output_dir=tmp_path / "discoverable",
        save_annotated_video=False,
    )
    summary_dict = result_obj.to_dict()

    assert "html_report" in summary_dict["evidence_paths"]  # type: ignore[operator]
    assert "frame_report" in summary_dict["evidence_paths"]  # type: ignore[operator]


def test_passing_report_omits_the_unprotected_section() -> None:
    """Confirm a clean pass renders no failure evidence at all."""

    document_text = render_html_report(
        _passing_result(),
        [],
        [],
    )

    assert "Unprotected frames" not in document_text
    assert "PASS" in document_text


def test_thumbnail_dataclass_is_immutable() -> None:
    """Confirm captured evidence cannot be mutated after capture."""

    thumbnail_obj = FrameThumbnail(1, b"\xff\xd8ref", b"\xff\xd8cand")

    with pytest.raises(AttributeError):
        thumbnail_obj.frame_number = 2  # type: ignore[misc]


def _passing_result() -> object:
    """Return a minimal passing result for rendering tests."""

    from visual_verifier import VerificationResult, VerificationStatus

    return VerificationResult(
        status=VerificationStatus.PASS,
        reference_path=Path("reference.mp4"),
        candidate_path=Path("candidate.mp4"),
        policy_name="generic_change_every_frame",
    )
