"""Read and validate a reviewed target file.

Targets are the one input this package cannot check against the media,
so the file is validated strictly and rejected loudly. A silently
dropped row would mean a region nobody verified, reported as verified.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path

from visual_verifier.exceptions import TargetValidationError
from visual_verifier.models import BoundingBox
from visual_verifier.targets.models import (
    UNKNOWN_TARGET_TYPE_TEXT,
    Target,
    TargetSource,
)
from visual_verifier.type_aliases import PathInput

REQUIRED_COLUMNS_TUPLE = (
    "frame_number",
    "target_id",
    "x1",
    "y1",
    "x2",
    "y2",
)
OPTIONAL_COLUMNS_TUPLE = ("target_type", "required", "source")
TRUE_TEXTS_FROZENSET = frozenset({"1", "true", "yes", "y"})
FALSE_TEXTS_FROZENSET = frozenset({"0", "false", "no", "n"})
CSV_ENCODING_TEXT = "utf-8-sig"


def load_targets(targets_path_input: PathInput) -> tuple[Target, ...]:
    """Read a reviewed target CSV file.

    Args:
        targets_path_input: Path to the target file.

    Returns:
        Every declared target, ordered by frame then target identifier.

    Raises:
        TargetValidationError: When the file is missing, unreadable, or
            carries an invalid row.
    """

    targets_path_obj = Path(targets_path_input).expanduser()
    rows_list = _read_rows(targets_path_obj)
    targets_list = [
        _build_target(row_dict, row_number_int, targets_path_obj)
        for row_number_int, row_dict in enumerate(rows_list, start=2)
    ]
    _reject_duplicates(targets_list, targets_path_obj)
    return tuple(
        sorted(
            targets_list,
            key=lambda target_obj: (
                target_obj.frame_number,
                target_obj.target_id,
            ),
        )
    )


def _read_rows(targets_path_obj: Path) -> list[dict[str, str]]:
    """Read every data row and confirm the header is complete.

    Args:
        targets_path_obj: Path to the target file.

    Returns:
        Raw rows keyed by column name.

    Raises:
        TargetValidationError: When the file cannot be read or a
            required column is missing.
    """

    try:
        file_text = targets_path_obj.read_text(encoding=CSV_ENCODING_TEXT)
    except OSError as error_obj:
        raise TargetValidationError(
            "Could not read the target file.",
            context_mapping={
                "targets_path": str(targets_path_obj),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj

    reader_obj = csv.DictReader(file_text.splitlines())
    _validate_header(reader_obj.fieldnames, targets_path_obj)
    return list(reader_obj)


def _validate_header(
    field_names: Sequence[str] | None,
    targets_path_obj: Path,
) -> None:
    """Confirm every required column is present.

    Args:
        field_names: Column names read from the file.
        targets_path_obj: Path used in error context.

    Raises:
        TargetValidationError: When a required column is missing.
    """

    present_frozenset = frozenset(field_names or ())
    missing_list = [
        column_str
        for column_str in REQUIRED_COLUMNS_TUPLE
        if column_str not in present_frozenset
    ]
    if missing_list:
        raise TargetValidationError(
            "The target file is missing required columns.",
            context_mapping={
                "targets_path": str(targets_path_obj),
                "missing_columns": missing_list,
                "required_columns": list(REQUIRED_COLUMNS_TUPLE),
            },
        )


def _build_target(
    row_dict: dict[str, str],
    row_number_int: int,
    targets_path_obj: Path,
) -> Target:
    """Convert one validated row into a target.

    Args:
        row_dict: Raw row keyed by column name.
        row_number_int: One-based line number, for error context.
        targets_path_obj: Path used in error context.

    Returns:
        The parsed target.

    Raises:
        TargetValidationError: When a field is missing or invalid.
    """

    frame_number_int = _parse_frame_number(
        row_dict, row_number_int, targets_path_obj
    )
    target_id_str = (row_dict.get("target_id") or "").strip()
    if not target_id_str:
        raise _row_error(
            "Every target needs a stable identifier.",
            row_number_int,
            targets_path_obj,
            {},
        )

    box_obj = _parse_box(row_dict, row_number_int, targets_path_obj)
    return Target(
        frame_number=frame_number_int,
        target_id=target_id_str,
        box=box_obj,
        target_type=(row_dict.get("target_type") or "").strip()
        or UNKNOWN_TARGET_TYPE_TEXT,
        required=_parse_bool(
            row_dict.get("required"), row_number_int, targets_path_obj
        ),
        source=_parse_source(
            row_dict.get("source"), row_number_int, targets_path_obj
        ),
    )


def _parse_frame_number(
    row_dict: dict[str, str],
    row_number_int: int,
    targets_path_obj: Path,
) -> int:
    """Parse and validate one one-based frame number.

    Args:
        row_dict: Raw row keyed by column name.
        row_number_int: One-based line number, for error context.
        targets_path_obj: Path used in error context.

    Returns:
        The parsed frame number.

    Raises:
        TargetValidationError: When the frame number is not a positive
            whole number.
    """

    frame_number_int = _parse_int(
        row_dict, "frame_number", row_number_int, targets_path_obj
    )
    if frame_number_int < 1:
        raise _row_error(
            "Target frame numbers are one-based.",
            row_number_int,
            targets_path_obj,
            {"frame_number": frame_number_int},
        )
    return frame_number_int


def _parse_box(
    row_dict: dict[str, str],
    row_number_int: int,
    targets_path_obj: Path,
) -> BoundingBox:
    """Parse and validate one target box.

    Args:
        row_dict: Raw row keyed by column name.
        row_number_int: One-based line number, for error context.
        targets_path_obj: Path used in error context.

    Returns:
        The parsed box.

    Raises:
        TargetValidationError: When the box has no positive area or a
            negative coordinate.
    """

    box_obj = BoundingBox(
        x1=_parse_int(row_dict, "x1", row_number_int, targets_path_obj),
        y1=_parse_int(row_dict, "y1", row_number_int, targets_path_obj),
        x2=_parse_int(row_dict, "x2", row_number_int, targets_path_obj),
        y2=_parse_int(row_dict, "y2", row_number_int, targets_path_obj),
    )
    if min(box_obj.x1, box_obj.y1) < 0:
        raise _row_error(
            "Target coordinates cannot be negative.",
            row_number_int,
            targets_path_obj,
            {"box": box_obj.as_tuple()},
        )
    if not box_obj.is_valid:
        raise _row_error(
            "Target boxes need positive width and height.",
            row_number_int,
            targets_path_obj,
            {"box": box_obj.as_tuple()},
        )
    return box_obj


def _parse_int(
    row_dict: dict[str, str],
    column_str: str,
    row_number_int: int,
    targets_path_obj: Path,
) -> int:
    """Parse one integer field.

    Args:
        row_dict: Raw row keyed by column name.
        column_str: Column to read.
        row_number_int: One-based line number, for error context.
        targets_path_obj: Path used in error context.

    Returns:
        The parsed value.

    Raises:
        TargetValidationError: When the field is absent or not an
            integer.
    """

    raw_text = (row_dict.get(column_str) or "").strip()
    try:
        return int(raw_text)
    except ValueError as error_obj:
        raise _row_error(
            f"Column {column_str!r} must be a whole number.",
            row_number_int,
            targets_path_obj,
            {column_str: raw_text},
        ) from error_obj


def _parse_bool(
    raw_value: str | None,
    row_number_int: int,
    targets_path_obj: Path,
) -> bool:
    """Parse the optional ``required`` flag.

    Args:
        raw_value: Raw cell value, which may be absent.
        row_number_int: One-based line number, for error context.
        targets_path_obj: Path used in error context.

    Returns:
        The parsed flag, defaulting to ``True``.

    Raises:
        TargetValidationError: When the value is not recognizable.
    """

    normalized_text = (raw_value or "").strip().lower()
    if not normalized_text:
        return True
    if normalized_text in TRUE_TEXTS_FROZENSET:
        return True
    if normalized_text in FALSE_TEXTS_FROZENSET:
        return False
    raise _row_error(
        "Column 'required' must be true or false.",
        row_number_int,
        targets_path_obj,
        {"required": raw_value},
    )


def _parse_source(
    raw_value: str | None,
    row_number_int: int,
    targets_path_obj: Path,
) -> TargetSource:
    """Parse the optional ``source`` field.

    Args:
        raw_value: Raw cell value, which may be absent.
        row_number_int: One-based line number, for error context.
        targets_path_obj: Path used in error context.

    Returns:
        The parsed provenance, defaulting to manual review.

    Raises:
        TargetValidationError: When the value names no known source.
    """

    normalized_text = (raw_value or "").strip().lower()
    if not normalized_text:
        return TargetSource.MANUAL
    try:
        return TargetSource(normalized_text)
    except ValueError as error_obj:
        raise _row_error(
            "Column 'source' must be manual, interpolated, or detector.",
            row_number_int,
            targets_path_obj,
            {"source": raw_value},
        ) from error_obj


def _reject_duplicates(
    targets_list: Iterable[Target],
    targets_path_obj: Path,
) -> None:
    """Reject a target declared twice in the same frame.

    Args:
        targets_list: Parsed targets.
        targets_path_obj: Path used in error context.

    Raises:
        TargetValidationError: When a frame declares one identifier
            more than once, which makes coverage ambiguous.
    """

    seen_set: set[tuple[int, str]] = set()
    for target_obj in targets_list:
        key_tuple = (target_obj.frame_number, target_obj.target_id)
        if key_tuple in seen_set:
            raise TargetValidationError(
                "A target is declared more than once in the same frame.",
                context_mapping={
                    "targets_path": str(targets_path_obj),
                    "frame_number": target_obj.frame_number,
                    "target_id": target_obj.target_id,
                },
            )
        seen_set.add(key_tuple)


def _row_error(
    message_str: str,
    row_number_int: int,
    targets_path_obj: Path,
    extra_context_mapping: dict[str, object],
) -> TargetValidationError:
    """Build a validation error naming the offending line.

    Args:
        message_str: Human-readable problem description.
        row_number_int: One-based line number in the file.
        targets_path_obj: Path to the target file.
        extra_context_mapping: Additional diagnostic fields.

    Returns:
        The error to raise.
    """

    context_mapping: dict[str, object] = {
        "targets_path": str(targets_path_obj),
        "line_number": row_number_int,
    }
    context_mapping.update(extra_context_mapping)
    return TargetValidationError(message_str, context_mapping=context_mapping)


__all__ = ["load_targets"]
