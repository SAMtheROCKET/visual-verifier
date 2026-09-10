"""Validate reviewed targets against the media they describe.

`loading.py` checks that a target file is syntactically well formed. That
is not enough. A target declaring frame 99 of a 15-frame video, or a box
extending past the right edge of the image, parses perfectly and then
describes nothing.

A target nobody can evaluate is worse than a malformed one, because it
disappears quietly: the frame loop never visits it, no coverage is
measured, and the run reports `PASS` on a requirement that was never
checked. Verification that silently skips a declared requirement is not
verification.

So every target is checked against the reference media before any frame
is read, and checked again afterwards to confirm it really was evaluated.
Both raise `TargetValidationError` rather than producing a verdict.
"""

from __future__ import annotations

from collections.abc import Iterable

from visual_verifier.exceptions import TargetValidationError
from visual_verifier.models import MediaMetadata
from visual_verifier.targets.models import Target, TargetCoverage

MAXIMUM_REPORTED_PROBLEMS_INT = 10


def validate_targets_against_media(
    targets_tuple: tuple[Target, ...],
    reference_metadata_obj: MediaMetadata,
) -> None:
    """Reject any target that cannot exist in the reference media.

    Args:
        targets_tuple: Reviewed targets, before interpolation.
        reference_metadata_obj: Metadata of the reference media.

    Raises:
        TargetValidationError: When a target names a frame the media does
            not have, or a box that does not fit inside the frame.
    """

    if not targets_tuple:
        return

    problems_list = [
        *_frame_range_problems(targets_tuple, reference_metadata_obj),
        *_bounds_problems(targets_tuple, reference_metadata_obj),
    ]
    if not problems_list:
        return

    raise TargetValidationError(
        "Targets do not fit the reference media.",
        context_mapping={
            "problem_count": len(problems_list),
            "problems": problems_list[:MAXIMUM_REPORTED_PROBLEMS_INT],
            "reference_frame_count": reference_metadata_obj.frame_count,
            "reference_width": reference_metadata_obj.width,
            "reference_height": reference_metadata_obj.height,
        },
    )


def _frame_range_problems(
    targets_tuple: tuple[Target, ...],
    reference_metadata_obj: MediaMetadata,
) -> list[str]:
    """Return a problem for every target naming a frame that cannot exist.

    Args:
        targets_tuple: Reviewed targets.
        reference_metadata_obj: Metadata of the reference media.

    Returns:
        Human-readable problem descriptions, possibly empty.
    """

    frame_count_int = reference_metadata_obj.frame_count
    if frame_count_int <= 0:
        return []

    beyond_dict: dict[str, list[int]] = {}
    for target_obj in targets_tuple:
        if target_obj.frame_number > frame_count_int:
            beyond_dict.setdefault(target_obj.target_id, []).append(
                target_obj.frame_number
            )

    return [
        (
            f"target {target_id_str!r} names "
            f"{_frame_phrase(frames_list)}, but the reference media has "
            f"{frame_count_int} frames"
        )
        for target_id_str, frames_list in sorted(beyond_dict.items())
    ]


def _frame_phrase(frames_list: list[int]) -> str:
    """Describe a set of offending frames without listing all of them.

    Args:
        frames_list: Frame numbers sharing one problem.

    Returns:
        A readable phrase naming one frame or summarizing many.
    """

    ordered_list = sorted(frames_list)
    if len(ordered_list) == 1:
        return f"frame {ordered_list[0]}"
    return (
        f"{len(ordered_list)} frames from {ordered_list[0]} to "
        f"{ordered_list[-1]}"
    )


def _bounds_problems(
    targets_tuple: tuple[Target, ...],
    reference_metadata_obj: MediaMetadata,
) -> list[str]:
    """Return a problem for every box that does not fit the frame.

    Coordinates use exclusive end values, so a box may touch the right or
    bottom edge but never cross it.

    Args:
        targets_tuple: Reviewed targets.
        reference_metadata_obj: Metadata of the reference media.

    Returns:
        Human-readable problem descriptions, possibly empty.
    """

    width_int = reference_metadata_obj.width
    height_int = reference_metadata_obj.height
    if width_int <= 0 or height_int <= 0:
        return []

    offending_dict: dict[tuple[str, tuple[int, int, int, int]], list[int]] = {}
    for target_obj in targets_tuple:
        box_obj = target_obj.box
        if box_obj.x2 <= width_int and box_obj.y2 <= height_int:
            continue
        key_tuple = (target_obj.target_id, box_obj.as_tuple())
        offending_dict.setdefault(key_tuple, []).append(
            target_obj.frame_number
        )

    return [
        (
            f"target {target_id_str!r} on {_frame_phrase(frames_list)} "
            f"has box {box_tuple}, which extends past the "
            f"{width_int}x{height_int} frame"
        )
        for (target_id_str, box_tuple), frames_list in sorted(
            offending_dict.items()
        )
    ]


def confirm_every_target_was_evaluated(
    targets_tuple: tuple[Target, ...],
    coverages_iterable: Iterable[TargetCoverage],
) -> None:
    """Confirm no declared target fell out of the run unmeasured.

    Media metadata can disagree with what a decoder actually yields, so a
    target inside the declared frame count can still never be reached.
    This is the last chance to notice before a verdict is returned.

    Args:
        targets_tuple: Targets the run was supposed to evaluate.
        coverages_iterable: Coverage measured during the run.

    Raises:
        TargetValidationError: When a declared target was never measured.
    """

    if not targets_tuple:
        return

    measured_frozenset = frozenset(
        (coverage_obj.target.frame_number, coverage_obj.target.target_id)
        for coverage_obj in coverages_iterable
    )
    unevaluated_list = [
        {
            "frame_number": target_obj.frame_number,
            "target_id": target_obj.target_id,
        }
        for target_obj in targets_tuple
        if (target_obj.frame_number, target_obj.target_id)
        not in measured_frozenset
    ]
    if not unevaluated_list:
        return

    raise TargetValidationError(
        "Declared targets were never evaluated, so no verdict is safe.",
        context_mapping={
            "unevaluated_count": len(unevaluated_list),
            "unevaluated_targets": unevaluated_list[
                :MAXIMUM_REPORTED_PROBLEMS_INT
            ],
        },
    )


__all__ = [
    "confirm_every_target_was_evaluated",
    "validate_targets_against_media",
]
