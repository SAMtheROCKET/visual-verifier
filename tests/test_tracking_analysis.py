"""Test temporal continuity and stability measurements."""

import pytest

from tests.tracking_helpers import make_region
from visual_verifier.models import BoundingBox
from visual_verifier.tracking.analysis import analyze_tracks
from visual_verifier.tracking.models import (
    TrackEvent,
    TrackEventType,
    TrackLifecycleState,
    TrackObservation,
    TrackState,
)


def _build_observations() -> tuple[TrackObservation, ...]:
    """Return one interrupted three-observation track fixture."""

    return tuple(
        TrackObservation(
            track_id=1,
            frame_number=frame_number_int,
            timestamp_seconds=float(frame_number_int - 1),
            detection_index=0,
            region=make_region(
                BoundingBox(offset_int, 0, offset_int + 10, 10),
                severity_score=40.0 + frame_number_int,
            ),
            association_iou=None if frame_number_int == 1 else 0.5,
            lifecycle_state=TrackLifecycleState.CONFIRMED,
        )
        for frame_number_int, offset_int in ((1, 0), (2, 1), (4, 3))
    )


def _build_state() -> TrackState:
    """Return the final closed state for the analysis fixture."""

    return TrackState(
        track_id=1,
        lifecycle_state=TrackLifecycleState.CLOSED,
        first_frame=1,
        last_observed_frame=4,
        hit_count=3,
        consecutive_hit_count=1,
        missing_frame_count=0,
        recovery_count=1,
        last_box=BoundingBox(3, 0, 13, 10),
    )


def test_analysis_reports_gap_continuity_and_lineage_counts() -> None:
    """Confirm one interrupted track receives expected integrity metrics."""

    events_tuple = (
        TrackEvent(1, TrackEventType.TRACK_SPLIT, 2, 1, (2,)),
        TrackEvent(2, TrackEventType.TRACK_MERGED, 4, 1, (2,)),
    )
    summary_obj = analyze_tracks(
        _build_observations(),
        (_build_state(),),
        events_tuple,
    )[0]

    assert summary_obj.confirmed
    assert summary_obj.missing_frames == (3,)
    assert summary_obj.gap_count == 1
    assert summary_obj.longest_gap_frames == 1
    assert summary_obj.continuity_ratio == pytest.approx(0.75)
    assert summary_obj.fragmentation_index == pytest.approx(0.5)
    assert summary_obj.mean_association_iou == pytest.approx(0.5)
    assert summary_obj.recovery_count == 1
    assert summary_obj.split_event_count == 1
    assert summary_obj.merge_event_count == 1
    assert summary_obj.area_stability_ratio == pytest.approx(1.0)
    assert summary_obj.center_jitter_px > 0.0
