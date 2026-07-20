"""Evaluate region measurements against false-positive filters."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from visual_verifier.exceptions import PolicyEvaluationError
from visual_verifier.models import DetectionConfig

CHANGED_RATIO_TOO_LOW_REASON_STR = "changed_ratio_too_low"
MEAN_DIFFERENCE_TOO_LOW_REASON_STR = "mean_diff_too_low"
SEVERITY_SCORE_TOO_LOW_REASON_STR = "severity_score_too_low"


@dataclass(frozen=True, slots=True)
class RegionFilterDecision:
    """Store the acceptance decision for one measured region.

    Attributes:
        accepted: Whether the region passed every configured filter.
        rejection_reasons: Stable reason codes for failed filters.
    """

    accepted: bool
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable representation of the decision.

        Returns:
            Dictionary containing the acceptance flag and reason codes.
        """

        return {
            "accepted": self.accepted,
            "rejection_reasons": list(self.rejection_reasons),
        }


def evaluate_region_filtering(
    *,
    changed_ratio: float,
    mean_diff: float,
    severity_score: float,
    config: DetectionConfig,
) -> RegionFilterDecision:
    """Evaluate one region against all configured filtering thresholds.

    Args:
        changed_ratio: Fraction of region pixels classified as changed.
        mean_diff: Mean absolute grayscale difference for the region.
        severity_score: Composite processing-severity score.
        config: Detection thresholds controlling region acceptance.

    Returns:
        Immutable region-filter decision and rejection reason codes.

    Raises:
        PolicyEvaluationError: If a metric or threshold is invalid.
    """

    reasons_tuple = rejection_reasons(
        changed_ratio=changed_ratio,
        mean_diff=mean_diff,
        severity_score=severity_score,
        config=config,
    )
    return RegionFilterDecision(
        accepted=not reasons_tuple,
        rejection_reasons=reasons_tuple,
    )


def rejection_reasons(
    *,
    changed_ratio: float,
    mean_diff: float,
    severity_score: float,
    config: DetectionConfig,
) -> tuple[str, ...]:
    """Return stable reason codes for every failed region filter.

    Args:
        changed_ratio: Fraction of region pixels classified as changed.
        mean_diff: Mean absolute grayscale difference for the region.
        severity_score: Composite processing-severity score.
        config: Detection thresholds controlling region acceptance.

    Returns:
        Rejection reason codes in deterministic evaluation order.

    Raises:
        PolicyEvaluationError: If a metric or threshold is invalid.
    """

    _validate_filter_inputs(
        changed_ratio=changed_ratio,
        mean_diff=mean_diff,
        severity_score=severity_score,
        config=config,
    )
    reasons_list: list[str] = []
    if changed_ratio < config.min_changed_ratio:
        reasons_list.append(CHANGED_RATIO_TOO_LOW_REASON_STR)
    if mean_diff < config.min_mean_diff:
        reasons_list.append(MEAN_DIFFERENCE_TOO_LOW_REASON_STR)
    if severity_score < config.min_severity_score:
        reasons_list.append(SEVERITY_SCORE_TOO_LOW_REASON_STR)
    return tuple(reasons_list)


def is_region_accepted(
    *,
    changed_ratio: float,
    mean_diff: float,
    severity_score: float,
    config: DetectionConfig,
) -> bool:
    """Return whether one region passes every configured filter.

    Args:
        changed_ratio: Fraction of region pixels classified as changed.
        mean_diff: Mean absolute grayscale difference for the region.
        severity_score: Composite processing-severity score.
        config: Detection thresholds controlling region acceptance.

    Returns:
        ``True`` when no rejection reason is produced.

    Raises:
        PolicyEvaluationError: If a metric or threshold is invalid.
    """

    decision_obj = evaluate_region_filtering(
        changed_ratio=changed_ratio,
        mean_diff=mean_diff,
        severity_score=severity_score,
        config=config,
    )
    return decision_obj.accepted


def _validate_filter_inputs(
    *,
    changed_ratio: float,
    mean_diff: float,
    severity_score: float,
    config: DetectionConfig,
) -> None:
    """Validate runtime measurements and configured thresholds."""

    value_pairs_tuple = (
        ("changed_ratio", changed_ratio, config.min_changed_ratio),
        ("mean_diff", mean_diff, config.min_mean_diff),
        ("severity_score", severity_score, config.min_severity_score),
    )
    for (
        metric_name_str,
        metric_value_float,
        threshold_float,
    ) in value_pairs_tuple:
        _validate_non_negative_finite_value(
            metric_name_str,
            metric_value_float,
            value_role_str="measurement",
        )
        _validate_non_negative_finite_value(
            metric_name_str,
            threshold_float,
            value_role_str="threshold",
        )


def _validate_non_negative_finite_value(
    metric_name_str: str,
    metric_value_float: float,
    *,
    value_role_str: str,
) -> None:
    """Require one measurement or threshold to be finite and non-negative."""

    if isfinite(metric_value_float) and metric_value_float >= 0.0:
        return
    raise PolicyEvaluationError(
        f"Region-filter {value_role_str} must be finite and non-negative.",
        context_mapping={
            "metric": metric_name_str,
            "role": value_role_str,
            "value": metric_value_float,
        },
    )


__all__ = [
    "CHANGED_RATIO_TOO_LOW_REASON_STR",
    "MEAN_DIFFERENCE_TOO_LOW_REASON_STR",
    "RegionFilterDecision",
    "SEVERITY_SCORE_TOO_LOW_REASON_STR",
    "evaluate_region_filtering",
    "is_region_accepted",
    "rejection_reasons",
]
