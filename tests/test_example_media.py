"""Validate the bundled example-video fixtures."""

from pathlib import Path

import pytest

from visual_verifier.media import iter_video_pairs, read_video_metadata

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLE_MEDIA_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples" / "media"
EXAMPLE_VIDEO_FILENAMES_TUPLE = (
    "video_raw.mp4",
    "video_blur.mp4",
    "video_blur_partial.mp4",
)
CANDIDATE_VIDEO_FILENAMES_TUPLE = (
    "video_blur.mp4",
    "video_blur_partial.mp4",
)
EXPECTED_FRAME_COUNT_INT = 15
EXPECTED_FRAME_RATE_FLOAT = 2.0
EXPECTED_WIDTH_INT = 1280
EXPECTED_HEIGHT_INT = 720
EXPECTED_DURATION_SECONDS_FLOAT = 7.5


@pytest.mark.parametrize(
    "video_filename_str",
    EXAMPLE_VIDEO_FILENAMES_TUPLE,
)
def test_example_video_metadata(video_filename_str: str) -> None:
    """Confirm every bundled video has the expected normalized metadata."""

    video_path_obj = EXAMPLE_MEDIA_DIRECTORY_PATH / video_filename_str
    metadata_obj = read_video_metadata(video_path_obj)

    assert metadata_obj.path == video_path_obj.resolve()
    assert metadata_obj.media_type == "video"
    assert metadata_obj.frame_count == EXPECTED_FRAME_COUNT_INT
    assert metadata_obj.fps == pytest.approx(EXPECTED_FRAME_RATE_FLOAT)
    assert metadata_obj.resolution == (
        EXPECTED_WIDTH_INT,
        EXPECTED_HEIGHT_INT,
    )
    assert metadata_obj.duration_seconds == pytest.approx(
        EXPECTED_DURATION_SECONDS_FLOAT
    )


@pytest.mark.parametrize(
    "candidate_filename_str",
    CANDIDATE_VIDEO_FILENAMES_TUPLE,
)
def test_example_video_pairs_are_synchronized(
    candidate_filename_str: str,
) -> None:
    """Confirm reference and candidate fixtures decode in lockstep."""

    reference_path_obj = EXAMPLE_MEDIA_DIRECTORY_PATH / "video_raw.mp4"
    candidate_path_obj = EXAMPLE_MEDIA_DIRECTORY_PATH / candidate_filename_str
    decoded_pair_count_int = 0

    for frame_pair_tuple in iter_video_pairs(
        reference_path_obj,
        candidate_path_obj,
    ):
        (
            frame_number_int,
            reference_frame_ndarray,
            candidate_frame_ndarray,
        ) = frame_pair_tuple
        decoded_pair_count_int += 1

        assert frame_number_int == decoded_pair_count_int
        assert reference_frame_ndarray.shape == (
            EXPECTED_HEIGHT_INT,
            EXPECTED_WIDTH_INT,
            3,
        )
        assert candidate_frame_ndarray.shape == (reference_frame_ndarray.shape)

    assert decoded_pair_count_int == EXPECTED_FRAME_COUNT_INT
