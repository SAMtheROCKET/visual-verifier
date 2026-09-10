"""Model reviewed targets and the coverage measured against them.

A target is a region a reviewer has declared *must* be anonymized. It is
the piece of information frame-level change detection cannot infer: the
difference between "something changed here" and "the thing that had to
change did change".

Provenance is carried on every target rather than inferred, because a
box a human drew and a box this package interpolated must never become
indistinguishable in a report.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from visual_verifier.models import BoundingBox

UNKNOWN_TARGET_TYPE_TEXT = "unspecified"


class TargetSource(Enum):
    """Where one target box came from.

    Attributes:
        MANUAL: Drawn or confirmed by a reviewer.
        INTERPOLATED: Derived by this package between two reviewed boxes.
        DETECTOR: Produced by an automatic detector and not yet reviewed.
    """

    MANUAL = "manual"
    INTERPOLATED = "interpolated"
    DETECTOR = "detector"

    @property
    def is_reviewed(self) -> bool:
        """Return whether a human confirmed this box."""

        return self is TargetSource.MANUAL


@dataclass(frozen=True, slots=True)
class Target:
    """One region that must be anonymized in one frame.

    Attributes:
        frame_number: One-based frame the target applies to.
        target_id: Identifier stable across frames.
        box: Target region in reference-media coordinates.
        target_type: Optional semantic category, such as ``plate``.
        required: Whether an uncovered target fails verification.
        source: Where the box came from.
    """

    frame_number: int
    target_id: str
    box: BoundingBox
    target_type: str = UNKNOWN_TARGET_TYPE_TEXT
    required: bool = True
    source: TargetSource = TargetSource.MANUAL

    def to_dict(self) -> dict[str, object]:
        """Return a serializable representation of this target.

        Returns:
            Mapping carrying the frame, identity, geometry, and source.
        """

        return {
            "frame_number": self.frame_number,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "x1": self.box.x1,
            "y1": self.box.y1,
            "x2": self.box.x2,
            "y2": self.box.y2,
            "required": self.required,
            "source": self.source.value,
        }


@dataclass(frozen=True, slots=True)
class TargetCoverage:
    """How much of one target was covered by accepted processing.

    Attributes:
        target: The target being measured.
        covered_ratio: Fraction of the target area covered, from 0 to 1.
        covered: Whether the ratio met the configured minimum.
        contributing_region_count: Accepted regions overlapping the
            target. More than one means the coverage is a union.
    """

    target: Target
    covered_ratio: float
    covered: bool
    contributing_region_count: int

    @property
    def is_failure(self) -> bool:
        """Return whether this target counts as a verification failure."""

        return self.target.required and not self.covered

    def to_dict(self) -> dict[str, object]:
        """Return a serializable representation of this measurement.

        Returns:
            Mapping carrying the target fields and the coverage result.
        """

        coverage_dict: dict[str, object] = dict(self.target.to_dict())
        coverage_dict.update(
            {
                "covered_ratio": self.covered_ratio,
                "covered": self.covered,
                "contributing_regions": self.contributing_region_count,
                "is_failure": self.is_failure,
            }
        )
        return coverage_dict


@dataclass(frozen=True, slots=True)
class TargetSummary:
    """Coverage of one target across every frame it appears in.

    Attributes:
        target_id: Identifier the summary describes.
        target_type: Semantic category carried by the target.
        first_frame: First frame the target appears in.
        last_frame: Last frame the target appears in.
        frame_count: Frames the target appears in.
        covered_frame_count: Frames where coverage met the minimum.
        uncovered_frames: Frames where it did not.
        mean_covered_ratio: Mean coverage across every frame.
        interpolated_frame_count: Frames whose box was interpolated.
        required: Whether failures on this target affect status.
    """

    target_id: str
    target_type: str
    first_frame: int
    last_frame: int
    frame_count: int
    covered_frame_count: int
    uncovered_frames: tuple[int, ...]
    mean_covered_ratio: float
    interpolated_frame_count: int
    required: bool

    @property
    def coverage_ratio(self) -> float:
        """Return the fraction of this target's frames that were covered."""

        if self.frame_count <= 0:
            return 0.0
        return self.covered_frame_count / self.frame_count

    def to_dict(self) -> dict[str, object]:
        """Return a serializable representation of this summary.

        Returns:
            Mapping suitable for the target report and JSON output.
        """

        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "frame_count": self.frame_count,
            "covered_frame_count": self.covered_frame_count,
            "uncovered_frames": list(self.uncovered_frames),
            "coverage_ratio": self.coverage_ratio,
            "mean_covered_ratio": self.mean_covered_ratio,
            "interpolated_frame_count": self.interpolated_frame_count,
            "required": self.required,
        }


__all__ = [
    "Target",
    "TargetCoverage",
    "TargetSource",
    "TargetSummary",
]
