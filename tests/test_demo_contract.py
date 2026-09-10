"""Execute the published example-media contract as a real regression.

``examples/expected/demo_expectations.json`` is the single declarative
source for the demo results quoted in the README, the changelog, and the
release checklist. Running it here prevents documentation drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from visual_verifier import verify_video

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLES_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples"
CONTRACT_FILE_PATH = (
    EXAMPLES_DIRECTORY_PATH / "expected" / "demo_expectations.json"
)


def _load_contract() -> dict[str, Any]:
    """Return the parsed declarative example contract.

    Returns:
        Mapping containing the schema version, frame count, and cases.
    """

    contract_text = CONTRACT_FILE_PATH.read_text(encoding="utf-8")
    loaded_contract_obj: dict[str, Any] = json.loads(contract_text)
    return loaded_contract_obj


DEMO_CONTRACT_DICT = _load_contract()
DEMO_CASE_NAMES_LIST = sorted(DEMO_CONTRACT_DICT["cases"])


def test_contract_declares_every_bundled_case() -> None:
    """Confirm the contract still covers both bundled comparisons."""

    assert DEMO_CONTRACT_DICT["schema_version"] == "1.0"
    assert DEMO_CASE_NAMES_LIST == ["full_blur", "partial_blur"]


@pytest.mark.parametrize("case_name_str", DEMO_CASE_NAMES_LIST)
def test_declared_media_paths_exist(case_name_str: str) -> None:
    """Confirm every declared fixture path resolves to a shipped file."""

    case_dict = DEMO_CONTRACT_DICT["cases"][case_name_str]

    for media_key_str in ("reference", "candidate"):
        media_path_obj = EXAMPLES_DIRECTORY_PATH / case_dict[media_key_str]
        assert media_path_obj.is_file()


@pytest.mark.parametrize("case_name_str", DEMO_CASE_NAMES_LIST)
def test_declared_case_matches_measured_behaviour(
    case_name_str: str,
    tmp_path: Path,
) -> None:
    """Confirm each published expectation matches a real verification run."""

    case_dict = DEMO_CONTRACT_DICT["cases"][case_name_str]
    result_obj = verify_video(
        EXAMPLES_DIRECTORY_PATH / case_dict["reference"],
        EXAMPLES_DIRECTORY_PATH / case_dict["candidate"],
        output_dir=tmp_path / case_name_str,
        save_annotated_video=False,
    )

    assert result_obj.status.value == case_dict["expected_status"]
    assert (
        list(result_obj.failed_frames) == (case_dict["expected_failed_frames"])
    )
    assert (
        result_obj.measurements["frames_checked"]
        == (DEMO_CONTRACT_DICT["frame_count"])
    )
    assert (
        result_obj.measurements["processing_coverage_percent"]
        == (case_dict["expected_processing_coverage_percent"])
    )
