"""Define immutable configuration for temporal region tracking."""

from __future__ import annotations

from dataclasses import dataclass

from visual_verifier.exceptions import ConfigurationError

DEFAULT_ASSOCIATION_IOU_THRESHOLD_FLOAT = 0.20
DEFAULT_MINIMUM_CONFIRMATION_HITS_INT = 2
DEFAULT_MAXIMUM_GAP_FRAMES_INT = 3
DEFAULT_LINEAGE_OVERLAP_THRESHOLD_FLOAT = 0.20


@dataclass(frozen=True, slots=True)
class TrackingConfig:
    """Configure deterministic temporal association and track lifecycle.

    Attributes:
        association_iou_threshold: Minimum intersection-over-union required
            to associate one detection with an active track.
        minimum_confirmation_hits: Consecutive or recovered observations
            required before a tentative track becomes confirmed.
        maximum_gap_frames: Number of consecutive missing frames tolerated
            before an active track is closed.
        lineage_overlap_threshold: Minimum overlap used when detecting
            split and merge lineage events.
        detect_lineage_events: Whether split and merge evidence is produced.
    """

    association_iou_threshold: float = DEFAULT_ASSOCIATION_IOU_THRESHOLD_FLOAT
    minimum_confirmation_hits: int = DEFAULT_MINIMUM_CONFIRMATION_HITS_INT
    maximum_gap_frames: int = DEFAULT_MAXIMUM_GAP_FRAMES_INT
    lineage_overlap_threshold: float = DEFAULT_LINEAGE_OVERLAP_THRESHOLD_FLOAT
    detect_lineage_events: bool = True

    def __post_init__(self) -> None:
        """Validate temporal tracking settings after construction.

        Raises:
            ConfigurationError: When one or more settings are invalid.
        """

        invalid_fields_list = self._find_invalid_fields()
        if not invalid_fields_list:
            return

        raise ConfigurationError(
            "Tracking configuration contains invalid values.",
            context_mapping={
                "invalid_fields": sorted(set(invalid_fields_list)),
            },
        )

    def _find_invalid_fields(self) -> list[str]:
        """Return configuration field names that fail validation.

        Returns:
            Names of invalid threshold or lifecycle settings.
        """

        invalid_fields_list: list[str] = []

        if not 0.0 <= self.association_iou_threshold <= 1.0:
            invalid_fields_list.append("association_iou_threshold")
        if self.minimum_confirmation_hits < 1:
            invalid_fields_list.append("minimum_confirmation_hits")
        if self.maximum_gap_frames < 0:
            invalid_fields_list.append("maximum_gap_frames")
        if not 0.0 <= self.lineage_overlap_threshold <= 1.0:
            invalid_fields_list.append("lineage_overlap_threshold")

        return invalid_fields_list

    def to_dict(self) -> dict[str, object]:
        """Return serializable temporal tracking settings.

        Returns:
            Dictionary containing each configuration field.
        """

        return {
            field_name_str: getattr(self, field_name_str)
            for field_name_str in self.__dataclass_fields__
        }


DEFAULT_TRACKING_CONFIG = TrackingConfig()

__all__ = [
    "DEFAULT_ASSOCIATION_IOU_THRESHOLD_FLOAT",
    "DEFAULT_LINEAGE_OVERLAP_THRESHOLD_FLOAT",
    "DEFAULT_MAXIMUM_GAP_FRAMES_INT",
    "DEFAULT_MINIMUM_CONFIRMATION_HITS_INT",
    "DEFAULT_TRACKING_CONFIG",
    "TrackingConfig",
]
