"""Draw human-readable verification and temporal tracking evidence."""

from __future__ import annotations

import cv2

from visual_verifier.models import RegionMeasurement, VerificationStatus
from visual_verifier.targets.models import TargetCoverage, TargetSource
from visual_verifier.tracking.models import (
    TrackLifecycleState,
    TrackObservation,
)
from visual_verifier.type_aliases import ImageArray

REGION_COLOR_BGR = (0, 255, 0)
COVERED_TARGET_COLOR_BGR = (255, 200, 0)
UNCOVERED_TARGET_COLOR_BGR = (0, 0, 255)
TARGET_BORDER_THICKNESS_INT = 2
TARGET_LABEL_OFFSET_Y_INT = 6
INTERPOLATED_MARK_TEXT = "~"
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
    tracking_observations: tuple[TrackObservation, ...] = (),
    target_coverages: tuple[TargetCoverage, ...] = (),
) -> ImageArray:
    """Return a frame annotated with verification and tracking evidence.

    Args:
        frame: Candidate image or video frame to annotate.
        frame_number: One-based frame number shown in the header.
        total_frames: Total number of frames shown in the header.
        regions: Accepted regions to draw on the frame.
        status: Verification outcome shown in the header.
        tracking_observations: Optional track identity for each region.
        target_coverages: Optional reviewed targets, drawn so a reviewer
            can see at a glance which required region was missed.

    Returns:
        Independent annotated copy of the supplied frame.
    """

    annotated_frame_ndarray = frame.copy()
    observation_lookup_dict = {
        observation_obj.detection_index: observation_obj
        for observation_obj in tracking_observations
    }
    _draw_region_annotations(
        annotated_frame_ndarray,
        regions,
        observation_lookup_dict,
    )
    _draw_target_annotations(annotated_frame_ndarray, target_coverages)
    _draw_header(
        annotated_frame_ndarray,
        frame_number,
        total_frames,
        len(regions),
        status,
    )
    return annotated_frame_ndarray


def _draw_target_annotations(
    annotated_frame_ndarray: ImageArray,
    target_coverages_tuple: tuple[TargetCoverage, ...],
) -> None:
    """Draw every reviewed target box and its coverage verdict.

    Args:
        annotated_frame_ndarray: Frame modified in place.
        target_coverages_tuple: Measured coverage for this frame.
    """

    for coverage_obj in target_coverages_tuple:
        color_bgr = (
            COVERED_TARGET_COLOR_BGR
            if coverage_obj.covered
            else UNCOVERED_TARGET_COLOR_BGR
        )
        box_obj = coverage_obj.target.box
        cv2.rectangle(
            annotated_frame_ndarray,
            (box_obj.x1, box_obj.y1),
            (box_obj.x2, box_obj.y2),
            color_bgr,
            TARGET_BORDER_THICKNESS_INT,
        )
        _draw_target_label(annotated_frame_ndarray, coverage_obj, color_bgr)


def _draw_target_label(
    annotated_frame_ndarray: ImageArray,
    coverage_obj: TargetCoverage,
    color_bgr: tuple[int, int, int],
) -> None:
    """Draw one target's identifier and measured coverage.

    An interpolated box is marked, because a reviewer must be able to
    tell which boxes a human actually drew.

    Args:
        annotated_frame_ndarray: Frame modified in place.
        coverage_obj: Coverage measurement being labelled.
        color_bgr: Colour matching the coverage verdict.
    """

    target_obj = coverage_obj.target
    provenance_text = (
        INTERPOLATED_MARK_TEXT
        if target_obj.source is TargetSource.INTERPOLATED
        else ""
    )
    label_text = (
        f"{provenance_text}{target_obj.target_id} "
        f"{coverage_obj.covered_ratio:.0%}"
    )
    cv2.putText(
        annotated_frame_ndarray,
        label_text,
        (
            target_obj.box.x1,
            max(
                REGION_TEXT_MINIMUM_Y_INT,
                target_obj.box.y2 + TARGET_LABEL_OFFSET_Y_INT + 12,
            ),
        ),
        TEXT_FONT_INT,
        REGION_TEXT_SCALE_FLOAT,
        color_bgr,
        REGION_TEXT_THICKNESS_INT,
        TEXT_LINE_TYPE_INT,
    )


def _draw_region_annotations(
    annotated_frame_ndarray: ImageArray,
    regions_tuple: tuple[RegionMeasurement, ...],
    observation_lookup_dict: dict[int, TrackObservation],
) -> None:
    """Draw every accepted region and optional track label in place."""

    for detection_index_int, region_obj in enumerate(regions_tuple):
        _draw_region(
            annotated_frame_ndarray,
            detection_index_int,
            region_obj,
            observation_lookup_dict.get(detection_index_int),
        )


def _draw_region(
    annotated_frame_ndarray: ImageArray,
    detection_index_int: int,
    region_obj: RegionMeasurement,
    observation_obj: TrackObservation | None,
) -> None:
    """Draw one region boundary and evidence label in place."""

    bounding_box_obj = region_obj.box
    cv2.rectangle(
        annotated_frame_ndarray,
        (bounding_box_obj.x1, bounding_box_obj.y1),
        (bounding_box_obj.x2, bounding_box_obj.y2),
        REGION_COLOR_BGR,
        REGION_BORDER_THICKNESS_INT,
    )
    _draw_region_label(
        annotated_frame_ndarray,
        detection_index_int,
        region_obj,
        observation_obj,
    )


def _draw_region_label(
    annotated_frame_ndarray: ImageArray,
    detection_index_int: int,
    region_obj: RegionMeasurement,
    observation_obj: TrackObservation | None,
) -> None:
    """Draw one compact region or track label above its box."""

    label_text_str = _build_region_label(
        detection_index_int,
        region_obj,
        observation_obj,
    )
    cv2.putText(
        annotated_frame_ndarray,
        label_text_str,
        _calculate_region_label_origin(region_obj),
        TEXT_FONT_INT,
        REGION_TEXT_SCALE_FLOAT,
        REGION_COLOR_BGR,
        REGION_TEXT_THICKNESS_INT,
        TEXT_LINE_TYPE_INT,
    )


def _build_region_label(
    detection_index_int: int,
    region_obj: RegionMeasurement,
    observation_obj: TrackObservation | None,
) -> str:
    """Build a track-aware label while preserving image-only fallback."""

    severity_text_str = (
        f"{region_obj.severity_label} | {region_obj.severity_score:.1f}"
    )
    if observation_obj is None:
        return f"R{detection_index_int + 1} | {severity_text_str}"

    track_label_str = observation_obj.track_label
    if observation_obj.lifecycle_state == TrackLifecycleState.TENTATIVE:
        track_label_str = f"{track_label_str}?"
    return f"{track_label_str} | {severity_text_str}"


def _calculate_region_label_origin(
    region_obj: RegionMeasurement,
) -> tuple[int, int]:
    """Calculate the top-left text origin for a region label."""

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
    """Draw frame-level verification evidence in place."""

    header_text_str = _build_header_text(
        frame_number_int,
        total_frames_int,
        region_count_int,
        status_enum,
    )
    cv2.putText(
        annotated_frame_ndarray,
        header_text_str,
        HEADER_TEXT_ORIGIN,
        TEXT_FONT_INT,
        HEADER_TEXT_SCALE_FLOAT,
        _select_header_color(status_enum),
        HEADER_TEXT_THICKNESS_INT,
        TEXT_LINE_TYPE_INT,
    )


def _build_header_text(
    frame_number_int: int,
    total_frames_int: int,
    region_count_int: int,
    status_enum: VerificationStatus,
) -> str:
    """Build the frame-level annotation header."""

    return (
        f"Frame {frame_number_int}/{total_frames_int} | "
        f"Regions: {region_count_int} | {status_enum.value}"
    )


def _select_header_color(
    status_enum: VerificationStatus,
) -> tuple[int, int, int]:
    """Select the BGR header color for a verification outcome."""

    if status_enum == VerificationStatus.PASS:
        return PASS_HEADER_COLOR_BGR
    return FAILURE_HEADER_COLOR_BGR


__all__ = ["annotate_frame"]
