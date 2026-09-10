"""Read normalized metadata from image and video files."""

from __future__ import annotations

from pathlib import Path

import cv2

from visual_verifier.exceptions import MediaReadError
from visual_verifier.models import MediaMetadata
from visual_verifier.type_aliases import PathInput, VideoCapture

IMAGE_MEDIA_TYPE_STR = "image"
VIDEO_MEDIA_TYPE_STR = "video"
UNKNOWN_DURATION_SECONDS_FLOAT = 0.0
UNKNOWN_FRAME_RATE_FLOAT = 0.0


def read_video_metadata(path: PathInput) -> MediaMetadata:
    """Read video dimensions and timing metadata without full decoding.

    Args:
        path: Filesystem path to the video file.

    Returns:
        Normalized metadata describing the video.

    Raises:
        MediaReadError: If the path is invalid, the video cannot be opened,
            or the decoder reports invalid frame dimensions.
    """

    media_path_obj = _resolve_media_path(path, VIDEO_MEDIA_TYPE_STR)
    video_capture_obj = cv2.VideoCapture(str(media_path_obj))

    try:
        _validate_video_capture(video_capture_obj, media_path_obj)
        return _build_video_metadata(
            media_path_obj,
            video_capture_obj,
        )
    finally:
        video_capture_obj.release()


def read_image_metadata(path: PathInput) -> MediaMetadata:
    """Read image dimensions from one decodable file.

    Args:
        path: Filesystem path to the image file.

    Returns:
        Normalized metadata describing the image.

    Raises:
        MediaReadError: If the path is invalid or the image cannot be
            decoded.
    """

    media_path_obj = _resolve_media_path(path, IMAGE_MEDIA_TYPE_STR)
    image_ndarray = cv2.imread(
        str(media_path_obj),
        cv2.IMREAD_UNCHANGED,
    )

    if image_ndarray is None:
        raise _create_media_read_error(
            "Could not decode image.",
            media_path_obj,
            IMAGE_MEDIA_TYPE_STR,
        )

    image_height_int, image_width_int = image_ndarray.shape[:2]
    _validate_dimensions(
        image_width_int,
        image_height_int,
        media_path_obj,
        IMAGE_MEDIA_TYPE_STR,
    )

    return MediaMetadata(
        path=media_path_obj,
        media_type=IMAGE_MEDIA_TYPE_STR,
        width=image_width_int,
        height=image_height_int,
    )


def _resolve_media_path(
    path: PathInput,
    media_type_str: str,
) -> Path:
    """Resolve and validate one media path.

    Args:
        path: User-provided filesystem path.
        media_type_str: Media category used in diagnostics.

    Returns:
        Absolute, normalized path to an existing regular file.

    Raises:
        MediaReadError: If the path does not identify a regular file.
    """

    media_path_obj = Path(path).expanduser().resolve()
    if media_path_obj.is_file():
        return media_path_obj

    raise _create_media_read_error(
        "Media file does not exist.",
        media_path_obj,
        media_type_str,
    )


def _validate_video_capture(
    video_capture_obj: VideoCapture,
    media_path_obj: Path,
) -> None:
    """Validate that OpenCV opened a video stream.

    Args:
        video_capture_obj: OpenCV video-capture instance.
        media_path_obj: Resolved video path used in diagnostics.

    Raises:
        MediaReadError: If the capture could not be opened.
    """

    if video_capture_obj.isOpened():
        return

    raise _create_media_read_error(
        "Could not open video.",
        media_path_obj,
        VIDEO_MEDIA_TYPE_STR,
    )


def _build_video_metadata(
    media_path_obj: Path,
    video_capture_obj: VideoCapture,
) -> MediaMetadata:
    """Build metadata from an open video capture.

    Args:
        media_path_obj: Resolved video path.
        video_capture_obj: Open OpenCV video-capture instance.

    Returns:
        Normalized video metadata.

    Raises:
        MediaReadError: If frame dimensions are invalid.
    """
    frame_rate_float = _read_capture_float(
        video_capture_obj,
        cv2.CAP_PROP_FPS,
    )
    frame_count_int = _read_capture_int(
        video_capture_obj,
        cv2.CAP_PROP_FRAME_COUNT,
    )
    frame_width_int = _read_capture_int(
        video_capture_obj,
        cv2.CAP_PROP_FRAME_WIDTH,
    )
    frame_height_int = _read_capture_int(
        video_capture_obj,
        cv2.CAP_PROP_FRAME_HEIGHT,
    )
    _validate_dimensions(
        frame_width_int,
        frame_height_int,
        media_path_obj,
        VIDEO_MEDIA_TYPE_STR,
    )
    return MediaMetadata(
        path=media_path_obj,
        media_type=VIDEO_MEDIA_TYPE_STR,
        width=frame_width_int,
        height=frame_height_int,
        frame_count=max(0, frame_count_int),
        fps=max(UNKNOWN_FRAME_RATE_FLOAT, frame_rate_float),
        duration_seconds=_calculate_duration(
            frame_count_int,
            frame_rate_float,
        ),
    )


def _read_capture_float(
    video_capture_obj: VideoCapture,
    property_identifier_int: int,
) -> float:
    """Read one floating-point OpenCV capture property.

    Args:
        video_capture_obj: Open OpenCV video-capture instance.
        property_identifier_int: OpenCV capture-property identifier.

    Returns:
        Property value converted to ``float``.
    """

    return float(video_capture_obj.get(property_identifier_int))


def _read_capture_int(
    video_capture_obj: VideoCapture,
    property_identifier_int: int,
) -> int:
    """Read one integer-valued OpenCV capture property.

    Args:
        video_capture_obj: Open OpenCV video-capture instance.
        property_identifier_int: OpenCV capture-property identifier.

    Returns:
        Property value converted to ``int``.
    """

    return int(video_capture_obj.get(property_identifier_int))


def _calculate_duration(
    frame_count_int: int,
    frame_rate_float: float,
) -> float:
    """Calculate duration from frame count and frame rate.

    Args:
        frame_count_int: Number of frames reported by the decoder.
        frame_rate_float: Frames per second reported by the decoder.

    Returns:
        Duration in seconds, or zero when timing data is unavailable.
    """

    if frame_count_int <= 0 or frame_rate_float <= 0.0:
        return UNKNOWN_DURATION_SECONDS_FLOAT

    return frame_count_int / frame_rate_float


def _validate_dimensions(
    width_int: int,
    height_int: int,
    media_path_obj: Path,
    media_type_str: str,
) -> None:
    """Validate positive media dimensions.

    Args:
        width_int: Media width in pixels.
        height_int: Media height in pixels.
        media_path_obj: Resolved media path used in diagnostics.
        media_type_str: Media category used in diagnostics.

    Raises:
        MediaReadError: If either dimension is non-positive.
    """

    if width_int > 0 and height_int > 0:
        return

    raise MediaReadError(
        "Decoder reported invalid media dimensions.",
        context_mapping={
            "path": str(media_path_obj),
            "media_type": media_type_str,
            "width": width_int,
            "height": height_int,
        },
    )


def _create_media_read_error(
    message_str: str,
    media_path_obj: Path,
    media_type_str: str,
) -> MediaReadError:
    """Create a media-read error with consistent context.

    Args:
        message_str: Human-readable failure explanation.
        media_path_obj: Resolved media path.
        media_type_str: Media category associated with the path.

    Returns:
        Structured media-read exception.
    """

    return MediaReadError(
        message_str,
        context_mapping={
            "path": str(media_path_obj),
            "media_type": media_type_str,
        },
    )


__all__ = [
    "read_image_metadata",
    "read_video_metadata",
]
