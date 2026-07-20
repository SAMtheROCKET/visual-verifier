"""Write tabular verification evidence to CSV files."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from visual_verifier.exceptions import ReportWriteError
from visual_verifier.type_aliases import PathInput, ReportRow

CSV_ENCODING_TEXT = "utf-8-sig"
CSV_INCLUDE_INDEX_BOOL = False


def write_csv_report(
    report_rows_list: list[ReportRow],
    output_path_input: PathInput,
    *,
    column_names: Sequence[str] | None = None,
) -> Path:
    """Write ordered report rows to a CSV file.

    Args:
        report_rows_list: Report rows in the required output order.
        output_path_input: Destination path for the CSV report.
        column_names: Optional stable schema used when rows are empty.

    Returns:
        Path to the generated CSV report.

    Raises:
        ReportWriteError: If the destination cannot be prepared or written.
    """

    output_path_obj = _prepare_output_path(output_path_input)
    report_dataframe_obj = _build_report_dataframe(
        report_rows_list,
        column_names,
    )
    _write_report_dataframe(report_dataframe_obj, output_path_obj)
    return output_path_obj


def _prepare_output_path(output_path_input: PathInput) -> Path:
    """Create the destination directory for a CSV report."""

    output_path_obj = Path(output_path_input).expanduser()
    try:
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error_obj:
        raise ReportWriteError(
            "Could not prepare the CSV report directory.",
            context_mapping={
                "output_path": str(output_path_obj),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj
    return output_path_obj


def _build_report_dataframe(
    report_rows_list: list[ReportRow],
    column_names: Sequence[str] | None,
) -> pd.DataFrame:
    """Build a dataframe without changing row or column order."""

    if column_names is None:
        return pd.DataFrame(report_rows_list)
    return pd.DataFrame(report_rows_list, columns=list(column_names))


def _write_report_dataframe(
    report_dataframe_obj: pd.DataFrame,
    output_path_obj: Path,
) -> None:
    """Serialize a dataframe using the repository CSV convention."""

    try:
        report_dataframe_obj.to_csv(
            output_path_obj,
            index=CSV_INCLUDE_INDEX_BOOL,
            encoding=CSV_ENCODING_TEXT,
        )
    except (OSError, TypeError, UnicodeError, ValueError) as error_obj:
        raise ReportWriteError(
            "Could not write the CSV report.",
            context_mapping={
                "output_path": str(output_path_obj),
                "row_count": len(report_dataframe_obj.index),
                "column_count": len(report_dataframe_obj.columns),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj


__all__ = ["write_csv_report"]
