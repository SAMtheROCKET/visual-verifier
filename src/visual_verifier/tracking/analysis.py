"""Calculate continuity and stability metrics for completed tracks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from math import hypot
from statistics import fmean

from visual_verifier.tracking.models import (
    TrackEvent,
    TrackEventType,
    TrackLifecycleState,
    TrackObservation,
    TrackState,
    TrackSummary,
)


@dataclass(frozen=True, slots=True)
class _TimingMetrics:
    """Store frame-span and gap measurements for one track."""

    first_frame: int
    last_frame: int
    active_span_frames: int
    missing_frames: tuple[int, ...]
    gap_count: int
    longest_gap_frames: int
    continuity_ratio: float
    fragmentation_index: float


@dataclass(frozen=True, slots=True)
class _QualityMetrics:
    """Store association, severity, and box-stability measurements."""

    mean_association_iou: float
    minimum_association_iou: float
    mean_severity_score: float
    maximum_severity_score: float
    mean_changed_ratio: float
    mean_area_px: float
    center_jitter_px: float
    area_stability_ratio: float


def analyze_tracks(
    observations: Sequence[TrackObservation],
    states: Sequence[TrackState],
    events: Sequence[TrackEvent],
) -> tuple[TrackSummary, ...]:
    """Build one deterministic temporal integrity summary per track."""

    observation_groups_dict = _group_observations(observations)
    states_dict = {state_obj.track_id: state_obj for state_obj in states}
    summaries_list: list[TrackSummary] = []

    for track_id_int in sorted(observation_groups_dict):
        summaries_list.append(
            _build_track_summary(
                track_id_int,
                observation_groups_dict[track_id_int],
                states_dict[track_id_int],
                events,
            )
        )
    return tuple(summaries_list)


def _group_observations(
    observations: Sequence[TrackObservation],
) -> dict[int, list[TrackObservation]]:
    """Group observations by track ID in chronological order."""

    grouped_dict: dict[int, list[TrackObservation]] = defaultdict(list)
    for observation_obj in observations:
        grouped_dict[observation_obj.track_id].append(observation_obj)
    for track_observations_list in grouped_dict.values():
        track_observations_list.sort(
            key=lambda item_obj: (
                item_obj.frame_number,
                item_obj.detection_index,
            )
        )
    return dict(grouped_dict)


def _build_track_summary(
    track_id_int: int,
    observations: Sequence[TrackObservation],
    state_obj: TrackState,
    events: Sequence[TrackEvent],
) -> TrackSummary:
    """Combine timing, quality, lifecycle, and lineage measurements."""

    timing_obj = _calculate_timing_metrics(observations)
    quality_obj = _calculate_quality_metrics(observations)
    return TrackSummary(
        track_id=track_id_int,
        final_state=state_obj.lifecycle_state,
        first_frame=timing_obj.first_frame,
        last_frame=timing_obj.last_frame,
        observation_count=len(observations),
        confirmed=_was_confirmed(observations),
        active_span_frames=timing_obj.active_span_frames,
        missing_frames=timing_obj.missing_frames,
        gap_count=timing_obj.gap_count,
        longest_gap_frames=timing_obj.longest_gap_frames,
        continuity_ratio=timing_obj.continuity_ratio,
        fragmentation_index=timing_obj.fragmentation_index,
        mean_association_iou=quality_obj.mean_association_iou,
        minimum_association_iou=quality_obj.minimum_association_iou,
        mean_severity_score=quality_obj.mean_severity_score,
        maximum_severity_score=quality_obj.maximum_severity_score,
        mean_changed_ratio=quality_obj.mean_changed_ratio,
        mean_area_px=quality_obj.mean_area_px,
        center_jitter_px=quality_obj.center_jitter_px,
        area_stability_ratio=quality_obj.area_stability_ratio,
        recovery_count=state_obj.recovery_count,
        split_event_count=_count_lineage_events(
            track_id_int,
            events,
            TrackEventType.TRACK_SPLIT,
        ),
        merge_event_count=_count_lineage_events(
            track_id_int,
            events,
            TrackEventType.TRACK_MERGED,
        ),
    )


def _calculate_timing_metrics(
    observations: Sequence[TrackObservation],
) -> _TimingMetrics:
    """Calculate frame span, missing frames, gaps, and continuity."""

    observed_frames_tuple = tuple(
        sorted({item_obj.frame_number for item_obj in observations})
    )
    first_frame_int = observed_frames_tuple[0]
    last_frame_int = observed_frames_tuple[-1]
    active_span_int = last_frame_int - first_frame_int + 1
    observed_frames_set = set(observed_frames_tuple)
    missing_frames_tuple = tuple(
        frame_number_int
        for frame_number_int in range(first_frame_int, last_frame_int + 1)
        if frame_number_int not in observed_frames_set
    )
    gap_count_int, longest_gap_int = _gap_statistics(missing_frames_tuple)
    return _TimingMetrics(
        first_frame=first_frame_int,
        last_frame=last_frame_int,
        active_span_frames=active_span_int,
        missing_frames=missing_frames_tuple,
        gap_count=gap_count_int,
        longest_gap_frames=longest_gap_int,
        continuity_ratio=round(len(observations) / active_span_int, 6),
        fragmentation_index=_fragmentation_index(
            gap_count_int,
            len(observations),
        ),
    )


def _calculate_quality_metrics(
    observations: Sequence[TrackObservation],
) -> _QualityMetrics:
    """Calculate association, severity, and geometry stability metrics."""

    association_values_list = [
        item_obj.association_iou
        for item_obj in observations
        if item_obj.association_iou is not None
    ]
    return _QualityMetrics(
        mean_association_iou=_mean_or_zero(association_values_list),
        minimum_association_iou=_minimum_or_zero(association_values_list),
        mean_severity_score=_mean_region_value(
            observations,
            "severity_score",
        ),
        maximum_severity_score=max(
            item_obj.region.severity_score for item_obj in observations
        ),
        mean_changed_ratio=_mean_region_value(
            observations,
            "changed_ratio",
        ),
        mean_area_px=round(
            fmean(item_obj.box.area for item_obj in observations),
            2,
        ),
        center_jitter_px=_center_jitter(observations),
        area_stability_ratio=_area_stability(observations),
    )


def _was_confirmed(
    observations: Sequence[TrackObservation],
) -> bool:
    """Return whether any observation reached confirmed lifecycle state."""

    return any(
        item_obj.lifecycle_state == TrackLifecycleState.CONFIRMED
        for item_obj in observations
    )


def _gap_statistics(missing_frames: Sequence[int]) -> tuple[int, int]:
    """Return number of missing runs and longest consecutive run."""

    if not missing_frames:
        return 0, 0
    gap_count_int = 1
    current_gap_int = 1
    longest_gap_int = 1
    for index_int in range(1, len(missing_frames)):
        if missing_frames[index_int] == missing_frames[index_int - 1] + 1:
            current_gap_int += 1
        else:
            gap_count_int += 1
            current_gap_int = 1
        longest_gap_int = max(longest_gap_int, current_gap_int)
    return gap_count_int, longest_gap_int


def _fragmentation_index(
    gap_count_int: int,
    observation_count_int: int,
) -> float:
    """Return gap count normalized by possible observation transitions."""

    denominator_int = max(observation_count_int - 1, 1)
    return round(gap_count_int / denominator_int, 6)


def _mean_region_value(
    observations: Sequence[TrackObservation],
    attribute_name_str: str,
) -> float:
    """Return a rounded mean for one numeric region attribute."""

    values_list = [
        float(getattr(item_obj.region, attribute_name_str))
        for item_obj in observations
    ]
    return round(fmean(values_list), 6)


def _mean_or_zero(values: Sequence[float]) -> float:
    """Return a rounded mean or zero for an empty sequence."""

    if not values:
        return 0.0
    return round(fmean(values), 6)


def _minimum_or_zero(values: Sequence[float]) -> float:
    """Return a rounded minimum or zero for an empty sequence."""

    if not values:
        return 0.0
    return round(min(values), 6)


def _center_jitter(
    observations: Sequence[TrackObservation],
) -> float:
    """Return mean center displacement between consecutive observations."""

    if len(observations) < 2:
        return 0.0
    displacement_values_list = [
        _center_displacement(previous_obj, current_obj)
        for previous_obj, current_obj in zip(
            observations,
            observations[1:],
            strict=False,
        )
    ]
    return round(fmean(displacement_values_list), 4)


def _center_displacement(
    previous_obj: TrackObservation,
    current_obj: TrackObservation,
) -> float:
    """Return Euclidean center movement between two observations."""

    previous_center_tuple = _box_center(previous_obj)
    current_center_tuple = _box_center(current_obj)
    return hypot(
        current_center_tuple[0] - previous_center_tuple[0],
        current_center_tuple[1] - previous_center_tuple[1],
    )


def _box_center(observation: TrackObservation) -> tuple[float, float]:
    """Return the floating-point center of one observation box."""

    box_obj = observation.box
    return (
        (box_obj.x1 + box_obj.x2) / 2.0,
        (box_obj.y1 + box_obj.y2) / 2.0,
    )


def _area_stability(
    observations: Sequence[TrackObservation],
) -> float:
    """Return minimum-to-maximum area ratio in range [0, 1]."""

    area_values_list = [item_obj.box.area for item_obj in observations]
    maximum_area_int = max(area_values_list)
    if maximum_area_int <= 0:
        return 0.0
    return round(min(area_values_list) / maximum_area_int, 6)


def _count_lineage_events(
    track_id_int: int,
    events: Sequence[TrackEvent],
    event_type_enum: TrackEventType,
) -> int:
    """Count lineage events where a track is primary or related."""

    return sum(
        event_obj.event_type == event_type_enum
        and (
            event_obj.primary_track_id == track_id_int
            or track_id_int in event_obj.related_track_ids
        )
        for event_obj in events
    )


__all__ = ["analyze_tracks"]
