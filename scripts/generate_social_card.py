"""Render the 1200x630 social preview card.

Every link shared to a forum, chat, or social network renders from this
image. It is generated from the bundled fixture rather than drawn by
hand, so the plate it shows blurred and the plate it shows readable are
the actual frames the demo verifies. A hand-made mock could drift from
what the tool does; this cannot.

    uv run --with pillow python scripts/generate_social_card.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from visual_verifier.type_aliases import ImageArray

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLE_MEDIA_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples" / "media"
ASSET_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "docs" / "assets"
CARD_FILENAME_STR = "social_card.png"

CARD_WIDTH_INT = 1200
CARD_HEIGHT_INT = 630
MARGIN_INT = 56

PASS_FRAME_NUMBER_INT = 3
FAIL_FRAME_NUMBER_INT = 4
PLATE_CROP_BOX_TUPLE = (610, 485, 850, 549)

PANEL_WIDTH_INT = 512
PANEL_HEIGHT_INT = 168
PANEL_GAP_INT = 32
PANEL_TOP_INT = 300

BACKGROUND_COLOR = (24, 23, 22)
PANEL_BACKGROUND_COLOR = (33, 32, 31)
TEXT_COLOR = (240, 240, 238)
MUTED_COLOR = (158, 156, 153)
PASS_COLOR = (61, 176, 106)
FAIL_COLOR = (223, 74, 63)

HEADLINE_TEXT = "A changed frame is not the same"
HEADLINE_SECOND_TEXT = "as a protected target."
EYEBROW_TEXT = "VISUAL VERIFIER"
SUBHEAD_TEXT = "Find the frames your anonymizer missed."
INSTALL_TEXT = "pip install visual-verifier"

FONT_CANDIDATES_TUPLE = (
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)
MONO_FONT_CANDIDATES_TUPLE = (
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
)


def main() -> int:
    """Render and write the social preview card.

    Returns:
        Process exit code. ``1`` when the fixture cannot be read.
    """

    frames_dict = _read_fixture_frames()
    if frames_dict is None:
        print("Could not read the bundled fixture frames.", file=sys.stderr)
        return 1

    card_image = Image.new(
        "RGB", (CARD_WIDTH_INT, CARD_HEIGHT_INT), BACKGROUND_COLOR
    )
    draw_obj = ImageDraw.Draw(card_image)
    _draw_text_block(draw_obj)
    _draw_comparison_panels(card_image, draw_obj, frames_dict)

    ASSET_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    output_path_obj = ASSET_DIRECTORY_PATH / CARD_FILENAME_STR
    card_image.save(output_path_obj, format="PNG", optimize=True)
    print(f"Wrote {output_path_obj.relative_to(REPOSITORY_ROOT_PATH)}")
    return 0


def _load_font(
    candidates_tuple: tuple[str, ...],
    size_int: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return the first available font at one size.

    Args:
        candidates_tuple: Font paths to try in order.
        size_int: Point size.

    Returns:
        A usable font, falling back to Pillow's bitmap default.
    """

    for candidate_str in candidates_tuple:
        if Path(candidate_str).is_file():
            return ImageFont.truetype(candidate_str, size_int)
    return ImageFont.load_default()


def _read_fixture_frames() -> dict[str, ImageArray] | None:
    """Read the passing and failing frames from the bundled fixture.

    Returns:
        Cropped plate regions keyed by ``reference``, ``pass``, and
        ``fail``, or ``None`` when the media cannot be read.
    """

    reference_ndarray = _read_frame(
        EXAMPLE_MEDIA_DIRECTORY_PATH / "video_raw.mp4", FAIL_FRAME_NUMBER_INT
    )
    passing_ndarray = _read_frame(
        EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur_partial.mp4",
        PASS_FRAME_NUMBER_INT,
    )
    failing_ndarray = _read_frame(
        EXAMPLE_MEDIA_DIRECTORY_PATH / "video_blur_partial.mp4",
        FAIL_FRAME_NUMBER_INT,
    )
    if any(
        frame is None
        for frame in (reference_ndarray, passing_ndarray, failing_ndarray)
    ):
        return None
    return {
        "reference": reference_ndarray,
        "pass": passing_ndarray,
        "fail": failing_ndarray,
    }


def _read_frame(
    video_path_obj: Path,
    frame_number_int: int,
) -> ImageArray | None:
    """Read one one-based frame from a video.

    Args:
        video_path_obj: Video to read.
        frame_number_int: One-based frame number.

    Returns:
        The frame, or ``None`` when it cannot be read.
    """

    capture_obj = cv2.VideoCapture(str(video_path_obj))
    try:
        for _ in range(frame_number_int):
            read_ok_bool, frame_ndarray = capture_obj.read()
            if not read_ok_bool:
                return None
        return frame_ndarray
    finally:
        capture_obj.release()


def _draw_text_block(draw_obj: ImageDraw.ImageDraw) -> None:
    """Draw the eyebrow, headline, subhead, and install command.

    Args:
        draw_obj: Drawing context for the card.
    """

    eyebrow_font = _load_font(FONT_CANDIDATES_TUPLE, 24)
    headline_font = _load_font(FONT_CANDIDATES_TUPLE, 52)
    subhead_font = _load_font(FONT_CANDIDATES_TUPLE, 28)
    mono_font = _load_font(MONO_FONT_CANDIDATES_TUPLE, 24)

    draw_obj.text(
        (MARGIN_INT, MARGIN_INT),
        EYEBROW_TEXT,
        font=eyebrow_font,
        fill=PASS_COLOR,
    )
    draw_obj.text(
        (MARGIN_INT, MARGIN_INT + 46),
        HEADLINE_TEXT,
        font=headline_font,
        fill=TEXT_COLOR,
    )
    draw_obj.text(
        (MARGIN_INT, MARGIN_INT + 110),
        HEADLINE_SECOND_TEXT,
        font=headline_font,
        fill=TEXT_COLOR,
    )
    draw_obj.text(
        (MARGIN_INT, MARGIN_INT + 184),
        SUBHEAD_TEXT,
        font=subhead_font,
        fill=MUTED_COLOR,
    )
    draw_obj.text(
        (MARGIN_INT, CARD_HEIGHT_INT - MARGIN_INT - 26),
        INSTALL_TEXT,
        font=mono_font,
        fill=MUTED_COLOR,
    )


def _draw_comparison_panels(
    card_image: Image.Image,
    draw_obj: ImageDraw.ImageDraw,
    frames_dict: dict[str, ImageArray],
) -> None:
    """Draw the passing and failing plate crops side by side.

    Args:
        card_image: Card being composed.
        draw_obj: Drawing context for the card.
        frames_dict: Frames read from the bundled fixture.
    """

    label_font = _load_font(FONT_CANDIDATES_TUPLE, 22)
    panels_tuple = (
        ("FRAME 3   PASS", PASS_COLOR, frames_dict["pass"]),
        ("FRAME 4   FAIL", FAIL_COLOR, frames_dict["fail"]),
    )

    for index_int, (label_str, accent_color, frame_ndarray) in enumerate(
        panels_tuple
    ):
        left_int = MARGIN_INT + index_int * (PANEL_WIDTH_INT + PANEL_GAP_INT)
        bounds_tuple = (
            left_int,
            PANEL_TOP_INT,
            left_int + PANEL_WIDTH_INT,
            PANEL_TOP_INT + PANEL_HEIGHT_INT + 40,
        )
        draw_obj.rectangle(bounds_tuple, fill=PANEL_BACKGROUND_COLOR)
        draw_obj.text(
            (left_int + 16, PANEL_TOP_INT + 10),
            label_str,
            font=label_font,
            fill=accent_color,
        )
        card_image.paste(
            _crop_plate(frame_ndarray),
            (left_int + 16, PANEL_TOP_INT + 44),
        )
        draw_obj.rectangle(bounds_tuple, outline=accent_color, width=3)


def _crop_plate(frame_ndarray: ImageArray) -> Image.Image:
    """Return the licence-plate region scaled to the panel width.

    Args:
        frame_ndarray: Full frame in BGR order.

    Returns:
        The cropped, scaled region as an RGB image.
    """

    left_int, top_int, right_int, bottom_int = PLATE_CROP_BOX_TUPLE
    cropped_ndarray = frame_ndarray[top_int:bottom_int, left_int:right_int]
    rgb_ndarray = cv2.cvtColor(cropped_ndarray, cv2.COLOR_BGR2RGB)
    crop_image = Image.fromarray(rgb_ndarray)
    return crop_image.resize(
        (PANEL_WIDTH_INT - 32, PANEL_HEIGHT_INT - 40), Image.LANCZOS
    )


if __name__ == "__main__":
    raise SystemExit(main())
