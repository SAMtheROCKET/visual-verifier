"""Regression-test image verification and evidence output."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from visual_verifier import verify_image, verify_video
from visual_verifier.exceptions import MediaReadError
from visual_verifier.type_aliases import ImageArray

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLE_MEDIA_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples" / "media"
TEST_IMAGE_HEIGHT_INT = 32
TEST_IMAGE_WIDTH_INT = 32
ANNOTATED_VIDEO_FRAME_COUNT_INT = 15
ANNOTATED_VIDEO_WIDTH_INT = 1280
ANNOTATED_VIDEO_HEIGHT_INT = 720
EXPECTED_IMAGE_EVIDENCE_NAMES_FROZENSET = frozenset(
    {
        "annotated_image",
        "region_report",
        "summary_json",
    }
)


def _write_test_image(
    image_path_obj: Path,
    image_ndarray: ImageArray,
) -> None:
    """Write one test image and fail immediately if encoding fails."""

    image_written_bool = cv2.imwrite(
        str(image_path_obj),
        image_ndarray,
    )
    assert image_written_bool


def _create_identical_image_pair(
    temporary_directory_path_obj: Path,
) -> tuple[Path, Path]:
    """Create and return paths to two identical black test images."""

    reference_image_ndarray = np.zeros(
        (TEST_IMAGE_HEIGHT_INT, TEST_IMAGE_WIDTH_INT, 3),
        dtype=np.uint8,
    )
    candidate_image_ndarray = reference_image_ndarray.copy()
    reference_path_obj = temporary_directory_path_obj / "reference.png"
    candidate_path_obj = temporary_directory_path_obj / "candidate.png"
    _write_test_image(reference_path_obj, reference_image_ndarray)
    _write_test_image(candidate_path_obj, candidate_image_ndarray)
    return reference_path_obj, candidate_path_obj


def test_identical_images_fail_when_processing_is_expected(
    tmp_path: Path,
) -> None:
    """Confirm unchanged images fail when processing is mandatory."""

    reference_path_obj, candidate_path_obj = _create_identical_image_pair(
        tmp_path
    )

    result_obj = verify_image(
        reference_path_obj,
        candidate_path_obj,
        output_dir=tmp_path / "required_processing",
    )

    assert result_obj.failed
    assert result_obj.failed_frames == ()
    assert len(result_obj.failures) == 1
    assert result_obj.failures[0].code == "NO_PROCESSING_DETECTED"


def test_identical_images_pass_when_processing_is_optional(
    tmp_path: Path,
) -> None:
    """Confirm unchanged images pass when processing is optional."""

    reference_path_obj, candidate_path_obj = _create_identical_image_pair(
        tmp_path
    )

    result_obj = verify_image(
        reference_path_obj,
        candidate_path_obj,
        output_dir=tmp_path / "optional_processing",
        expect_processing=False,
    )

    assert result_obj.passed
    assert result_obj.failures == ()
    assert (
        frozenset(result_obj.evidence_paths)
        == EXPECTED_IMAGE_EVIDENCE_NAMES_FROZENSET
    )
    assert all(
        evidence_path_obj.exists()
        for evidence_path_obj in result_obj.evidence_paths.values()
    )


def test_missing_image_raises_structured_media_error(
    tmp_path: Path,
) -> None:
    """Confirm missing image inputs raise the package media exception."""

    missing_reference_path_obj = tmp_path / "missing_reference.png"
    missing_candidate_path_obj = tmp_path / "missing_candidate.png"

    with pytest.raises(MediaReadError) as error_info_obj:
        verify_image(
            missing_reference_path_obj,
            missing_candidate_path_obj,
        )

    assert error_info_obj.value.error_code == "MEDIA_READ_ERROR"
    assert error_info_obj.value.context_dict["media_type"] == "image"


def test_annotated_video_writer_creates_decodable_output(
    tmp_path: Path,
) -> None:
    """Confirm annotated evidence decodes with the reference geometry.

    A writer can open successfully and still produce an unplayable file
    when the host OpenCV build lacks a working encoder. Checking only the
    file size would hide that, so the evidence is decoded back.
    """

    result_obj = verify_video(
        EXAMPLE_MEDIA_DIRECTORY_PATH / "video_raw.mp4",
        EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur.mp4",
        output_dir=tmp_path / "video_result",
        save_annotated_video=True,
    )
    annotated_path_obj = result_obj.evidence_paths["annotated_video"]

    assert result_obj.passed
    assert annotated_path_obj.exists()
    assert annotated_path_obj.stat().st_size > 0

    decoded_frame_count_int = 0
    video_capture_obj = cv2.VideoCapture(str(annotated_path_obj))
    try:
        assert video_capture_obj.isOpened()
        while True:
            frame_read_bool, frame_ndarray = video_capture_obj.read()
            if not frame_read_bool:
                break
            assert frame_ndarray.shape == (
                ANNOTATED_VIDEO_HEIGHT_INT,
                ANNOTATED_VIDEO_WIDTH_INT,
                3,
            )
            decoded_frame_count_int += 1
    finally:
        video_capture_obj.release()

    assert decoded_frame_count_int == ANNOTATED_VIDEO_FRAME_COUNT_INT
