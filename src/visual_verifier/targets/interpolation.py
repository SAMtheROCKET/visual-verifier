"""Fill reviewed target gaps without inventing evidence.

A reviewer rarely annotates every frame. Interpolating between two
reviewed boxes is reasonable; interpolating across an arbitrary gap is
not, because a target can leave and re-enter a scene and a straight line
between its two appearances would place a box where nothing was.

Every generated box is marked `INTERPOLATED`, and no generated box ever
replaces a reviewed one.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import pairwise

from visual_verifier.models import BoundingBox
from visual_verifier.targets.models import Target, TargetSource


def interpolate_targets(
    targets_tuple: tuple[Target, ...],
    *,
    max_gap_int: int,
) -> tuple[Target, ...]:
    """Return the targets with permitted frame gaps filled.

    Args:
        targets_tuple: Reviewed targets.
        max_gap_int: Longest run of missing frames that may be filled.
            A gap longer than this is left empty.

    Returns:
        The original targets plus any interpolated boxes, ordered by
        frame then target identifier.
    """

    if max_gap_int <= 0:
        return targets_tuple

    by_identifier_dict: dict[str, list[Target]] = defaultdict(list)
    for target_obj in targets_tuple:
        by_identifier_dict[target_obj.target_id].append(target_obj)

    generated_list: list[Target] = []
    for track_targets_list in by_identifier_dict.values():
        generated_list.extend(
            _interpolate_one_target(track_targets_list, max_gap_int)
        )

    return tuple(
        sorted(
            (*targets_tuple, *generated_list),
            key=lambda target_obj: (
                target_obj.frame_number,
                target_obj.target_id,
            ),
        )
    )


def _interpolate_one_target(
    track_targets_list: list[Target],
    max_gap_int: int,
) -> list[Target]:
    """Fill the permitted gaps of one target identifier.

    Args:
        track_targets_list: Every declared box for one identifier.
        max_gap_int: Longest run of missing frames that may be filled.

    Returns:
        Newly generated boxes, which may be empty.
    """

    ordered_list = sorted(
        track_targets_list, key=lambda target_obj: target_obj.frame_number
    )
    generated_list: list[Target] = []

    for start_obj, end_obj in pairwise(ordered_list):
        gap_int = end_obj.frame_number - start_obj.frame_number - 1
        if gap_int <= 0 or gap_int > max_gap_int:
            continue
        generated_list.extend(_fill_gap(start_obj, end_obj))

    return generated_list


def _fill_gap(start_obj: Target, end_obj: Target) -> list[Target]:
    """Generate every box between two reviewed boxes of one target.

    Args:
        start_obj: Reviewed box before the gap.
        end_obj: Reviewed box after the gap.

    Returns:
        One interpolated target per missing frame.
    """

    span_int = end_obj.frame_number - start_obj.frame_number
    return [
        Target(
            frame_number=frame_number_int,
            target_id=start_obj.target_id,
            box=_interpolate_box(
                start_obj.box,
                end_obj.box,
                (frame_number_int - start_obj.frame_number) / span_int,
            ),
            target_type=start_obj.target_type,
            required=start_obj.required and end_obj.required,
            source=TargetSource.INTERPOLATED,
        )
        for frame_number_int in range(
            start_obj.frame_number + 1, end_obj.frame_number
        )
    ]


def _interpolate_box(
    start_box_obj: BoundingBox,
    end_box_obj: BoundingBox,
    progress_float: float,
) -> BoundingBox:
    """Linearly interpolate one box between two reviewed boxes.

    Args:
        start_box_obj: Box before the gap.
        end_box_obj: Box after the gap.
        progress_float: Position in the gap, from 0 to 1.

    Returns:
        The interpolated box, rounded to whole pixels.
    """

    return BoundingBox(
        x1=_interpolate_value(
            start_box_obj.x1, end_box_obj.x1, progress_float
        ),
        y1=_interpolate_value(
            start_box_obj.y1, end_box_obj.y1, progress_float
        ),
        x2=_interpolate_value(
            start_box_obj.x2, end_box_obj.x2, progress_float
        ),
        y2=_interpolate_value(
            start_box_obj.y2, end_box_obj.y2, progress_float
        ),
    )


def _interpolate_value(
    start_int: int,
    end_int: int,
    progress_float: float,
) -> int:
    """Interpolate one coordinate.

    Args:
        start_int: Coordinate before the gap.
        end_int: Coordinate after the gap.
        progress_float: Position in the gap, from 0 to 1.

    Returns:
        The interpolated coordinate, rounded to the nearest pixel.
    """

    return round(start_int + (end_int - start_int) * progress_float)


__all__ = ["interpolate_targets"]
