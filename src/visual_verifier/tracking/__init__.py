"""Expose deterministic temporal region-tracking interfaces."""

from visual_verifier.tracking.analysis import analyze_tracks
from visual_verifier.tracking.association import (
    AssociationMatch,
    AssociationResult,
    associate_tracks,
)
from visual_verifier.tracking.models import (
    FrameTrackingResult,
    TrackEvent,
    TrackEventType,
    TrackLifecycleState,
    TrackObservation,
    TrackState,
    TrackSummary,
    format_event_label,
    format_track_label,
)
from visual_verifier.tracking.tracker import TemporalRegionTracker

__all__ = [
    "AssociationMatch",
    "AssociationResult",
    "FrameTrackingResult",
    "TemporalRegionTracker",
    "TrackEvent",
    "TrackEventType",
    "TrackLifecycleState",
    "TrackObservation",
    "TrackState",
    "TrackSummary",
    "analyze_tracks",
    "associate_tracks",
    "format_event_label",
    "format_track_label",
]
