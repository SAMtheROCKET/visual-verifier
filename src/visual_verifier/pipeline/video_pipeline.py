"""Run reference-based video verification with temporal tracking evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2

from visual_verifier.config.targets import (
    DEFAULT_TARGET_CONFIG,
    TargetConfig,
)
from visual_verifier.config.tracking import (
    DEFAULT_TRACKING_CONFIG,
    TrackingConfig,
)
from visual_verifier.detection.region_extraction import detect_regions
from visual_verifier.exceptions import ReportWriteError
from visual_verifier.media.metadata import read_video_metadata
from visual_verifier.media.normalization import (
    resize_candidate_to_reference,
)
from visual_verifier.media.thumbnails import encode_frame_thumbnail
from visual_verifier.media.video_reader import iter_video_pairs
from visual_verifier.media.video_writer import open_annotated_writer
from visual_verifier.models import (
    DetectionConfig,
    FrameVerification,
    MediaMetadata,
    RegionMeasurement,
    VerificationFailure,
    VerificationResult,
    VerificationStatus,
)
from visual_verifier.reporting.annotations import annotate_frame
from visual_verifier.reporting.csv_report import write_csv_report
from visual_verifier.reporting.html_report import (
    HTML_REPORT_FILENAME_STR,
    FrameThumbnail,
    write_html_report,
)
from visual_verifier.reporting.json_report import write_json_report
from visual_verifier.reporting.track_report import write_tracking_reports
from visual_verifier.targets.coverage import (
    group_targets_by_frame,
    measure_frame_targets,
    summarize_targets,
)
from visual_verifier.targets.interpolation import interpolate_targets
from visual_verifier.targets.models import (
    Target,
    TargetCoverage,
    TargetSummary,
)
from visual_verifier.tracking.analysis import analyze_tracks
from visual_verifier.tracking.models import (
    FrameTrackingResult,
    TrackEvent,
    TrackObservation,
    TrackSummary,
)
from visual_verifier.tracking.tracker import TemporalRegionTracker
from visual_verifier.type_aliases import ImageArray, PathInput, ReportRow

FALLBACK_VIDEO_FPS_FLOAT = 30.0
GENERIC_VIDEO_POLICY_NAME_STR = "generic_change_every_frame"
TARGET_VIDEO_POLICY_NAME_STR = "target_coverage_every_frame"
UNPROCESSED_FRAMES_FAILURE_CODE_STR = "UNPROCESSED_FRAMES"
UNCOVERED_TARGETS_FAILURE_CODE_STR = "UNCOVERED_TARGETS"
ANNOTATED_VIDEO_FILENAME_STR = "annotated_video.mp4"
FRAME_REPORT_FILENAME_STR = "frame_report.csv"
REGION_REPORT_FILENAME_STR = "region_report.csv"
REJECTED_REGION_REPORT_FILENAME_STR = "rejected_region_report.csv"
TARGET_REPORT_FILENAME_STR = "target_report.csv"
SUMMARY_REPORT_FILENAME_STR = "summary.json"
MAX_CAPTURED_THUMBNAILS_INT = 24


@dataclass(frozen=True, slots=True)
class _VideoRunContext:
    """Store resolved paths, metadata, and optional output location."""

    reference_path_obj: Path
    candidate_path_obj: Path
    reference_metadata_obj: MediaMetadata
    candidate_metadata_obj: MediaMetadata
    output_path_obj: Path | None


@dataclass(slots=True)
class _VideoRunBuffers:
    """Collect verification and optional tracking evidence during one run."""

    frame_results_list: list[FrameVerification] = field(default_factory=list)
    frame_rows_list: list[ReportRow] = field(default_factory=list)
    accepted_rows_list: list[ReportRow] = field(default_factory=list)
    rejected_rows_list: list[ReportRow] = field(default_factory=list)
    failed_frames_list: list[int] = field(default_factory=list)
    tracking_results_list: list[FrameTrackingResult] = field(
        default_factory=list
    )
    tracking_observations_tuple: tuple[TrackObservation, ...] = ()
    tracking_events_tuple: tuple[TrackEvent, ...] = ()
    track_summaries_tuple: tuple[TrackSummary, ...] = ()
    failed_frame_thumbnails_list: list[FrameThumbnail] = field(
        default_factory=list
    )
    target_coverages_list: list[TargetCoverage] = field(default_factory=list)
    target_failed_frames_list: list[int] = field(default_factory=list)
    target_summaries_tuple: tuple[TargetSummary, ...] = ()

    def record(
        self,
        frame_result_obj: FrameVerification,
        tracking_result_obj: FrameTrackingResult | None,
    ) -> None:
        """Record one frame result and its optional tracking evidence."""

        self.frame_results_list.append(frame_result_obj)
        self.frame_rows_list.append(_build_frame_row(frame_result_obj))
        self.accepted_rows_list.extend(
            _build_region_rows(
                frame_result_obj.frame_number,
                frame_result_obj.accepted_regions,
            )
        )
        self.rejected_rows_list.extend(
            _build_region_rows(
                frame_result_obj.frame_number,
                frame_result_obj.rejected_regions,
            )
        )
        if frame_result_obj.failed:
            self.failed_frames_list.append(frame_result_obj.frame_number)
        if tracking_result_obj is not None:
            self.tracking_results_list.append(tracking_result_obj)

    def record_targets(
        self,
        frame_number_int: int,
        coverages_tuple: tuple[TargetCoverage, ...],
    ) -> None:
        """Record target coverage measured for one frame.

        Args:
            frame_number_int: One-based frame number.
            coverages_tuple: Coverage of every target in that frame.
        """

        if not coverages_tuple:
            return
        self.target_coverages_list.extend(coverages_tuple)
        if any(coverage_obj.is_failure for coverage_obj in coverages_tuple):
            self.target_failed_frames_list.append(frame_number_int)

    def finalize_targets(self) -> None:
        """Summarize target coverage once every frame has been read."""

        self.target_summaries_tuple = summarize_targets(
            self.target_coverages_list
        )

    def capture_failed_frame(
        self,
        frame_result_obj: FrameVerification,
        reference_frame_ndarray: ImageArray,
        candidate_frame_ndarray: ImageArray,
    ) -> None:
        """Store thumbnails for one unprotected frame.

        Args:
            frame_result_obj: Completed frame verification.
            reference_frame_ndarray: Original frame.
            candidate_frame_ndarray: Normalized candidate frame.
        """

        if not frame_result_obj.failed:
            return
        if len(self.failed_frame_thumbnails_list) >= (
            MAX_CAPTURED_THUMBNAILS_INT
        ):
            return
        self.failed_frame_thumbnails_list.append(
            FrameThumbnail(
                frame_number=frame_result_obj.frame_number,
                reference_jpeg_bytes=encode_frame_thumbnail(
                    reference_frame_ndarray
                ),
                candidate_jpeg_bytes=encode_frame_thumbnail(
                    candidate_frame_ndarray
                ),
            )
        )

    def finalize_tracking(
        self,
        tracker_obj: TemporalRegionTracker,
    ) -> None:
        """Store completed tracking evidence and calculated summaries."""

        self.tracking_observations_tuple = tracker_obj.observations
        self.tracking_events_tuple = tracker_obj.events
        self.track_summaries_tuple = analyze_tracks(
            tracker_obj.observations,
            tracker_obj.states,
            tracker_obj.events,
        )


@dataclass(slots=True)
class _AnnotatedVideoWriter:
    """Own an optional OpenCV writer and its evidence path."""

    video_writer_obj: cv2.VideoWriter | None = None
    output_path_obj: Path | None = None

    def write(self, frame_ndarray: ImageArray) -> None:
        """Write one annotated frame when output is enabled."""

        if self.video_writer_obj is not None:
            self.video_writer_obj.write(frame_ndarray)

    def close(self) -> None:
        """Release the underlying OpenCV writer when present."""

        if self.video_writer_obj is not None:
            self.video_writer_obj.release()


class VideoVerificationPipeline:
    """Verify one candidate video and optionally track accepted regions."""

    def __init__(
        self,
        *,
        expect_processing_every_frame_bool: bool,
        save_annotated_video_bool: bool,
        save_html_report_bool: bool,
        detection_config_obj: DetectionConfig,
        enable_tracking_bool: bool,
        tracking_config_obj: TrackingConfig,
        targets_tuple: tuple[Target, ...] = (),
        target_config_obj: TargetConfig = DEFAULT_TARGET_CONFIG,
    ) -> None:
        """Initialize the video-verification pipeline."""

        self._expect_processing_every_frame_bool = (
            expect_processing_every_frame_bool
        )
        self._save_annotated_video_bool = save_annotated_video_bool
        self._save_html_report_bool = save_html_report_bool
        self._detection_config_obj = detection_config_obj
        self._enable_tracking_bool = enable_tracking_bool
        self._tracking_config_obj = tracking_config_obj
        self._target_config_obj = target_config_obj
        self._targets_tuple = _prepare_targets(
            targets_tuple, target_config_obj
        )
        self._targets_by_frame_dict = group_targets_by_frame(
            self._targets_tuple
        )

    def run(
        self,
        reference_path_input: PathInput,
        candidate_path_input: PathInput,
        output_dir_input: PathInput | None,
    ) -> VerificationResult:
        """Verify a video pair and optionally write temporal evidence."""

        run_context_obj = _prepare_video_run_context(
            reference_path_input,
            candidate_path_input,
            output_dir_input,
        )
        annotated_writer_obj = self._create_annotated_writer(
            run_context_obj.output_path_obj,
            run_context_obj.reference_metadata_obj,
        )
        tracker_obj = self._create_tracker()
        run_buffers_obj = _VideoRunBuffers()
        last_frame_number_int = self._execute_frame_processing(
            run_context_obj,
            annotated_writer_obj,
            run_buffers_obj,
            tracker_obj,
        )
        if tracker_obj is not None:
            tracker_obj.finish(last_frame_number_int)
            run_buffers_obj.finalize_tracking(tracker_obj)
        run_buffers_obj.finalize_targets()
        result_obj = _build_result_from_context(
            run_context_obj,
            run_buffers_obj,
            self._enable_tracking_bool,
            self._tracking_config_obj,
            bool(self._targets_tuple),
            self._target_config_obj,
        )
        return _write_optional_evidence(
            result_obj,
            run_buffers_obj,
            run_context_obj.output_path_obj,
            annotated_writer_obj.output_path_obj,
            self._enable_tracking_bool,
            self._save_html_report_bool,
        )

    def _create_tracker(self) -> TemporalRegionTracker | None:
        """Create a new tracker session when tracking is enabled."""

        if not self._enable_tracking_bool:
            return None
        return TemporalRegionTracker(self._tracking_config_obj)

    def _execute_frame_processing(
        self,
        run_context_obj: _VideoRunContext,
        annotated_writer_obj: _AnnotatedVideoWriter,
        run_buffers_obj: _VideoRunBuffers,
        tracker_obj: TemporalRegionTracker | None,
    ) -> int:
        """Process frame pairs while guaranteeing writer cleanup."""

        try:
            return self._process_frame_pairs(
                run_context_obj,
                annotated_writer_obj,
                run_buffers_obj,
                tracker_obj,
            )
        finally:
            annotated_writer_obj.close()

    def _create_annotated_writer(
        self,
        output_path_obj: Path | None,
        reference_metadata_obj: MediaMetadata,
    ) -> _AnnotatedVideoWriter:
        """Create the optional annotated-video writer."""

        if output_path_obj is None:
            return _AnnotatedVideoWriter()
        if not self._save_annotated_video_bool:
            return _AnnotatedVideoWriter()
        annotated_path_obj = output_path_obj / ANNOTATED_VIDEO_FILENAME_STR
        return _AnnotatedVideoWriter(
            video_writer_obj=_open_video_writer(
                annotated_path_obj,
                reference_metadata_obj,
            ),
            output_path_obj=annotated_path_obj,
        )

    def _process_frame_pairs(
        self,
        run_context_obj: _VideoRunContext,
        annotated_writer_obj: _AnnotatedVideoWriter,
        run_buffers_obj: _VideoRunBuffers,
        tracker_obj: TemporalRegionTracker | None,
    ) -> int:
        """Process every synchronized frame pair and return the last frame."""

        last_frame_number_int = 0
        for frame_pair_tuple in iter_video_pairs(
            run_context_obj.reference_path_obj,
            run_context_obj.candidate_path_obj,
        ):
            frame_number_int, reference_frame_ndarray, candidate_ndarray = (
                frame_pair_tuple
            )
            last_frame_number_int = frame_number_int
            normalized_candidate_ndarray = resize_candidate_to_reference(
                reference_frame_ndarray,
                candidate_ndarray,
            )
            frame_result_obj, coverages_tuple = self._evaluate_frame(
                frame_number_int,
                run_context_obj.reference_metadata_obj,
                reference_frame_ndarray,
                normalized_candidate_ndarray,
            )
            tracking_result_obj = _update_tracker(
                tracker_obj,
                frame_result_obj,
            )
            run_buffers_obj.record(frame_result_obj, tracking_result_obj)
            run_buffers_obj.record_targets(frame_number_int, coverages_tuple)
            run_buffers_obj.capture_failed_frame(
                frame_result_obj,
                reference_frame_ndarray,
                normalized_candidate_ndarray,
            )
            _write_annotated_frame(
                annotated_writer_obj,
                normalized_candidate_ndarray,
                frame_result_obj,
                tracking_result_obj,
                run_context_obj.reference_metadata_obj.frame_count,
                coverages_tuple,
            )
        return last_frame_number_int

    def _evaluate_frame(
        self,
        frame_number_int: int,
        reference_metadata_obj: MediaMetadata,
        reference_frame_ndarray: ImageArray,
        candidate_frame_ndarray: ImageArray,
    ) -> tuple[FrameVerification, tuple[TargetCoverage, ...]]:
        """Detect regions and evaluate one synchronized frame.

        Args:
            frame_number_int: One-based frame number.
            reference_metadata_obj: Reference media metadata.
            reference_frame_ndarray: Original frame.
            candidate_frame_ndarray: Normalized candidate frame.

        Returns:
            The frame verification and its target coverage, which is
            empty when no targets were supplied.
        """

        accepted_regions_tuple, rejected_regions_tuple = detect_regions(
            reference_frame_ndarray,
            candidate_frame_ndarray,
            self._detection_config_obj,
        )
        coverages_tuple = measure_frame_targets(
            self._targets_by_frame_dict.get(frame_number_int, ()),
            accepted_regions_tuple,
            min_covered_ratio=self._target_config_obj.min_covered_ratio,
        )
        frame_result_obj = FrameVerification(
            frame_number=frame_number_int,
            timestamp_seconds=_calculate_timestamp_seconds(
                frame_number_int,
                reference_metadata_obj.fps,
            ),
            candidate_region_count=(
                len(accepted_regions_tuple) + len(rejected_regions_tuple)
            ),
            accepted_region_count=len(accepted_regions_tuple),
            rejected_region_count=len(rejected_regions_tuple),
            max_severity_score=_maximum_severity(accepted_regions_tuple),
            status=_select_status(
                self._frame_passed(accepted_regions_tuple, coverages_tuple)
            ),
            accepted_regions=accepted_regions_tuple,
            rejected_regions=rejected_regions_tuple,
        )
        return frame_result_obj, coverages_tuple

    def _frame_passed(
        self,
        accepted_regions_tuple: tuple[RegionMeasurement, ...],
        coverages_tuple: tuple[TargetCoverage, ...],
    ) -> bool:
        """Evaluate whether one frame satisfies the active expectation.

        Args:
            accepted_regions_tuple: Accepted processing regions.
            coverages_tuple: Target coverage measured for this frame.

        Returns:
            Whether the frame passes. A frame carrying an uncovered
            required target fails even when other processing occurred,
            which is the whole point of supplying targets.

        Note:
            Unlike tracking, targets deliberately affect the verdict.
            Tracking is evidence; a target is a requirement.
        """

        if self._target_config_obj.fail_on_uncovered_target and any(
            coverage_obj.is_failure for coverage_obj in coverages_tuple
        ):
            return False
        if not self._expect_processing_every_frame_bool:
            return True
        return bool(accepted_regions_tuple)


def verify_video_pipeline(
    reference: PathInput,
    candidate: PathInput,
    *,
    output_dir: PathInput | None,
    expect_processing_every_frame: bool,
    save_annotated_video: bool,
    save_html_report: bool,
    config: DetectionConfig,
    enable_tracking: bool = True,
    tracking_config: TrackingConfig = DEFAULT_TRACKING_CONFIG,
    targets: tuple[Target, ...] = (),
    target_config: TargetConfig = DEFAULT_TARGET_CONFIG,
) -> VerificationResult:
    """Verify one video pair through the modular video pipeline."""

    pipeline_obj = VideoVerificationPipeline(
        expect_processing_every_frame_bool=(expect_processing_every_frame),
        save_annotated_video_bool=save_annotated_video,
        save_html_report_bool=save_html_report,
        detection_config_obj=config,
        enable_tracking_bool=enable_tracking,
        tracking_config_obj=tracking_config,
        targets_tuple=targets,
        target_config_obj=target_config,
    )
    return pipeline_obj.run(reference, candidate, output_dir)


def _prepare_targets(
    targets_tuple: tuple[Target, ...],
    target_config_obj: TargetConfig,
) -> tuple[Target, ...]:
    """Interpolate permitted target gaps before verification starts.

    Args:
        targets_tuple: Reviewed targets, which may be empty.
        target_config_obj: Configuration for this run.

    Returns:
        The targets to verify against, with interpolated boxes marked
        as such so no report can present one as reviewed.
    """

    if not targets_tuple:
        return ()
    if not target_config_obj.interpolate_missing_frames:
        return targets_tuple
    return interpolate_targets(
        targets_tuple,
        max_gap_int=target_config_obj.max_interpolation_gap,
    )


def _prepare_video_run_context(
    reference_path_input: PathInput,
    candidate_path_input: PathInput,
    output_dir_input: PathInput | None,
) -> _VideoRunContext:
    """Resolve paths and read metadata required for one run."""

    reference_path_obj = _resolve_video_path(reference_path_input)
    candidate_path_obj = _resolve_video_path(candidate_path_input)
    return _VideoRunContext(
        reference_path_obj=reference_path_obj,
        candidate_path_obj=candidate_path_obj,
        reference_metadata_obj=read_video_metadata(reference_path_obj),
        candidate_metadata_obj=read_video_metadata(candidate_path_obj),
        output_path_obj=_prepare_output_directory(output_dir_input),
    )


def _resolve_video_path(path_input: PathInput) -> Path:
    """Resolve one user-supplied video path."""

    return Path(path_input).expanduser().resolve()


def _prepare_output_directory(
    output_dir_input: PathInput | None,
) -> Path | None:
    """Create and return the optional evidence-output directory."""

    if output_dir_input is None:
        return None
    output_path_obj = Path(output_dir_input).expanduser().resolve()
    try:
        output_path_obj.mkdir(parents=True, exist_ok=True)
    except OSError as error_obj:
        raise ReportWriteError(
            "Could not prepare the video evidence directory.",
            context_mapping={
                "output_path": str(output_path_obj),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj
    return output_path_obj


def _open_video_writer(
    annotated_path_obj: Path,
    reference_metadata_obj: MediaMetadata,
) -> cv2.VideoWriter:
    """Open an annotated-video writer for the reference geometry.

    Args:
        annotated_path_obj: Destination path for annotated evidence.
        reference_metadata_obj: Reference metadata supplying the output
            frame rate and resolution.

    Returns:
        Open OpenCV writer using the first codec this platform supports.

    Raises:
        ReportWriteError: When no supported codec can be opened.
    """

    return open_annotated_writer(
        annotated_path_obj,
        _select_output_frame_rate(reference_metadata_obj.fps),
        reference_metadata_obj.resolution,
    )


def _select_output_frame_rate(reference_fps_float: float) -> float:
    """Select a valid frame rate for annotated output."""

    if reference_fps_float > 0.0:
        return reference_fps_float
    return FALLBACK_VIDEO_FPS_FLOAT


def _update_tracker(
    tracker_obj: TemporalRegionTracker | None,
    frame_result_obj: FrameVerification,
) -> FrameTrackingResult | None:
    """Update optional tracking state for one completed frame."""

    if tracker_obj is None:
        return None
    return tracker_obj.update(
        frame_result_obj.frame_number,
        frame_result_obj.timestamp_seconds,
        frame_result_obj.accepted_regions,
    )


def _write_annotated_frame(
    annotated_writer_obj: _AnnotatedVideoWriter,
    candidate_frame_ndarray: ImageArray,
    frame_result_obj: FrameVerification,
    tracking_result_obj: FrameTrackingResult | None,
    total_frames_int: int,
    target_coverages_tuple: tuple[TargetCoverage, ...] = (),
) -> None:
    """Annotate and optionally encode one candidate frame.

    Args:
        annotated_writer_obj: Writer, which may be disabled.
        candidate_frame_ndarray: Normalized candidate frame.
        frame_result_obj: Completed frame verification.
        tracking_result_obj: Optional tracking evidence.
        total_frames_int: Frame count shown in the header.
        target_coverages_tuple: Reviewed targets drawn for review.
    """

    if annotated_writer_obj.video_writer_obj is None:
        return
    observations_tuple: tuple[TrackObservation, ...] = ()
    if tracking_result_obj is not None:
        observations_tuple = tracking_result_obj.observations
    annotated_writer_obj.write(
        annotate_frame(
            candidate_frame_ndarray,
            frame_number=frame_result_obj.frame_number,
            total_frames=total_frames_int,
            regions=frame_result_obj.accepted_regions,
            status=frame_result_obj.status,
            tracking_observations=observations_tuple,
            target_coverages=target_coverages_tuple,
        )
    )


def _calculate_timestamp_seconds(
    frame_number_int: int,
    frames_per_second_float: float,
) -> float:
    """Calculate a timestamp from one-based frame numbering."""

    if frames_per_second_float <= 0.0:
        return 0.0
    return round(
        (frame_number_int - 1) / frames_per_second_float,
        6,
    )


def _maximum_severity(
    regions_tuple: tuple[RegionMeasurement, ...],
) -> float:
    """Return maximum accepted-region severity for one frame."""

    return max(
        (region_obj.severity_score for region_obj in regions_tuple),
        default=0.0,
    )


def _select_status(passed_bool: bool) -> VerificationStatus:
    """Convert a policy outcome into a verification status."""

    if passed_bool:
        return VerificationStatus.PASS
    return VerificationStatus.FAIL


def _build_result_from_context(
    run_context_obj: _VideoRunContext,
    run_buffers_obj: _VideoRunBuffers,
    tracking_enabled_bool: bool,
    tracking_config_obj: TrackingConfig,
    targets_enabled_bool: bool = False,
    target_config_obj: TargetConfig = DEFAULT_TARGET_CONFIG,
) -> VerificationResult:
    """Build the final typed video-verification result."""

    failed_frames_tuple = tuple(run_buffers_obj.failed_frames_list)
    policy_name_str = (
        TARGET_VIDEO_POLICY_NAME_STR
        if targets_enabled_bool
        else GENERIC_VIDEO_POLICY_NAME_STR
    )
    return VerificationResult(
        status=_select_status(not failed_frames_tuple),
        reference_path=run_context_obj.reference_path_obj,
        candidate_path=run_context_obj.candidate_path_obj,
        policy_name=policy_name_str,
        failures=_build_failures(failed_frames_tuple, run_buffers_obj),
        failed_frames=failed_frames_tuple,
        measurements=_build_measurements(
            run_context_obj.reference_metadata_obj,
            run_context_obj.candidate_metadata_obj,
            run_buffers_obj,
            tracking_enabled_bool,
            tracking_config_obj,
            targets_enabled_bool,
            target_config_obj,
        ),
    )


def _build_frame_row(
    frame_result_obj: FrameVerification,
) -> ReportRow:
    """Convert one frame result into a CSV row."""

    return {
        "frame_number": frame_result_obj.frame_number,
        "timestamp_seconds": frame_result_obj.timestamp_seconds,
        "candidate_region_count": frame_result_obj.candidate_region_count,
        "accepted_region_count": frame_result_obj.accepted_region_count,
        "rejected_region_count": frame_result_obj.rejected_region_count,
        "max_severity_score": frame_result_obj.max_severity_score,
        "frame_status": frame_result_obj.status.value,
    }


def _build_region_rows(
    frame_number_int: int,
    regions_tuple: tuple[RegionMeasurement, ...],
) -> list[ReportRow]:
    """Convert region measurements into ordered CSV rows."""

    return [
        _build_region_row(frame_number_int, index_int, region_obj)
        for index_int, region_obj in enumerate(regions_tuple, start=1)
    ]


def _build_region_row(
    frame_number_int: int,
    region_index_int: int,
    region_obj: RegionMeasurement,
) -> ReportRow:
    """Convert one region measurement into a CSV row."""

    box_obj = region_obj.box
    return {
        "frame_number": frame_number_int,
        "region_id_in_frame": region_index_int,
        "x1": box_obj.x1,
        "y1": box_obj.y1,
        "x2": box_obj.x2,
        "y2": box_obj.y2,
        "width": box_obj.width,
        "height": box_obj.height,
        "area_px": box_obj.area,
        "changed_pixels": region_obj.changed_pixels,
        "changed_ratio": region_obj.changed_ratio,
        "mean_diff": region_obj.mean_diff,
        "max_diff": region_obj.max_diff,
        "laplacian_reference": region_obj.laplacian_reference,
        "laplacian_candidate": region_obj.laplacian_candidate,
        "sharpness_percentage_candidate_vs_reference": (
            region_obj.sharpness_percentage_candidate_vs_reference
        ),
        "edge_change_ratio": region_obj.edge_change_ratio,
        "severity_score": region_obj.severity_score,
        "severity_label": region_obj.severity_label,
        "accepted": region_obj.accepted,
        "rejection_reasons": list(region_obj.rejection_reasons),
    }


def _build_failures(
    failed_frames_tuple: tuple[int, ...],
    run_buffers_obj: _VideoRunBuffers,
) -> tuple[VerificationFailure, ...]:
    """Build the top-level failure tuple.

    Args:
        failed_frames_tuple: Every frame that failed for any reason.
        run_buffers_obj: Collected evidence, read for target failures.

    Returns:
        One failure per distinct reason, so a report can say whether a
        frame failed because nothing was processed or because a
        required target was left uncovered.
    """

    if not failed_frames_tuple:
        return ()

    target_failed_frozenset = frozenset(
        run_buffers_obj.target_failed_frames_list
    )
    unprocessed_list = [
        frame_int
        for frame_int in failed_frames_tuple
        if frame_int not in target_failed_frozenset
    ]

    failures_list: list[VerificationFailure] = []
    if unprocessed_list:
        failures_list.append(
            VerificationFailure(
                code=UNPROCESSED_FRAMES_FAILURE_CODE_STR,
                message=(
                    "No accepted processing was detected in frames "
                    f"{unprocessed_list}."
                ),
                measurements={"failed_frames": unprocessed_list},
            )
        )
    if target_failed_frozenset:
        failures_list.append(_build_target_failure(run_buffers_obj))
    return tuple(failures_list)


def _build_target_failure(
    run_buffers_obj: _VideoRunBuffers,
) -> VerificationFailure:
    """Describe which required targets were left uncovered.

    Args:
        run_buffers_obj: Collected evidence.

    Returns:
        The target failure, naming the identifiers and the frames.
    """

    failed_frames_list = sorted(set(run_buffers_obj.target_failed_frames_list))
    uncovered_ids_list = sorted(
        {
            coverage_obj.target.target_id
            for coverage_obj in run_buffers_obj.target_coverages_list
            if coverage_obj.is_failure
        }
    )
    return VerificationFailure(
        code=UNCOVERED_TARGETS_FAILURE_CODE_STR,
        message=(
            f"Required targets {uncovered_ids_list} were not covered by "
            f"accepted processing in frames {failed_frames_list}."
        ),
        measurements={
            "failed_frames": failed_frames_list,
            "uncovered_target_ids": uncovered_ids_list,
        },
    )


def _build_measurements(
    reference_metadata_obj: MediaMetadata,
    candidate_metadata_obj: MediaMetadata,
    run_buffers_obj: _VideoRunBuffers,
    tracking_enabled_bool: bool,
    tracking_config_obj: TrackingConfig,
    targets_enabled_bool: bool = False,
    target_config_obj: TargetConfig = DEFAULT_TARGET_CONFIG,
) -> dict[str, object]:
    """Build top-level video and temporal integrity measurements."""

    frames_checked_int = len(run_buffers_obj.frame_results_list)
    processed_frames_int = sum(
        item_obj.accepted_region_count > 0
        for item_obj in run_buffers_obj.frame_results_list
    )
    measurements_dict: dict[str, object] = {
        "reference_metadata": _metadata_to_dict(reference_metadata_obj),
        "candidate_metadata": _metadata_to_dict(candidate_metadata_obj),
        "frames_checked": frames_checked_int,
        "frames_with_processing": processed_frames_int,
        "frames_without_processing": len(run_buffers_obj.failed_frames_list),
        "processing_coverage_percent": _calculate_processing_coverage(
            processed_frames_int,
            frames_checked_int,
        ),
        "accepted_region_count": len(run_buffers_obj.accepted_rows_list),
        "rejected_region_count": len(run_buffers_obj.rejected_rows_list),
        "tracking_enabled": tracking_enabled_bool,
    }
    if tracking_enabled_bool:
        measurements_dict["tracking"] = _build_tracking_measurements(
            run_buffers_obj,
            tracking_config_obj,
        )
    measurements_dict["targets_enabled"] = targets_enabled_bool
    if targets_enabled_bool:
        measurements_dict["targets"] = _build_target_measurements(
            run_buffers_obj,
            target_config_obj,
        )
    return measurements_dict


def _build_target_measurements(
    run_buffers_obj: _VideoRunBuffers,
    target_config_obj: TargetConfig,
) -> dict[str, object]:
    """Return aggregate target coverage metrics and per-target rows.

    Args:
        run_buffers_obj: Collected evidence.
        target_config_obj: Configuration the run used.

    Returns:
        Mapping carrying the configuration, totals, and summaries.
    """

    coverages_list = run_buffers_obj.target_coverages_list
    summaries_tuple = run_buffers_obj.target_summaries_tuple
    covered_int = sum(
        1 for coverage_obj in coverages_list if coverage_obj.covered
    )
    interpolated_int = sum(
        summary_obj.interpolated_frame_count for summary_obj in summaries_tuple
    )
    return {
        "config": {
            "min_covered_ratio": target_config_obj.min_covered_ratio,
            "interpolate_missing_frames": (
                target_config_obj.interpolate_missing_frames
            ),
            "max_interpolation_gap": target_config_obj.max_interpolation_gap,
            "fail_on_uncovered_target": (
                target_config_obj.fail_on_uncovered_target
            ),
        },
        "target_count": len(summaries_tuple),
        "target_frame_count": len(coverages_list),
        "covered_target_frame_count": covered_int,
        "uncovered_target_frame_count": len(coverages_list) - covered_int,
        "interpolated_frame_count": interpolated_int,
        "target_coverage_percent": _calculate_processing_coverage(
            covered_int, len(coverages_list)
        ),
        "target_summaries": [
            summary_obj.to_dict() for summary_obj in summaries_tuple
        ],
    }


def _build_tracking_measurements(
    run_buffers_obj: _VideoRunBuffers,
    tracking_config_obj: TrackingConfig,
) -> dict[str, object]:
    """Return aggregate tracking metrics and serialized summaries."""

    summaries_tuple = run_buffers_obj.track_summaries_tuple
    continuity_values_list = [
        summary_obj.continuity_ratio for summary_obj in summaries_tuple
    ]
    mean_continuity_float = 0.0
    if continuity_values_list:
        mean_continuity_float = round(
            sum(continuity_values_list) / len(continuity_values_list),
            6,
        )
    return {
        "config": tracking_config_obj.to_dict(),
        "track_count": len(summaries_tuple),
        "observation_count": len(run_buffers_obj.tracking_observations_tuple),
        "event_count": len(run_buffers_obj.tracking_events_tuple),
        "tracks_with_gaps": sum(
            summary_obj.gap_count > 0 for summary_obj in summaries_tuple
        ),
        "mean_continuity_ratio": mean_continuity_float,
        "track_summaries": [
            summary_obj.to_dict() for summary_obj in summaries_tuple
        ],
    }


def _calculate_processing_coverage(
    processed_frames_int: int,
    frames_checked_int: int,
) -> float:
    """Calculate percentage of frames containing accepted processing."""

    if frames_checked_int <= 0:
        return 0.0
    return round(processed_frames_int / frames_checked_int * 100.0, 2)


def _metadata_to_dict(
    metadata_obj: MediaMetadata,
) -> dict[str, int | float]:
    """Convert video metadata into the established report schema."""

    return {
        "frame_count": metadata_obj.frame_count,
        "fps": metadata_obj.fps,
        "width": metadata_obj.width,
        "height": metadata_obj.height,
    }


def _write_optional_evidence(
    result_obj: VerificationResult,
    run_buffers_obj: _VideoRunBuffers,
    output_path_obj: Path | None,
    annotated_path_obj: Path | None,
    tracking_enabled_bool: bool,
    html_report_enabled_bool: bool,
) -> VerificationResult:
    """Write requested evidence and enrich the immutable result.

    Every evidence path is resolved before ``summary.json`` is written, so
    the machine-readable document describes each file written beside it.

    Args:
        result_obj: Verification result before evidence is attached.
        run_buffers_obj: Collected frame, region, and tracking evidence.
        output_path_obj: Evidence directory, or ``None`` to write nothing.
        annotated_path_obj: Annotated video path when one was written.
        tracking_enabled_bool: Whether temporal reports were produced.
        html_report_enabled_bool: Whether to write the HTML report.

    Returns:
        Result enriched with every generated evidence path.
    """

    if output_path_obj is None:
        return result_obj
    evidence_paths_dict = _resolve_evidence_paths(
        run_buffers_obj,
        output_path_obj,
        annotated_path_obj,
        tracking_enabled_bool,
        html_report_enabled_bool,
    )
    enriched_result_obj = result_obj.with_evidence_paths(evidence_paths_dict)
    write_json_report(
        enriched_result_obj.to_dict(),
        evidence_paths_dict["summary_json"],
    )
    if html_report_enabled_bool:
        write_html_report(
            enriched_result_obj,
            run_buffers_obj.frame_results_list,
            run_buffers_obj.failed_frame_thumbnails_list,
            evidence_paths_dict["html_report"],
        )
    return enriched_result_obj


def _resolve_evidence_paths(
    run_buffers_obj: _VideoRunBuffers,
    output_path_obj: Path,
    annotated_path_obj: Path | None,
    tracking_enabled_bool: bool,
    html_report_enabled_bool: bool,
) -> dict[str, Path]:
    """Write tabular evidence and resolve every generated file path.

    Args:
        run_buffers_obj: Collected frame, region, and tracking evidence.
        output_path_obj: Evidence directory for this run.
        annotated_path_obj: Annotated video path when one was written.
        tracking_enabled_bool: Whether temporal reports were produced.
        html_report_enabled_bool: Whether an HTML report is written.

    Returns:
        Named paths for every evidence file in this run.
    """

    evidence_paths_dict = _write_tabular_evidence(
        run_buffers_obj,
        output_path_obj,
    )
    if tracking_enabled_bool:
        evidence_paths_dict.update(
            write_tracking_reports(
                run_buffers_obj.track_summaries_tuple,
                run_buffers_obj.tracking_observations_tuple,
                run_buffers_obj.tracking_events_tuple,
                output_path_obj,
            )
        )
    if run_buffers_obj.target_coverages_list:
        evidence_paths_dict["target_report"] = _write_target_evidence(
            run_buffers_obj, output_path_obj
        )
    if annotated_path_obj is not None:
        evidence_paths_dict["annotated_video"] = annotated_path_obj
    if html_report_enabled_bool:
        evidence_paths_dict["html_report"] = (
            output_path_obj / HTML_REPORT_FILENAME_STR
        )
    evidence_paths_dict["summary_json"] = (
        output_path_obj / SUMMARY_REPORT_FILENAME_STR
    )
    return evidence_paths_dict


def _write_target_evidence(
    run_buffers_obj: _VideoRunBuffers,
    output_path_obj: Path,
) -> Path:
    """Write one row per target per frame.

    Args:
        run_buffers_obj: Collected evidence.
        output_path_obj: Evidence directory for this run.

    Returns:
        Path to the written target report.
    """

    return write_csv_report(
        [
            coverage_obj.to_dict()
            for coverage_obj in run_buffers_obj.target_coverages_list
        ],
        output_path_obj / TARGET_REPORT_FILENAME_STR,
    )


def _write_tabular_evidence(
    run_buffers_obj: _VideoRunBuffers,
    output_path_obj: Path,
) -> dict[str, Path]:
    """Write frame, accepted-region, and rejected-region CSV reports."""

    return {
        "frame_report": write_csv_report(
            run_buffers_obj.frame_rows_list,
            output_path_obj / FRAME_REPORT_FILENAME_STR,
        ),
        "region_report": write_csv_report(
            run_buffers_obj.accepted_rows_list,
            output_path_obj / REGION_REPORT_FILENAME_STR,
        ),
        "rejected_region_report": write_csv_report(
            run_buffers_obj.rejected_rows_list,
            output_path_obj / REJECTED_REGION_REPORT_FILENAME_STR,
        ),
    }


__all__ = [
    "VideoVerificationPipeline",
    "verify_video_pipeline",
]
