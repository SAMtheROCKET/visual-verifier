"""Expose stable metric calculations for Visual Verifier."""

from visual_verifier.metrics.geometry import (
    calculate_intersection_area,
    calculate_intersection_box,
    calculate_iou,
    calculate_target_coverage_ratio,
    calculate_union_area,
    clip_box_to_frame,
    intersection_area,
)
from visual_verifier.metrics.pixel import (
    PixelDifferenceStatistics,
    calculate_grayscale_difference,
    calculate_pixel_difference_statistics,
    convert_image_to_grayscale,
    create_changed_pixel_mask,
    grayscale_difference,
)
from visual_verifier.metrics.sharpness import (
    SHARPNESS_EPSILON_FLOAT,
    SharpnessStatistics,
    calculate_candidate_sharpness_percentage,
    calculate_laplacian_variance,
    calculate_relative_sharpness_change,
    calculate_sharpness_statistics,
    laplacian_variance,
)

__all__ = [
    "SHARPNESS_EPSILON_FLOAT",
    "PixelDifferenceStatistics",
    "SharpnessStatistics",
    "calculate_candidate_sharpness_percentage",
    "calculate_grayscale_difference",
    "calculate_intersection_area",
    "calculate_intersection_box",
    "calculate_iou",
    "calculate_laplacian_variance",
    "calculate_pixel_difference_statistics",
    "calculate_relative_sharpness_change",
    "calculate_sharpness_statistics",
    "calculate_target_coverage_ratio",
    "calculate_union_area",
    "clip_box_to_frame",
    "convert_image_to_grayscale",
    "create_changed_pixel_mask",
    "grayscale_difference",
    "intersection_area",
    "laplacian_variance",
]
