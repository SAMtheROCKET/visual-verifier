"""Detect explainable split and merge lineage events."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from visual_verifier.metrics.geometry import calculate_intersection_area
from visual_verifier.models import BoundingBox
from visual_verifier.tracking.models import (
    TrackEventType,
    TrackObservation,
    TrackState,
)


@dataclass(frozen=True, slots=True)
class LineageEventCandidate:
    """Describe one split or merge before event-ID allocation."""

    event_type: TrackEventType
    primary_track_id: int
    related_track_ids: tuple[int, ...]
    description: str

    @property
    def signature(self) -> tuple[object, ...]:
        """Return a stable signature used to suppress repeated events."""

        return (
            self.event_type.value,
            self.primary_track_id,
            self.related_track_ids,
        )


def detect_lineage_event_candidates(
    previous_states: Sequence[TrackState],
    current_observations: Sequence[TrackObservation],
    overlap_threshold: float,
) -> tuple[LineageEventCandidate, ...]:
    """Detect split and merge relationships across adjacent frames.

    Args:
        previous_states: Active track snapshots before current association.
        current_observations: Track observations assigned in this frame.
        overlap_threshold: Minimum overlap coefficient for lineage evidence.

    Returns:
        Deterministically ordered split and merge event candidates.
    """

    split_candidates_tuple = _detect_split_candidates(
        previous_states,
        current_observations,
        overlap_threshold,
    )
    merge_candidates_tuple = _detect_merge_candidates(
        previous_states,
        current_observations,
        overlap_threshold,
    )
    return tuple(
        sorted(
            split_candidates_tuple + merge_candidates_tuple,
            key=lambda candidate_obj: candidate_obj.signature,
        )
    )


def calculate_overlap_coefficient(
    first_box: BoundingBox,
    second_box: BoundingBox,
) -> float:
    """Return intersection divided by the smaller valid box area."""

    smaller_area_int = min(first_box.area, second_box.area)
    if smaller_area_int <= 0:
        return 0.0
    intersection_area_int = calculate_intersection_area(
        first_box,
        second_box,
    )
    return intersection_area_int / smaller_area_int


def _detect_split_candidates(
    previous_states: Sequence[TrackState],
    current_observations: Sequence[TrackObservation],
    overlap_threshold: float,
) -> tuple[LineageEventCandidate, ...]:
    """Return candidates where one previous track overlaps many current."""

    candidates_list: list[LineageEventCandidate] = []
    for previous_state_obj in previous_states:
        current_ids_tuple = _overlapping_current_track_ids(
            previous_state_obj,
            current_observations,
            overlap_threshold,
        )
        if len(current_ids_tuple) < 2:
            continue
        related_ids_tuple = tuple(
            track_id_int
            for track_id_int in current_ids_tuple
            if track_id_int != previous_state_obj.track_id
        )
        if not related_ids_tuple:
            continue
        candidates_list.append(
            LineageEventCandidate(
                event_type=TrackEventType.TRACK_SPLIT,
                primary_track_id=previous_state_obj.track_id,
                related_track_ids=related_ids_tuple,
                description=(
                    f"Track T{previous_state_obj.track_id:03d} overlaps "
                    f"multiple current tracks {current_ids_tuple}."
                ),
            )
        )
    return tuple(candidates_list)


def _detect_merge_candidates(
    previous_states: Sequence[TrackState],
    current_observations: Sequence[TrackObservation],
    overlap_threshold: float,
) -> tuple[LineageEventCandidate, ...]:
    """Return candidates where many previous tracks overlap one current."""

    candidates_list: list[LineageEventCandidate] = []
    for observation_obj in current_observations:
        previous_ids_tuple = _overlapping_previous_track_ids(
            observation_obj,
            previous_states,
            overlap_threshold,
        )
        if len(previous_ids_tuple) < 2:
            continue
        related_ids_tuple = tuple(
            track_id_int
            for track_id_int in previous_ids_tuple
            if track_id_int != observation_obj.track_id
        )
        if not related_ids_tuple:
            continue
        candidates_list.append(
            LineageEventCandidate(
                event_type=TrackEventType.TRACK_MERGED,
                primary_track_id=observation_obj.track_id,
                related_track_ids=related_ids_tuple,
                description=(
                    f"Current track {observation_obj.track_label} overlaps "
                    f"multiple previous tracks {previous_ids_tuple}."
                ),
            )
        )
    return tuple(candidates_list)


def _overlapping_current_track_ids(
    previous_state: TrackState,
    observations: Sequence[TrackObservation],
    threshold: float,
) -> tuple[int, ...]:
    """Return current track IDs sufficiently overlapping one prior state."""

    track_ids_set = {
        observation_obj.track_id
        for observation_obj in observations
        if calculate_overlap_coefficient(
            previous_state.last_box,
            observation_obj.box,
        )
        >= threshold
    }
    return tuple(sorted(track_ids_set))


def _overlapping_previous_track_ids(
    observation: TrackObservation,
    previous_states: Sequence[TrackState],
    threshold: float,
) -> tuple[int, ...]:
    """Return previous track IDs overlapping one current observation."""

    track_ids_set = {
        state_obj.track_id
        for state_obj in previous_states
        if calculate_overlap_coefficient(
            state_obj.last_box,
            observation.box,
        )
        >= threshold
    }
    return tuple(sorted(track_ids_set))


__all__ = [
    "LineageEventCandidate",
    "calculate_overlap_coefficient",
    "detect_lineage_event_candidates",
]
