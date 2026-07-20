"""Maintain deterministic temporal region-track lifecycle state."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from visual_verifier.config.tracking import TrackingConfig
from visual_verifier.models import BoundingBox, RegionMeasurement
from visual_verifier.tracking.association import (
    AssociationMatch,
    associate_tracks,
)
from visual_verifier.tracking.events import (
    LineageEventCandidate,
    detect_lineage_event_candidates,
)
from visual_verifier.tracking.models import (
    FrameTrackingResult,
    TrackEvent,
    TrackEventType,
    TrackLifecycleState,
    TrackObservation,
    TrackState,
)


@dataclass(slots=True)
class _MutableTrack:
    """Own mutable counters for one internal tracker entity."""

    track_id: int
    lifecycle_state: TrackLifecycleState
    first_frame: int
    last_observed_frame: int
    hit_count: int
    consecutive_hit_count: int
    missing_frame_count: int
    recovery_count: int
    last_box: BoundingBox

    @classmethod
    def create(
        cls,
        track_id_int: int,
        frame_number_int: int,
        box_obj: BoundingBox,
        minimum_confirmation_hits_int: int,
    ) -> _MutableTrack:
        """Create a new tentative or immediately confirmed track."""

        lifecycle_state_enum = TrackLifecycleState.TENTATIVE
        if minimum_confirmation_hits_int <= 1:
            lifecycle_state_enum = TrackLifecycleState.CONFIRMED
        return cls(
            track_id=track_id_int,
            lifecycle_state=lifecycle_state_enum,
            first_frame=frame_number_int,
            last_observed_frame=frame_number_int,
            hit_count=1,
            consecutive_hit_count=1,
            missing_frame_count=0,
            recovery_count=0,
            last_box=box_obj,
        )

    def observe(
        self,
        frame_number_int: int,
        box_obj: BoundingBox,
        minimum_confirmation_hits_int: int,
    ) -> tuple[bool, bool, int]:
        """Record a match and return transition flags and prior gap."""

        previous_state_enum = self.lifecycle_state
        previous_gap_frames_int = self.missing_frame_count
        self.last_observed_frame = frame_number_int
        self.last_box = box_obj
        self.hit_count += 1
        self.consecutive_hit_count += 1
        self.missing_frame_count = 0

        recovered_bool = previous_state_enum == TrackLifecycleState.LOST
        if recovered_bool:
            self.recovery_count += 1
            self.lifecycle_state = TrackLifecycleState.CONFIRMED
        elif self.hit_count >= minimum_confirmation_hits_int:
            self.lifecycle_state = TrackLifecycleState.CONFIRMED

        confirmed_bool = (
            previous_state_enum == TrackLifecycleState.TENTATIVE
            and self.lifecycle_state == TrackLifecycleState.CONFIRMED
        )
        return confirmed_bool, recovered_bool, previous_gap_frames_int

    def mark_missing(
        self,
        maximum_gap_frames_int: int,
    ) -> tuple[bool, bool]:
        """Advance a missing counter and return lost and closed transitions."""

        previous_state_enum = self.lifecycle_state
        self.missing_frame_count += 1
        self.consecutive_hit_count = 0
        if self.missing_frame_count > maximum_gap_frames_int:
            self.lifecycle_state = TrackLifecycleState.CLOSED
        else:
            self.lifecycle_state = TrackLifecycleState.LOST

        lost_bool = previous_state_enum not in {
            TrackLifecycleState.LOST,
            TrackLifecycleState.CLOSED,
        }
        closed_bool = (
            previous_state_enum != TrackLifecycleState.CLOSED
            and self.lifecycle_state == TrackLifecycleState.CLOSED
        )
        return lost_bool, closed_bool

    def close(self) -> bool:
        """Close the track and return whether a transition occurred."""

        if self.lifecycle_state == TrackLifecycleState.CLOSED:
            return False
        self.lifecycle_state = TrackLifecycleState.CLOSED
        return True

    def snapshot(self) -> TrackState:
        """Return one immutable public lifecycle snapshot."""

        return TrackState(
            track_id=self.track_id,
            lifecycle_state=self.lifecycle_state,
            first_frame=self.first_frame,
            last_observed_frame=self.last_observed_frame,
            hit_count=self.hit_count,
            consecutive_hit_count=self.consecutive_hit_count,
            missing_frame_count=self.missing_frame_count,
            recovery_count=self.recovery_count,
            last_box=self.last_box,
        )


class TemporalRegionTracker:
    """Track accepted processing regions through synchronized video frames."""

    def __init__(self, config: TrackingConfig) -> None:
        """Initialize an empty deterministic tracker session."""

        self._config_obj = config
        self._next_track_id_int = 1
        self._next_event_id_int = 1
        self._tracks_dict: dict[int, _MutableTrack] = {}
        self._observations_list: list[TrackObservation] = []
        self._events_list: list[TrackEvent] = []
        self._frame_results_list: list[FrameTrackingResult] = []
        self._lineage_signatures_set: set[tuple[object, ...]] = set()

    def update(
        self,
        frame_number: int,
        timestamp_seconds: float,
        regions: Sequence[RegionMeasurement],
    ) -> FrameTrackingResult:
        """Associate regions and update lifecycle state for one frame."""

        previous_states_tuple = self.active_states
        association_result_obj = associate_tracks(
            previous_states_tuple,
            regions,
            self._config_obj.association_iou_threshold,
        )
        frame_observations_list: list[TrackObservation] = []
        frame_events_list: list[TrackEvent] = []
        self._apply_matches(
            frame_number,
            timestamp_seconds,
            regions,
            association_result_obj.matches,
            frame_observations_list,
            frame_events_list,
        )
        self._apply_missing_tracks(
            frame_number,
            association_result_obj.unmatched_track_ids,
            frame_events_list,
        )
        self._create_unmatched_tracks(
            frame_number,
            timestamp_seconds,
            regions,
            association_result_obj.unmatched_detection_indices,
            frame_observations_list,
            frame_events_list,
        )
        self._append_lineage_events(
            frame_number,
            previous_states_tuple,
            frame_observations_list,
            frame_events_list,
        )
        return self._record_frame_result(
            frame_number,
            timestamp_seconds,
            frame_observations_list,
            frame_events_list,
        )

    def finish(self, frame_number: int) -> tuple[TrackEvent, ...]:
        """Close all remaining active tracks at the end of a video."""

        closing_events_list: list[TrackEvent] = []
        for track_id_int in sorted(self._tracks_dict):
            track_obj = self._tracks_dict[track_id_int]
            if not track_obj.close():
                continue
            closing_events_list.append(
                self._emit_event(
                    TrackEventType.TRACK_CLOSED,
                    frame_number,
                    track_id_int,
                    description=(
                        f"Track T{track_id_int:03d} closed at end of run."
                    ),
                )
            )
        self._events_list.extend(closing_events_list)
        return tuple(closing_events_list)

    @property
    def active_states(self) -> tuple[TrackState, ...]:
        """Return non-closed track states in ascending ID order."""

        return tuple(
            track_obj.snapshot()
            for _, track_obj in sorted(self._tracks_dict.items())
            if track_obj.lifecycle_state != TrackLifecycleState.CLOSED
        )

    @property
    def states(self) -> tuple[TrackState, ...]:
        """Return all current track states in ascending ID order."""

        return tuple(
            track_obj.snapshot()
            for _, track_obj in sorted(self._tracks_dict.items())
        )

    @property
    def observations(self) -> tuple[TrackObservation, ...]:
        """Return every observation in frame and detection order."""

        return tuple(self._observations_list)

    @property
    def events(self) -> tuple[TrackEvent, ...]:
        """Return every emitted event in event-ID order."""

        return tuple(self._events_list)

    @property
    def frame_results(self) -> tuple[FrameTrackingResult, ...]:
        """Return every frame-level tracking result."""

        return tuple(self._frame_results_list)

    def _apply_matches(
        self,
        frame_number_int: int,
        timestamp_seconds_float: float,
        regions: Sequence[RegionMeasurement],
        matches: Sequence[AssociationMatch],
        observations_list: list[TrackObservation],
        events_list: list[TrackEvent],
    ) -> None:
        """Apply selected associations to existing mutable tracks."""

        for match_obj in matches:
            self._apply_match(
                frame_number_int,
                timestamp_seconds_float,
                regions[match_obj.detection_index],
                match_obj,
                observations_list,
                events_list,
            )

    def _apply_match(
        self,
        frame_number_int: int,
        timestamp_seconds_float: float,
        region_obj: RegionMeasurement,
        match_obj: AssociationMatch,
        observations_list: list[TrackObservation],
        events_list: list[TrackEvent],
    ) -> None:
        """Update one track and append its transition evidence."""

        track_obj = self._tracks_dict[match_obj.track_id]
        transition_tuple = track_obj.observe(
            frame_number_int,
            region_obj.box,
            self._config_obj.minimum_confirmation_hits,
        )
        self._append_observation_transitions(
            frame_number_int,
            track_obj,
            transition_tuple,
            events_list,
        )
        observations_list.append(
            self._build_observation(
                track_obj,
                frame_number_int,
                timestamp_seconds_float,
                match_obj.detection_index,
                region_obj,
                match_obj.iou,
            )
        )

    def _append_observation_transitions(
        self,
        frame_number_int: int,
        track_obj: _MutableTrack,
        transition_tuple: tuple[bool, bool, int],
        events_list: list[TrackEvent],
    ) -> None:
        """Append confirmation and recovery transitions for one match."""

        confirmed_bool, recovered_bool, gap_frames_int = transition_tuple
        if confirmed_bool:
            events_list.append(
                self._emit_event(
                    TrackEventType.TRACK_CONFIRMED,
                    frame_number_int,
                    track_obj.track_id,
                    description=(
                        f"Track T{track_obj.track_id:03d} confirmed."
                    ),
                )
            )
        if recovered_bool:
            events_list.append(
                self._emit_event(
                    TrackEventType.TRACK_RECOVERED,
                    frame_number_int,
                    track_obj.track_id,
                    gap_frames=gap_frames_int,
                    description=(
                        f"Track T{track_obj.track_id:03d} recovered."
                    ),
                )
            )

    def _apply_missing_tracks(
        self,
        frame_number_int: int,
        unmatched_track_ids: Sequence[int],
        events_list: list[TrackEvent],
    ) -> None:
        """Advance missing counters and emit LOST or CLOSED transitions."""

        for track_id_int in sorted(unmatched_track_ids):
            track_obj = self._tracks_dict[track_id_int]
            lost_bool, closed_bool = track_obj.mark_missing(
                self._config_obj.maximum_gap_frames
            )
            if lost_bool:
                events_list.append(
                    self._emit_event(
                        TrackEventType.TRACK_LOST,
                        frame_number_int,
                        track_id_int,
                        gap_frames=track_obj.missing_frame_count,
                        description=f"Track T{track_id_int:03d} was lost.",
                    )
                )
            if closed_bool:
                events_list.append(
                    self._emit_event(
                        TrackEventType.TRACK_CLOSED,
                        frame_number_int,
                        track_id_int,
                        gap_frames=track_obj.missing_frame_count,
                        description=(
                            f"Track T{track_id_int:03d} exceeded gap "
                            "tolerance and closed."
                        ),
                    )
                )

    def _create_unmatched_tracks(
        self,
        frame_number_int: int,
        timestamp_seconds_float: float,
        regions: Sequence[RegionMeasurement],
        detection_indices: Sequence[int],
        observations_list: list[TrackObservation],
        events_list: list[TrackEvent],
    ) -> None:
        """Create tracks for unmatched current detections."""

        for detection_index_int in sorted(detection_indices):
            self._create_track_for_detection(
                frame_number_int,
                timestamp_seconds_float,
                detection_index_int,
                regions[detection_index_int],
                observations_list,
                events_list,
            )

    def _create_track_for_detection(
        self,
        frame_number_int: int,
        timestamp_seconds_float: float,
        detection_index_int: int,
        region_obj: RegionMeasurement,
        observations_list: list[TrackObservation],
        events_list: list[TrackEvent],
    ) -> None:
        """Allocate one track and append creation evidence."""

        track_obj = _MutableTrack.create(
            self._next_track_id_int,
            frame_number_int,
            region_obj.box,
            self._config_obj.minimum_confirmation_hits,
        )
        self._tracks_dict[track_obj.track_id] = track_obj
        self._next_track_id_int += 1
        events_list.append(
            self._emit_event(
                TrackEventType.TRACK_CREATED,
                frame_number_int,
                track_obj.track_id,
                description=(
                    f"Track {track_obj.snapshot().track_label} created."
                ),
            )
        )
        self._append_immediate_confirmation(
            frame_number_int,
            track_obj,
            events_list,
        )
        observations_list.append(
            self._build_observation(
                track_obj,
                frame_number_int,
                timestamp_seconds_float,
                detection_index_int,
                region_obj,
                None,
            )
        )

    def _append_immediate_confirmation(
        self,
        frame_number_int: int,
        track_obj: _MutableTrack,
        events_list: list[TrackEvent],
    ) -> None:
        """Emit confirmation when one hit is sufficient."""

        if track_obj.lifecycle_state != TrackLifecycleState.CONFIRMED:
            return
        events_list.append(
            self._emit_event(
                TrackEventType.TRACK_CONFIRMED,
                frame_number_int,
                track_obj.track_id,
                description=(f"Track T{track_obj.track_id:03d} confirmed."),
            )
        )

    def _append_lineage_events(
        self,
        frame_number_int: int,
        previous_states: Sequence[TrackState],
        observations: Sequence[TrackObservation],
        events_list: list[TrackEvent],
    ) -> None:
        """Detect, de-duplicate, and emit split and merge evidence."""

        if not self._config_obj.detect_lineage_events:
            return
        candidates_tuple = detect_lineage_event_candidates(
            previous_states,
            observations,
            self._config_obj.lineage_overlap_threshold,
        )
        for candidate_obj in candidates_tuple:
            if candidate_obj.signature in self._lineage_signatures_set:
                continue
            self._lineage_signatures_set.add(candidate_obj.signature)
            events_list.append(
                self._emit_lineage_event(frame_number_int, candidate_obj)
            )

    def _emit_lineage_event(
        self,
        frame_number_int: int,
        candidate_obj: LineageEventCandidate,
    ) -> TrackEvent:
        """Allocate one event ID for a lineage candidate."""

        return self._emit_event(
            candidate_obj.event_type,
            frame_number_int,
            candidate_obj.primary_track_id,
            related_track_ids=candidate_obj.related_track_ids,
            description=candidate_obj.description,
        )

    def _emit_event(
        self,
        event_type_enum: TrackEventType,
        frame_number_int: int,
        primary_track_id_int: int,
        *,
        related_track_ids: tuple[int, ...] = (),
        gap_frames: int = 0,
        description: str,
    ) -> TrackEvent:
        """Allocate and return one immutable tracking event."""

        event_obj = TrackEvent(
            event_id=self._next_event_id_int,
            event_type=event_type_enum,
            frame_number=frame_number_int,
            primary_track_id=primary_track_id_int,
            related_track_ids=related_track_ids,
            gap_frames=gap_frames,
            description=description,
        )
        self._next_event_id_int += 1
        return event_obj

    @staticmethod
    def _build_observation(
        track_obj: _MutableTrack,
        frame_number_int: int,
        timestamp_seconds_float: float,
        detection_index_int: int,
        region_obj: RegionMeasurement,
        association_iou_float: float | None,
    ) -> TrackObservation:
        """Build one immutable track observation."""

        return TrackObservation(
            track_id=track_obj.track_id,
            frame_number=frame_number_int,
            timestamp_seconds=timestamp_seconds_float,
            detection_index=detection_index_int,
            region=region_obj,
            association_iou=association_iou_float,
            lifecycle_state=track_obj.lifecycle_state,
        )

    def _record_frame_result(
        self,
        frame_number_int: int,
        timestamp_seconds_float: float,
        observations_list: list[TrackObservation],
        events_list: list[TrackEvent],
    ) -> FrameTrackingResult:
        """Persist frame observations and events and return the result."""

        self._observations_list.extend(observations_list)
        self._events_list.extend(events_list)
        result_obj = FrameTrackingResult(
            frame_number=frame_number_int,
            timestamp_seconds=timestamp_seconds_float,
            observations=tuple(observations_list),
            active_tracks=self.active_states,
            events=tuple(events_list),
        )
        self._frame_results_list.append(result_obj)
        return result_obj


__all__ = ["TemporalRegionTracker"]
