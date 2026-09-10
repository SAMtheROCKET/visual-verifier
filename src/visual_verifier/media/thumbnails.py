"""Encode small frame thumbnails for embedding in evidence reports.

Thumbnails are embedded directly into the HTML report so a reviewer can
forward a single self-contained file. That makes size a correctness
concern: only failing frames are captured, and each one is downscaled and
JPEG-compressed before it reaches the document.
"""

from __future__ import annotations

from typing import cast

import cv2

from visual_verifier.exceptions import ReportWriteError
from visual_verifier.type_aliases import ImageArray

THUMBNAIL_MAX_WIDTH_INT = 480
THUMBNAIL_JPEG_QUALITY_INT = 78
JPEG_SUFFIX_TEXT = ".jpg"


def encode_frame_thumbnail(
    frame_ndarray: ImageArray,
    max_width_int: int = THUMBNAIL_MAX_WIDTH_INT,
) -> bytes:
    """Downscale one frame and encode it as JPEG bytes.

    Args:
        frame_ndarray: Full-resolution source frame.
        max_width_int: Width above which the frame is downscaled. Frames
            narrower than this are encoded at their original size.

    Returns:
        JPEG-encoded thumbnail bytes.

    Raises:
        ReportWriteError: When OpenCV cannot encode the frame.
    """

    scaled_frame_ndarray = _downscale_to_width(frame_ndarray, max_width_int)
    encoded_bool, encoded_buffer = cv2.imencode(
        JPEG_SUFFIX_TEXT,
        scaled_frame_ndarray,
        [int(cv2.IMWRITE_JPEG_QUALITY), THUMBNAIL_JPEG_QUALITY_INT],
    )
    if not encoded_bool:
        raise ReportWriteError(
            "Could not encode an evidence thumbnail.",
            context_mapping={
                "width": int(scaled_frame_ndarray.shape[1]),
                "height": int(scaled_frame_ndarray.shape[0]),
            },
        )
    return bytes(encoded_buffer.tobytes())


def _downscale_to_width(
    frame_ndarray: ImageArray,
    max_width_int: int,
) -> ImageArray:
    """Return the frame scaled down to at most one width.

    Args:
        frame_ndarray: Full-resolution source frame.
        max_width_int: Maximum permitted output width in pixels.

    Returns:
        The original frame, or a proportionally downscaled copy.
    """

    source_height_int, source_width_int = frame_ndarray.shape[:2]
    if source_width_int <= max_width_int or max_width_int <= 0:
        return frame_ndarray
    target_height_int = max(
        1,
        round(source_height_int * max_width_int / source_width_int),
    )
    scaled_frame_ndarray = cv2.resize(
        frame_ndarray,
        (max_width_int, target_height_int),
        interpolation=cv2.INTER_AREA,
    )
    return cast("ImageArray", scaled_frame_ndarray)


__all__ = [
    "THUMBNAIL_MAX_WIDTH_INT",
    "encode_frame_thumbnail",
]
