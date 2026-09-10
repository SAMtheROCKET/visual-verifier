"""Define typed domain models for temporal region tracking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from visual_verifier.models import BoundingBox, RegionMeasurement

TRACK_LABEL_PREFIX_STR = "T"
TRACK_LABEL_WIDTH_INT = 3
EVENT_LABEL_PREFIX_STR = "E"
EVENT_LABEL_WIDTH_INT = 4


class TrackLifecycleState(str, Enum):
    """Represent the lifecycle state of one temporal region track."""

    TENTATIVE = "TENTATIVE"
    CONFIRMED = "CONFIRMED"
    LOST = "LOST"
    CLOSED = "CLOSED"


class TrackEventType(str, Enum):
    """Represent one explainable temporal tracking event."""

    TRACK_CREATED = "TRACK_CREATED"
    TRACK_CONFIRMED = "TRACK_CONFIRMED"
    TRACK_LOST = "TRACK_LOST"
    TRACK_RECOVERED = "TRACK_RECOVERED"
    TRACK_CLOSED = "TRACK_CLOSED"
    TRACK_SPLIT = "TRACK_SPLIT"
    TRACK_MERGED = "TRACK_MERGED"


def format_track_label(track_id_int: int) -> str:
    """Return a stable human-readable label for one numeric track ID.

    Args:
        track_id_int: Positive numeric identifier allocated by the tracker.

    Returns:
        Zero-padded track label such as ``T001``.
    """

    return f"{TRACK_LABEL_PREFIX_STR}{track_id_int:0{TRACK_LABEL_WIDTH_INT}d}"


def format_event_label(event_id_int: int) -> str:
    """Return a stable human-readable label for one event ID.

    Args:
        event_id_int: Positive numeric identifier allocated by the tracker.

    Returns:
        Zero-padded event label such as ``E0001``.
    """

    return f"{EVENT_LABEL_PREFIX_STR}{event_id_int:0{EVENT_LABEL_WIDTH_INT}d}"


@dataclass(frozen=True, slots=True)
class TrackObservation:
    """Store one accepted region associated with a temporal track.

    Attributes:
        track_id: Numeric track identifier allocated for the run.
        frame_number: One-based frame number containing the observation.
        timestamp_seconds: Timestamp derived from the reference video FPS.
        detection_index: Zero-based accepted-region index in this frame.
        region: Accepted region measurements produced by detection.
        association_iou: IoU used to associate the region with an existing
            track. ``None`` means the observation created a new track.
        lifecycle_state: Track state after recording this observation.
    """

    track_id: int
    frame_number: int
    timestamp_seconds: float
    detection_index: int
    region: RegionMeasurement
    association_iou: float | None
    lifecycle_state: TrackLifecycleState

    @property
    def track_label(self) -> str:
        """Return the zero-padded display label for this track."""

        return format_track_label(self.track_id)

    @property
    def box(self) -> BoundingBox:
        """Return the bounding box associated with this observation."""

        return self.region.box

    def to_dict(self) -> dict[str, object]:
        """Return serializable observation evidence.

        Returns:
            Dictionary containing identifiers, timing, state, and region
            measurements.
        """

        return {
            "track_id": self.track_id,
            "track_label": self.track_label,
            "frame_number": self.frame_number,
            "timestamp_seconds": self.timestamp_seconds,
            "detection_index": self.detection_index,
            "association_iou": self.association_iou,
            "lifecycle_state": self.lifecycle_state.value,
            "region": self.region.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class TrackState:
    """Store an immutable lifecycle snapshot for one track.

    Attributes:
        track_id: Numeric identifier allocated for the run.
        lifecycle_state: Current lifecycle state.
        first_frame: Frame where the track was created.
        last_observed_frame: Most recent frame containing an observation.
        hit_count: Total number of associated observations.
        consecutive_hit_count: Observations since the most recent gap.
        missing_frame_count: Consecutive frames without an observation.
        recovery_count: Number of LOST-to-CONFIRMED recoveries.
        last_box: Most recent observed bounding box.
    """

    track_id: int
    lifecycle_state: TrackLifecycleState
    first_frame: int
    last_observed_frame: int
    hit_count: int
    consecutive_hit_count: int
    missing_frame_count: int
    recovery_count: int
    last_box: BoundingBox

    @property
    def track_label(self) -> str:
        """Return the zero-padded display label for this track."""

        return format_track_label(self.track_id)

    @property
    def active_span_frames(self) -> int:
        """Return the inclusive observed span of this track."""

        return max(0, self.last_observed_frame - self.first_frame + 1)

    @property
    def is_active(self) -> bool:
        """Return whether this state may participate in association."""

        return self.lifecycle_state != TrackLifecycleState.CLOSED

    def to_dict(self) -> dict[str, object]:
        """Return serializable lifecycle state.

        Returns:
            Dictionary containing lifecycle counters and the latest box.
        """

        return {
            "track_id": self.track_id,
            "track_label": self.track_label,
            "lifecycle_state": self.lifecycle_state.value,
            "first_frame": self.first_frame,
            "last_observed_frame": self.last_observed_frame,
            "active_span_frames": self.active_span_frames,
            "hit_count": self.hit_count,
            "consecutive_hit_count": self.consecutive_hit_count,
            "missing_frame_count": self.missing_frame_count,
            "recovery_count": self.recovery_count,
            "last_box": self.last_box.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class TrackEvent:
    """Represent one temporal lifecycle or lineage event.

    Attributes:
        event_id: Monotonically increasing event identifier.
        event_type: Lifecycle or lineage event category.
        frame_number: One-based frame where the event was observed.
        primary_track_id: Track primarily affected by the event.
        related_track_ids: Other tracks involved in a split or merge.
        gap_frames: Missing-frame duration associated with the event.
        description: Human-readable explanation for evidence reports.
    """

    event_id: int
    event_type: TrackEventType
    frame_number: int
    primary_track_id: int
    related_track_ids: tuple[int, ...] = ()
    gap_frames: int = 0
    description: str = ""

    @property
    def event_label(self) -> str:
        """Return the zero-padded display label for this event."""

        return format_event_label(self.event_id)

    @property
    def primary_track_label(self) -> str:
        """Return the display label for the primary track."""

        return format_track_label(self.primary_track_id)

    @property
    def related_track_labels(self) -> tuple[str, ...]:
        """Return display labels for all related tracks."""

        return tuple(
            format_track_label(track_id_int)
            for track_id_int in self.related_track_ids
        )

    def to_dict(self) -> dict[str, object]:
        """Return serializable event evidence.

        Returns:
            Dictionary containing event identifiers and relationships.
        """

        return {
            "event_id": self.event_id,
            "event_label": self.event_label,
            "event_type": self.event_type.value,
            "frame_number": self.frame_number,
            "primary_track_id": self.primary_track_id,
            "primary_track_label": self.primary_track_label,
            "related_track_ids": list(self.related_track_ids),
            "related_track_labels": list(self.related_track_labels),
            "gap_frames": self.gap_frames,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class TrackSummary:
    """Store completed temporal integrity metrics for one track."""

    track_id: int
    final_state: TrackLifecycleState
    first_frame: int
    last_frame: int
    observation_count: int
    confirmed: bool
    active_span_frames: int
    missing_frames: tuple[int, ...]
    gap_count: int
    longest_gap_frames: int
    continuity_ratio: float
    fragmentation_index: float
    mean_association_iou: float
    minimum_association_iou: float
    mean_severity_score: float
    maximum_severity_score: float
    mean_changed_ratio: float
    mean_area_px: float
    center_jitter_px: float
    area_stability_ratio: float
    recovery_count: int
    split_event_count: int
    merge_event_count: int

    @property
    def track_label(self) -> str:
        """Return the zero-padded display label for this track."""

        return format_track_label(self.track_id)

    def to_dict(self) -> dict[str, object]:
        """Return serializable temporal integrity measurements."""

        return {
            "track_id": self.track_id,
            "track_label": self.track_label,
            "final_state": self.final_state.value,
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "observation_count": self.observation_count,
            "confirmed": self.confirmed,
            "active_span_frames": self.active_span_frames,
            "missing_frames": list(self.missing_frames),
            "gap_count": self.gap_count,
            "longest_gap_frames": self.longest_gap_frames,
            "continuity_ratio": self.continuity_ratio,
            "fragmentation_index": self.fragmentation_index,
            "mean_association_iou": self.mean_association_iou,
            "minimum_association_iou": self.minimum_association_iou,
            "mean_severity_score": self.mean_severity_score,
            "maximum_severity_score": self.maximum_severity_score,
            "mean_changed_ratio": self.mean_changed_ratio,
            "mean_area_px": self.mean_area_px,
            "center_jitter_px": self.center_jitter_px,
            "area_stability_ratio": self.area_stability_ratio,
            "recovery_count": self.recovery_count,
            "split_event_count": self.split_event_count,
            "merge_event_count": self.merge_event_count,
        }


@dataclass(frozen=True, slots=True)
class FrameTrackingResult:
    """Store temporal tracking evidence produced for one video frame.

    Attributes:
        frame_number: One-based frame processed by the tracker.
        timestamp_seconds: Timestamp derived from the reference FPS.
        observations: Regions associated with tracks in this frame.
        active_tracks: Track states after processing the frame.
        events: Lifecycle and lineage events emitted for this frame.
    """

    frame_number: int
    timestamp_seconds: float
    observations: tuple[TrackObservation, ...] = ()
    active_tracks: tuple[TrackState, ...] = ()
    events: tuple[TrackEvent, ...] = ()

    @property
    def observed_track_ids(self) -> tuple[int, ...]:
        """Return sorted unique track IDs observed in this frame."""

        observed_ids_set = {
            observation_obj.track_id for observation_obj in self.observations
        }
        return tuple(sorted(observed_ids_set))

    @property
    def observed_track_labels(self) -> tuple[str, ...]:
        """Return display labels for tracks observed in this frame."""

        return tuple(
            format_track_label(track_id_int)
            for track_id_int in self.observed_track_ids
        )

    def to_dict(self) -> dict[str, object]:
        """Return serializable frame-level tracking evidence.

        Returns:
            Dictionary containing observations, active states, and events.
        """

        return {
            "frame_number": self.frame_number,
            "timestamp_seconds": self.timestamp_seconds,
            "observed_track_ids": list(self.observed_track_ids),
            "observed_track_labels": list(self.observed_track_labels),
            "observations": [
                observation_obj.to_dict()
                for observation_obj in self.observations
            ],
            "active_tracks": [
                track_state_obj.to_dict()
                for track_state_obj in self.active_tracks
            ],
            "events": [event_obj.to_dict() for event_obj in self.events],
        }


__all__ = [
    "EVENT_LABEL_PREFIX_STR",
    "EVENT_LABEL_WIDTH_INT",
    "TRACK_LABEL_PREFIX_STR",
    "TRACK_LABEL_WIDTH_INT",
    "FrameTrackingResult",
    "TrackEvent",
    "TrackEventType",
    "TrackLifecycleState",
    "TrackObservation",
    "TrackState",
    "TrackSummary",
    "format_event_label",
    "format_track_label",
]
