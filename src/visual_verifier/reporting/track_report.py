"""Build and write temporal tracking evidence reports."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from visual_verifier.reporting.csv_report import write_csv_report
from visual_verifier.tracking.models import (
    TrackEvent,
    TrackObservation,
    TrackSummary,
)
from visual_verifier.type_aliases import PathInput, ReportRow

TRACK_REPORT_FILENAME_STR = "track_report.csv"
TRACK_OBSERVATION_REPORT_FILENAME_STR = "track_observation_report.csv"
TRACK_EVENT_REPORT_FILENAME_STR = "track_event_report.csv"

TRACK_REPORT_COLUMNS_TUPLE = (
    "track_id",
    "track_label",
    "final_state",
    "first_frame",
    "last_frame",
    "observation_count",
    "confirmed",
    "active_span_frames",
    "missing_frames",
    "gap_count",
    "longest_gap_frames",
    "continuity_ratio",
    "fragmentation_index",
    "mean_association_iou",
    "minimum_association_iou",
    "mean_severity_score",
    "maximum_severity_score",
    "mean_changed_ratio",
    "mean_area_px",
    "center_jitter_px",
    "area_stability_ratio",
    "recovery_count",
    "split_event_count",
    "merge_event_count",
)
TRACK_OBSERVATION_COLUMNS_TUPLE = (
    "track_id",
    "track_label",
    "frame_number",
    "timestamp_seconds",
    "detection_index",
    "lifecycle_state",
    "association_iou",
    "x1",
    "y1",
    "x2",
    "y2",
    "width",
    "height",
    "area_px",
    "changed_pixels",
    "changed_ratio",
    "mean_diff",
    "max_diff",
    "severity_score",
    "severity_label",
)
TRACK_EVENT_COLUMNS_TUPLE = (
    "event_id",
    "event_label",
    "event_type",
    "frame_number",
    "primary_track_id",
    "primary_track_label",
    "related_track_ids",
    "related_track_labels",
    "gap_frames",
    "description",
)


def write_tracking_reports(
    summaries: Sequence[TrackSummary],
    observations: Sequence[TrackObservation],
    events: Sequence[TrackEvent],
    output_directory: PathInput,
) -> dict[str, Path]:
    """Write all temporal tracking CSV reports.

    Args:
        summaries: Completed per-track temporal integrity summaries.
        observations: Frame-level region-to-track observations.
        events: Lifecycle and lineage events.
        output_directory: Destination directory for tracking reports.

    Returns:
        Named filesystem paths for all generated tracking reports.
    """

    output_path_obj = Path(output_directory).expanduser().resolve()
    return {
        "track_report": write_csv_report(
            build_track_rows(summaries),
            output_path_obj / TRACK_REPORT_FILENAME_STR,
            column_names=TRACK_REPORT_COLUMNS_TUPLE,
        ),
        "track_observation_report": write_csv_report(
            build_observation_rows(observations),
            output_path_obj / TRACK_OBSERVATION_REPORT_FILENAME_STR,
            column_names=TRACK_OBSERVATION_COLUMNS_TUPLE,
        ),
        "track_event_report": write_csv_report(
            build_event_rows(events),
            output_path_obj / TRACK_EVENT_REPORT_FILENAME_STR,
            column_names=TRACK_EVENT_COLUMNS_TUPLE,
        ),
    }


def build_track_rows(
    summaries: Sequence[TrackSummary],
) -> list[ReportRow]:
    """Return ordered CSV rows for completed track summaries."""

    rows_list: list[ReportRow] = []
    for summary_obj in summaries:
        row_dict = summary_obj.to_dict()
        row_dict["missing_frames"] = "|".join(
            str(frame_number_int)
            for frame_number_int in summary_obj.missing_frames
        )
        rows_list.append(row_dict)
    return rows_list


def build_observation_rows(
    observations: Sequence[TrackObservation],
) -> list[ReportRow]:
    """Return ordered CSV rows for track observations."""

    return [
        _build_observation_row(observation_obj)
        for observation_obj in observations
    ]


def build_event_rows(events: Sequence[TrackEvent]) -> list[ReportRow]:
    """Return ordered CSV rows for lifecycle and lineage events."""

    return [
        {
            "event_id": event_obj.event_id,
            "event_label": event_obj.event_label,
            "event_type": event_obj.event_type.value,
            "frame_number": event_obj.frame_number,
            "primary_track_id": event_obj.primary_track_id,
            "primary_track_label": event_obj.primary_track_label,
            "related_track_ids": "|".join(
                str(track_id_int)
                for track_id_int in event_obj.related_track_ids
            ),
            "related_track_labels": "|".join(event_obj.related_track_labels),
            "gap_frames": event_obj.gap_frames,
            "description": event_obj.description,
        }
        for event_obj in events
    ]


def _build_observation_row(
    observation_obj: TrackObservation,
) -> ReportRow:
    """Flatten one track observation into a stable tabular row."""

    box_obj = observation_obj.box
    region_obj = observation_obj.region
    return {
        "track_id": observation_obj.track_id,
        "track_label": observation_obj.track_label,
        "frame_number": observation_obj.frame_number,
        "timestamp_seconds": observation_obj.timestamp_seconds,
        "detection_index": observation_obj.detection_index,
        "lifecycle_state": observation_obj.lifecycle_state.value,
        "association_iou": observation_obj.association_iou,
        "x1": box_obj.x1,
        "y1": box_obj.y1,
        "x2": box_obj.x2,
        "y2": box_obj.y2,
        "width": box_obj.width,
        "height": box_obj.height,
        "area_px": box_obj.area,
        "changed_pixels": region_obj.changed_pixels,
        "changed_ratio": region_obj.changed_ratio,
        "mean_diff": region_obj.mean_diff,
        "max_diff": region_obj.max_diff,
        "severity_score": region_obj.severity_score,
        "severity_label": region_obj.severity_label,
    }


__all__ = [
    "TRACK_EVENT_REPORT_FILENAME_STR",
    "TRACK_OBSERVATION_REPORT_FILENAME_STR",
    "TRACK_REPORT_FILENAME_STR",
    "build_event_rows",
    "build_observation_rows",
    "build_track_rows",
    "write_tracking_reports",
]
