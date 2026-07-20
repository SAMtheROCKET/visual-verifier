"""Test split and merge lineage-event detection."""

from tests.tracking_helpers import make_region
from visual_verifier.models import BoundingBox
from visual_verifier.tracking.events import (
    detect_lineage_event_candidates,
)
from visual_verifier.tracking.models import (
    TrackEventType,
    TrackLifecycleState,
    TrackObservation,
    TrackState,
)


def _state(track_id_int: int, box_obj: BoundingBox) -> TrackState:
    """Return one confirmed previous-frame state."""

    return TrackState(
        track_id=track_id_int,
        lifecycle_state=TrackLifecycleState.CONFIRMED,
        first_frame=1,
        last_observed_frame=1,
        hit_count=2,
        consecutive_hit_count=2,
        missing_frame_count=0,
        recovery_count=0,
        last_box=box_obj,
    )


def _observation(
    track_id_int: int,
    detection_index_int: int,
    box_obj: BoundingBox,
) -> TrackObservation:
    """Return one current-frame confirmed observation."""

    return TrackObservation(
        track_id=track_id_int,
        frame_number=2,
        timestamp_seconds=0.5,
        detection_index=detection_index_int,
        region=make_region(box_obj),
        association_iou=0.5,
        lifecycle_state=TrackLifecycleState.CONFIRMED,
    )


def test_one_previous_box_and_two_current_boxes_form_split() -> None:
    """Confirm a persistent track plus a new branch emits a split."""

    candidates_tuple = detect_lineage_event_candidates(
        (_state(1, BoundingBox(0, 0, 20, 10)),),
        (
            _observation(1, 0, BoundingBox(0, 0, 10, 10)),
            _observation(2, 1, BoundingBox(10, 0, 20, 10)),
        ),
        0.5,
    )

    assert len(candidates_tuple) == 1
    assert candidates_tuple[0].event_type == TrackEventType.TRACK_SPLIT
    assert candidates_tuple[0].primary_track_id == 1
    assert candidates_tuple[0].related_track_ids == (2,)


def test_two_previous_boxes_and_one_current_box_form_merge() -> None:
    """Confirm two prior tracks converging into one emits a merge."""

    candidates_tuple = detect_lineage_event_candidates(
        (
            _state(1, BoundingBox(0, 0, 10, 10)),
            _state(2, BoundingBox(10, 0, 20, 10)),
        ),
        (_observation(1, 0, BoundingBox(0, 0, 20, 10)),),
        0.5,
    )

    assert len(candidates_tuple) == 1
    assert candidates_tuple[0].event_type == TrackEventType.TRACK_MERGED
    assert candidates_tuple[0].primary_track_id == 1
    assert candidates_tuple[0].related_track_ids == (2,)
