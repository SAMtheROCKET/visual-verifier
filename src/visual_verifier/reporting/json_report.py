"""Write structured verification evidence to JSON files."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from visual_verifier.exceptions import ReportWriteError
from visual_verifier.type_aliases import PathInput

JSON_ENCODING_TEXT = "utf-8"
JSON_INDENT_INT = 2
JSON_ENSURE_ASCII_BOOL = False


def write_json_report(
    data: Mapping[str, object],
    path: PathInput,
) -> Path:
    """Write an ordered mapping to a human-readable JSON report.

    Args:
        data: Structured verification data to serialize.
        path: Destination path for the JSON report.

    Returns:
        Path to the generated JSON report.

    Raises:
        ReportWriteError: If serialization or file writing fails.

    Warning:
        Values unsupported by the standard JSON encoder are converted to
        strings to preserve the repository's existing report behaviour.
    """

    output_path_obj = _prepare_output_path(path)
    serialized_json_text = _serialize_json_payload(data)
    _write_json_text(serialized_json_text, output_path_obj)
    return output_path_obj


def _prepare_output_path(output_path_input: PathInput) -> Path:
    """Create the destination directory for a JSON report.

    Args:
        output_path_input: User-provided destination path.

    Returns:
        Expanded destination path.

    Raises:
        ReportWriteError: If the parent directory cannot be created.
    """

    output_path_obj = Path(output_path_input).expanduser()
    try:
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error_obj:
        raise ReportWriteError(
            "Could not prepare the JSON report directory.",
            context_mapping={
                "output_path": str(output_path_obj),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj
    return output_path_obj


def _serialize_json_payload(
    data_mapping: Mapping[str, object],
) -> str:
    """Serialize report data without changing key insertion order.

    Args:
        data_mapping: Structured report data in output order.

    Returns:
        Indented Unicode JSON text.

    Raises:
        ReportWriteError: If the report data cannot be serialized.
    """

    try:
        return json.dumps(
            dict(data_mapping),
            indent=JSON_INDENT_INT,
            ensure_ascii=JSON_ENSURE_ASCII_BOOL,
            default=str,
        )
    except (TypeError, ValueError) as error_obj:
        raise ReportWriteError(
            "Could not serialize the JSON report.",
            context_mapping={
                "key_count": len(data_mapping),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj


def _write_json_text(
    serialized_json_text: str,
    output_path_obj: Path,
) -> None:
    """Write serialized JSON text using the repository convention.

    Args:
        serialized_json_text: Complete JSON document text.
        output_path_obj: Destination path for the JSON report.

    Raises:
        ReportWriteError: If the destination cannot be written.
    """

    try:
        output_path_obj.write_text(
            serialized_json_text,
            encoding=JSON_ENCODING_TEXT,
        )
    except (OSError, UnicodeError) as error_obj:
        raise ReportWriteError(
            "Could not write the JSON report.",
            context_mapping={
                "output_path": str(output_path_obj),
                "character_count": len(serialized_json_text),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj


__all__ = ["write_json_report"]
