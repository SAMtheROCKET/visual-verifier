"""Refuse targets the media cannot contain.

A target declaring a frame the video does not have parses perfectly and
then vanishes: the frame loop never visits it, no coverage is measured,
and the run reports `PASS` on a requirement nobody checked. That is worse
than a malformed file, because it fails silently and in the safe-looking
direction.

Every check here exists because that false `PASS` was real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from visual_verifier import verify_video
from visual_verifier.exceptions import TargetValidationError
from visual_verifier.media.metadata import read_video_metadata
from visual_verifier.models import BoundingBox, MediaMetadata
from visual_verifier.targets.models import Target, TargetCoverage
from visual_verifier.targets.validation import (
    confirm_every_target_was_evaluated,
    validate_targets_against_media,
)

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parents[1]
EXAMPLES_DIRECTORY_PATH = REPOSITORY_ROOT_PATH / "examples"
REFERENCE_PATH = EXAMPLES_DIRECTORY_PATH / "media" / "video_raw.mp4"
FULL_BLUR_PATH = EXAMPLES_DIRECTORY_PATH / "media" / "video_blur.mp4"
FIXTURE_FRAME_COUNT_INT = 15
FIXTURE_WIDTH_INT = 1280
FIXTURE_HEIGHT_INT = 720
DEFAULT_BOX = BoundingBox(x1=10, y1=10, x2=110, y2=90)


def _metadata() -> MediaMetadata:
    """Return metadata matching the bundled fixture.

    Returns:
        Metadata for a 15-frame 1280x720 clip.
    """

    return MediaMetadata(
        path=REFERENCE_PATH,
        media_type="video",
        width=FIXTURE_WIDTH_INT,
        height=FIXTURE_HEIGHT_INT,
        frame_count=FIXTURE_FRAME_COUNT_INT,
        fps=5.0,
    )


def _target(
    frame_number_int: int,
    box_obj: BoundingBox,
    target_id_str: str = "PLATE_A",
) -> Target:
    """Return one target.

    Args:
        frame_number_int: Frame the target applies to.
        box_obj: Target geometry.
        target_id_str: Target identifier.

    Returns:
        The target.
    """

    return Target(
        frame_number=frame_number_int,
        target_id=target_id_str,
        box=box_obj,
    )


def _coverage(target_obj: Target) -> TargetCoverage:
    """Return a fully covered measurement for one target.

    Args:
        target_obj: Target that was measured.

    Returns:
        The coverage record.
    """

    return TargetCoverage(
        target=target_obj,
        covered_ratio=1.0,
        covered=True,
        contributing_region_count=1,
    )


def _write_targets(tmp_path: Path, rows_list: list[str]) -> Path:
    """Write a target file.

    Args:
        tmp_path: Directory to write into.
        rows_list: Rows following the standard header.

    Returns:
        Path to the written file.
    """

    targets_path_obj = tmp_path / "targets.csv"
    targets_path_obj.write_text(
        "frame_number,target_id,x1,y1,x2,y2\n" + "\n".join(rows_list) + "\n",
        encoding="utf-8",
    )
    return targets_path_obj


def test_the_fixture_matches_the_dimensions_assumed_here() -> None:
    """Confirm the numbers these checks rely on are the real ones."""

    metadata_obj = read_video_metadata(REFERENCE_PATH)

    assert metadata_obj.frame_count == FIXTURE_FRAME_COUNT_INT
    assert metadata_obj.width == FIXTURE_WIDTH_INT
    assert metadata_obj.height == FIXTURE_HEIGHT_INT


def test_a_frame_beyond_the_media_is_rejected() -> None:
    """Confirm a target naming a frame that cannot exist is refused."""

    with pytest.raises(TargetValidationError) as error_info:
        validate_targets_against_media(
            (_target(99, DEFAULT_BOX),), _metadata()
        )

    context_dict = error_info.value.context_dict
    assert context_dict["reference_frame_count"] == FIXTURE_FRAME_COUNT_INT
    assert "99" in str(context_dict["problems"])


def test_the_last_frame_is_accepted() -> None:
    """Confirm the boundary frame is usable rather than off by one."""

    validate_targets_against_media(
        (_target(FIXTURE_FRAME_COUNT_INT, DEFAULT_BOX),), _metadata()
    )


@pytest.mark.parametrize(
    "box_obj",
    [
        BoundingBox(x1=1200, y1=650, x2=1400, y2=750),
        BoundingBox(x1=10, y1=10, x2=FIXTURE_WIDTH_INT + 1, y2=90),
        BoundingBox(x1=10, y1=10, x2=110, y2=FIXTURE_HEIGHT_INT + 1),
    ],
)
def test_a_box_outside_the_frame_is_rejected(box_obj: BoundingBox) -> None:
    """Confirm an impossible rectangle never reaches coverage.

    Beyond correctness, this keeps an arbitrarily large box away from
    mask allocation.
    """

    with pytest.raises(TargetValidationError):
        validate_targets_against_media((_target(1, box_obj),), _metadata())


def test_a_box_touching_the_edge_is_accepted() -> None:
    """Confirm exclusive end coordinates may reach the frame edge."""

    edge_box_obj = BoundingBox(
        x1=FIXTURE_WIDTH_INT - 100,
        y1=FIXTURE_HEIGHT_INT - 100,
        x2=FIXTURE_WIDTH_INT,
        y2=FIXTURE_HEIGHT_INT,
    )

    validate_targets_against_media((_target(1, edge_box_obj),), _metadata())


def test_every_problem_is_reported_not_only_the_first() -> None:
    """Confirm a reviewer sees the whole list, not one line at a time."""

    oversized_box_obj = BoundingBox(x1=10, y1=10, x2=9000, y2=90)

    with pytest.raises(TargetValidationError) as error_info:
        validate_targets_against_media(
            (
                _target(99, DEFAULT_BOX, "A"),
                _target(100, DEFAULT_BOX, "B"),
                _target(1, oversized_box_obj, "C"),
            ),
            _metadata(),
        )

    assert error_info.value.context_dict["problem_count"] == 3


def test_no_targets_validates_trivially() -> None:
    """Confirm the check is inert when no targets were supplied."""

    validate_targets_against_media((), _metadata())


def test_an_unevaluated_target_is_refused_after_the_run() -> None:
    """Confirm a target that fell out of the run stops the verdict.

    Media metadata can disagree with what a decoder yields, so this is
    the last chance to notice before a result is returned.
    """

    declared_tuple = (_target(1, DEFAULT_BOX), _target(2, DEFAULT_BOX))

    with pytest.raises(TargetValidationError) as error_info:
        confirm_every_target_was_evaluated(
            declared_tuple, [_coverage(declared_tuple[0])]
        )

    assert error_info.value.context_dict["unevaluated_count"] == 1


def test_a_fully_evaluated_run_passes_the_post_check() -> None:
    """Confirm the safety net does not fire on a healthy run."""

    declared_tuple = (_target(1, DEFAULT_BOX),)

    confirm_every_target_was_evaluated(
        declared_tuple, [_coverage(declared_tuple[0])]
    )


def test_a_ghost_target_cannot_produce_a_passing_run(
    tmp_path: Path,
) -> None:
    """Confirm the false PASS this module exists for cannot return.

    A required target on a frame the video does not have, against media
    that otherwise passes cleanly, previously returned `PASS` with zero
    targets measured.
    """

    targets_path_obj = _write_targets(tmp_path, ["99,PLATE_X,100,100,200,200"])

    with pytest.raises(TargetValidationError):
        verify_video(
            REFERENCE_PATH,
            FULL_BLUR_PATH,
            output_dir=tmp_path / "run",
            targets=targets_path_obj,
            save_annotated_video=False,
            save_html_report=False,
        )


def test_an_out_of_bounds_target_stops_the_run(tmp_path: Path) -> None:
    """Confirm an impossible box fails rather than reporting uncovered."""

    targets_path_obj = _write_targets(
        tmp_path,
        [
            f"{frame_int},PLATE_OOB,1200,650,1400,750"
            for frame_int in range(1, FIXTURE_FRAME_COUNT_INT + 1)
        ],
    )

    with pytest.raises(TargetValidationError):
        verify_video(
            REFERENCE_PATH,
            FULL_BLUR_PATH,
            output_dir=tmp_path / "run",
            targets=targets_path_obj,
            save_annotated_video=False,
            save_html_report=False,
        )


def test_validation_happens_before_any_evidence_is_written(
    tmp_path: Path,
) -> None:
    """Confirm a rejected run leaves no half-written evidence directory."""

    targets_path_obj = _write_targets(tmp_path, ["99,PLATE_X,100,100,200,200"])
    output_path_obj = tmp_path / "run"

    with pytest.raises(TargetValidationError):
        verify_video(
            REFERENCE_PATH,
            FULL_BLUR_PATH,
            output_dir=output_path_obj,
            targets=targets_path_obj,
            save_annotated_video=False,
            save_html_report=False,
        )

    assert not (output_path_obj / "summary.json").exists()


def test_repeated_problems_are_collapsed_into_one_line() -> None:
    """Confirm one bad box on many frames reports once, not many times.

    A target file usually repeats the same box on every frame, so
    reporting each frame separately buries the single real mistake in
    dozens of identical lines.
    """

    bad_box_obj = BoundingBox(x1=1200, y1=650, x2=1400, y2=750)

    with pytest.raises(TargetValidationError) as error_info:
        validate_targets_against_media(
            tuple(
                _target(frame_int, bad_box_obj, "PLATE_OOB")
                for frame_int in range(1, FIXTURE_FRAME_COUNT_INT + 1)
            ),
            _metadata(),
        )

    context_dict = error_info.value.context_dict
    assert context_dict["problem_count"] == 1
    assert "15 frames from 1 to 15" in str(context_dict["problems"][0])


def test_distinct_problems_stay_distinct() -> None:
    """Confirm collapsing does not merge two genuinely different faults."""

    with pytest.raises(TargetValidationError) as error_info:
        validate_targets_against_media(
            (
                _target(1, BoundingBox(x1=1200, y1=10, x2=1400, y2=90), "A"),
                _target(1, BoundingBox(x1=10, y1=650, x2=110, y2=900), "B"),
            ),
            _metadata(),
        )

    assert error_info.value.context_dict["problem_count"] == 2
