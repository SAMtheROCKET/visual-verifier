"""Configure target-aware verification.

The defaults are deliberately strict. A target is the reviewer's
statement that a specific region had to be anonymized, so accepting
partial coverage by default would quietly reintroduce the failure this
feature exists to catch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from visual_verifier.exceptions import ConfigurationError

MINIMUM_RATIO_FLOAT: Final[float] = 0.0
MAXIMUM_RATIO_FLOAT: Final[float] = 1.0
MAXIMUM_SENSIBLE_GAP_INT: Final[int] = 300


@dataclass(frozen=True, slots=True)
class TargetConfig:
    """Configure how targets are interpolated and scored.

    Attributes:
        min_covered_ratio: Fraction of a target's area that accepted
            processing must cover before the target counts as
            anonymized.
        interpolate_missing_frames: Fill frames between two reviewed
            boxes of the same target.
        max_interpolation_gap: Longest run of missing frames that may be
            interpolated. A longer gap is left empty, because a target
            can leave and re-enter a scene and inventing boxes across
            that would fabricate evidence.
        fail_on_uncovered_target: Let an uncovered required target fail
            verification. Turn it off to collect target evidence without
            changing the verdict.
    """

    min_covered_ratio: float = 0.9
    interpolate_missing_frames: bool = True
    max_interpolation_gap: int = 5
    fail_on_uncovered_target: bool = True

    def __post_init__(self) -> None:
        """Validate the configuration immediately after construction.

        Raises:
            ConfigurationError: When a value cannot be applied safely.
        """

        self._validate_covered_ratio()
        self._validate_interpolation_gap()

    def _validate_covered_ratio(self) -> None:
        """Validate the minimum coverage ratio.

        Raises:
            ConfigurationError: When the ratio is outside zero to one.
        """

        if not (
            MINIMUM_RATIO_FLOAT < self.min_covered_ratio <= MAXIMUM_RATIO_FLOAT
        ):
            raise ConfigurationError(
                "Target coverage ratio must be above 0 and at most 1.",
                context_mapping={
                    "min_covered_ratio": self.min_covered_ratio,
                },
            )

    def _validate_interpolation_gap(self) -> None:
        """Validate the interpolation gap limit.

        Raises:
            ConfigurationError: When the gap is negative or implausible.
        """

        if self.max_interpolation_gap < 0:
            raise ConfigurationError(
                "Target interpolation gap cannot be negative.",
                context_mapping={
                    "max_interpolation_gap": self.max_interpolation_gap,
                },
            )
        if self.max_interpolation_gap > MAXIMUM_SENSIBLE_GAP_INT:
            raise ConfigurationError(
                "Target interpolation gap is implausibly long.",
                context_mapping={
                    "max_interpolation_gap": self.max_interpolation_gap,
                    "maximum_supported": MAXIMUM_SENSIBLE_GAP_INT,
                },
            )


DEFAULT_TARGET_CONFIG: Final[TargetConfig] = TargetConfig()

__all__ = [
    "DEFAULT_TARGET_CONFIG",
    "TargetConfig",
]
