"""Synthesize the sequence families of the Anonymization Gap Benchmark.

Every sequence is a pair of clips: a reference scene and a candidate in
which a licence plate should have been anonymized. Some candidates are
anonymized correctly, and some carry a deliberate, labelled failure.

The scenes are generated rather than collected. Real anonymized footage
cannot be published without the very privacy problem this tool exists to
check, and a generated scene lets each failure mode be varied one at a
time with exact ground truth. The generator is parameterized in ways the
shipped `visual_verifier.demo` scene is not, which is why it does not
reuse it: the benchmark needs to vary target size, target count, and
motion, and the demo deliberately does not.

Everything here is deterministic. The same seed produces the same bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import cv2
import numpy as np

from visual_verifier.media.video_writer import open_annotated_writer
from visual_verifier.type_aliases import ImageArray

FRAME_COUNT_INT = 20
FRAME_RATE_FLOAT = 5.0
FRAME_WIDTH_INT = 640
FRAME_HEIGHT_INT = 360

PLATE_WIDTH_INT = 96
PLATE_HEIGHT_INT = 40
PLATE_TOP_Y_INT = 232
PLATE_BLUR_PADDING_INT = 6
STRONG_BLUR_KERNEL_TUPLE = (31, 31)
WEAK_BLUR_KERNEL_TUPLE = (3, 3)
OFFSET_BLUR_SHIFT_INT = 140

ROAD_TOP_Y_INT = 250
LANE_MARK_TOP_Y_INT = 320
LANE_MARK_HEIGHT_INT = 10
LANE_MARK_WIDTH_INT = 46
LANE_MARK_SPACING_INT = 90
LANE_MARK_SPEED_INT = 18

ROAD_COLOR_BGR = (70, 70, 74)
LANE_COLOR_BGR = (225, 225, 225)
VEHICLE_COLOR_BGR = (48, 44, 52)
PLATE_COLOR_BGR = (242, 242, 238)
PLATE_CHARACTER_COLOR_BGR = (24, 24, 28)

COMPRESSION_QUALITY_INT = 30
SENSOR_NOISE_SCALE_FLOAT = 2.0


class Protection(Enum):
    """How a candidate frame treats the target that must be anonymized.

    Attributes:
        STRONG: Correctly anonymized with a heavy blur.
        NONE: Left completely untouched.
        WEAK: Blurred so lightly the characters stay readable.
        OFFSET: Blurred, but the blur lands beside the target.
        PARTIAL: Only part of the target is covered.
    """

    STRONG = "strong"
    NONE = "none"
    WEAK = "weak"
    OFFSET = "offset"
    PARTIAL = "partial"

    @property
    def leaves_target_exposed(self) -> bool:
        """Return whether this treatment fails to anonymize the target."""

        return self is not Protection.STRONG


@dataclass(frozen=True, slots=True)
class SceneSpec:
    """Describe the scene a sequence family renders.

    Attributes:
        target_count_int: Number of licence plates in the scene.
        target_scale_float: Plate size relative to the default.
        motion_step_int: Horizontal pixels a plate moves per frame.
        add_compression_bool: Re-encode the candidate as low-quality JPEG.
        add_sensor_noise_bool: Add reference-only noise, as a real second
            capture of the same scene would carry.
    """

    target_count_int: int = 1
    target_scale_float: float = 1.0
    motion_step_int: int = 14
    add_compression_bool: bool = False
    add_sensor_noise_bool: bool = False


@dataclass(frozen=True, slots=True)
class BenchmarkSequence:
    """One generated reference and candidate pair with its ground truth.

    Attributes:
        scenario_name_str: Family the sequence belongs to.
        sequence_id_str: Unique identifier including the seed.
        reference_path: Generated reference clip.
        candidate_path: Generated candidate clip.
        exposed_frames_tuple: One-based frames where the target was left
            exposed. This is the ground truth every method is scored on.
        frame_count_int: Frames in each clip.
        seed_int: Layout seed, used to split calibration from evaluation.
        is_calibration_family_bool: Whether the family may be tuned on.
    """

    scenario_name_str: str
    sequence_id_str: str
    reference_path: Path
    candidate_path: Path
    exposed_frames_tuple: tuple[int, ...]
    frame_count_int: int
    seed_int: int
    is_calibration_family_bool: bool


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """Describe one benchmark family.

    Attributes:
        name_str: Short family identifier used in reports.
        description_str: What failure mode the family probes.
        scene_spec: Scene parameters shared by every sequence.
        exposed_frames_tuple: Frames carrying the failure.
        protection: Treatment applied to those frames.
        is_calibration_family_bool: Whether a team calibrating a
            threshold would plausibly have this footage in hand. Only
            these families are offered to the baselines for tuning.
    """

    name_str: str
    description_str: str
    scene_spec: SceneSpec
    exposed_frames_tuple: tuple[int, ...]
    protection: Protection
    is_calibration_family_bool: bool = False


SCENARIO_SPECS_TUPLE: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        name_str="fully_anonymized",
        description_str="Every frame correctly blurred. Nothing to find.",
        scene_spec=SceneSpec(),
        exposed_frames_tuple=(),
        protection=Protection.STRONG,
        is_calibration_family_bool=True,
    ),
    ScenarioSpec(
        name_str="one_missed_frame",
        description_str="A single frame slipped through unblurred.",
        scene_spec=SceneSpec(),
        exposed_frames_tuple=(9,),
        protection=Protection.NONE,
        is_calibration_family_bool=True,
    ),
    ScenarioSpec(
        name_str="three_missed_frames",
        description_str="Three scattered frames slipped through.",
        scene_spec=SceneSpec(),
        exposed_frames_tuple=(4, 11, 17),
        protection=Protection.NONE,
        is_calibration_family_bool=True,
    ),
    ScenarioSpec(
        name_str="long_gap",
        description_str="Five consecutive frames left unprotected.",
        scene_spec=SceneSpec(),
        exposed_frames_tuple=(8, 9, 10, 11, 12),
        protection=Protection.NONE,
        is_calibration_family_bool=True,
    ),
    ScenarioSpec(
        name_str="weak_blur",
        description_str="Blur applied, but too light to anonymize.",
        scene_spec=SceneSpec(),
        exposed_frames_tuple=(6, 13),
        protection=Protection.WEAK,
    ),
    ScenarioSpec(
        name_str="partial_region",
        description_str="Only half the plate was covered.",
        scene_spec=SceneSpec(),
        exposed_frames_tuple=(5, 12),
        protection=Protection.PARTIAL,
    ),
    ScenarioSpec(
        name_str="offset_blur",
        description_str="Blur landed beside the plate, not on it.",
        scene_spec=SceneSpec(),
        exposed_frames_tuple=(7, 14),
        protection=Protection.OFFSET,
    ),
    ScenarioSpec(
        name_str="fast_motion",
        description_str="Plate crosses the frame quickly.",
        scene_spec=SceneSpec(motion_step_int=26),
        exposed_frames_tuple=(6, 15),
        protection=Protection.NONE,
        is_calibration_family_bool=True,
    ),
    ScenarioSpec(
        name_str="small_target",
        description_str="Plate covers a small fraction of the frame.",
        scene_spec=SceneSpec(target_scale_float=0.25),
        exposed_frames_tuple=(5, 10, 15),
        protection=Protection.NONE,
    ),
    ScenarioSpec(
        name_str="multiple_targets",
        description_str="Three plates; one is missed while others are not.",
        scene_spec=SceneSpec(target_count_int=3),
        exposed_frames_tuple=(6, 13),
        protection=Protection.NONE,
    ),
    ScenarioSpec(
        name_str="compressed",
        description_str="Candidate re-encoded, so every pixel moved a little.",
        scene_spec=SceneSpec(add_compression_bool=True),
        exposed_frames_tuple=(7, 14),
        protection=Protection.NONE,
    ),
    ScenarioSpec(
        name_str="compressed_small_target",
        description_str=(
            "A small plate missed in footage where every pixel moved."
        ),
        scene_spec=SceneSpec(
            target_scale_float=0.25, add_compression_bool=True
        ),
        exposed_frames_tuple=(6, 13),
        protection=Protection.NONE,
    ),
    ScenarioSpec(
        name_str="sensor_noise",
        description_str="Reference carries capture noise the candidate lacks.",
        scene_spec=SceneSpec(add_sensor_noise_bool=True),
        exposed_frames_tuple=(8, 15),
        protection=Protection.NONE,
    ),
)


def build_sequences(
    output_directory_path: Path,
    seeds_tuple: tuple[int, ...],
) -> list[BenchmarkSequence]:
    """Generate every benchmark sequence under one directory.

    Args:
        output_directory_path: Directory the clips are written into.
        seeds_tuple: Seeds to repeat each family with. Each seed shifts
            the scene so a family is measured over several layouts.

    Returns:
        Every generated sequence, in a stable order.
    """

    sequences_list: list[BenchmarkSequence] = []
    for scenario_spec in SCENARIO_SPECS_TUPLE:
        for seed_int in seeds_tuple:
            sequences_list.append(
                _build_one_sequence(
                    output_directory_path, scenario_spec, seed_int
                )
            )
    return sequences_list


def _build_one_sequence(
    output_directory_path: Path,
    scenario_spec: ScenarioSpec,
    seed_int: int,
) -> BenchmarkSequence:
    """Render and write one reference and candidate pair.

    Args:
        output_directory_path: Directory the clips are written into.
        scenario_spec: Family being generated.
        seed_int: Seed shifting the scene layout.

    Returns:
        The generated sequence and its ground truth.
    """

    sequence_id_str = f"{scenario_spec.name_str}_seed{seed_int:02d}"
    sequence_directory_path = output_directory_path / sequence_id_str
    sequence_directory_path.mkdir(parents=True, exist_ok=True)
    reference_path_obj = sequence_directory_path / "reference.mp4"
    candidate_path_obj = sequence_directory_path / "candidate.mp4"

    _write_clip(
        reference_path_obj,
        scenario_spec,
        seed_int,
        is_candidate_bool=False,
    )
    _write_clip(
        candidate_path_obj,
        scenario_spec,
        seed_int,
        is_candidate_bool=True,
    )

    return BenchmarkSequence(
        scenario_name_str=scenario_spec.name_str,
        sequence_id_str=sequence_id_str,
        reference_path=reference_path_obj,
        candidate_path=candidate_path_obj,
        exposed_frames_tuple=scenario_spec.exposed_frames_tuple,
        frame_count_int=FRAME_COUNT_INT,
        seed_int=seed_int,
        is_calibration_family_bool=(scenario_spec.is_calibration_family_bool),
    )


def _write_clip(
    output_path_obj: Path,
    scenario_spec: ScenarioSpec,
    seed_int: int,
    *,
    is_candidate_bool: bool,
) -> None:
    """Write one clip of a sequence.

    Args:
        output_path_obj: Destination MP4 path.
        scenario_spec: Family being generated.
        seed_int: Seed shifting the scene layout.
        is_candidate_bool: Apply anonymization treatment when true.

    Raises:
        ReportWriteError: When no supported codec can be opened.
    """

    scene_spec = scenario_spec.scene_spec
    writer_obj = open_annotated_writer(
        output_path_obj,
        FRAME_RATE_FLOAT,
        (FRAME_WIDTH_INT, FRAME_HEIGHT_INT),
    )
    try:
        for frame_number_int in range(1, FRAME_COUNT_INT + 1):
            frame_ndarray = render_frame(
                frame_number_int, scene_spec, seed_int
            )
            if is_candidate_bool:
                _apply_treatment(
                    frame_ndarray, frame_number_int, scenario_spec, seed_int
                )
                if scene_spec.add_compression_bool:
                    frame_ndarray = _recompress(frame_ndarray)
            elif scene_spec.add_sensor_noise_bool:
                frame_ndarray = _add_sensor_noise(
                    frame_ndarray, frame_number_int, seed_int
                )
            writer_obj.write(frame_ndarray)
    finally:
        writer_obj.release()


def _apply_treatment(
    frame_ndarray: ImageArray,
    frame_number_int: int,
    scenario_spec: ScenarioSpec,
    seed_int: int,
) -> None:
    """Anonymize every target in place, honouring the family's failure.

    Args:
        frame_ndarray: Frame modified in place.
        frame_number_int: One-based frame number.
        scenario_spec: Family being generated.
        seed_int: Seed shifting the scene layout.
    """

    scene_spec = scenario_spec.scene_spec
    is_failing_frame_bool = (
        frame_number_int in scenario_spec.exposed_frames_tuple
    )
    boxes_list = target_boxes(frame_number_int, scene_spec, seed_int)

    for target_index_int, box_tuple in enumerate(boxes_list):
        protection_obj = Protection.STRONG
        if is_failing_frame_bool and target_index_int == 0:
            protection_obj = scenario_spec.protection
        _blur_box(frame_ndarray, box_tuple, protection_obj)


def _blur_box(
    frame_ndarray: ImageArray,
    box_tuple: tuple[int, int, int, int],
    protection_obj: Protection,
) -> None:
    """Apply one anonymization treatment to one target box.

    Args:
        frame_ndarray: Frame modified in place.
        box_tuple: Target box as ``(left, top, right, bottom)``.
        protection_obj: Treatment to apply.
    """

    if protection_obj is Protection.NONE:
        return

    left_int, top_int, right_int, bottom_int = box_tuple
    padding_int = PLATE_BLUR_PADDING_INT
    kernel_tuple = STRONG_BLUR_KERNEL_TUPLE

    if protection_obj is Protection.WEAK:
        kernel_tuple = WEAK_BLUR_KERNEL_TUPLE
    elif protection_obj is Protection.OFFSET:
        left_int += OFFSET_BLUR_SHIFT_INT
        right_int += OFFSET_BLUR_SHIFT_INT
    elif protection_obj is Protection.PARTIAL:
        right_int = left_int + (right_int - left_int) // 2

    region_slice = (
        slice(
            max(0, top_int - padding_int),
            min(FRAME_HEIGHT_INT, bottom_int + padding_int),
        ),
        slice(
            max(0, left_int - padding_int),
            min(FRAME_WIDTH_INT, right_int + padding_int),
        ),
    )
    region_ndarray = frame_ndarray[region_slice]
    if region_ndarray.size == 0:
        return
    frame_ndarray[region_slice] = cv2.GaussianBlur(
        region_ndarray, kernel_tuple, 0
    )


def render_frame(
    frame_number_int: int,
    scene_spec: SceneSpec,
    seed_int: int,
) -> ImageArray:
    """Render one deterministic scene frame.

    Args:
        frame_number_int: One-based frame number.
        scene_spec: Scene parameters.
        seed_int: Seed shifting the scene layout.

    Returns:
        The rendered frame.
    """

    frame_ndarray: ImageArray = np.zeros(
        (FRAME_HEIGHT_INT, FRAME_WIDTH_INT, 3), dtype=np.uint8
    )
    _draw_background(frame_ndarray)
    _draw_lane_markings(frame_ndarray, frame_number_int)
    for box_tuple in target_boxes(frame_number_int, scene_spec, seed_int):
        _draw_vehicle_with_plate(frame_ndarray, box_tuple)
    return frame_ndarray


def target_boxes(
    frame_number_int: int,
    scene_spec: SceneSpec,
    seed_int: int,
) -> list[tuple[int, int, int, int]]:
    """Return every target box in one frame.

    Args:
        frame_number_int: One-based frame number.
        scene_spec: Scene parameters.
        seed_int: Seed shifting the scene layout.

    Returns:
        Boxes as ``(left, top, right, bottom)``, the first being the
        target whose anonymization the benchmark scores.
    """

    width_int = max(8, int(PLATE_WIDTH_INT * scene_spec.target_scale_float))
    height_int = max(6, int(PLATE_HEIGHT_INT * scene_spec.target_scale_float))
    boxes_list: list[tuple[int, int, int, int]] = []

    for target_index_int in range(scene_spec.target_count_int):
        start_x_int = 60 + (seed_int * 13) + (target_index_int * 190)
        left_int = start_x_int + frame_number_int * scene_spec.motion_step_int
        left_int %= FRAME_WIDTH_INT - width_int - 20
        left_int += 10
        top_int = PLATE_TOP_Y_INT - (target_index_int * 26)
        boxes_list.append(
            (left_int, top_int, left_int + width_int, top_int + height_int)
        )

    return boxes_list


def _draw_background(frame_ndarray: ImageArray) -> None:
    """Fill the frame with a graded sky above a flat road surface."""

    for row_index_int in range(FRAME_HEIGHT_INT):
        frame_ndarray[row_index_int, :] = (
            170 - row_index_int // 4,
            140 - row_index_int // 6,
            110 - row_index_int // 8,
        )
    cv2.rectangle(
        frame_ndarray,
        (0, ROAD_TOP_Y_INT),
        (FRAME_WIDTH_INT, FRAME_HEIGHT_INT),
        ROAD_COLOR_BGR,
        thickness=-1,
    )


def _draw_lane_markings(
    frame_ndarray: ImageArray,
    frame_number_int: int,
) -> None:
    """Draw scrolling lane markings so the road is not a flat block."""

    offset_int = (
        frame_number_int * LANE_MARK_SPEED_INT
    ) % LANE_MARK_SPACING_INT
    for start_x_int in range(
        -LANE_MARK_SPACING_INT, FRAME_WIDTH_INT, LANE_MARK_SPACING_INT
    ):
        left_int = start_x_int + offset_int
        cv2.rectangle(
            frame_ndarray,
            (left_int, LANE_MARK_TOP_Y_INT),
            (
                left_int + LANE_MARK_WIDTH_INT,
                LANE_MARK_TOP_Y_INT + LANE_MARK_HEIGHT_INT,
            ),
            LANE_COLOR_BGR,
            thickness=-1,
        )


def _draw_vehicle_with_plate(
    frame_ndarray: ImageArray,
    box_tuple: tuple[int, int, int, int],
) -> None:
    """Draw a vehicle body behind one readable licence plate.

    Args:
        frame_ndarray: Frame modified in place.
        box_tuple: Plate box as ``(left, top, right, bottom)``.
    """

    left_int, top_int, right_int, bottom_int = box_tuple
    plate_width_int = right_int - left_int
    plate_height_int = bottom_int - top_int

    cv2.rectangle(
        frame_ndarray,
        (left_int - plate_width_int // 2, top_int - plate_height_int * 2),
        (right_int + plate_width_int // 2, bottom_int + plate_height_int // 2),
        VEHICLE_COLOR_BGR,
        thickness=-1,
    )
    cv2.rectangle(
        frame_ndarray,
        (left_int, top_int),
        (right_int, bottom_int),
        PLATE_COLOR_BGR,
        thickness=-1,
    )
    _draw_plate_characters(frame_ndarray, box_tuple)


def _draw_plate_characters(
    frame_ndarray: ImageArray,
    box_tuple: tuple[int, int, int, int],
) -> None:
    """Draw readable character bars inside one plate box.

    Args:
        frame_ndarray: Frame modified in place.
        box_tuple: Plate box as ``(left, top, right, bottom)``.
    """

    left_int, top_int, right_int, bottom_int = box_tuple
    character_count_int = 6
    span_int = (right_int - left_int) // (character_count_int + 1)
    if span_int <= 0:
        return

    for character_index_int in range(character_count_int):
        character_left_int = (
            left_int + span_int // 2 + character_index_int * span_int
        )
        cv2.rectangle(
            frame_ndarray,
            (character_left_int, top_int + 6),
            (character_left_int + max(2, span_int // 2), bottom_int - 6),
            PLATE_CHARACTER_COLOR_BGR,
            thickness=-1,
        )


def _recompress(frame_ndarray: ImageArray) -> ImageArray:
    """Return the frame after a lossy JPEG round trip.

    Args:
        frame_ndarray: Frame to re-encode.

    Returns:
        The re-encoded frame, or the original if encoding failed.
    """

    encoded_ok_bool, encoded_ndarray = cv2.imencode(
        ".jpg",
        frame_ndarray,
        [int(cv2.IMWRITE_JPEG_QUALITY), COMPRESSION_QUALITY_INT],
    )
    if not encoded_ok_bool:
        return frame_ndarray
    decoded_ndarray: ImageArray = cv2.imdecode(
        encoded_ndarray, cv2.IMREAD_COLOR
    )
    return decoded_ndarray


def _add_sensor_noise(
    frame_ndarray: ImageArray,
    frame_number_int: int,
    seed_int: int,
) -> ImageArray:
    """Return the frame with deterministic capture noise added.

    Args:
        frame_ndarray: Frame to disturb.
        frame_number_int: One-based frame number, mixed into the seed.
        seed_int: Sequence seed.

    Returns:
        The noisy frame.
    """

    generator_obj = np.random.default_rng(seed_int * 1000 + frame_number_int)
    noise_ndarray = generator_obj.normal(
        0.0, SENSOR_NOISE_SCALE_FLOAT, frame_ndarray.shape
    )
    noisy_ndarray: ImageArray = np.clip(
        frame_ndarray.astype(np.float64) + noise_ndarray, 0, 255
    ).astype(np.uint8)
    return noisy_ndarray
