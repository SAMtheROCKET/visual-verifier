"""Generate and verify a self-contained demonstration.

A new user should be able to see a real anonymization failure without
cloning the repository, downloading fixtures, or supplying media of their
own. This module synthesizes a short scene in which a licence plate is
blurred on every frame except three, then verifies it.

The sample is generated rather than shipped: it keeps the wheel small,
needs no network access, and is reproducible on every platform. The clip
is deliberately synthetic, and the command says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from visual_verifier.api import verify_video
from visual_verifier.media.video_writer import open_annotated_writer
from visual_verifier.models import BoundingBox, VerificationResult
from visual_verifier.type_aliases import ImageArray, PathInput

DEMONSTRATION_DIRECTORY_NAME_STR = "visual-verifier-demo"
REFERENCE_FILENAME_STR = "reference.mp4"
CANDIDATE_FILENAME_STR = "candidate.mp4"
REPORT_DIRECTORY_NAME_STR = "report"

DEMONSTRATION_FRAME_COUNT_INT = 15
DEMONSTRATION_FRAME_RATE_FLOAT = 2.0
DEMONSTRATION_WIDTH_INT = 640
DEMONSTRATION_HEIGHT_INT = 360
UNPROCESSED_FRAMES_TUPLE = (4, 8, 12)

PLATE_WIDTH_INT = 96
PLATE_HEIGHT_INT = 40
PLATE_START_X_INT = 210
PLATE_TOP_Y_INT = 232
PLATE_STEP_X_INT = 14
PLATE_BLUR_PADDING_INT = 6
PLATE_BLUR_KERNEL_TUPLE = (31, 31)
PLATE_CHARACTER_COUNT_INT = 6

ROAD_TOP_Y_INT = 250
LANE_MARK_TOP_Y_INT = 320
LANE_MARK_HEIGHT_INT = 10
LANE_MARK_WIDTH_INT = 46
LANE_MARK_SPACING_INT = 90
LANE_MARK_SPEED_INT = 18

ROAD_COLOR_BGR = (70, 70, 74)
LANE_COLOR_BGR = (225, 225, 225)
VEHICLE_COLOR_BGR = (48, 44, 52)
WINDOW_COLOR_BGR = (30, 28, 34)
PLATE_COLOR_BGR = (242, 242, 238)
PLATE_CHARACTER_COLOR_BGR = (24, 24, 28)


@dataclass(frozen=True, slots=True)
class DemonstrationResult:
    """Report where the demonstration wrote its media and evidence.

    Attributes:
        reference_path: Generated original clip.
        candidate_path: Generated processed clip with three gaps.
        report_directory: Directory holding the generated evidence.
        verification_result: Result produced by the normal video API.
        expected_unprocessed_frames: Frames deliberately left unblurred.
    """

    reference_path: Path
    candidate_path: Path
    report_directory: Path
    verification_result: VerificationResult
    expected_unprocessed_frames: tuple[int, ...]

    @property
    def behaved_as_documented(self) -> bool:
        """Return whether the demonstration found exactly the gaps sown."""

        return (
            self.verification_result.failed
            and self.verification_result.failed_frames
            == self.expected_unprocessed_frames
        )


def run_demonstration(
    output_dir: PathInput | None = None,
) -> DemonstrationResult:
    """Generate a sample anonymization failure and verify it.

    Args:
        output_dir: Directory for the generated media and evidence.
            Defaults to ``./visual-verifier-demo``.

    Returns:
        Paths to every generated artefact and the verification result.

    Raises:
        ReportWriteError: When the sample media cannot be written, which
            usually means this OpenCV build has no usable video codec.
    """

    demonstration_path_obj = Path(
        output_dir or DEMONSTRATION_DIRECTORY_NAME_STR
    ).expanduser()
    demonstration_path_obj.mkdir(parents=True, exist_ok=True)
    reference_path_obj = demonstration_path_obj / REFERENCE_FILENAME_STR
    candidate_path_obj = demonstration_path_obj / CANDIDATE_FILENAME_STR
    report_path_obj = demonstration_path_obj / REPORT_DIRECTORY_NAME_STR

    _write_demonstration_video(reference_path_obj, apply_blur_bool=False)
    _write_demonstration_video(candidate_path_obj, apply_blur_bool=True)

    return DemonstrationResult(
        reference_path=reference_path_obj,
        candidate_path=candidate_path_obj,
        report_directory=report_path_obj,
        verification_result=verify_video(
            reference_path_obj,
            candidate_path_obj,
            output_dir=report_path_obj,
        ),
        expected_unprocessed_frames=UNPROCESSED_FRAMES_TUPLE,
    )


def _write_demonstration_video(
    output_path_obj: Path,
    *,
    apply_blur_bool: bool,
) -> None:
    """Write one generated clip, optionally blurring the licence plate.

    Args:
        output_path_obj: Destination MP4 path.
        apply_blur_bool: Blur the plate on every frame except the three
            deliberately unprocessed ones.

    Raises:
        ReportWriteError: When no supported codec can be opened.
    """

    video_writer_obj = open_annotated_writer(
        output_path_obj,
        DEMONSTRATION_FRAME_RATE_FLOAT,
        (DEMONSTRATION_WIDTH_INT, DEMONSTRATION_HEIGHT_INT),
    )
    try:
        for frame_number_int in range(1, DEMONSTRATION_FRAME_COUNT_INT + 1):
            frame_ndarray = _render_scene_frame(frame_number_int)
            if apply_blur_bool and (
                frame_number_int not in UNPROCESSED_FRAMES_TUPLE
            ):
                _blur_plate_region(frame_ndarray, frame_number_int)
            video_writer_obj.write(frame_ndarray)
    finally:
        video_writer_obj.release()


def _render_scene_frame(frame_number_int: int) -> ImageArray:
    """Render one deterministic frame of the sample scene.

    Args:
        frame_number_int: One-based frame number.

    Returns:
        Rendered frame containing a road, a vehicle, and a plate.
    """

    frame_ndarray: ImageArray = np.zeros(
        (DEMONSTRATION_HEIGHT_INT, DEMONSTRATION_WIDTH_INT, 3),
        dtype=np.uint8,
    )
    _draw_sky_and_road(frame_ndarray)
    _draw_lane_markings(frame_ndarray, frame_number_int)
    _draw_vehicle(frame_ndarray, _plate_box(frame_number_int))
    return frame_ndarray


def _draw_sky_and_road(frame_ndarray: ImageArray) -> None:
    """Fill the frame with a graded sky above a flat road surface."""

    for row_index_int in range(DEMONSTRATION_HEIGHT_INT):
        frame_ndarray[row_index_int, :] = (
            170 - row_index_int // 4,
            140 - row_index_int // 6,
            110 - row_index_int // 8,
        )
    cv2.rectangle(
        frame_ndarray,
        (0, ROAD_TOP_Y_INT),
        (DEMONSTRATION_WIDTH_INT, DEMONSTRATION_HEIGHT_INT),
        ROAD_COLOR_BGR,
        thickness=-1,
    )


def _draw_lane_markings(
    frame_ndarray: ImageArray,
    frame_number_int: int,
) -> None:
    """Draw lane markings that advance with the frame number."""

    total_span_int = DEMONSTRATION_WIDTH_INT + LANE_MARK_SPACING_INT
    for marking_index_int in range(-1, 9):
        left_x_int = (
            marking_index_int * LANE_MARK_SPACING_INT
            + frame_number_int * LANE_MARK_SPEED_INT
        ) % total_span_int - LANE_MARK_SPACING_INT // 2
        cv2.rectangle(
            frame_ndarray,
            (left_x_int, LANE_MARK_TOP_Y_INT),
            (
                left_x_int + LANE_MARK_WIDTH_INT,
                LANE_MARK_TOP_Y_INT + LANE_MARK_HEIGHT_INT,
            ),
            LANE_COLOR_BGR,
            thickness=-1,
        )


def _draw_vehicle(
    frame_ndarray: ImageArray,
    plate_box_obj: BoundingBox,
) -> None:
    """Draw the vehicle body, window, and readable licence plate."""

    cv2.rectangle(
        frame_ndarray,
        (plate_box_obj.x1 - 62, plate_box_obj.y1 - 96),
        (plate_box_obj.x2 + 62, plate_box_obj.y2 + 26),
        VEHICLE_COLOR_BGR,
        thickness=-1,
    )
    cv2.rectangle(
        frame_ndarray,
        (plate_box_obj.x1 - 54, plate_box_obj.y1 - 84),
        (plate_box_obj.x2 + 54, plate_box_obj.y1 - 30),
        WINDOW_COLOR_BGR,
        thickness=-1,
    )
    cv2.rectangle(
        frame_ndarray,
        (plate_box_obj.x1, plate_box_obj.y1),
        (plate_box_obj.x2, plate_box_obj.y2),
        PLATE_COLOR_BGR,
        thickness=-1,
    )
    for character_index_int in range(PLATE_CHARACTER_COUNT_INT):
        character_x_int = plate_box_obj.x1 + 8 + character_index_int * 14
        cv2.rectangle(
            frame_ndarray,
            (character_x_int, plate_box_obj.y1 + 9),
            (character_x_int + 9, plate_box_obj.y2 - 9),
            PLATE_CHARACTER_COLOR_BGR,
            thickness=-1,
        )


def _plate_box(frame_number_int: int) -> BoundingBox:
    """Return the licence-plate box for one frame of the sample scene.

    Args:
        frame_number_int: One-based frame number.

    Returns:
        Plate box that drifts steadily across the clip.
    """

    left_x_int = PLATE_START_X_INT + PLATE_STEP_X_INT * (frame_number_int - 1)
    return BoundingBox(
        left_x_int,
        PLATE_TOP_Y_INT,
        left_x_int + PLATE_WIDTH_INT,
        PLATE_TOP_Y_INT + PLATE_HEIGHT_INT,
    )


def _blur_plate_region(
    frame_ndarray: ImageArray,
    frame_number_int: int,
) -> None:
    """Blur the licence-plate region of one frame in place.

    Args:
        frame_ndarray: Frame modified in place.
        frame_number_int: One-based frame number.
    """

    plate_box_obj = _plate_box(frame_number_int)
    top_int = plate_box_obj.y1 - PLATE_BLUR_PADDING_INT
    bottom_int = plate_box_obj.y2 + PLATE_BLUR_PADDING_INT
    left_int = plate_box_obj.x1 - PLATE_BLUR_PADDING_INT
    right_int = plate_box_obj.x2 + PLATE_BLUR_PADDING_INT
    frame_ndarray[top_int:bottom_int, left_int:right_int] = cv2.GaussianBlur(
        frame_ndarray[top_int:bottom_int, left_int:right_int],
        PLATE_BLUR_KERNEL_TUPLE,
        0,
    )


__all__ = [
    "UNPROCESSED_FRAMES_TUPLE",
    "DemonstrationResult",
    "run_demonstration",
]
