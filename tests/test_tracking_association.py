"""Test deterministic one-to-one temporal association."""

from tests.tracking_helpers import make_region
from visual_verifier.models import BoundingBox
from visual_verifier.tracking.association import associate_tracks
from visual_verifier.tracking.models import (
    TrackLifecycleState,
    TrackState,
)


def _make_state(track_id_int: int, box_obj: BoundingBox) -> TrackState:
    """Return one active confirmed track state."""

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


def test_association_matches_each_track_and_detection_once() -> None:
    """Confirm valid pairs are selected without assignment conflicts."""

    track_states_tuple = (
        _make_state(1, BoundingBox(0, 0, 10, 10)),
        _make_state(2, BoundingBox(20, 0, 30, 10)),
    )
    regions_tuple = (
        make_region(BoundingBox(1, 0, 11, 10)),
        make_region(BoundingBox(21, 0, 31, 10)),
    )

    result_obj = associate_tracks(track_states_tuple, regions_tuple, 0.2)

    assert tuple(
        (match_obj.track_id, match_obj.detection_index)
        for match_obj in result_obj.matches
    ) == ((1, 0), (2, 1))
    assert result_obj.unmatched_track_ids == ()
    assert result_obj.unmatched_detection_indices == ()


def test_equal_iou_tie_prefers_lower_track_id() -> None:
    """Confirm input order cannot change deterministic tie resolution."""

    shared_box_obj = BoundingBox(0, 0, 10, 10)
    reversed_states_tuple = (
        _make_state(2, shared_box_obj),
        _make_state(1, shared_box_obj),
    )
    regions_tuple = (make_region(shared_box_obj),)

    result_obj = associate_tracks(reversed_states_tuple, regions_tuple, 0.2)

    assert len(result_obj.matches) == 1
    assert result_obj.matches[0].track_id == 1
    assert result_obj.matches[0].detection_index == 0
    assert result_obj.unmatched_track_ids == (2,)
