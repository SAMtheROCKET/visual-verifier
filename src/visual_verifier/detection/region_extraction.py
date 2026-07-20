"""Detect, measure, and classify changed image regions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias

import cv2
import numpy as np
from numpy.typing import NDArray

from visual_verifier.detection.filtering import (
    RegionFilterDecision,
    evaluate_region_filtering,
)
from visual_verifier.detection.severity import (
    calculate_severity,
    severity_label,
)
from visual_verifier.metrics.geometry import clip_box_to_frame
from visual_verifier.metrics.pixel import (
    PixelDifferenceStatistics,
    calculate_grayscale_difference,
    calculate_pixel_difference_statistics,
    create_changed_pixel_mask,
)
from visual_verifier.metrics.sharpness import (
    SharpnessStatistics,
    calculate_sharpness_statistics,
)
from visual_verifier.models import (
    BoundingBox,
    DetectionConfig,
    RegionMeasurement,
)
from visual_verifier.type_aliases import ImageArray, MaskArray

MORPHOLOGY_DILATION_ITERATIONS_INT = 1
REGION_METRIC_DECIMAL_PLACES_INT = 6
MAXIMUM_MASK_VALUE_INT = 255

ContourArray: TypeAlias = NDArray[np.int32]
RegionCollection: TypeAlias = tuple[RegionMeasurement, ...]
RegionDetectionResult: TypeAlias = tuple[
    RegionCollection,
    RegionCollection,
]


@dataclass(frozen=True, slots=True)
class _DifferenceArtifacts:
    """Store difference data used for contour detection and measurement."""

    difference_image: ImageArray
    cleaned_mask: MaskArray


@dataclass(frozen=True, slots=True)
class _RegionCrops:
    """Store aligned reference, candidate, and difference region crops."""

    reference_image: ImageArray
    candidate_image: ImageArray
    difference_image: ImageArray


@dataclass(frozen=True, slots=True)
class _RegionStatistics:
    """Store complete numerical evidence for one candidate region."""

    pixel_statistics: PixelDifferenceStatistics
    sharpness_statistics: SharpnessStatistics
    edge_change_ratio: float
    severity_score: float


def _normalize_uint8_array(
    source_array_ndarray: NDArray[Any],
) -> ImageArray:
    """Return one contiguous unsigned 8-bit array.

    Args:
        source_array_ndarray: Numeric array returned by NumPy or OpenCV.

    Returns:
        Contiguous unsigned 8-bit image array.
    """

    contiguous_array_ndarray = np.ascontiguousarray(
        source_array_ndarray,
    )
    return contiguous_array_ndarray.astype(
        np.uint8,
        copy=False,
    )


def _create_morphology_kernel(
    config_obj: DetectionConfig,
) -> ImageArray:
    """Create the rectangular kernel used to merge changed pixels.

    Args:
        config_obj: Region-detection configuration.

    Returns:
        Rectangular unsigned 8-bit morphology kernel.
    """

    kernel_size_tuple = (
        config_obj.merge_kernel_size,
        config_obj.merge_kernel_size,
    )
    kernel_ndarray = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        kernel_size_tuple,
    )
    return _normalize_uint8_array(kernel_ndarray)


def _clean_changed_pixel_mask(
    changed_mask_ndarray: MaskArray,
    morphology_kernel_ndarray: ImageArray,
) -> MaskArray:
    """Merge nearby changed pixels and expand the resulting regions.

    Args:
        changed_mask_ndarray: Binary changed-pixel mask.
        morphology_kernel_ndarray: Rectangular morphology kernel.

    Returns:
        Closed and dilated binary mask.
    """

    closed_mask_ndarray = cv2.morphologyEx(
        changed_mask_ndarray,
        cv2.MORPH_CLOSE,
        morphology_kernel_ndarray,
    )
    dilated_mask_ndarray = cv2.dilate(
        closed_mask_ndarray,
        morphology_kernel_ndarray,
        iterations=MORPHOLOGY_DILATION_ITERATIONS_INT,
    )
    return _normalize_uint8_array(dilated_mask_ndarray)


def _create_difference_artifacts(
    reference_image_ndarray: ImageArray,
    candidate_image_ndarray: ImageArray,
    config_obj: DetectionConfig,
) -> _DifferenceArtifacts:
    """Create aligned difference data and a cleaned contour mask.

    Args:
        reference_image_ndarray: Reference image or video frame.
        candidate_image_ndarray: Processed candidate image or frame.
        config_obj: Region-detection configuration.

    Returns:
        Difference image and cleaned binary mask.

    Raises:
        MediaCompatibilityError: If image dimensions are incompatible.
    """

    difference_image_ndarray = calculate_grayscale_difference(
        reference_image_ndarray,
        candidate_image_ndarray,
    )
    changed_mask_ndarray = create_changed_pixel_mask(
        difference_image_ndarray,
        config_obj.diff_threshold,
    )
    morphology_kernel_ndarray = _create_morphology_kernel(config_obj)
    cleaned_mask_ndarray = _clean_changed_pixel_mask(
        changed_mask_ndarray,
        morphology_kernel_ndarray,
    )
    return _DifferenceArtifacts(
        difference_image=difference_image_ndarray,
        cleaned_mask=cleaned_mask_ndarray,
    )


def _find_external_contours(
    cleaned_mask_ndarray: MaskArray,
) -> list[ContourArray]:
    """Find external contours in a cleaned difference mask.

    Args:
        cleaned_mask_ndarray: Binary mask containing merged regions.

    Returns:
        OpenCV contour arrays in the order returned by OpenCV.
    """

    contours_sequence, _hierarchy_ndarray = cv2.findContours(
        cleaned_mask_ndarray,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    return [
        contour_ndarray.astype(np.int32, copy=False)
        for contour_ndarray in contours_sequence
    ]


def _create_padded_bounding_box(
    contour_ndarray: ContourArray,
    frame_width_int: int,
    frame_height_int: int,
    config_obj: DetectionConfig,
) -> BoundingBox:
    """Convert one contour into a padded frame-clipped box.

    Args:
        contour_ndarray: OpenCV contour coordinates.
        frame_width_int: Reference-frame width in pixels.
        frame_height_int: Reference-frame height in pixels.
        config_obj: Region-detection configuration.

    Returns:
        Padded bounding box clipped to valid frame coordinates.
    """

    coordinate_x_int, coordinate_y_int, width_int, height_int = (
        cv2.boundingRect(contour_ndarray)
    )
    padded_box_obj = BoundingBox(
        x1=coordinate_x_int - config_obj.box_padding,
        y1=coordinate_y_int - config_obj.box_padding,
        x2=coordinate_x_int + width_int + config_obj.box_padding,
        y2=coordinate_y_int + height_int + config_obj.box_padding,
    )
    return clip_box_to_frame(
        padded_box_obj,
        frame_width_int,
        frame_height_int,
    )


def _box_meets_size_thresholds(
    bounding_box_obj: BoundingBox,
    config_obj: DetectionConfig,
) -> bool:
    """Return whether a box satisfies every geometric threshold.

    Args:
        bounding_box_obj: Candidate bounding box.
        config_obj: Region-detection configuration.

    Returns:
        ``True`` when area, width, and height are large enough.
    """

    return (
        bounding_box_obj.area >= config_obj.min_box_area
        and bounding_box_obj.width >= config_obj.min_box_width
        and bounding_box_obj.height >= config_obj.min_box_height
    )


def _extract_region_crops(
    reference_image_ndarray: ImageArray,
    candidate_image_ndarray: ImageArray,
    difference_image_ndarray: ImageArray,
    bounding_box_obj: BoundingBox,
) -> _RegionCrops:
    """Extract aligned arrays for one valid bounding box.

    Args:
        reference_image_ndarray: Reference image or video frame.
        candidate_image_ndarray: Processed candidate image or frame.
        difference_image_ndarray: Grayscale absolute-difference image.
        bounding_box_obj: Valid frame-clipped bounding box.

    Returns:
        Aligned reference, candidate, and difference crops.
    """

    row_slice_obj = slice(bounding_box_obj.y1, bounding_box_obj.y2)
    column_slice_obj = slice(bounding_box_obj.x1, bounding_box_obj.x2)
    return _RegionCrops(
        reference_image=reference_image_ndarray[
            row_slice_obj,
            column_slice_obj,
        ],
        candidate_image=candidate_image_ndarray[
            row_slice_obj,
            column_slice_obj,
        ],
        difference_image=difference_image_ndarray[
            row_slice_obj,
            column_slice_obj,
        ],
    )


def _calculate_region_statistics(
    region_crops_obj: _RegionCrops,
    config_obj: DetectionConfig,
) -> _RegionStatistics:
    """Calculate pixel, sharpness, and severity evidence for a region.

    Args:
        region_crops_obj: Aligned arrays for one candidate region.
        config_obj: Region-detection configuration.

    Returns:
        Complete numerical evidence for the region.
    """

    pixel_statistics_obj = calculate_pixel_difference_statistics(
        region_crops_obj.difference_image,
        config_obj.diff_threshold,
    )
    sharpness_statistics_obj = calculate_sharpness_statistics(
        region_crops_obj.reference_image,
        region_crops_obj.candidate_image,
    )
    severity_score_float, edge_change_ratio_float = calculate_severity(
        mean_diff=pixel_statistics_obj.mean_difference,
        changed_ratio=pixel_statistics_obj.changed_ratio,
        laplacian_reference=(sharpness_statistics_obj.reference_variance),
        laplacian_candidate=(sharpness_statistics_obj.candidate_variance),
        diff_normalizer=config_obj.diff_normalizer,
        changed_ratio_normalizer=config_obj.changed_ratio_normalizer,
    )
    return _RegionStatistics(
        pixel_statistics=pixel_statistics_obj,
        sharpness_statistics=sharpness_statistics_obj,
        edge_change_ratio=edge_change_ratio_float,
        severity_score=severity_score_float,
    )


def _evaluate_region_filter(
    statistics_obj: _RegionStatistics,
    config_obj: DetectionConfig,
) -> RegionFilterDecision:
    """Evaluate one measured region against false-positive filters."""

    return evaluate_region_filtering(
        changed_ratio=statistics_obj.pixel_statistics.changed_ratio,
        mean_diff=statistics_obj.pixel_statistics.mean_difference,
        severity_score=statistics_obj.severity_score,
        config=config_obj,
    )


def _round_region_metric(metric_value_float: float) -> float:
    """Round one report metric to the stable region precision."""

    return round(
        metric_value_float,
        REGION_METRIC_DECIMAL_PLACES_INT,
    )


def _build_region_measurement(
    bounding_box_obj: BoundingBox,
    statistics_obj: _RegionStatistics,
    filter_decision_obj: RegionFilterDecision,
) -> RegionMeasurement:
    """Build the public domain model for one measured region."""

    pixel_statistics_obj = statistics_obj.pixel_statistics
    sharpness_statistics_obj = statistics_obj.sharpness_statistics
    return RegionMeasurement(
        box=bounding_box_obj,
        changed_pixels=pixel_statistics_obj.changed_pixels,
        changed_ratio=_round_region_metric(
            pixel_statistics_obj.changed_ratio,
        ),
        mean_diff=_round_region_metric(
            pixel_statistics_obj.mean_difference,
        ),
        max_diff=_round_region_metric(
            pixel_statistics_obj.maximum_difference,
        ),
        laplacian_reference=_round_region_metric(
            sharpness_statistics_obj.reference_variance,
        ),
        laplacian_candidate=_round_region_metric(
            sharpness_statistics_obj.candidate_variance,
        ),
        sharpness_percentage_candidate_vs_reference=(
            _round_region_metric(
                sharpness_statistics_obj.candidate_percentage,
            )
        ),
        edge_change_ratio=statistics_obj.edge_change_ratio,
        severity_score=statistics_obj.severity_score,
        severity_label=severity_label(statistics_obj.severity_score),
        accepted=filter_decision_obj.accepted,
        rejection_reasons=filter_decision_obj.rejection_reasons,
    )


def _measure_contour(
    contour_ndarray: ContourArray,
    reference_image_ndarray: ImageArray,
    candidate_image_ndarray: ImageArray,
    difference_image_ndarray: ImageArray,
    config_obj: DetectionConfig,
) -> RegionMeasurement | None:
    """Convert one contour into a measured region when large enough."""

    frame_height_int, frame_width_int = reference_image_ndarray.shape[:2]
    bounding_box_obj = _create_padded_bounding_box(
        contour_ndarray,
        frame_width_int,
        frame_height_int,
        config_obj,
    )
    if not _box_meets_size_thresholds(bounding_box_obj, config_obj):
        return None
    region_crops_obj = _extract_region_crops(
        reference_image_ndarray,
        candidate_image_ndarray,
        difference_image_ndarray,
        bounding_box_obj,
    )
    statistics_obj = _calculate_region_statistics(
        region_crops_obj,
        config_obj,
    )
    filter_decision_obj = _evaluate_region_filter(
        statistics_obj,
        config_obj,
    )
    return _build_region_measurement(
        bounding_box_obj,
        statistics_obj,
        filter_decision_obj,
    )


def _partition_measured_regions(
    contours_list: list[ContourArray],
    reference_image_ndarray: ImageArray,
    candidate_image_ndarray: ImageArray,
    difference_image_ndarray: ImageArray,
    config_obj: DetectionConfig,
) -> tuple[list[RegionMeasurement], list[RegionMeasurement]]:
    """Measure contours and partition accepted from rejected regions."""

    accepted_regions_list: list[RegionMeasurement] = []
    rejected_regions_list: list[RegionMeasurement] = []
    for contour_ndarray in contours_list:
        region_measurement_obj = _measure_contour(
            contour_ndarray,
            reference_image_ndarray,
            candidate_image_ndarray,
            difference_image_ndarray,
            config_obj,
        )
        if region_measurement_obj is None:
            continue
        if region_measurement_obj.accepted:
            accepted_regions_list.append(region_measurement_obj)
        else:
            rejected_regions_list.append(region_measurement_obj)
    return accepted_regions_list, rejected_regions_list


def _region_position_sort_key(
    region_measurement_obj: RegionMeasurement,
) -> tuple[int, int]:
    """Return top and left coordinates for deterministic region sorting."""

    return (
        region_measurement_obj.box.y1,
        region_measurement_obj.box.x1,
    )


def _sort_regions(
    regions_list: list[RegionMeasurement],
) -> RegionCollection:
    """Return measured regions in deterministic top-left order."""

    return tuple(
        sorted(
            regions_list,
            key=_region_position_sort_key,
        )
    )


def detect_regions(
    reference_ndarray: ImageArray,
    candidate_ndarray: ImageArray,
    config_obj: DetectionConfig,
) -> RegionDetectionResult:
    """Detect, measure, filter, and sort changed regions.

    Args:
        reference_ndarray: Reference image or video frame.
        candidate_ndarray: Processed candidate image or video frame.
        config_obj: Region-detection and filtering configuration.

    Returns:
        Accepted and rejected region measurements in top-left order.

    Raises:
        MediaCompatibilityError: If the image pair is incompatible.
        ConfigurationError: If severity configuration is invalid.
        PolicyEvaluationError: If measured filter values are invalid.
    """

    artifacts_obj = _create_difference_artifacts(
        reference_ndarray,
        candidate_ndarray,
        config_obj,
    )
    contours_list = _find_external_contours(
        artifacts_obj.cleaned_mask,
    )
    accepted_regions_list, rejected_regions_list = _partition_measured_regions(
        contours_list,
        reference_ndarray,
        candidate_ndarray,
        artifacts_obj.difference_image,
        config_obj,
    )
    return (
        _sort_regions(accepted_regions_list),
        _sort_regions(rejected_regions_list),
    )


__all__ = [
    "RegionDetectionResult",
    "detect_regions",
]
