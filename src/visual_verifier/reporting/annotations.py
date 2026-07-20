"""Draw human-readable verification evidence on image and video frames."""

from __future__ import annotations

import cv2

from visual_verifier.models import RegionMeasurement, VerificationStatus
from visual_verifier.type_aliases import ImageArray

REGION_COLOR_BGR = (0, 255, 0)
PASS_HEADER_COLOR_BGR = (0, 255, 255)
FAILURE_HEADER_COLOR_BGR = (0, 0, 255)
REGION_BORDER_THICKNESS_INT = 2
REGION_TEXT_SCALE_FLOAT = 0.5
REGION_TEXT_THICKNESS_INT = 2
REGION_TEXT_MINIMUM_Y_INT = 20
REGION_TEXT_OFFSET_Y_INT = 8
HEADER_TEXT_ORIGIN = (20, 35)
HEADER_TEXT_SCALE_FLOAT = 0.7
HEADER_TEXT_THICKNESS_INT = 2
TEXT_FONT_INT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_LINE_TYPE_INT = cv2.LINE_AA


def annotate_frame(
    frame: ImageArray,
    *,
    frame_number: int,
    total_frames: int,
    regions: tuple[RegionMeasurement, ...],
    status: VerificationStatus,
) -> ImageArray:
    """Return a frame annotated with region and verification evidence.

    Args:
        frame: Candidate image or video frame to annotate.
        frame_number: One-based frame number shown in the header.
        total_frames: Total number of frames shown in the header.
        regions: Accepted regions to draw on the frame.
        status: Verification outcome shown in the header.

    Returns:
        Independent annotated copy of the supplied frame.
    """

    annotated_frame_ndarray = frame.copy()
    _draw_region_annotations(annotated_frame_ndarray, regions)
    _draw_header(
        annotated_frame_ndarray,
        frame_number,
        total_frames,
        len(regions),
        status,
    )
    return annotated_frame_ndarray


def _draw_region_annotations(
    annotated_frame_ndarray: ImageArray,
    regions_tuple: tuple[RegionMeasurement, ...],
) -> None:
    """Draw every accepted region and its severity label in place.

    Args:
        annotated_frame_ndarray: Writable frame receiving annotations.
        regions_tuple: Ordered region measurements to draw.

    Returns:
        None. The supplied frame is modified in place.
    """

    for region_index_int, region_obj in enumerate(
        regions_tuple,
        start=1,
    ):
        _draw_region(
            annotated_frame_ndarray,
            region_index_int,
            region_obj,
        )


def _draw_region(
    annotated_frame_ndarray: ImageArray,
    region_index_int: int,
    region_obj: RegionMeasurement,
) -> None:
    """Draw one region boundary and severity label in place.

    Args:
        annotated_frame_ndarray: Writable frame receiving annotations.
        region_index_int: One-based display index for the region.
        region_obj: Region geometry and severity measurements.

    Returns:
        None. The supplied frame is modified in place.
    """

    bounding_box_obj = region_obj.box
    top_left_point_tuple = (
        bounding_box_obj.x1,
        bounding_box_obj.y1,
    )
    bottom_right_point_tuple = (
        bounding_box_obj.x2,
        bounding_box_obj.y2,
    )
    cv2.rectangle(
        annotated_frame_ndarray,
        top_left_point_tuple,
        bottom_right_point_tuple,
        REGION_COLOR_BGR,
        REGION_BORDER_THICKNESS_INT,
    )
    _draw_region_label(
        annotated_frame_ndarray,
        region_index_int,
        region_obj,
    )


def _draw_region_label(
    annotated_frame_ndarray: ImageArray,
    region_index_int: int,
    region_obj: RegionMeasurement,
) -> None:
    """Draw one region severity label above its bounding box.

    Args:
        annotated_frame_ndarray: Writable frame receiving annotations.
        region_index_int: One-based display index for the region.
        region_obj: Region geometry and severity measurements.

    Returns:
        None. The supplied frame is modified in place.
    """

    label_text_str = _build_region_label(region_index_int, region_obj)
    label_origin_tuple = _calculate_region_label_origin(region_obj)
    cv2.putText(
        annotated_frame_ndarray,
        label_text_str,
        label_origin_tuple,
        TEXT_FONT_INT,
        REGION_TEXT_SCALE_FLOAT,
        REGION_COLOR_BGR,
        REGION_TEXT_THICKNESS_INT,
        TEXT_LINE_TYPE_INT,
    )


def _build_region_label(
    region_index_int: int,
    region_obj: RegionMeasurement,
) -> str:
    """Build the compact label displayed for one region.

    Args:
        region_index_int: One-based display index for the region.
        region_obj: Region severity measurements.

    Returns:
        Region index, numerical severity, and severity category.
    """

    return (
        f"R{region_index_int} S:{region_obj.severity_score} "
        f"{region_obj.severity_label}"
    )


def _calculate_region_label_origin(
    region_obj: RegionMeasurement,
) -> tuple[int, int]:
    """Calculate the top-left text origin for a region label.

    Args:
        region_obj: Region whose box anchors the label.

    Returns:
        Pixel coordinates for OpenCV text drawing.
    """

    bounding_box_obj = region_obj.box
    label_y_int = max(
        REGION_TEXT_MINIMUM_Y_INT,
        bounding_box_obj.y1 - REGION_TEXT_OFFSET_Y_INT,
    )
    return bounding_box_obj.x1, label_y_int


def _draw_header(
    annotated_frame_ndarray: ImageArray,
    frame_number_int: int,
    total_frames_int: int,
    region_count_int: int,
    status_enum: VerificationStatus,
) -> None:
    """Draw frame-level verification evidence in place.

    Args:
        annotated_frame_ndarray: Writable frame receiving the header.
        frame_number_int: One-based frame number.
        total_frames_int: Total number of frames.
        region_count_int: Number of accepted regions drawn.
        status_enum: Frame or image verification outcome.

    Returns:
        None. The supplied frame is modified in place.
    """

    header_text_str = _build_header_text(
        frame_number_int,
        total_frames_int,
        region_count_int,
        status_enum,
    )
    header_color_tuple = _select_header_color(status_enum)
    cv2.putText(
        annotated_frame_ndarray,
        header_text_str,
        HEADER_TEXT_ORIGIN,
        TEXT_FONT_INT,
        HEADER_TEXT_SCALE_FLOAT,
        header_color_tuple,
        HEADER_TEXT_THICKNESS_INT,
        TEXT_LINE_TYPE_INT,
    )


def _build_header_text(
    frame_number_int: int,
    total_frames_int: int,
    region_count_int: int,
    status_enum: VerificationStatus,
) -> str:
    """Build the frame-level annotation header.

    Args:
        frame_number_int: One-based frame number.
        total_frames_int: Total number of frames.
        region_count_int: Number of accepted regions drawn.
        status_enum: Frame or image verification outcome.

    Returns:
        Formatted frame, region-count, and status text.
    """

    return (
        f"Frame {frame_number_int}/{total_frames_int} | "
        f"Regions: {region_count_int} | {status_enum.value}"
    )


def _select_header_color(
    status_enum: VerificationStatus,
) -> tuple[int, int, int]:
    """Select the BGR header color for a verification outcome.

    Args:
        status_enum: Frame or image verification outcome.

    Returns:
        Yellow for pass, otherwise red, preserving legacy behaviour.
    """

    if status_enum == VerificationStatus.PASS:
        return PASS_HEADER_COLOR_BGR
    return FAILURE_HEADER_COLOR_BGR


__all__ = ["annotate_frame"]
