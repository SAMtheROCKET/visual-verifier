"""Read synchronized frame pairs from reference and candidate videos."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from visual_verifier.exceptions import MediaReadError
from visual_verifier.type_aliases import (
    ImageArray,
    PathInput,
    VideoFramePair,
)

REFERENCE_ROLE_STR = "reference"
CANDIDATE_ROLE_STR = "candidate"
FIRST_FRAME_NUMBER_INT = 1


class VideoPairReader(Iterator[VideoFramePair]):
    """Read synchronized reference and candidate frames by index.

    The reader owns both OpenCV capture objects and releases them when the
    stream ends or when the context manager exits.

    Args:
        reference_path: Filesystem path to the reference video.
        candidate_path: Filesystem path to the processed candidate video.

    Raises:
        MediaReadError: If either path is invalid or cannot be opened.

    Warning:
        The iterator stops when either video reaches its end. It does not
        duplicate, interpolate, or otherwise synthesize missing frames.
    """

    def __init__(
        self,
        reference_path: PathInput,
        candidate_path: PathInput,
    ) -> None:
        """Store validated paths and initialize the reader state.

        Args:
            reference_path: Filesystem path to the reference video.
            candidate_path: Filesystem path to the candidate video.

        Raises:
            MediaReadError: If either path is not an existing file.
        """

        self._reference_path_obj = _resolve_video_path(
            reference_path,
            REFERENCE_ROLE_STR,
        )
        self._candidate_path_obj = _resolve_video_path(
            candidate_path,
            CANDIDATE_ROLE_STR,
        )
        self._reference_capture_obj: Any | None = None
        self._candidate_capture_obj: Any | None = None
        self._next_frame_number_int = FIRST_FRAME_NUMBER_INT
        self._closed_bool = False

    def __enter__(self) -> VideoPairReader:
        """Open both video streams and return this reader.

        Returns:
            Open synchronized video-pair reader.

        Raises:
            MediaReadError: If either video cannot be opened.
        """

        if self._reference_capture_obj is not None:
            return self

        self._reference_capture_obj = _open_video_capture(
            self._reference_path_obj,
            REFERENCE_ROLE_STR,
        )
        try:
            self._candidate_capture_obj = _open_video_capture(
                self._candidate_path_obj,
                CANDIDATE_ROLE_STR,
            )
        except MediaReadError:
            self.close()
            raise

        return self

    def __exit__(
        self,
        exception_type_obj: object,
        exception_value_obj: object,
        traceback_obj: object,
    ) -> None:
        """Release both video streams when leaving the context.

        Args:
            exception_type_obj: Active exception type, when present.
            exception_value_obj: Active exception value, when present.
            traceback_obj: Active traceback, when present.
        """

        del exception_type_obj
        del exception_value_obj
        del traceback_obj
        self.close()

    def __iter__(self) -> VideoPairReader:
        """Return this reader as its own iterator.

        Returns:
            Current synchronized video-pair reader.
        """

        return self

    def __next__(self) -> VideoFramePair:
        """Read the next synchronized frame pair.

        Returns:
            One-based frame number and both decoded frames.

        Raises:
            MediaReadError: If iteration begins before the reader is opened.
            StopIteration: When either video reaches its end.
        """

        reference_capture_obj = self._require_open_capture(
            self._reference_capture_obj,
            REFERENCE_ROLE_STR,
        )
        candidate_capture_obj = self._require_open_capture(
            self._candidate_capture_obj,
            CANDIDATE_ROLE_STR,
        )
        reference_frame_ndarray = _read_frame(reference_capture_obj)
        candidate_frame_ndarray = _read_frame(candidate_capture_obj)

        if reference_frame_ndarray is None or candidate_frame_ndarray is None:
            self.close()
            raise StopIteration

        frame_number_int = self._next_frame_number_int
        self._next_frame_number_int += 1
        return (
            frame_number_int,
            reference_frame_ndarray,
            candidate_frame_ndarray,
        )

    def close(self) -> None:
        """Release both captures exactly once."""

        if self._closed_bool:
            return

        _release_capture(self._reference_capture_obj)
        _release_capture(self._candidate_capture_obj)
        self._reference_capture_obj = None
        self._candidate_capture_obj = None
        self._closed_bool = True

    def _require_open_capture(
        self,
        video_capture_obj: Any | None,
        video_role_str: str,
    ) -> Any:
        """Return one open capture or raise a lifecycle error.

        Args:
            video_capture_obj: Capture instance to validate.
            video_role_str: Reference or candidate diagnostic role.

        Returns:
            Open OpenCV capture instance.

        Raises:
            MediaReadError: If the reader is not open.
        """

        if video_capture_obj is not None and not self._closed_bool:
            return video_capture_obj

        raise MediaReadError(
            "Video-pair reader is not open.",
            context_mapping={"video_role": video_role_str},
        )


def iter_video_pairs(
    reference_path: PathInput,
    candidate_path: PathInput,
) -> Iterator[VideoFramePair]:
    """Yield synchronized frame pairs using one-based frame numbers.

    Args:
        reference_path: Filesystem path to the reference video.
        candidate_path: Filesystem path to the processed candidate video.

    Yields:
        One-based frame number, reference frame, and candidate frame.

    Raises:
        MediaReadError: If either video is invalid or cannot be opened.

    Warning:
        Iteration stops when the shorter video reaches its end.
    """

    with VideoPairReader(reference_path, candidate_path) as reader_obj:
        yield from reader_obj


def _resolve_video_path(
    path: PathInput,
    video_role_str: str,
) -> Path:
    """Resolve and validate one video path.

    Args:
        path: User-provided video path.
        video_role_str: Reference or candidate diagnostic role.

    Returns:
        Absolute path to an existing regular file.

    Raises:
        MediaReadError: If the path is not an existing file.
    """

    video_path_obj = Path(path).expanduser().resolve()
    if video_path_obj.is_file():
        return video_path_obj

    raise MediaReadError(
        "Video file does not exist.",
        context_mapping={
            "video_path": str(video_path_obj),
            "video_role": video_role_str,
        },
    )


def _open_video_capture(
    video_path_obj: Path,
    video_role_str: str,
) -> Any:
    """Open one OpenCV video capture.

    Args:
        video_path_obj: Resolved path to the video.
        video_role_str: Reference or candidate diagnostic role.

    Returns:
        Open OpenCV capture instance.

    Raises:
        MediaReadError: If OpenCV cannot open the stream.
    """

    video_capture_obj = cv2.VideoCapture(str(video_path_obj))
    if video_capture_obj.isOpened():
        return video_capture_obj

    video_capture_obj.release()
    raise MediaReadError(
        "Could not open video.",
        context_mapping={
            "video_path": str(video_path_obj),
            "video_role": video_role_str,
        },
    )


def _read_frame(video_capture_obj: Any) -> ImageArray | None:
    """Decode and normalize the next frame from one capture.

    Args:
        video_capture_obj: Open OpenCV capture instance.

    Returns:
        Contiguous unsigned 8-bit frame, or ``None`` at end of stream.
    """

    frame_read_bool, frame_ndarray = video_capture_obj.read()
    if not frame_read_bool or frame_ndarray is None:
        return None

    normalized_frame_ndarray: ImageArray = np.asarray(
        frame_ndarray,
        dtype=np.uint8,
    )
    return np.ascontiguousarray(normalized_frame_ndarray)


def _release_capture(video_capture_obj: Any | None) -> None:
    """Release an optional OpenCV capture.

    Args:
        video_capture_obj: Capture instance to release, when present.
    """

    if video_capture_obj is not None:
        video_capture_obj.release()


__all__ = ["VideoPairReader", "iter_video_pairs"]
