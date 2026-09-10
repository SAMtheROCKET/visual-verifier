"""Target-aware verification.

A target is a reviewer's statement that a specific region *had* to be
anonymized. Frame-level change detection answers "did something change
here"; targets answer "did the thing that mattered change".

Provenance is explicit throughout. A box a reviewer drew and a box this
package interpolated are never interchangeable in a report, and an
automatic detector's box is never silently treated as ground truth.
"""

from __future__ import annotations

from visual_verifier.targets.coverage import (
    group_targets_by_frame,
    measure_frame_targets,
    summarize_targets,
)
from visual_verifier.targets.interpolation import interpolate_targets
from visual_verifier.targets.loading import load_targets
from visual_verifier.targets.models import (
    Target,
    TargetCoverage,
    TargetSource,
    TargetSummary,
)

__all__ = [
    "Target",
    "TargetCoverage",
    "TargetSource",
    "TargetSummary",
    "group_targets_by_frame",
    "interpolate_targets",
    "load_targets",
    "measure_frame_targets",
    "summarize_targets",
]
