"""Protect annotated-video codec selection across OpenCV builds.

Codec support is the only host-dependent capability in the package, so it
is tested directly rather than only through the video pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from visual_verifier.exceptions import ReportWriteError
from visual_verifier.media.video_writer import (
    VIDEO_CODEC_CANDIDATES_TUPLE,
    find_supported_codec,
    open_annotated_writer,
)

WRITER_RESOLUTION_TUPLE = (64, 48)
WRITER_FRAME_RATE_FLOAT = 10.0


def test_candidate_codecs_are_mp4_compatible() -> None:
    """Confirm every fallback codec is legal inside an MP4 container.

    A codec that opens but cannot be muxed into MP4 would produce
    unplayable evidence, which is worse than failing loudly.
    """

    assert VIDEO_CODEC_CANDIDATES_TUPLE
    assert VIDEO_CODEC_CANDIDATES_TUPLE[0] == "mp4v"
    for codec_text in VIDEO_CODEC_CANDIDATES_TUPLE:
        assert len(codec_text) == 4


def test_this_platform_supports_at_least_one_codec() -> None:
    """Confirm the host OpenCV build can write annotated evidence.

    This is the check that makes cross-platform CI meaningful. A runner
    without a working encoder fails here with a clear cause rather than
    somewhere inside a pipeline run.
    """

    supported_codec_str = find_supported_codec()

    assert supported_codec_str in VIDEO_CODEC_CANDIDATES_TUPLE


def test_codec_probe_leaves_no_files_behind(tmp_path: Path) -> None:
    """Confirm probing for codec support writes nothing durable."""

    find_supported_codec()

    assert not list(tmp_path.iterdir())


def test_writer_opens_for_a_valid_destination(tmp_path: Path) -> None:
    """Confirm a writer opens and releases cleanly for a real path."""

    annotated_path_obj = tmp_path / "annotated.mp4"
    video_writer_obj = open_annotated_writer(
        annotated_path_obj,
        WRITER_FRAME_RATE_FLOAT,
        WRITER_RESOLUTION_TUPLE,
    )

    try:
        assert video_writer_obj.isOpened()
    finally:
        video_writer_obj.release()

    assert annotated_path_obj.exists()


def test_unwritable_destination_raises_a_structured_error(
    tmp_path: Path,
) -> None:
    """Confirm an impossible destination reports every attempted codec."""

    unwritable_path_obj = tmp_path / "absent_directory" / "annotated.mp4"

    with pytest.raises(ReportWriteError) as error_info_obj:
        open_annotated_writer(
            unwritable_path_obj,
            WRITER_FRAME_RATE_FLOAT,
            WRITER_RESOLUTION_TUPLE,
        )

    context_dict = error_info_obj.value.context_dict

    assert error_info_obj.value.error_code == "REPORT_WRITE_ERROR"
    assert context_dict["attempted_codecs"] == list(
        VIDEO_CODEC_CANDIDATES_TUPLE
    )
    assert context_dict["output_path"] == str(unwritable_path_obj)
