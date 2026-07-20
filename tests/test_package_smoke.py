"""Test package imports and command-line smoke behavior."""

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

EXPECTED_VERSION_STR = "0.2.0a0"
EXPECTED_PUBLIC_EXPORTS_FROZENSET = frozenset(
    {
        "VerificationResult",
        "VerificationStatus",
        "__version__",
        "verify_image",
        "verify_video",
    }
)


def test_package_version_is_defined() -> None:
    """Confirm the importable package reports its release version."""

    assert __version__ == EXPECTED_VERSION_STR


def test_top_level_public_exports_are_stable() -> None:
    """Confirm only the supported package API is publicly exported."""

    assert (
        frozenset(visual_verifier.__all__) == EXPECTED_PUBLIC_EXPORTS_FROZENSET
    )


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
    assert "Environment status: OK" in captured_output_obj.out
    assert captured_output_obj.err == ""
