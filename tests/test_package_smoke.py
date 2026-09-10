"""Test package imports, exported surface, and release metadata."""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

import pytest

import visual_verifier
from visual_verifier import (
    VerificationResult,
    VerificationStatus,
    __version__,
    verify_image,
    verify_video,
)
from visual_verifier.cli import main

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
CITATION_FILE_PATH = REPOSITORY_ROOT_PATH / "CITATION.cff"
CITATION_VERSION_PATTERN = re.compile(r"^version:\s*(\S+)\s*$", re.MULTILINE)
EXPECTED_VERSION_STR = "0.3.0"
EXPECTED_PUBLIC_EXPORTS_FROZENSET = frozenset(
    {
        "DEFAULT_DETECTION_CONFIG",
        "DEFAULT_TARGET_CONFIG",
        "DEFAULT_TRACKING_CONFIG",
        "BoundingBox",
        "ConfigurationError",
        "DetectionConfig",
        "FrameVerification",
        "MediaCompatibilityError",
        "MediaMetadata",
        "MediaReadError",
        "PolicyEvaluationError",
        "RegionMeasurement",
        "ReportWriteError",
        "Target",
        "TargetConfig",
        "TargetCoverage",
        "TargetSource",
        "TargetSummary",
        "TargetValidationError",
        "TrackingConfig",
        "VerificationFailedError",
        "VerificationFailure",
        "VerificationResult",
        "VerificationStatus",
        "VisualVerifierError",
        "__version__",
        "verify_image",
        "verify_video",
    }
)


def test_package_version_is_defined() -> None:
    """Confirm the importable package reports its release version."""

    assert __version__ == EXPECTED_VERSION_STR


def test_installed_metadata_matches_package_version() -> None:
    """Confirm packaging metadata is derived from one version constant."""

    assert metadata.version("visual-verifier") == __version__


def test_citation_metadata_matches_package_version() -> None:
    """Confirm citation metadata cannot drift from the package version."""

    citation_text = CITATION_FILE_PATH.read_text(encoding="utf-8")
    version_match_obj = CITATION_VERSION_PATTERN.search(citation_text)

    assert version_match_obj is not None
    assert version_match_obj.group(1) == __version__


def test_top_level_public_exports_are_stable() -> None:
    """Confirm only the supported package API is publicly exported."""

    assert (
        frozenset(visual_verifier.__all__) == EXPECTED_PUBLIC_EXPORTS_FROZENSET
    )


@pytest.mark.parametrize("export_name_str", sorted(visual_verifier.__all__))
def test_every_declared_export_is_importable(export_name_str: str) -> None:
    """Confirm every advertised export resolves to a real attribute."""

    assert hasattr(visual_verifier, export_name_str)


def test_public_verification_symbols_are_importable() -> None:
    """Confirm public functions and result models remain importable."""

    assert callable(verify_image)
    assert callable(verify_video)
    assert VerificationResult.__name__ == "VerificationResult"
    assert VerificationStatus.PASS.value == "PASS"


def test_doctor_command_reports_a_healthy_environment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Confirm the doctor command succeeds and prints key dependencies."""

    exit_code_int = main(["doctor"])
    captured_output_obj = capsys.readouterr()

    assert exit_code_int == 0
    assert "Visual Verifier environment check" in captured_output_obj.out
    assert f"Visual Verifier: {EXPECTED_VERSION_STR}" in (
        captured_output_obj.out
    )
    assert "OpenCV:" in captured_output_obj.out
    assert "Video codec:" in captured_output_obj.out
    assert "Environment status: OK" in captured_output_obj.out
    assert captured_output_obj.err == ""
