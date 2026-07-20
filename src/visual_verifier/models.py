"""Define typed domain models for Visual Verifier workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from visual_verifier.exceptions import (
    ConfigurationError,
    VerificationFailedError,
)

DEFAULT_FAILURE_MESSAGE = "Visual verification failed."


class VerificationStatus(str, Enum):
    """Represent the top-level outcome of a verification run."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Represent an axis-aligned box with exclusive end coordinates.

    Attributes:
        x1: Left coordinate, inclusive.
        y1: Top coordinate, inclusive.
        x2: Right coordinate, exclusive.
        y2: Bottom coordinate, exclusive.
    """

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        """Return the non-negative bounding-box width in pixels."""

        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        """Return the non-negative bounding-box height in pixels."""

        return max(0, self.y2 - self.y1)

    @property
    def area(self) -> int:
        """Return the non-negative bounding-box area in pixels."""

        return self.width * self.height

    @property
    def is_valid(self) -> bool:
        """Return whether the box encloses a positive pixel area."""

        return self.width > 0 and self.height > 0

    def as_tuple(self) -> tuple[int, int, int, int]:
        """Return coordinates in ``x1, y1, x2, y2`` order.

        Returns:
            Four integer coordinates using exclusive end coordinates.
        """

        return self.x1, self.y1, self.x2, self.y2

    def to_dict(self) -> dict[str, int]:
        """Return a machine-readable bounding-box representation.

        Returns:
            Coordinate, dimension, and area values.
        """

        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "width": self.width,
            "height": self.height,
            "area": self.area,
        }


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    """Store normalized metadata for one image or video input.

    Attributes:
        path: Resolved filesystem path to the media.
        media_type: Media category, such as ``image`` or ``video``.
        width: Frame width in pixels.
        height: Frame height in pixels.
        frame_count: Number of frames available for verification.
        fps: Frames per second for video media.
        duration_seconds: Media duration in seconds.
    """

    path: Path
    media_type: str
    width: int
    height: int
    frame_count: int = 1
    fps: float = 0.0
    duration_seconds: float = 0.0

    @property
    def resolution(self) -> tuple[int, int]:
        """Return media resolution as width and height."""

        return self.width, self.height

    def to_dict(self) -> dict[str, object]:
        """Return serializable media metadata.

        Returns:
            Dictionary containing path, dimensions, and timing metadata.
        """

        return {
            "path": str(self.path),
            "media_type": self.media_type,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count,
            "fps": self.fps,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True, slots=True)
class DetectionConfig:
    """Configure region detection and processing-severity thresholds.

    Values preserve the validated V2.1 prototype defaults while exposing a
    stable configuration object for package, CLI, and test callers.
    """

    diff_threshold: int = 30
    min_box_area: int = 80
    min_box_width: int = 6
    min_box_height: int = 6
    merge_kernel_size: int = 9
    box_padding: int = 3
    min_changed_ratio: float = 0.03
    min_mean_diff: float = 5.0
    min_severity_score: float = 8.0
    diff_normalizer: float = 80.0
    changed_ratio_normalizer: float = 0.75

    def __post_init__(self) -> None:
        """Validate detection thresholds immediately after construction.

        Raises:
            ConfigurationError: When a threshold cannot be applied safely.
        """

        self._validate_integer_thresholds()
        self._validate_float_thresholds()

    def _validate_integer_thresholds(self) -> None:
        """Validate integer thresholds used by OpenCV operations.

        Raises:
            ConfigurationError: When an integer threshold is invalid.
        """

        integer_thresholds_dict = {
            "diff_threshold": self.diff_threshold,
            "min_box_area": self.min_box_area,
            "min_box_width": self.min_box_width,
            "min_box_height": self.min_box_height,
            "merge_kernel_size": self.merge_kernel_size,
            "box_padding": self.box_padding,
        }
        invalid_names_list: list[str] = []
        threshold_items_view = integer_thresholds_dict.items()

        for threshold_name_str, threshold_value_int in threshold_items_view:
            if threshold_value_int < 0:
                invalid_names_list.append(threshold_name_str)
        if self.merge_kernel_size == 0:
            invalid_names_list.append("merge_kernel_size")
        self._raise_for_invalid_thresholds(invalid_names_list)

    def _validate_float_thresholds(self) -> None:
        """Validate floating-point thresholds and normalizers.

        Raises:
            ConfigurationError: When a floating-point threshold is invalid.
        """

        non_negative_values_dict = {
            "min_changed_ratio": self.min_changed_ratio,
            "min_mean_diff": self.min_mean_diff,
            "min_severity_score": self.min_severity_score,
        }
        invalid_names_list: list[str] = []
        threshold_items_view = non_negative_values_dict.items()

        for threshold_name_str, threshold_value_float in threshold_items_view:
            if threshold_value_float < 0.0:
                invalid_names_list.append(threshold_name_str)
        if self.diff_normalizer <= 0.0:
            invalid_names_list.append("diff_normalizer")
        if self.changed_ratio_normalizer <= 0.0:
            invalid_names_list.append("changed_ratio_normalizer")
        self._raise_for_invalid_thresholds(invalid_names_list)

    @staticmethod
    def _raise_for_invalid_thresholds(
        invalid_names_list: list[str],
    ) -> None:
        """Raise one structured error for invalid threshold names.

        Args:
            invalid_names_list: Configuration fields that failed validation.

        Raises:
            ConfigurationError: When one or more names are supplied.
        """

        if not invalid_names_list:
            return
        unique_names_list = sorted(set(invalid_names_list))
        raise ConfigurationError(
            "Detection configuration contains invalid thresholds.",
            context_mapping={"invalid_fields": unique_names_list},
        )

    def to_dict(self) -> dict[str, object]:
        """Return all detection thresholds as serializable values.

        Returns:
            Dictionary containing every configuration field.
        """

        return {
            field_name_str: getattr(self, field_name_str)
            for field_name_str in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class RegionMeasurement:
    """Store measurements for one detected candidate region."""

    box: BoundingBox
    changed_pixels: int
    changed_ratio: float
    mean_diff: float
    max_diff: float
    laplacian_reference: float
    laplacian_candidate: float
    sharpness_percentage_candidate_vs_reference: float
    edge_change_ratio: float
    severity_score: float
    severity_label: str
    accepted: bool
    rejection_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return serializable region measurements.

        Returns:
            Dictionary containing geometry, intensity, and severity values.
        """

        return {
            "box": self.box.to_dict(),
            "changed_pixels": self.changed_pixels,
            "changed_ratio": self.changed_ratio,
            "mean_diff": self.mean_diff,
            "max_diff": self.max_diff,
            "laplacian_reference": self.laplacian_reference,
            "laplacian_candidate": self.laplacian_candidate,
            "sharpness_percentage_candidate_vs_reference": (
                self.sharpness_percentage_candidate_vs_reference
            ),
            "edge_change_ratio": self.edge_change_ratio,
            "severity_score": self.severity_score,
            "severity_label": self.severity_label,
            "accepted": self.accepted,
            "rejection_reasons": list(self.rejection_reasons),
        }


@dataclass(frozen=True, slots=True)
class FrameVerification:
    """Store verification evidence and status for one video frame."""

    frame_number: int
    timestamp_seconds: float
    candidate_region_count: int
    accepted_region_count: int
    rejected_region_count: int
    max_severity_score: float
    status: VerificationStatus
    accepted_regions: tuple[RegionMeasurement, ...] = ()
    rejected_regions: tuple[RegionMeasurement, ...] = ()

    @property
    def passed(self) -> bool:
        """Return whether the frame satisfied the active policy."""

        return self.status == VerificationStatus.PASS

    @property
    def failed(self) -> bool:
        """Return whether the frame violated the active policy."""

        return self.status == VerificationStatus.FAIL

    def to_dict(self) -> dict[str, object]:
        """Return serializable frame-level verification evidence.

        Returns:
            Dictionary containing frame measurements and region evidence.
        """

        return {
            "frame_number": self.frame_number,
            "timestamp_seconds": self.timestamp_seconds,
            "candidate_region_count": self.candidate_region_count,
            "accepted_region_count": self.accepted_region_count,
            "rejected_region_count": self.rejected_region_count,
            "max_severity_score": self.max_severity_score,
            "status": self.status.value,
            "accepted_regions": [
                region_obj.to_dict() for region_obj in self.accepted_regions
            ],
            "rejected_regions": [
                region_obj.to_dict() for region_obj in self.rejected_regions
            ],
        }


@dataclass(frozen=True, slots=True)
class VerificationFailure:
    """Represent one explicit policy violation or verification defect."""

    code: str
    message: str
    frame_number: int | None = None
    target_id: str | None = None
    measurements: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return serializable failure details.

        Returns:
            Dictionary containing identifiers and measured evidence.
        """

        return {
            "code": self.code,
            "message": self.message,
            "frame_number": self.frame_number,
            "target_id": self.target_id,
            "measurements": _serialize_mapping(self.measurements),
        }


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Represent the stable result returned by public verification APIs."""

    status: VerificationStatus
    reference_path: Path
    candidate_path: Path
    policy_name: str
    failures: tuple[VerificationFailure, ...] = ()
    failed_frames: tuple[int, ...] = ()
    measurements: dict[str, object] = field(default_factory=dict)
    evidence_paths: dict[str, Path] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return whether the verification completed successfully."""

        return self.status == VerificationStatus.PASS

    @property
    def failed(self) -> bool:
        """Return whether the verification found policy violations."""

        return self.status == VerificationStatus.FAIL

    @property
    def errored(self) -> bool:
        """Return whether the verification ended with an execution error."""

        return self.status == VerificationStatus.ERROR

    def with_evidence_paths(
        self,
        evidence_paths_mapping: Mapping[str, Path],
    ) -> VerificationResult:
        """Return a copy enriched with generated evidence paths.

        Args:
            evidence_paths_mapping: Named report and annotation paths.

        Returns:
            Immutable result copy containing the supplied paths.
        """

        return replace(
            self,
            evidence_paths=dict(evidence_paths_mapping),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a fully serializable result representation.

        Returns:
            Dictionary suitable for JSON reports and CLI output.
        """

        return {
            "status": self.status.value,
            "reference_path": str(self.reference_path),
            "candidate_path": str(self.candidate_path),
            "policy_name": self.policy_name,
            "failures": [
                failure_obj.to_dict() for failure_obj in self.failures
            ],
            "failed_frames": list(self.failed_frames),
            "measurements": _serialize_mapping(self.measurements),
            "evidence_paths": _serialize_path_mapping(
                self.evidence_paths,
            ),
        }

    def raise_for_failure(self) -> None:
        """Raise a structured exception when policy verification failed.

        Raises:
            VerificationFailedError: When the result status is ``FAIL``.
        """

        if not self.failed:
            return
        failure_details_str = "; ".join(
            f"{failure_obj.code}: {failure_obj.message}"
            for failure_obj in self.failures
        )
        raise VerificationFailedError(
            failure_details_str or DEFAULT_FAILURE_MESSAGE,
            context_mapping={
                "policy_name": self.policy_name,
                "failed_frames": list(self.failed_frames),
                "failure_count": len(self.failures),
            },
        )


def _serialize_path_mapping(
    path_values_mapping: Mapping[str, Path],
) -> dict[str, str]:
    """Convert named filesystem paths into string values.

    Args:
        path_values_mapping: Named filesystem paths to serialize.

    Returns:
        Dictionary containing the same names and string paths.
    """

    serialized_paths_dict: dict[str, str] = {}

    for path_name_str, path_obj in path_values_mapping.items():
        serialized_paths_dict[path_name_str] = str(path_obj)

    return serialized_paths_dict


def _serialize_mapping(
    values_mapping: Mapping[str, object],
) -> dict[str, object]:
    """Convert mapping values into report-safe Python objects.

    Args:
        values_mapping: Named values requiring recursive conversion.

    Returns:
        Dictionary containing JSON-compatible values when possible.
    """

    return {
        str(value_name_obj): _serialize_value(value_obj)
        for value_name_obj, value_obj in values_mapping.items()
    }


def _serialize_value(value_obj: object) -> object:
    """Convert common domain values into report-safe representations.

    Args:
        value_obj: Arbitrary measurement or diagnostic value.

    Returns:
        Recursively converted value suitable for standard JSON encoders.
    """

    if isinstance(value_obj, Path):
        return str(value_obj)
    if isinstance(value_obj, Enum):
        return value_obj.value
    if isinstance(value_obj, Mapping):
        return _serialize_mapping(value_obj)
    if isinstance(value_obj, Sequence) and not isinstance(
        value_obj,
        (str, bytes, bytearray),
    ):
        return [_serialize_value(item_obj) for item_obj in value_obj]
    return value_obj


__all__ = [
    "BoundingBox",
    "DetectionConfig",
    "FrameVerification",
    "MediaMetadata",
    "RegionMeasurement",
    "VerificationFailure",
    "VerificationResult",
    "VerificationStatus",
]
