"""Protect configuration validation and serialization guarantees."""

from __future__ import annotations

import json

import pytest

from visual_verifier import (
    DEFAULT_DETECTION_CONFIG,
    DEFAULT_TRACKING_CONFIG,
    ConfigurationError,
    DetectionConfig,
    TrackingConfig,
)

INVALID_DETECTION_FIELDS_LIST: list[tuple[str, float]] = [
    ("diff_threshold", -1),
    ("min_box_area", -1),
    ("min_box_width", -1),
    ("min_box_height", -1),
    ("merge_kernel_size", 0),
    ("box_padding", -1),
    ("min_changed_ratio", -0.1),
    ("min_mean_diff", -1.0),
    ("min_severity_score", -1.0),
    ("diff_normalizer", 0.0),
    ("changed_ratio_normalizer", 0.0),
]
INVALID_TRACKING_FIELDS_LIST: list[tuple[str, float]] = [
    ("association_iou_threshold", -0.1),
    ("association_iou_threshold", 1.1),
    ("minimum_confirmation_hits", 0),
    ("maximum_gap_frames", -1),
    ("lineage_overlap_threshold", 1.5),
]


@pytest.mark.parametrize(
    ("field_name_str", "invalid_value_obj"),
    INVALID_DETECTION_FIELDS_LIST,
)
def test_detection_config_rejects_invalid_thresholds(
    field_name_str: str,
    invalid_value_obj: float,
) -> None:
    """Confirm every detection threshold is validated at construction."""

    with pytest.raises(ConfigurationError) as error_info_obj:
        DetectionConfig(**{field_name_str: invalid_value_obj})

    assert error_info_obj.value.error_code == "CONFIGURATION_ERROR"
    assert (
        field_name_str in (error_info_obj.value.context_dict["invalid_fields"])
    )


@pytest.mark.parametrize(
    ("field_name_str", "invalid_value_obj"),
    INVALID_TRACKING_FIELDS_LIST,
)
def test_tracking_config_rejects_invalid_thresholds(
    field_name_str: str,
    invalid_value_obj: float,
) -> None:
    """Confirm every tracking threshold is validated at construction."""

    with pytest.raises(ConfigurationError) as error_info_obj:
        TrackingConfig(**{field_name_str: invalid_value_obj})

    assert error_info_obj.value.error_code == "CONFIGURATION_ERROR"
    assert (
        field_name_str in (error_info_obj.value.context_dict["invalid_fields"])
    )


def test_default_configurations_are_valid_and_immutable() -> None:
    """Confirm shipped defaults construct cleanly and cannot be mutated."""

    assert DetectionConfig() == DEFAULT_DETECTION_CONFIG
    assert TrackingConfig() == DEFAULT_TRACKING_CONFIG

    with pytest.raises(AttributeError):
        DEFAULT_DETECTION_CONFIG.diff_threshold = 99  # type: ignore[misc]

    with pytest.raises(AttributeError):
        DEFAULT_TRACKING_CONFIG.maximum_gap_frames = 99  # type: ignore[misc]


def test_configuration_dictionaries_are_json_serializable() -> None:
    """Confirm configuration snapshots survive the report round trip."""

    detection_dict = DEFAULT_DETECTION_CONFIG.to_dict()
    tracking_dict = DEFAULT_TRACKING_CONFIG.to_dict()

    assert json.loads(json.dumps(detection_dict)) == detection_dict
    assert json.loads(json.dumps(tracking_dict)) == tracking_dict
    assert set(detection_dict) == set(DetectionConfig.__dataclass_fields__)
    assert set(tracking_dict) == set(TrackingConfig.__dataclass_fields__)


def test_configuration_error_serializes_its_diagnostic_context() -> None:
    """Confirm structured errors expose a stable machine-readable shape."""

    with pytest.raises(ConfigurationError) as error_info_obj:
        TrackingConfig(maximum_gap_frames=-5)

    error_dict = error_info_obj.value.to_dict()

    assert error_dict["error_code"] == "CONFIGURATION_ERROR"
    assert error_dict["message"]
    assert json.loads(json.dumps(error_dict)) == error_dict
