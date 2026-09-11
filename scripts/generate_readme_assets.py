"""Generate the README demonstration assets from the bundled fixtures.

Every pixel in the generated assets comes from a real verification run
over `examples/media/`, and the tracked region boxes are read back from
the generated reports. Nothing here is mocked or hand-drawn, so the
documentation cannot show behaviour the tool does not have.

Pillow is needed only to assemble the animated GIF and is deliberately
not a project dependency. Run this from the repository root with:

    uv run --with pillow python scripts/generate_readme_assets.py
"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from visual_verifier import verify_video
from visual_verifier.type_aliases import ImageArray

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLE_MEDIA_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples" / "media"
ASSET_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "docs" / "assets"
DEMO_GIF_FILENAME_STR = "verification_demo.gif"
CLOSEUP_FILENAME_STR = "missed_frame_closeup.png"
COMPARISON_FILENAME_STR = "pass_fail_comparison.png"
PRIMARY_TRACK_LABEL_STR = "T001"

PANEL_WIDTH_INT = 640
BANNER_HEIGHT_INT = 48
FRAME_VIEW_HEIGHT_INT = 360
CROP_LABEL_HEIGHT_INT = 22
CROP_HEIGHT_INT = 152
CROP_WIDTH_INT = 308
CROP_GAP_INT = 24
CROP_ZOOM_FACTOR_FLOAT = 2.2

BACKGROUND_COLOR_BGR = (34, 32, 30)
TEXT_COLOR_BGR = (238, 238, 238)
MUTED_TEXT_COLOR_BGR = (168, 166, 164)
PASS_COLOR_BGR = (110, 196, 92)
FAIL_COLOR_BGR = (72, 76, 236)
FONT_FACE = cv2.FONT_HERSHEY_DUPLEX

COMPARISON_TITLE_HEIGHT_INT = 36
COMPARISON_CAPTION_HEIGHT_INT = 26
COMPARISON_FOOTER_HEIGHT_INT = 36
PASS_FRAME_DURATION_MS = 520
FAIL_FRAME_DURATION_MS = 1100
GIF_PALETTE_SIZE_INT = 96
VERDICT_DURATION_MS = 2600
VERDICT_TITLE_TEXT = "FAIL"
VERDICT_FOOTER_TEXT = "pip install visual-verifier"


def main() -> int:
    """Generate every README asset and report where it was written.

    Returns:
        Process exit code. ``0`` on success and ``1`` when Pillow, which
        is required only for GIF assembly, is unavailable.
    """

    try:
        from PIL import Image
    except ImportError:
        print(
            "Pillow is required. Run:\n"
            "  uv run --with pillow python "
            "scripts/generate_readme_assets.py",
            file=sys.stderr,
        )
        return 1

    ASSET_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    reference_frames_list = _load_frames("video_raw.mp4")
    candidate_frames_list = _load_frames("video_blur_partial.mp4")

    with tempfile.TemporaryDirectory() as temporary_directory_str:
        evidence_path_obj = Path(temporary_directory_str)
        failed_frames_frozenset, track_boxes_dict = _run_verification(
            evidence_path_obj
        )

    panels_list = [
        _build_panel(
            frame_number_int,
            reference_frames_list[frame_number_int - 1],
            candidate_frames_list[frame_number_int - 1],
            _resolve_box(track_boxes_dict, frame_number_int),
            frame_number_int not in failed_frames_frozenset,
            len(reference_frames_list),
        )
        for frame_number_int in range(1, len(reference_frames_list) + 1)
    ]

    _write_gif(Image, panels_list, failed_frames_frozenset)
    _write_closeup(panels_list, sorted(failed_frames_frozenset)[0])
    _write_comparison(
        candidate_frames_list,
        track_boxes_dict,
        sorted(failed_frames_frozenset),
        len(reference_frames_list),
    )
    return 0


def _load_frames(media_filename_str: str) -> list[ImageArray]:
    """Decode every frame of one bundled fixture video.

    Args:
        media_filename_str: Filename inside ``examples/media``.

    Returns:
        Decoded frames in presentation order.
    """

    video_capture_obj = cv2.VideoCapture(
        str(EXAMPLE_MEDIA_DIRECTORY_PATH / media_filename_str)
    )
    decoded_frames_list: list[ImageArray] = []
    try:
        while True:
            frame_read_bool, frame_ndarray = video_capture_obj.read()
            if not frame_read_bool:
                break
            decoded_frames_list.append(frame_ndarray)
    finally:
        video_capture_obj.release()
    return decoded_frames_list


def _run_verification(
    evidence_path_obj: Path,
) -> tuple[frozenset[int], dict[int, tuple[int, int, int, int]]]:
    """Verify the partial-blur fixture and read the tracked region boxes.

    Args:
        evidence_path_obj: Temporary directory for generated reports.

    Returns:
        Failed frame numbers, and the primary track box per observed
        frame taken from ``track_observation_report.csv``.
    """

    result_obj = verify_video(
        EXAMPLE_MEDIA_DIRECTORY_PATH / "video_raw.mp4",
        EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur_partial.mp4",
        output_dir=evidence_path_obj,
        save_annotated_video=False,
    )
    observation_path_obj = result_obj.evidence_paths[
        "track_observation_report"
    ]
    track_boxes_dict: dict[int, tuple[int, int, int, int]] = {}

    with observation_path_obj.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as report_file_obj:
        for report_row_dict in csv.DictReader(report_file_obj):
            if report_row_dict["track_label"] != PRIMARY_TRACK_LABEL_STR:
                continue
            track_boxes_dict[int(report_row_dict["frame_number"])] = (
                int(report_row_dict["x1"]),
                int(report_row_dict["y1"]),
                int(report_row_dict["x2"]),
                int(report_row_dict["y2"]),
            )

    return frozenset(result_obj.failed_frames), track_boxes_dict


def _resolve_box(
    track_boxes_dict: dict[int, tuple[int, int, int, int]],
    frame_number_int: int,
) -> tuple[int, int, int, int]:
    """Return the tracked box, interpolating across missing frames.

    A frame with no accepted region has no observed box. The demo still
    needs to show where the region was expected, so the position is
    linearly interpolated between the nearest observed neighbours.

    Args:
        track_boxes_dict: Observed boxes keyed by frame number.
        frame_number_int: Frame whose box is required.

    Returns:
        Observed or interpolated box coordinates.
    """

    if frame_number_int in track_boxes_dict:
        return track_boxes_dict[frame_number_int]

    observed_frames_list = sorted(track_boxes_dict)
    previous_frames_list = [
        candidate_int
        for candidate_int in observed_frames_list
        if candidate_int < frame_number_int
    ]
    next_frames_list = [
        candidate_int
        for candidate_int in observed_frames_list
        if candidate_int > frame_number_int
    ]
    if not previous_frames_list:
        return track_boxes_dict[next_frames_list[0]]
    if not next_frames_list:
        return track_boxes_dict[previous_frames_list[-1]]

    previous_frame_int = previous_frames_list[-1]
    next_frame_int = next_frames_list[0]
    blend_float = (frame_number_int - previous_frame_int) / (
        next_frame_int - previous_frame_int
    )
    previous_box_tuple = track_boxes_dict[previous_frame_int]
    next_box_tuple = track_boxes_dict[next_frame_int]
    return tuple(  # type: ignore[return-value]
        round(previous_value + blend_float * (next_value - previous_value))
        for previous_value, next_value in zip(
            previous_box_tuple, next_box_tuple, strict=True
        )
    )


def _build_panel(
    frame_number_int: int,
    reference_frame_ndarray: ImageArray,
    candidate_frame_ndarray: ImageArray,
    box_tuple: tuple[int, int, int, int],
    frame_passed_bool: bool,
    total_frames_int: int,
) -> ImageArray:
    """Compose one demonstration panel for a single verified frame.

    Args:
        frame_number_int: One-based frame number.
        reference_frame_ndarray: Original frame.
        candidate_frame_ndarray: Processed candidate frame.
        box_tuple: Tracked region box in candidate coordinates.
        frame_passed_bool: Whether the frame satisfied the policy.
        total_frames_int: Total frames in the comparison.

    Returns:
        Rendered panel image.
    """

    panel_ndarray = _blank_panel(
        BANNER_HEIGHT_INT
        + FRAME_VIEW_HEIGHT_INT
        + CROP_LABEL_HEIGHT_INT
        + CROP_HEIGHT_INT
    )
    status_color_bgr = PASS_COLOR_BGR if frame_passed_bool else FAIL_COLOR_BGR
    _draw_banner(
        panel_ndarray,
        frame_number_int,
        total_frames_int,
        frame_passed_bool,
        status_color_bgr,
    )
    _draw_frame_view(
        panel_ndarray,
        candidate_frame_ndarray,
        box_tuple,
        status_color_bgr,
    )
    _draw_crop_row(
        panel_ndarray,
        reference_frame_ndarray,
        candidate_frame_ndarray,
        box_tuple,
        status_color_bgr,
    )
    return panel_ndarray


def _draw_banner(
    panel_ndarray: ImageArray,
    frame_number_int: int,
    total_frames_int: int,
    frame_passed_bool: bool,
    status_color_bgr: tuple[int, int, int],
) -> None:
    """Draw the frame counter and policy verdict banner."""

    cv2.rectangle(
        panel_ndarray,
        (0, 0),
        (PANEL_WIDTH_INT, BANNER_HEIGHT_INT),
        status_color_bgr,
        thickness=-1,
    )
    counter_text = f"Frame {frame_number_int:02d} / {total_frames_int}"
    verdict_text = (
        "PASS  licence plate blurred"
        if frame_passed_bool
        else "FAIL  no processing detected"
    )
    cv2.putText(
        panel_ndarray,
        counter_text,
        (16, 31),
        FONT_FACE,
        0.55,
        (20, 20, 20),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        panel_ndarray,
        verdict_text,
        (196, 31),
        FONT_FACE,
        0.58,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def _draw_frame_view(
    panel_ndarray: ImageArray,
    candidate_frame_ndarray: ImageArray,
    box_tuple: tuple[int, int, int, int],
    status_color_bgr: tuple[int, int, int],
) -> None:
    """Draw the downscaled candidate frame with the tracked region."""

    scaled_frame_ndarray = cv2.resize(
        candidate_frame_ndarray,
        (PANEL_WIDTH_INT, FRAME_VIEW_HEIGHT_INT),
        interpolation=cv2.INTER_AREA,
    )
    scale_x_float = PANEL_WIDTH_INT / candidate_frame_ndarray.shape[1]
    scale_y_float = FRAME_VIEW_HEIGHT_INT / candidate_frame_ndarray.shape[0]
    x1_int, y1_int, x2_int, y2_int = box_tuple
    cv2.rectangle(
        scaled_frame_ndarray,
        (int(x1_int * scale_x_float) - 4, int(y1_int * scale_y_float) - 4),
        (int(x2_int * scale_x_float) + 4, int(y2_int * scale_y_float) + 4),
        status_color_bgr,
        thickness=2,
    )
    cv2.putText(
        scaled_frame_ndarray,
        PRIMARY_TRACK_LABEL_STR,
        (int(x1_int * scale_x_float) - 4, int(y1_int * scale_y_float) - 10),
        FONT_FACE,
        0.45,
        status_color_bgr,
        1,
        cv2.LINE_AA,
    )
    panel_ndarray[
        BANNER_HEIGHT_INT : BANNER_HEIGHT_INT + FRAME_VIEW_HEIGHT_INT,
        0:PANEL_WIDTH_INT,
    ] = scaled_frame_ndarray


def _draw_crop_row(
    panel_ndarray: ImageArray,
    reference_frame_ndarray: ImageArray,
    candidate_frame_ndarray: ImageArray,
    box_tuple: tuple[int, int, int, int],
    status_color_bgr: tuple[int, int, int],
) -> None:
    """Draw magnified reference and candidate crops side by side."""

    label_top_int = BANNER_HEIGHT_INT + FRAME_VIEW_HEIGHT_INT
    crop_top_int = label_top_int + CROP_LABEL_HEIGHT_INT
    left_x_int = 0
    right_x_int = CROP_WIDTH_INT + CROP_GAP_INT

    _put_crop_label(
        panel_ndarray, "REFERENCE  original", left_x_int, label_top_int
    )
    _put_crop_label(
        panel_ndarray, "CANDIDATE  processed", right_x_int, label_top_int
    )
    panel_ndarray[
        crop_top_int : crop_top_int + CROP_HEIGHT_INT,
        left_x_int : left_x_int + CROP_WIDTH_INT,
    ] = _magnified_crop(reference_frame_ndarray, box_tuple)
    candidate_crop_ndarray = _magnified_crop(
        candidate_frame_ndarray, box_tuple
    )
    cv2.rectangle(
        candidate_crop_ndarray,
        (1, 1),
        (CROP_WIDTH_INT - 2, CROP_HEIGHT_INT - 2),
        status_color_bgr,
        thickness=3,
    )
    panel_ndarray[
        crop_top_int : crop_top_int + CROP_HEIGHT_INT,
        right_x_int : right_x_int + CROP_WIDTH_INT,
    ] = candidate_crop_ndarray


def _put_crop_label(
    panel_ndarray: ImageArray,
    label_text: str,
    left_x_int: int,
    top_y_int: int,
) -> None:
    """Draw one small caption above a magnified crop."""

    cv2.putText(
        panel_ndarray,
        label_text,
        (left_x_int + 4, top_y_int + 15),
        FONT_FACE,
        0.42,
        MUTED_TEXT_COLOR_BGR,
        1,
        cv2.LINE_AA,
    )


def _magnified_crop(
    frame_ndarray: ImageArray,
    box_tuple: tuple[int, int, int, int],
) -> ImageArray:
    """Return a magnified crop centred on the tracked region.

    Args:
        frame_ndarray: Full-resolution source frame.
        box_tuple: Tracked region box in source coordinates.

    Returns:
        Crop resized to the fixed comparison-tile dimensions.
    """

    frame_height_int, frame_width_int = frame_ndarray.shape[:2]
    x1_int, y1_int, x2_int, y2_int = box_tuple
    center_x_int = (x1_int + x2_int) // 2
    center_y_int = (y1_int + y2_int) // 2
    source_width_int = max(1, int((x2_int - x1_int) * CROP_ZOOM_FACTOR_FLOAT))
    source_height_int = max(
        1, int(source_width_int * CROP_HEIGHT_INT / CROP_WIDTH_INT)
    )
    left_int = max(
        0, min(center_x_int - source_width_int // 2, frame_width_int - 1)
    )
    top_int = max(
        0, min(center_y_int - source_height_int // 2, frame_height_int - 1)
    )
    right_int = min(frame_width_int, left_int + source_width_int)
    bottom_int = min(frame_height_int, top_int + source_height_int)
    cropped_ndarray = frame_ndarray[top_int:bottom_int, left_int:right_int]
    resized_crop_ndarray: ImageArray = cv2.resize(
        cropped_ndarray,
        (CROP_WIDTH_INT, CROP_HEIGHT_INT),
        interpolation=cv2.INTER_NEAREST,
    )
    return resized_crop_ndarray


def _build_verdict_panel(
    panel_height_int: int,
    failed_frames_frozenset: frozenset[int],
    total_frames_int: int,
) -> ImageArray:
    """Render the closing verdict card for the demonstration GIF.

    Every number on the card is derived from the run that produced the
    animation, so the card cannot disagree with the demo contract it
    illustrates.

    Args:
        panel_height_int: Height of the animation's other panels.
        failed_frames_frozenset: Frames the run reported as unprotected.
        total_frames_int: Frames compared in the run.

    Returns:
        One panel stating the result the animation just demonstrated.
    """

    panel_ndarray: ImageArray = np.full(
        (panel_height_int, PANEL_WIDTH_INT, 3),
        BACKGROUND_COLOR_BGR,
        dtype=np.uint8,
    )
    lines_tuple = _verdict_lines(failed_frames_frozenset, total_frames_int)
    for (
        text_str,
        scale_float,
        thickness_int,
        color_bgr,
        y_ratio,
    ) in lines_tuple:
        _put_centered_text(
            panel_ndarray,
            text_str,
            int(panel_height_int * y_ratio),
            scale_float,
            thickness_int,
            color_bgr,
        )
    return panel_ndarray


def _verdict_lines(
    failed_frames_frozenset: frozenset[int],
    total_frames_int: int,
) -> tuple[tuple[str, float, int, tuple[int, int, int], float], ...]:
    """Return the verdict card's lines with their type styling.

    Args:
        failed_frames_frozenset: Frames reported as unprotected.
        total_frames_int: Frames compared in the run.

    Returns:
        Text, font scale, thickness, colour, and vertical position for
        each line.
    """

    failed_text = ", ".join(
        str(frame_int) for frame_int in sorted(failed_frames_frozenset)
    )
    caption_text = (
        f"{len(failed_frames_frozenset)} of {total_frames_int} frames "
        "were never anonymized"
    )
    return (
        (VERDICT_TITLE_TEXT, 1.9, 3, FAIL_COLOR_BGR, 0.36),
        (f"Frames missed: {failed_text}", 0.78, 2, TEXT_COLOR_BGR, 0.50),
        (caption_text, 0.56, 1, MUTED_TEXT_COLOR_BGR, 0.60),
        (VERDICT_FOOTER_TEXT, 0.62, 1, MUTED_TEXT_COLOR_BGR, 0.78),
    )


def _put_centered_text(
    panel_ndarray: ImageArray,
    text_str: str,
    baseline_y_int: int,
    scale_float: float,
    thickness_int: int,
    color_bgr: tuple[int, int, int],
) -> None:
    """Draw one horizontally centred line of text.

    Args:
        panel_ndarray: Panel modified in place.
        text_str: Line to draw.
        baseline_y_int: Text baseline in pixels.
        scale_float: Font scale.
        thickness_int: Stroke thickness.
        color_bgr: Text colour.
    """

    (text_width_int, _), _ = cv2.getTextSize(
        text_str, FONT_FACE, scale_float, thickness_int
    )
    cv2.putText(
        panel_ndarray,
        text_str,
        ((PANEL_WIDTH_INT - text_width_int) // 2, baseline_y_int),
        FONT_FACE,
        scale_float,
        color_bgr,
        thickness_int,
        cv2.LINE_AA,
    )


def _write_gif(
    image_module: object,
    panels_list: list[ImageArray],
    failed_frames_frozenset: frozenset[int],
) -> None:
    """Assemble and save the animated demonstration GIF."""

    pil_frames_list = [
        image_module.fromarray(  # type: ignore[attr-defined]
            cv2.cvtColor(panel_ndarray, cv2.COLOR_BGR2RGB)
        ).quantize(colors=GIF_PALETTE_SIZE_INT)
        for panel_ndarray in panels_list
    ]
    durations_list = [
        FAIL_FRAME_DURATION_MS
        if frame_number_int in failed_frames_frozenset
        else PASS_FRAME_DURATION_MS
        for frame_number_int in range(1, len(panels_list) + 1)
    ]

    # The run ends on its verdict, so the loop reads as a complete story
    # rather than stopping mid-sequence.
    verdict_panel_ndarray = _build_verdict_panel(
        panels_list[0].shape[0], failed_frames_frozenset, len(panels_list)
    )
    pil_frames_list.append(
        image_module.fromarray(  # type: ignore[attr-defined]
            cv2.cvtColor(verdict_panel_ndarray, cv2.COLOR_BGR2RGB)
        ).quantize(colors=GIF_PALETTE_SIZE_INT)
    )
    durations_list.append(VERDICT_DURATION_MS)
    output_path_obj = ASSET_DIRECTORY_PATH / DEMO_GIF_FILENAME_STR
    pil_frames_list[0].save(
        output_path_obj,
        save_all=True,
        append_images=pil_frames_list[1:],
        duration=durations_list,
        loop=0,
        optimize=True,
    )
    size_kib_float = output_path_obj.stat().st_size / 1024
    print(f"wrote {output_path_obj} ({size_kib_float:.0f} KiB)")


def _write_closeup(
    panels_list: list[ImageArray],
    failed_frame_number_int: int,
) -> None:
    """Save a static still of the first failing frame."""

    output_path_obj = ASSET_DIRECTORY_PATH / CLOSEUP_FILENAME_STR
    cv2.imwrite(
        str(output_path_obj),
        panels_list[failed_frame_number_int - 1],
    )
    size_kib_float = output_path_obj.stat().st_size / 1024
    print(f"wrote {output_path_obj} ({size_kib_float:.0f} KiB)")


def _write_comparison(
    candidate_frames_list: list[ImageArray],
    track_boxes_dict: dict[int, tuple[int, int, int, int]],
    failed_frames_list: list[int],
    total_frames_int: int,
) -> None:
    """Save a compact pass-versus-fail comparison of one licence plate.

    Args:
        candidate_frames_list: Decoded processed candidate frames.
        track_boxes_dict: Observed primary-track boxes by frame number.
        failed_frames_list: Ordered failing frame numbers.
        total_frames_int: Total frames in the comparison.
    """

    panel_ndarray = _build_comparison_panel(
        candidate_frames_list,
        track_boxes_dict,
        failed_frames_list,
        total_frames_int,
    )
    output_path_obj = ASSET_DIRECTORY_PATH / COMPARISON_FILENAME_STR
    cv2.imwrite(str(output_path_obj), panel_ndarray)
    size_kib_float = output_path_obj.stat().st_size / 1024
    print(f"wrote {output_path_obj} ({size_kib_float:.0f} KiB)")


def _build_comparison_panel(
    candidate_frames_list: list[ImageArray],
    track_boxes_dict: dict[int, tuple[int, int, int, int]],
    failed_frames_list: list[int],
    total_frames_int: int,
) -> ImageArray:
    """Compose the pass-versus-fail comparison image.

    Args:
        candidate_frames_list: Decoded processed candidate frames.
        track_boxes_dict: Observed primary-track boxes by frame number.
        failed_frames_list: Ordered failing frame numbers.
        total_frames_int: Total frames in the comparison.

    Returns:
        Rendered comparison panel.
    """

    failed_frame_int = failed_frames_list[0]
    panel_ndarray = _blank_panel(
        COMPARISON_TITLE_HEIGHT_INT
        + CROP_HEIGHT_INT
        + COMPARISON_CAPTION_HEIGHT_INT
        + COMPARISON_FOOTER_HEIGHT_INT
    )
    _put_centred_text(
        panel_ndarray,
        "Same licence plate, one frame apart",
        24,
        0.62,
        TEXT_COLOR_BGR,
    )
    _place_comparison_pair(
        panel_ndarray,
        candidate_frames_list,
        track_boxes_dict,
        failed_frame_int,
    )
    _put_centred_text(
        panel_ndarray,
        f"{len(failed_frames_list)} of {total_frames_int} frames missed: "
        f"{', '.join(str(n) for n in failed_frames_list)}   exit code 2",
        panel_ndarray.shape[0] - 13,
        0.5,
        MUTED_TEXT_COLOR_BGR,
    )
    return panel_ndarray


def _place_comparison_pair(
    panel_ndarray: ImageArray,
    candidate_frames_list: list[ImageArray],
    track_boxes_dict: dict[int, tuple[int, int, int, int]],
    failed_frame_int: int,
) -> None:
    """Draw the passing and failing tiles for one adjacent frame pair.

    Args:
        panel_ndarray: Canvas receiving both tiles.
        candidate_frames_list: Decoded processed candidate frames.
        track_boxes_dict: Observed primary-track boxes by frame number.
        failed_frame_int: Frame number of the first policy failure.
    """

    tile_specs_tuple = (
        (failed_frame_int - 1, 0, "PASS  plate blurred", PASS_COLOR_BGR),
        (
            failed_frame_int,
            CROP_WIDTH_INT + CROP_GAP_INT,
            "FAIL  plate readable",
            FAIL_COLOR_BGR,
        ),
    )
    for frame_int, left_x_int, verdict_text, color_bgr in tile_specs_tuple:
        _place_comparison_tile(
            panel_ndarray,
            candidate_frames_list[frame_int - 1],
            _resolve_box(track_boxes_dict, frame_int),
            left_x_int,
            f"Frame {frame_int:02d}  {verdict_text}",
            color_bgr,
        )


def _blank_panel(panel_height_int: int) -> ImageArray:
    """Return an empty canvas filled with the shared theme colour.

    Args:
        panel_height_int: Required canvas height in pixels.

    Returns:
        Blank panel of the standard demonstration width.
    """

    blank_panel_ndarray: ImageArray = np.full(
        (panel_height_int, PANEL_WIDTH_INT, 3),
        BACKGROUND_COLOR_BGR,
        dtype=np.uint8,
    )
    return blank_panel_ndarray


def _place_comparison_tile(
    panel_ndarray: ImageArray,
    frame_ndarray: ImageArray,
    box_tuple: tuple[int, int, int, int],
    left_x_int: int,
    caption_text: str,
    border_color_bgr: tuple[int, int, int],
) -> None:
    """Draw one bordered crop tile with its caption underneath."""

    crop_ndarray = _magnified_crop(frame_ndarray, box_tuple)
    cv2.rectangle(
        crop_ndarray,
        (1, 1),
        (CROP_WIDTH_INT - 2, CROP_HEIGHT_INT - 2),
        border_color_bgr,
        thickness=3,
    )
    panel_ndarray[
        COMPARISON_TITLE_HEIGHT_INT : COMPARISON_TITLE_HEIGHT_INT
        + CROP_HEIGHT_INT,
        left_x_int : left_x_int + CROP_WIDTH_INT,
    ] = crop_ndarray
    cv2.putText(
        panel_ndarray,
        caption_text,
        (left_x_int + 4, COMPARISON_TITLE_HEIGHT_INT + CROP_HEIGHT_INT + 18),
        FONT_FACE,
        0.45,
        border_color_bgr,
        1,
        cv2.LINE_AA,
    )


def _put_centred_text(
    panel_ndarray: ImageArray,
    text_str: str,
    baseline_y_int: int,
    font_scale_float: float,
    color_bgr: tuple[int, int, int],
) -> None:
    """Draw one horizontally centred line of text."""

    (text_width_int, _), _ = cv2.getTextSize(
        text_str, FONT_FACE, font_scale_float, 1
    )
    cv2.putText(
        panel_ndarray,
        text_str,
        ((PANEL_WIDTH_INT - text_width_int) // 2, baseline_y_int),
        FONT_FACE,
        font_scale_float,
        color_bgr,
        1,
        cv2.LINE_AA,
    )


if __name__ == "__main__":
    raise SystemExit(main())
