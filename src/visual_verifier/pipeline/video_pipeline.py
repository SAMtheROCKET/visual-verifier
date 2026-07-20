"""Run reference-based verification for one video pair."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2

from visual_verifier.detection.region_extraction import detect_regions
from visual_verifier.exceptions import ReportWriteError
from visual_verifier.media.metadata import read_video_metadata
from visual_verifier.media.normalization import (
    resize_candidate_to_reference,
)
from visual_verifier.media.video_reader import iter_video_pairs
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
from visual_verifier.reporting.json_report import write_json_report
from visual_verifier.type_aliases import ImageArray, PathInput, ReportRow

VIDEO_CODEC_TEXT = "mp4v"
FALLBACK_VIDEO_FPS_FLOAT = 30.0
GENERIC_VIDEO_POLICY_NAME_STR = "generic_change_every_frame"
UNPROCESSED_FRAMES_FAILURE_CODE_STR = "UNPROCESSED_FRAMES"
ANNOTATED_VIDEO_FILENAME_STR = "annotated_video.mp4"
FRAME_REPORT_FILENAME_STR = "frame_report.csv"
REGION_REPORT_FILENAME_STR = "region_report.csv"
REJECTED_REGION_REPORT_FILENAME_STR = "rejected_region_report.csv"
SUMMARY_REPORT_FILENAME_STR = "summary.json"


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
    """Collect frame, region, and failure data during one run."""

    frame_results_list: list[FrameVerification] = field(default_factory=list)
    frame_rows_list: list[ReportRow] = field(default_factory=list)
    accepted_rows_list: list[ReportRow] = field(default_factory=list)
    rejected_rows_list: list[ReportRow] = field(default_factory=list)
    failed_frames_list: list[int] = field(default_factory=list)

    def record(self, frame_result_obj: FrameVerification) -> None:
        """Record one frame result and its tabular report rows.

        Args:
            frame_result_obj: Completed verification result for one frame.
        """

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


@dataclass(slots=True)
class _AnnotatedVideoWriter:
    """Own an optional OpenCV writer and its evidence path."""

    video_writer_obj: cv2.VideoWriter | None = None
    output_path_obj: Path | None = None

    def write(self, frame_ndarray: ImageArray) -> None:
        """Write one annotated frame when output is enabled.

        Args:
            frame_ndarray: Annotated video frame to encode.
        """

        if self.video_writer_obj is None:
            return
        self.video_writer_obj.write(frame_ndarray)

    def close(self) -> None:
        """Release the underlying OpenCV writer when present."""

        if self.video_writer_obj is not None:
            self.video_writer_obj.release()


class VideoVerificationPipeline:
    """Verify one candidate video against one reference video."""

    def __init__(
        self,
        *,
        expect_processing_every_frame_bool: bool,
        save_annotated_video_bool: bool,
        detection_config_obj: DetectionConfig,
    ) -> None:
        """Initialize the video-verification pipeline.

        Args:
            expect_processing_every_frame_bool: Require an accepted region
                in every synchronized frame.
            save_annotated_video_bool: Write an annotated MP4 when evidence
                output is enabled.
            detection_config_obj: Region-detection thresholds.
        """

        self._expect_processing_every_frame_bool = (
            expect_processing_every_frame_bool
        )
        self._save_annotated_video_bool = save_annotated_video_bool
        self._detection_config_obj = detection_config_obj

    def run(
        self,
        reference_path_input: PathInput,
        candidate_path_input: PathInput,
        output_dir_input: PathInput | None,
    ) -> VerificationResult:
        """Verify a video pair and optionally write evidence.

        Args:
            reference_path_input: Path to the original video.
            candidate_path_input: Path to the processed video.
            output_dir_input: Optional evidence-output directory.

        Returns:
            Final typed video-verification result.

        Raises:
            ReportWriteError: If evidence output cannot be prepared.

        Warning:
            Frames are synchronized by index in this foundation phase.
        """

        run_context_obj = _prepare_video_run_context(
            reference_path_input,
            candidate_path_input,
            output_dir_input,
        )
        annotated_writer_obj = self._create_annotated_writer(
            run_context_obj.output_path_obj,
            run_context_obj.reference_metadata_obj,
        )
        run_buffers_obj = _VideoRunBuffers()
        self._execute_frame_processing(
            run_context_obj,
            annotated_writer_obj,
            run_buffers_obj,
        )
        result_obj = _build_result_from_context(
            run_context_obj,
            run_buffers_obj,
        )
        return _write_optional_evidence(
            result_obj,
            run_buffers_obj,
            run_context_obj.output_path_obj,
            annotated_writer_obj.output_path_obj,
        )

    def _execute_frame_processing(
        self,
        run_context_obj: _VideoRunContext,
        annotated_writer_obj: _AnnotatedVideoWriter,
        run_buffers_obj: _VideoRunBuffers,
    ) -> None:
        """Process frame pairs while guaranteeing writer cleanup.

        Args:
            run_context_obj: Resolved paths and metadata for the run.
            annotated_writer_obj: Optional annotated-video writer.
            run_buffers_obj: Mutable run-level evidence buffers.
        """

        try:
            self._process_frame_pairs(
                run_context_obj.reference_path_obj,
                run_context_obj.candidate_path_obj,
                run_context_obj.reference_metadata_obj,
                annotated_writer_obj,
                run_buffers_obj,
            )
        finally:
            annotated_writer_obj.close()

    def _create_annotated_writer(
        self,
        output_path_obj: Path | None,
        reference_metadata_obj: MediaMetadata,
    ) -> _AnnotatedVideoWriter:
        """Create the optional annotated-video writer.

        Args:
            output_path_obj: Optional evidence-output directory.
            reference_metadata_obj: Reference video dimensions and timing.

        Returns:
            Writer wrapper, disabled when output was not requested.

        Raises:
            ReportWriteError: If OpenCV cannot initialize the writer.
        """

        if output_path_obj is None:
            return _AnnotatedVideoWriter()
        if not self._save_annotated_video_bool:
            return _AnnotatedVideoWriter()

        annotated_path_obj = output_path_obj / ANNOTATED_VIDEO_FILENAME_STR
        video_writer_obj = _open_video_writer(
            annotated_path_obj,
            reference_metadata_obj,
        )
        return _AnnotatedVideoWriter(
            video_writer_obj=video_writer_obj,
            output_path_obj=annotated_path_obj,
        )

    def _process_frame_pairs(
        self,
        reference_path_obj: Path,
        candidate_path_obj: Path,
        reference_metadata_obj: MediaMetadata,
        annotated_writer_obj: _AnnotatedVideoWriter,
        run_buffers_obj: _VideoRunBuffers,
    ) -> None:
        """Process every synchronized frame pair.

        Args:
            reference_path_obj: Resolved reference-video path.
            candidate_path_obj: Resolved candidate-video path.
            reference_metadata_obj: Reference video metadata.
            annotated_writer_obj: Optional annotated-frame writer.
            run_buffers_obj: Mutable run-level evidence buffers.
        """

        for frame_pair_tuple in iter_video_pairs(
            reference_path_obj,
            candidate_path_obj,
        ):
            (
                frame_number_int,
                reference_frame_ndarray,
                candidate_frame_ndarray,
            ) = frame_pair_tuple
            normalized_candidate_ndarray = resize_candidate_to_reference(
                reference_frame_ndarray,
                candidate_frame_ndarray,
            )
            frame_result_obj = self._evaluate_frame(
                frame_number_int,
                reference_metadata_obj,
                reference_frame_ndarray,
                normalized_candidate_ndarray,
            )
            run_buffers_obj.record(frame_result_obj)
            _write_annotated_frame(
                annotated_writer_obj,
                normalized_candidate_ndarray,
                frame_result_obj,
                reference_metadata_obj.frame_count,
            )

    def _evaluate_frame(
        self,
        frame_number_int: int,
        reference_metadata_obj: MediaMetadata,
        reference_frame_ndarray: ImageArray,
        candidate_frame_ndarray: ImageArray,
    ) -> FrameVerification:
        """Detect regions and evaluate one synchronized frame.

        Args:
            frame_number_int: One-based frame number.
            reference_metadata_obj: Reference video timing metadata.
            reference_frame_ndarray: Original video frame.
            candidate_frame_ndarray: Size-normalized candidate frame.

        Returns:
            Typed frame-level verification result.
        """

        accepted_regions_tuple, rejected_regions_tuple = detect_regions(
            reference_frame_ndarray,
            candidate_frame_ndarray,
            self._detection_config_obj,
        )
        frame_passed_bool = self._frame_passed(accepted_regions_tuple)
        return FrameVerification(
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
            status=_select_status(frame_passed_bool),
            accepted_regions=accepted_regions_tuple,
            rejected_regions=rejected_regions_tuple,
        )

    def _frame_passed(
        self,
        accepted_regions_tuple: tuple[RegionMeasurement, ...],
    ) -> bool:
        """Evaluate whether one frame satisfies the active expectation.

        Args:
            accepted_regions_tuple: Regions accepted by detection policy.

        Returns:
            ``True`` when processing is optional or was detected.
        """

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
    config: DetectionConfig,
) -> VerificationResult:
    """Verify one video pair through the modular video pipeline.

    Args:
        reference: Path to the original video.
        candidate: Path to the processed video.
        output_dir: Optional directory for generated evidence.
        expect_processing_every_frame: Require processing in every frame.
        save_annotated_video: Write annotated video evidence.
        config: Region-detection thresholds.

    Returns:
        Typed video-verification result.
    """

    pipeline_obj = VideoVerificationPipeline(
        expect_processing_every_frame_bool=(expect_processing_every_frame),
        save_annotated_video_bool=save_annotated_video,
        detection_config_obj=config,
    )
    return pipeline_obj.run(reference, candidate, output_dir)


def _prepare_video_run_context(
    reference_path_input: PathInput,
    candidate_path_input: PathInput,
    output_dir_input: PathInput | None,
) -> _VideoRunContext:
    """Resolve paths and read metadata required for one run.

    Args:
        reference_path_input: Path to the original video.
        candidate_path_input: Path to the processed video.
        output_dir_input: Optional evidence-output directory.

    Returns:
        Immutable run context containing paths and metadata.
    """

    reference_path_obj = _resolve_video_path(reference_path_input)
    candidate_path_obj = _resolve_video_path(candidate_path_input)
    return _VideoRunContext(
        reference_path_obj=reference_path_obj,
        candidate_path_obj=candidate_path_obj,
        reference_metadata_obj=read_video_metadata(reference_path_obj),
        candidate_metadata_obj=read_video_metadata(candidate_path_obj),
        output_path_obj=_prepare_output_directory(output_dir_input),
    )


def _build_result_from_context(
    run_context_obj: _VideoRunContext,
    run_buffers_obj: _VideoRunBuffers,
) -> VerificationResult:
    """Build a result from one prepared run context.

    Args:
        run_context_obj: Resolved paths and metadata for the run.
        run_buffers_obj: Collected frame and region evidence.

    Returns:
        Verification result without optional evidence paths.
    """

    return _build_verification_result(
        run_context_obj.reference_path_obj,
        run_context_obj.candidate_path_obj,
        run_context_obj.reference_metadata_obj,
        run_context_obj.candidate_metadata_obj,
        run_buffers_obj,
    )


def _resolve_video_path(path_input: PathInput) -> Path:
    """Resolve one user-supplied video path.

    Args:
        path_input: User-provided filesystem path.

    Returns:
        Absolute, expanded filesystem path.
    """

    return Path(path_input).expanduser().resolve()


def _prepare_output_directory(
    output_dir_input: PathInput | None,
) -> Path | None:
    """Create and return the optional evidence-output directory.

    Args:
        output_dir_input: Optional user-provided output directory.

    Returns:
        Resolved output directory, or ``None`` when disabled.

    Raises:
        ReportWriteError: If the directory cannot be created.
    """

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
    """Open and validate an OpenCV annotated-video writer.

    Args:
        annotated_path_obj: Destination MP4 path.
        reference_metadata_obj: Reference dimensions and frame rate.

    Returns:
        Open OpenCV video writer.

    Raises:
        ReportWriteError: If the writer cannot be opened.
    """

    codec_int = _build_video_codec()
    frames_per_second_float = _select_output_frame_rate(
        reference_metadata_obj.fps
    )
    video_writer_obj = cv2.VideoWriter(
        str(annotated_path_obj),
        codec_int,
        frames_per_second_float,
        reference_metadata_obj.resolution,
    )
    if video_writer_obj.isOpened():
        return video_writer_obj

    video_writer_obj.release()
    raise ReportWriteError(
        "Could not open the annotated-video writer.",
        context_mapping={
            "output_path": str(annotated_path_obj),
            "codec": VIDEO_CODEC_TEXT,
            "fps": frames_per_second_float,
            "resolution": reference_metadata_obj.resolution,
        },
    )


def _build_video_codec() -> int:
    """Build the OpenCV four-character video-codec identifier.

    Returns:
        Integer codec identifier for the configured MP4 codec.
    """

    return cv2.VideoWriter.fourcc(
        VIDEO_CODEC_TEXT[0],
        VIDEO_CODEC_TEXT[1],
        VIDEO_CODEC_TEXT[2],
        VIDEO_CODEC_TEXT[3],
    )


def _select_output_frame_rate(reference_fps_float: float) -> float:
    """Select a valid frame rate for annotated output.

    Args:
        reference_fps_float: Frame rate reported for the reference video.

    Returns:
        Reference frame rate when positive, otherwise the fallback rate.
    """

    if reference_fps_float > 0.0:
        return reference_fps_float
    return FALLBACK_VIDEO_FPS_FLOAT


def _write_annotated_frame(
    annotated_writer_obj: _AnnotatedVideoWriter,
    candidate_frame_ndarray: ImageArray,
    frame_result_obj: FrameVerification,
    total_frames_int: int,
) -> None:
    """Annotate and optionally encode one candidate frame.

    Args:
        annotated_writer_obj: Optional output writer.
        candidate_frame_ndarray: Size-normalized candidate frame.
        frame_result_obj: Verification evidence for the frame.
        total_frames_int: Reference frame count used in the header.
    """

    if annotated_writer_obj.video_writer_obj is None:
        return

    annotated_frame_ndarray = annotate_frame(
        candidate_frame_ndarray,
        frame_number=frame_result_obj.frame_number,
        total_frames=total_frames_int,
        regions=frame_result_obj.accepted_regions,
        status=frame_result_obj.status,
    )
    annotated_writer_obj.write(annotated_frame_ndarray)


def _calculate_timestamp_seconds(
    frame_number_int: int,
    frames_per_second_float: float,
) -> float:
    """Calculate a timestamp from one-based frame numbering.

    Args:
        frame_number_int: One-based frame number.
        frames_per_second_float: Reference video frame rate.

    Returns:
        Rounded timestamp in seconds, or zero when timing is unavailable.
    """

    if frames_per_second_float <= 0.0:
        return 0.0
    timestamp_seconds_float = (frame_number_int - 1) / frames_per_second_float
    return round(timestamp_seconds_float, 6)


def _maximum_severity(
    regions_tuple: tuple[RegionMeasurement, ...],
) -> float:
    """Return the maximum accepted-region severity for one frame.

    Args:
        regions_tuple: Accepted region measurements.

    Returns:
        Maximum severity score, or zero when no region was accepted.
    """

    return max(
        (region_obj.severity_score for region_obj in regions_tuple),
        default=0.0,
    )


def _select_status(passed_bool: bool) -> VerificationStatus:
    """Convert a policy outcome into a verification status.

    Args:
        passed_bool: Whether the evaluated scope passed.

    Returns:
        ``PASS`` for true outcomes and ``FAIL`` otherwise.
    """

    if passed_bool:
        return VerificationStatus.PASS
    return VerificationStatus.FAIL


def _build_verification_result(
    reference_path_obj: Path,
    candidate_path_obj: Path,
    reference_metadata_obj: MediaMetadata,
    candidate_metadata_obj: MediaMetadata,
    run_buffers_obj: _VideoRunBuffers,
) -> VerificationResult:
    """Build the final typed video-verification result.

    Args:
        reference_path_obj: Resolved reference-video path.
        candidate_path_obj: Resolved candidate-video path.
        reference_metadata_obj: Reference video metadata.
        candidate_metadata_obj: Candidate video metadata.
        run_buffers_obj: Collected frame and region evidence.

    Returns:
        Verification result without optional evidence paths.
    """

    failed_frames_tuple = tuple(run_buffers_obj.failed_frames_list)
    return VerificationResult(
        status=_select_status(not failed_frames_tuple),
        reference_path=reference_path_obj,
        candidate_path=candidate_path_obj,
        policy_name=GENERIC_VIDEO_POLICY_NAME_STR,
        failures=_build_failures(failed_frames_tuple),
        failed_frames=failed_frames_tuple,
        measurements=_build_measurements(
            reference_metadata_obj,
            candidate_metadata_obj,
            run_buffers_obj,
        ),
    )


def _build_frame_row(
    frame_result_obj: FrameVerification,
) -> ReportRow:
    """Convert one frame result into a CSV row.

    Args:
        frame_result_obj: Completed frame-level verification result.

    Returns:
        Ordered frame-report row.
    """

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
    """Convert region measurements into ordered CSV rows.

    Args:
        frame_number_int: One-based source frame number.
        regions_tuple: Region measurements in detection order.

    Returns:
        One report row per region.
    """

    return [
        _build_region_row(
            frame_number_int,
            region_index_int,
            region_obj,
        )
        for region_index_int, region_obj in enumerate(
            regions_tuple,
            start=1,
        )
    ]


def _build_region_row(
    frame_number_int: int,
    region_index_int: int,
    region_obj: RegionMeasurement,
) -> ReportRow:
    """Convert one region measurement into a CSV row.

    Args:
        frame_number_int: One-based source frame number.
        region_index_int: One-based region number within the frame.
        region_obj: Region measurements and decision evidence.

    Returns:
        Ordered region-report row.
    """

    bounding_box_obj = region_obj.box
    return {
        "frame_number": frame_number_int,
        "region_id_in_frame": region_index_int,
        "x1": bounding_box_obj.x1,
        "y1": bounding_box_obj.y1,
        "x2": bounding_box_obj.x2,
        "y2": bounding_box_obj.y2,
        "width": bounding_box_obj.width,
        "height": bounding_box_obj.height,
        "area_px": bounding_box_obj.area,
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
) -> tuple[VerificationFailure, ...]:
    """Build the top-level failure tuple.

    Args:
        failed_frames_tuple: Frames without accepted processing regions.

    Returns:
        Empty tuple for success, otherwise one aggregate failure.
    """

    if not failed_frames_tuple:
        return ()

    failed_frames_list = list(failed_frames_tuple)
    return (
        VerificationFailure(
            code=UNPROCESSED_FRAMES_FAILURE_CODE_STR,
            message=(
                "No accepted processing was detected in frames "
                f"{failed_frames_list}."
            ),
            measurements={"failed_frames": failed_frames_list},
        ),
    )


def _build_measurements(
    reference_metadata_obj: MediaMetadata,
    candidate_metadata_obj: MediaMetadata,
    run_buffers_obj: _VideoRunBuffers,
) -> dict[str, object]:
    """Build top-level video measurements.

    Args:
        reference_metadata_obj: Reference video metadata.
        candidate_metadata_obj: Candidate video metadata.
        run_buffers_obj: Collected frame and region evidence.

    Returns:
        Ordered, report-safe video measurements.
    """

    frames_checked_int = len(run_buffers_obj.frame_results_list)
    processed_frames_int = sum(
        frame_result_obj.accepted_region_count > 0
        for frame_result_obj in run_buffers_obj.frame_results_list
    )
    coverage_percent_float = _calculate_processing_coverage(
        processed_frames_int,
        frames_checked_int,
    )
    return {
        "reference_metadata": _metadata_to_dict(reference_metadata_obj),
        "candidate_metadata": _metadata_to_dict(candidate_metadata_obj),
        "frames_checked": frames_checked_int,
        "frames_with_processing": processed_frames_int,
        "frames_without_processing": len(run_buffers_obj.failed_frames_list),
        "processing_coverage_percent": coverage_percent_float,
        "accepted_region_count": len(run_buffers_obj.accepted_rows_list),
        "rejected_region_count": len(run_buffers_obj.rejected_rows_list),
    }


def _calculate_processing_coverage(
    processed_frames_int: int,
    frames_checked_int: int,
) -> float:
    """Calculate the percentage of frames containing processing.

    Args:
        processed_frames_int: Frames with one or more accepted regions.
        frames_checked_int: Total synchronized frames evaluated.

    Returns:
        Processing coverage rounded to two decimal places.
    """

    if frames_checked_int <= 0:
        return 0.0
    coverage_percent_float = processed_frames_int / frames_checked_int * 100.0
    return round(coverage_percent_float, 2)


def _metadata_to_dict(
    metadata_obj: MediaMetadata,
) -> dict[str, int | float]:
    """Convert video metadata into the established report schema.

    Args:
        metadata_obj: Normalized media metadata.

    Returns:
        Frame count, frame rate, width, and height values.
    """

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
) -> VerificationResult:
    """Write requested evidence and enrich the immutable result.

    Args:
        result_obj: Verification result without evidence paths.
        run_buffers_obj: Collected frame and region evidence.
        output_path_obj: Optional evidence-output directory.
        annotated_path_obj: Optional annotated-video path.

    Returns:
        Original result when output is disabled, otherwise an enriched copy.
    """

    if output_path_obj is None:
        return result_obj

    evidence_paths_dict = _write_report_files(
        result_obj,
        run_buffers_obj,
        output_path_obj,
        annotated_path_obj,
    )
    return result_obj.with_evidence_paths(evidence_paths_dict)


def _write_report_files(
    result_obj: VerificationResult,
    run_buffers_obj: _VideoRunBuffers,
    output_path_obj: Path,
    annotated_path_obj: Path | None,
) -> dict[str, Path]:
    """Write all video evidence files.

    Args:
        result_obj: Verification result to serialize.
        run_buffers_obj: Collected tabular evidence.
        output_path_obj: Evidence-output directory.
        annotated_path_obj: Optional annotated-video path.

    Returns:
        Named paths for every generated evidence file.
    """

    evidence_paths_dict = _write_tabular_evidence(
        run_buffers_obj,
        output_path_obj,
    )
    evidence_paths_dict["summary_json"] = write_json_report(
        result_obj.to_dict(),
        output_path_obj / SUMMARY_REPORT_FILENAME_STR,
    )
    if annotated_path_obj is not None:
        evidence_paths_dict["annotated_video"] = annotated_path_obj
    return evidence_paths_dict


def _write_tabular_evidence(
    run_buffers_obj: _VideoRunBuffers,
    output_path_obj: Path,
) -> dict[str, Path]:
    """Write frame, accepted-region, and rejected-region CSV reports.

    Args:
        run_buffers_obj: Collected tabular evidence.
        output_path_obj: Evidence-output directory.

    Returns:
        Named paths for the three CSV reports.
    """

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
