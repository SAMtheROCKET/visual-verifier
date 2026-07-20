"""Associate accepted regions with active temporal tracks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from visual_verifier.metrics.geometry import calculate_iou
from visual_verifier.models import RegionMeasurement
from visual_verifier.tracking.models import TrackState


@dataclass(frozen=True, slots=True)
class AssociationMatch:
    """Represent one deterministic track-to-detection association."""

    track_id: int
    detection_index: int
    iou: float


@dataclass(frozen=True, slots=True)
class AssociationResult:
    """Store matches and unmatched identifiers for one frame."""

    matches: tuple[AssociationMatch, ...]
    unmatched_track_ids: tuple[int, ...]
    unmatched_detection_indices: tuple[int, ...]


def associate_tracks(
    track_states: Sequence[TrackState],
    detections: Sequence[RegionMeasurement],
    iou_threshold: float,
) -> AssociationResult:
    """Associate active tracks and detections using deterministic greedy IoU.

    Args:
        track_states: Active track snapshots before the current frame.
        detections: Accepted regions detected in the current frame.
        iou_threshold: Minimum IoU required for a valid association.

    Returns:
        Immutable association result with one-to-one matches.
    """

    candidate_matches_list = _build_candidate_matches(
        track_states,
        detections,
        iou_threshold,
    )
    selected_matches_list = _select_one_to_one_matches(candidate_matches_list)
    return _build_association_result(
        track_states,
        detections,
        selected_matches_list,
    )


def _build_candidate_matches(
    track_states: Sequence[TrackState],
    detections: Sequence[RegionMeasurement],
    iou_threshold: float,
) -> list[AssociationMatch]:
    """Return valid candidate pairs sorted by deterministic priority."""

    candidates_list: list[AssociationMatch] = []
    for track_state_obj in sorted(
        track_states,
        key=lambda state_obj: state_obj.track_id,
    ):
        for detection_index_int, region_obj in enumerate(detections):
            iou_float = calculate_iou(
                track_state_obj.last_box,
                region_obj.box,
            )
            if iou_float < iou_threshold:
                continue
            candidates_list.append(
                AssociationMatch(
                    track_id=track_state_obj.track_id,
                    detection_index=detection_index_int,
                    iou=round(iou_float, 6),
                )
            )
    return sorted(
        candidates_list,
        key=lambda match_obj: (
            -match_obj.iou,
            match_obj.track_id,
            match_obj.detection_index,
        ),
    )


def _select_one_to_one_matches(
    candidates: Sequence[AssociationMatch],
) -> list[AssociationMatch]:
    """Select non-conflicting matches from the ordered candidate list."""

    selected_list: list[AssociationMatch] = []
    assigned_track_ids_set: set[int] = set()
    assigned_detection_indices_set: set[int] = set()

    for match_obj in candidates:
        if match_obj.track_id in assigned_track_ids_set:
            continue
        if match_obj.detection_index in assigned_detection_indices_set:
            continue
        selected_list.append(match_obj)
        assigned_track_ids_set.add(match_obj.track_id)
        assigned_detection_indices_set.add(match_obj.detection_index)

    return sorted(selected_list, key=lambda item_obj: item_obj.track_id)


def _build_association_result(
    track_states: Sequence[TrackState],
    detections: Sequence[RegionMeasurement],
    matches: Sequence[AssociationMatch],
) -> AssociationResult:
    """Build unmatched identifier tuples from selected matches."""

    matched_track_ids_set = {match_obj.track_id for match_obj in matches}
    matched_detection_indices_set = {
        match_obj.detection_index for match_obj in matches
    }
    all_track_ids_set = {state_obj.track_id for state_obj in track_states}
    all_detection_indices_set = set(range(len(detections)))
    return AssociationResult(
        matches=tuple(matches),
        unmatched_track_ids=tuple(
            sorted(all_track_ids_set - matched_track_ids_set)
        ),
        unmatched_detection_indices=tuple(
            sorted(all_detection_indices_set - matched_detection_indices_set)
        ),
    )


__all__ = [
    "AssociationMatch",
    "AssociationResult",
    "associate_tracks",
]
