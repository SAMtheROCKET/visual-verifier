"""Build compact tracking fixtures for unit tests."""

from visual_verifier.models import BoundingBox, RegionMeasurement


def make_region(
    box: BoundingBox,
    *,
    severity_score: float = 50.0,
    changed_ratio: float = 0.5,
) -> RegionMeasurement:
    """Return one accepted region with deterministic measurements."""

    return RegionMeasurement(
        box=box,
        changed_pixels=max(1, box.area // 2),
        changed_ratio=changed_ratio,
        mean_diff=25.0,
        max_diff=80.0,
        laplacian_reference=120.0,
        laplacian_candidate=30.0,
        sharpness_percentage_candidate_vs_reference=25.0,
        edge_change_ratio=0.4,
        severity_score=severity_score,
        severity_label="HIGH",
        accepted=True,
        rejection_reasons=(),
    )
