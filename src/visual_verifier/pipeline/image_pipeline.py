"""Run reference-based verification for one image pair."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import cv2

from visual_verifier.detection.region_extraction import detect_regions
from visual_verifier.exceptions import MediaReadError, ReportWriteError
from visual_verifier.media.normalization import (
    resize_candidate_to_reference,
)
from visual_verifier.models import (
    DetectionConfig,
    RegionMeasurement,
    VerificationFailure,
    VerificationResult,
    VerificationStatus,
)
from visual_verifier.reporting.annotations import annotate_frame
from visual_verifier.reporting.csv_report import write_csv_report
from visual_verifier.reporting.json_report import write_json_report
from visual_verifier.type_aliases import ImageArray, PathInput, ReportRow

GENERIC_CHANGE_POLICY_NAME_STR = "generic_change"
NO_PROCESSING_FAILURE_CODE_STR = "NO_PROCESSING_DETECTED"
NO_PROCESSING_FAILURE_MESSAGE_STR = (
    "No accepted visual-processing region was detected."
)
ANNOTATED_IMAGE_FILENAME_STR = "annotated_image.png"
REGION_REPORT_FILENAME_STR = "region_report.csv"
SUMMARY_REPORT_FILENAME_STR = "summary.json"
IMAGE_READ_MODE_INT = cv2.IMREAD_COLOR
SINGLE_IMAGE_FRAME_NUMBER_INT = 1
SINGLE_IMAGE_TOTAL_FRAMES_INT = 1


class ImageVerificationPipeline:
    """Verify one candidate image against one reference image."""

    def __init__(
        self,
        *,
        expect_processing_bool: bool,
        detection_config_obj: DetectionConfig,
    ) -> None:
        """Initialize the image-verification pipeline.

        Args:
            expect_processing_bool: Require at least one accepted region.
            detection_config_obj: Region-detection thresholds.
        """

        self._expect_processing_bool = expect_processing_bool
        self._detection_config_obj = detection_config_obj

    def run(
        self,
        reference_path_input: PathInput,
        candidate_path_input: PathInput,
        output_dir_input: PathInput | None,
    ) -> VerificationResult:
        """Verify an image pair and optionally write evidence.

        Args:
            reference_path_input: Path to the original image.
            candidate_path_input: Path to the processed image.
            output_dir_input: Optional evidence directory.

        Returns:
            Final typed verification result.

        Raises:
            MediaReadError: If either image cannot be decoded.
            ReportWriteError: If requested evidence cannot be written.
        """

        reference_path_obj = _resolve_image_path(reference_path_input)
        candidate_path_obj = _resolve_image_path(candidate_path_input)
        reference_image_ndarray = _read_image(reference_path_obj)
        candidate_image_ndarray = _read_image(candidate_path_obj)
        normalized_candidate_ndarray = resize_candidate_to_reference(
            reference_image_ndarray,
            candidate_image_ndarray,
        )
        accepted_regions_tuple, rejected_regions_tuple = detect_regions(
            reference_image_ndarray,
            normalized_candidate_ndarray,
            self._detection_config_obj,
        )
        result_obj = self._build_result(
            reference_path_obj,
            candidate_path_obj,
            accepted_regions_tuple,
            rejected_regions_tuple,
        )
        return _write_optional_evidence(
            result_obj,
            normalized_candidate_ndarray,
            accepted_regions_tuple,
            output_dir_input,
        )

    def _build_result(
        self,
        reference_path_obj: Path,
        candidate_path_obj: Path,
        accepted_regions_tuple: tuple[RegionMeasurement, ...],
        rejected_regions_tuple: tuple[RegionMeasurement, ...],
    ) -> VerificationResult:
        """Build the typed image-verification result.

        Args:
            reference_path_obj: Resolved reference-image path.
            candidate_path_obj: Resolved candidate-image path.
            accepted_regions_tuple: Regions accepted by detection policy.
            rejected_regions_tuple: Regions rejected as insufficient change.

        Returns:
            Verification result without optional evidence paths.
        """

        passed_bool = self._determine_passed(accepted_regions_tuple)
        status_enum = _select_verification_status(passed_bool)
        failures_tuple = _build_failures(passed_bool)
        measurements_dict: dict[str, object] = {
            "accepted_region_count": len(accepted_regions_tuple),
            "rejected_region_count": len(rejected_regions_tuple),
        }
        return VerificationResult(
            status=status_enum,
            reference_path=reference_path_obj,
            candidate_path=candidate_path_obj,
            policy_name=GENERIC_CHANGE_POLICY_NAME_STR,
            failures=failures_tuple,
            measurements=measurements_dict,
        )

    def _determine_passed(
        self,
        accepted_regions_tuple: tuple[RegionMeasurement, ...],
    ) -> bool:
        """Evaluate the image-level processing expectation.

        Args:
            accepted_regions_tuple: Regions accepted by detection policy.

        Returns:
            ``True`` when the configured expectation is satisfied.
        """

        if not self._expect_processing_bool:
            return True
        return bool(accepted_regions_tuple)


def verify_image_pipeline(
    reference: PathInput,
    candidate: PathInput,
    *,
    output_dir: PathInput | None,
    expect_processing: bool,
    config: DetectionConfig,
) -> VerificationResult:
    """Verify one image pair through the modular image pipeline.

    Args:
        reference: Path to the original image.
        candidate: Path to the processed image.
        output_dir: Optional directory for generated evidence.
        expect_processing: Require at least one accepted changed region.
        config: Region-detection thresholds.

    Returns:
        Typed image-verification result.

    Raises:
        MediaReadError: If either image cannot be decoded.
        ReportWriteError: If requested evidence cannot be written.
    """

    pipeline_obj = ImageVerificationPipeline(
        expect_processing_bool=expect_processing,
        detection_config_obj=config,
    )
    return pipeline_obj.run(reference, candidate, output_dir)


def _resolve_image_path(path_input: PathInput) -> Path:
    """Resolve a user-supplied image path.

    Args:
        path_input: User-provided image path.

    Returns:
        Absolute, expanded filesystem path.
    """

    return Path(path_input).expanduser().resolve()


def _read_image(image_path_obj: Path) -> ImageArray:
    """Decode one image from disk.

    Args:
        image_path_obj: Resolved path to the image.

    Returns:
        Decoded three-channel ``uint8`` image.

    Raises:
        MediaReadError: If the path is not a file or decoding fails.
    """

    if not image_path_obj.is_file():
        raise _create_image_read_error(
            "Image file does not exist.",
            image_path_obj,
        )

    image_ndarray = cv2.imread(
        str(image_path_obj),
        IMAGE_READ_MODE_INT,
    )
    if image_ndarray is None:
        raise _create_image_read_error(
            "Could not decode image.",
            image_path_obj,
        )
    return cast(ImageArray, image_ndarray)


def _create_image_read_error(
    message_str: str,
    image_path_obj: Path,
) -> MediaReadError:
    """Create a structured image-decoding error.

    Args:
        message_str: Human-readable failure explanation.
        image_path_obj: Image path used in diagnostics.

    Returns:
        Structured media-read exception.
    """

    return MediaReadError(
        message_str,
        context_mapping={
            "image_path": str(image_path_obj),
            "media_type": "image",
        },
    )


def _select_verification_status(
    passed_bool: bool,
) -> VerificationStatus:
    """Map an image-level policy decision to a result status.

    Args:
        passed_bool: Whether the processing expectation was satisfied.

    Returns:
        ``PASS`` for success or ``FAIL`` for a policy violation.
    """

    if passed_bool:
        return VerificationStatus.PASS
    return VerificationStatus.FAIL


def _build_failures(
    passed_bool: bool,
) -> tuple[VerificationFailure, ...]:
    """Build image-level policy failures.

    Args:
        passed_bool: Whether the processing expectation was satisfied.

    Returns:
        Empty tuple for success or one no-processing failure.
    """

    if passed_bool:
        return ()
    return (
        VerificationFailure(
            code=NO_PROCESSING_FAILURE_CODE_STR,
            message=NO_PROCESSING_FAILURE_MESSAGE_STR,
        ),
    )


def _write_optional_evidence(
    result_obj: VerificationResult,
    candidate_image_ndarray: ImageArray,
    accepted_regions_tuple: tuple[RegionMeasurement, ...],
    output_dir_input: PathInput | None,
) -> VerificationResult:
    """Write requested evidence and enrich the result with its paths.

    Args:
        result_obj: Verification result without evidence paths.
        candidate_image_ndarray: Normalized candidate image.
        accepted_regions_tuple: Accepted regions to annotate and report.
        output_dir_input: Optional evidence directory.

    Returns:
        Original result or an immutable copy with evidence paths.

    Raises:
        ReportWriteError: If the output directory or image cannot be written.
    """

    if output_dir_input is None:
        return result_obj

    output_directory_path_obj = _prepare_output_directory(
        output_dir_input,
    )
    evidence_paths_dict = _write_image_outputs(
        result_obj,
        candidate_image_ndarray,
        accepted_regions_tuple,
        output_directory_path_obj,
    )
    return result_obj.with_evidence_paths(evidence_paths_dict)


def _prepare_output_directory(
    output_dir_input: PathInput,
) -> Path:
    """Resolve and create the image-evidence directory.

    Args:
        output_dir_input: User-provided evidence directory.

    Returns:
        Absolute evidence-directory path.

    Raises:
        ReportWriteError: If the directory cannot be created.
    """

    output_directory_path_obj = Path(output_dir_input).expanduser().resolve()
    try:
        output_directory_path_obj.mkdir(parents=True, exist_ok=True)
    except OSError as error_obj:
        raise ReportWriteError(
            "Could not prepare the image evidence directory.",
            context_mapping={
                "output_directory": str(output_directory_path_obj),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj
    return output_directory_path_obj


def _write_image_outputs(
    result_obj: VerificationResult,
    candidate_image_ndarray: ImageArray,
    accepted_regions_tuple: tuple[RegionMeasurement, ...],
    output_directory_path_obj: Path,
) -> dict[str, Path]:
    """Write image annotation, region table, and JSON summary.

    Args:
        result_obj: Verification result without evidence paths.
        candidate_image_ndarray: Normalized candidate image.
        accepted_regions_tuple: Accepted regions to annotate and report.
        output_directory_path_obj: Prepared evidence directory.

    Returns:
        Named paths to all generated evidence files.

    Raises:
        ReportWriteError: If any evidence file cannot be written.
    """

    annotated_path_obj = _write_annotated_image(
        result_obj,
        candidate_image_ndarray,
        accepted_regions_tuple,
        output_directory_path_obj,
    )
    region_rows_list = _build_region_rows(accepted_regions_tuple)
    region_report_path_obj = write_csv_report(
        region_rows_list,
        output_directory_path_obj / REGION_REPORT_FILENAME_STR,
    )
    summary_path_obj = write_json_report(
        result_obj.to_dict(),
        output_directory_path_obj / SUMMARY_REPORT_FILENAME_STR,
    )
    return {
        "annotated_image": annotated_path_obj,
        "region_report": region_report_path_obj,
        "summary_json": summary_path_obj,
    }


def _write_annotated_image(
    result_obj: VerificationResult,
    candidate_image_ndarray: ImageArray,
    accepted_regions_tuple: tuple[RegionMeasurement, ...],
    output_directory_path_obj: Path,
) -> Path:
    """Render and write the annotated candidate image.

    Args:
        result_obj: Verification result controlling header status.
        candidate_image_ndarray: Normalized candidate image.
        accepted_regions_tuple: Accepted regions to draw.
        output_directory_path_obj: Prepared evidence directory.

    Returns:
        Path to the generated annotated image.

    Raises:
        ReportWriteError: If OpenCV cannot encode or write the image.
    """

    annotated_image_ndarray = annotate_frame(
        candidate_image_ndarray,
        frame_number=SINGLE_IMAGE_FRAME_NUMBER_INT,
        total_frames=SINGLE_IMAGE_TOTAL_FRAMES_INT,
        regions=accepted_regions_tuple,
        status=result_obj.status,
    )
    annotated_path_obj = (
        output_directory_path_obj / ANNOTATED_IMAGE_FILENAME_STR
    )
    image_written_bool = cv2.imwrite(
        str(annotated_path_obj),
        annotated_image_ndarray,
    )
    if not image_written_bool:
        raise ReportWriteError(
            "Could not write the annotated image.",
            context_mapping={
                "output_path": str(annotated_path_obj),
            },
        )
    return annotated_path_obj


def _build_region_rows(
    regions_tuple: tuple[RegionMeasurement, ...],
) -> list[ReportRow]:
    """Convert accepted region measurements into report rows.

    Args:
        regions_tuple: Accepted regions in deterministic display order.

    Returns:
        Ordered rows for the image-level region CSV report.
    """

    report_rows_list: list[ReportRow] = []
    for region_index_int, region_obj in enumerate(
        regions_tuple,
        start=1,
    ):
        report_rows_list.append(
            _build_region_row(region_index_int, region_obj),
        )
    return report_rows_list


def _build_region_row(
    region_index_int: int,
    region_obj: RegionMeasurement,
) -> ReportRow:
    """Build one stable image-level region report row.

    Args:
        region_index_int: One-based region identifier.
        region_obj: Region geometry and severity measurements.

    Returns:
        Ordered mapping suitable for CSV serialization.
    """

    bounding_box_obj = region_obj.box
    return {
        "region_id": region_index_int,
        "x1": bounding_box_obj.x1,
        "y1": bounding_box_obj.y1,
        "x2": bounding_box_obj.x2,
        "y2": bounding_box_obj.y2,
        "severity_score": region_obj.severity_score,
        "severity_label": region_obj.severity_label,
    }


__all__ = [
    "ImageVerificationPipeline",
    "verify_image_pipeline",
]
