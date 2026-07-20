"""Test temporal track lifecycle, recovery, closure, and ID allocation."""

from tests.tracking_helpers import make_region
from visual_verifier.config import TrackingConfig
from visual_verifier.models import BoundingBox
from visual_verifier.tracking import (
    TemporalRegionTracker,
    TrackEventType,
    TrackLifecycleState,
)


def _build_tracker() -> TemporalRegionTracker:
    """Return a tracker configured for a short lifecycle test."""

    return TemporalRegionTracker(
        TrackingConfig(
            association_iou_threshold=0.1,
            minimum_confirmation_hits=2,
            maximum_gap_frames=2,
            detect_lineage_events=False,
        )
    )


def test_track_confirms_recovers_closes_and_never_reuses_id() -> None:
    """Confirm the complete lifecycle across observations and gaps."""

    tracker_obj = _build_tracker()
    region_obj = make_region(BoundingBox(0, 0, 10, 10))
    first_result_obj = tracker_obj.update(1, 0.0, (region_obj,))
    second_result_obj = tracker_obj.update(2, 0.5, (region_obj,))
    tracker_obj.update(3, 1.0, ())
    tracker_obj.update(4, 1.5, ())
    recovered_result_obj = tracker_obj.update(5, 2.0, (region_obj,))
    tracker_obj.update(6, 2.5, ())
    tracker_obj.update(7, 3.0, ())
    closed_result_obj = tracker_obj.update(8, 3.5, ())
    new_result_obj = tracker_obj.update(
        9,
        4.0,
        (make_region(BoundingBox(30, 0, 40, 10)),),
    )

    assert first_result_obj.observations[0].lifecycle_state == (
        TrackLifecycleState.TENTATIVE
    )
    assert second_result_obj.observations[0].lifecycle_state == (
        TrackLifecycleState.CONFIRMED
    )
    assert recovered_result_obj.observations[0].track_id == 1
    assert recovered_result_obj.observations[0].lifecycle_state == (
        TrackLifecycleState.CONFIRMED
    )
    assert closed_result_obj.active_tracks == ()
    assert new_result_obj.observations[0].track_id == 2
    _assert_expected_events(tracker_obj)


def _assert_expected_events(tracker_obj: TemporalRegionTracker) -> None:
    """Confirm expected lifecycle event types and recovery gap."""

    event_types_tuple = tuple(
        event_obj.event_type for event_obj in tracker_obj.events
    )
    assert TrackEventType.TRACK_CONFIRMED in event_types_tuple
    assert TrackEventType.TRACK_LOST in event_types_tuple
    assert TrackEventType.TRACK_RECOVERED in event_types_tuple
    assert TrackEventType.TRACK_CLOSED in event_types_tuple
    recovery_event_obj = next(
        event_obj
        for event_obj in tracker_obj.events
        if event_obj.event_type == TrackEventType.TRACK_RECOVERED
    )
    assert recovery_event_obj.gap_frames == 2
