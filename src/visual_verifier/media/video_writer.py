"""Open OpenCV writers for annotated video evidence.

Codec availability is the only part of Visual Verifier that depends on how
OpenCV was built on the host. This module isolates that dependency so the
pipeline can request a writer, the environment check can probe support
without producing evidence, and both agree on the candidate list.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2

from visual_verifier.exceptions import ReportWriteError

VIDEO_CODEC_CANDIDATES_TUPLE: tuple[str, ...] = ("mp4v", "avc1")
"""MP4-compatible codecs tried in order when opening annotated evidence."""

PROBE_FRAME_RATE_FLOAT = 10.0
PROBE_RESOLUTION_TUPLE = (64, 64)
PROBE_FILENAME_STR = "codec_probe.mp4"


def open_annotated_writer(
    annotated_path_obj: Path,
    frames_per_second_float: float,
    resolution_tuple: tuple[int, int],
) -> cv2.VideoWriter:
    """Open an annotated-video writer using the first supported codec.

    Args:
        annotated_path_obj: Destination path for annotated evidence.
        frames_per_second_float: Positive output frame rate.
        resolution_tuple: Output width and height in pixels.

    Returns:
        Open OpenCV writer bound to the destination path.

    Raises:
        ReportWriteError: When no candidate codec can be opened on this
            platform, or when the destination cannot be written.
    """

    for codec_text in VIDEO_CODEC_CANDIDATES_TUPLE:
        video_writer_obj = _try_open_writer(
            annotated_path_obj,
            codec_text,
            frames_per_second_float,
            resolution_tuple,
        )
        if video_writer_obj is not None:
            return video_writer_obj

    raise ReportWriteError(
        "No supported codec could open the annotated-video writer.",
        context_mapping={
            "output_path": str(annotated_path_obj),
            "attempted_codecs": list(VIDEO_CODEC_CANDIDATES_TUPLE),
            "fps": frames_per_second_float,
            "resolution": list(resolution_tuple),
        },
    )


def find_supported_codec() -> str | None:
    """Return the first annotated-video codec this platform can open.

    The probe writes nothing durable. It opens and immediately releases a
    writer inside a temporary directory that is removed afterwards.

    Returns:
        The first working codec name, or ``None`` when this OpenCV build
        cannot write annotated video at all.
    """

    with tempfile.TemporaryDirectory() as temporary_directory_str:
        probe_path_obj = Path(temporary_directory_str) / PROBE_FILENAME_STR
        for codec_text in VIDEO_CODEC_CANDIDATES_TUPLE:
            video_writer_obj = _try_open_writer(
                probe_path_obj,
                codec_text,
                PROBE_FRAME_RATE_FLOAT,
                PROBE_RESOLUTION_TUPLE,
            )
            if video_writer_obj is not None:
                video_writer_obj.release()
                return codec_text
    return None


def _try_open_writer(
    annotated_path_obj: Path,
    codec_text: str,
    frames_per_second_float: float,
    resolution_tuple: tuple[int, int],
) -> cv2.VideoWriter | None:
    """Try one codec and return an open writer when it succeeds.

    Args:
        annotated_path_obj: Destination path for the writer.
        codec_text: Four-character codec identifier, such as ``mp4v``.
        frames_per_second_float: Positive output frame rate.
        resolution_tuple: Output width and height in pixels.

    Returns:
        Open writer, or ``None`` when this codec is unavailable.
    """

    video_writer_obj = cv2.VideoWriter(
        str(annotated_path_obj),
        cv2.VideoWriter.fourcc(*codec_text),
        frames_per_second_float,
        resolution_tuple,
    )
    if video_writer_obj.isOpened():
        return video_writer_obj
    video_writer_obj.release()
    return None


__all__ = [
    "VIDEO_CODEC_CANDIDATES_TUPLE",
    "find_supported_codec",
    "open_annotated_writer",
]
