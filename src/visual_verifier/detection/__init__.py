"""Expose stable region-detection interfaces for Visual Verifier."""

from visual_verifier.detection.filtering import (
    RegionFilterDecision,
    evaluate_region_filtering,
    is_region_accepted,
    rejection_reasons,
)
from visual_verifier.detection.region_extraction import (
    RegionDetectionResult,
    detect_regions,
)
from visual_verifier.detection.severity import (
    SeverityLabel,
    calculate_severity,
    severity_label,
)

__all__ = [
    "RegionDetectionResult",
    "RegionFilterDecision",
    "SeverityLabel",
    "calculate_severity",
    "detect_regions",
    "evaluate_region_filtering",
    "is_region_accepted",
    "rejection_reasons",
    "severity_label",
]
