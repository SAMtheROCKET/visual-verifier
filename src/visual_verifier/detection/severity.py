"""Calculate deterministic processing-severity scores and labels."""

from __future__ import annotations

from math import isfinite
from typing import Literal, TypeAlias

from visual_verifier.exceptions import ConfigurationError

MINIMUM_SEVERITY_SCORE_FLOAT = 0.0
MAXIMUM_SEVERITY_SCORE_FLOAT = 100.0
VERY_HIGH_SEVERITY_THRESHOLD_FLOAT = 80.0
HIGH_SEVERITY_THRESHOLD_FLOAT = 60.0
MEDIUM_SEVERITY_THRESHOLD_FLOAT = 30.0
LOW_SEVERITY_THRESHOLD_FLOAT = 10.0
DIFFERENCE_COMPONENT_WEIGHT_FLOAT = 0.45
DENSITY_COMPONENT_WEIGHT_FLOAT = 0.25
EDGE_COMPONENT_WEIGHT_FLOAT = 0.30
EDGE_REFERENCE_EPSILON_FLOAT = 1e-9
SCORE_DECIMAL_PLACES_INT = 2
RATIO_DECIMAL_PLACES_INT = 6

SeverityLabel: TypeAlias = Literal[
    "VERY_HIGH",
    "HIGH",
    "MEDIUM",
    "LOW",
    "VERY_LOW",
]


def severity_label(score: float) -> SeverityLabel:
    """Classify a numerical severity score into a stable label.

    Args:
        score: Finite numerical severity score.

    Returns:
        Severity label corresponding to the configured score bands.

    Raises:
        ConfigurationError: If ``score`` is not finite.
    """

    _validate_finite_value("score", score)
    if score >= VERY_HIGH_SEVERITY_THRESHOLD_FLOAT:
        return "VERY_HIGH"
    if score >= HIGH_SEVERITY_THRESHOLD_FLOAT:
        return "HIGH"
    if score >= MEDIUM_SEVERITY_THRESHOLD_FLOAT:
        return "MEDIUM"
    if score >= LOW_SEVERITY_THRESHOLD_FLOAT:
        return "LOW"
    return "VERY_LOW"


def calculate_severity(
    *,
    mean_diff: float,
    changed_ratio: float,
    laplacian_reference: float,
    laplacian_candidate: float,
    diff_normalizer: float,
    changed_ratio_normalizer: float,
) -> tuple[float, float]:
    """Calculate transformation severity and relative edge change.

    Args:
        mean_diff: Mean absolute pixel difference for the region.
        changed_ratio: Fraction of region pixels classified as changed.
        laplacian_reference: Reference-region Laplacian variance.
        laplacian_candidate: Candidate-region Laplacian variance.
        diff_normalizer: Positive scale for mean pixel difference.
        changed_ratio_normalizer: Positive scale for changed-pixel ratio.

    Returns:
        Rounded severity score and relative edge-change ratio.

    Raises:
        ConfigurationError: If any input is invalid.
    """

    _validate_severity_inputs(
        mean_diff=mean_diff,
        changed_ratio=changed_ratio,
        laplacian_reference=laplacian_reference,
        laplacian_candidate=laplacian_candidate,
        diff_normalizer=diff_normalizer,
        changed_ratio_normalizer=changed_ratio_normalizer,
    )
    severity_score_float, edge_change_ratio_float = _calculate_values(
        mean_diff=mean_diff,
        changed_ratio=changed_ratio,
        laplacian_reference=laplacian_reference,
        laplacian_candidate=laplacian_candidate,
        diff_normalizer=diff_normalizer,
        changed_ratio_normalizer=changed_ratio_normalizer,
    )
    return (
        round(severity_score_float, SCORE_DECIMAL_PLACES_INT),
        round(edge_change_ratio_float, RATIO_DECIMAL_PLACES_INT),
    )


def _calculate_values(
    *,
    mean_diff: float,
    changed_ratio: float,
    laplacian_reference: float,
    laplacian_candidate: float,
    diff_normalizer: float,
    changed_ratio_normalizer: float,
) -> tuple[float, float]:
    """Calculate unrounded severity and edge-change values."""

    difference_component_float = _normalized_component(
        mean_diff,
        diff_normalizer,
    )
    density_component_float = _normalized_component(
        changed_ratio,
        changed_ratio_normalizer,
    )
    edge_change_ratio_float = _edge_change_ratio(
        laplacian_reference,
        laplacian_candidate,
    )
    severity_score_float = _weighted_severity_score(
        difference_component_float,
        density_component_float,
        edge_change_ratio_float,
    )
    return severity_score_float, edge_change_ratio_float


def _validate_severity_inputs(
    *,
    mean_diff: float,
    changed_ratio: float,
    laplacian_reference: float,
    laplacian_candidate: float,
    diff_normalizer: float,
    changed_ratio_normalizer: float,
) -> None:
    """Validate all numerical inputs used by the severity formula."""

    metric_values_dict = {
        "mean_diff": mean_diff,
        "changed_ratio": changed_ratio,
        "laplacian_reference": laplacian_reference,
        "laplacian_candidate": laplacian_candidate,
    }
    for metric_name_str, metric_value_float in metric_values_dict.items():
        _validate_non_negative_value(
            metric_name_str,
            metric_value_float,
        )
    _validate_positive_value("diff_normalizer", diff_normalizer)
    _validate_positive_value(
        "changed_ratio_normalizer",
        changed_ratio_normalizer,
    )


def _normalized_component(
    metric_value_float: float,
    normalizer_float: float,
) -> float:
    """Return one non-negative component limited to one."""

    normalized_value_float = metric_value_float / normalizer_float
    return min(1.0, normalized_value_float)


def _edge_change_ratio(
    laplacian_reference_float: float,
    laplacian_candidate_float: float,
) -> float:
    """Return relative Laplacian-variance change for one region."""

    if laplacian_reference_float <= EDGE_REFERENCE_EPSILON_FLOAT:
        return 0.0
    variance_delta_float = abs(
        laplacian_candidate_float - laplacian_reference_float
    )
    denominator_float = (
        laplacian_reference_float + EDGE_REFERENCE_EPSILON_FLOAT
    )
    return variance_delta_float / denominator_float


def _weighted_severity_score(
    difference_component_float: float,
    density_component_float: float,
    edge_change_ratio_float: float,
) -> float:
    """Combine normalized evidence components into a 0-100 score."""

    edge_component_float = min(1.0, edge_change_ratio_float)
    weighted_sum_float = (
        DIFFERENCE_COMPONENT_WEIGHT_FLOAT * difference_component_float
        + DENSITY_COMPONENT_WEIGHT_FLOAT * density_component_float
        + EDGE_COMPONENT_WEIGHT_FLOAT * edge_component_float
    )
    return weighted_sum_float * MAXIMUM_SEVERITY_SCORE_FLOAT


def _validate_non_negative_value(
    value_name_str: str,
    value_float: float,
) -> None:
    """Require one finite value greater than or equal to zero."""

    _validate_finite_value(value_name_str, value_float)
    if value_float < 0.0:
        _raise_invalid_value_error(
            value_name_str,
            value_float,
            "must be greater than or equal to zero",
        )


def _validate_positive_value(
    value_name_str: str,
    value_float: float,
) -> None:
    """Require one finite value greater than zero."""

    _validate_finite_value(value_name_str, value_float)
    if value_float <= 0.0:
        _raise_invalid_value_error(
            value_name_str,
            value_float,
            "must be greater than zero",
        )


def _validate_finite_value(
    value_name_str: str,
    value_float: float,
) -> None:
    """Require one finite floating-point value."""

    if not isfinite(value_float):
        _raise_invalid_value_error(
            value_name_str,
            value_float,
            "must be finite",
        )


def _raise_invalid_value_error(
    value_name_str: str,
    value_float: float,
    requirement_str: str,
) -> None:
    """Raise a structured configuration error for one invalid value."""

    message_str = f"{value_name_str} {requirement_str}."
    raise ConfigurationError(
        message_str,
        context_mapping={
            "parameter": value_name_str,
            "value": value_float,
            "requirement": requirement_str,
        },
    )


__all__ = [
    "SeverityLabel",
    "calculate_severity",
    "severity_label",
]
