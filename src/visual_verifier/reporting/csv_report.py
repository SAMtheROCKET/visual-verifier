"""Write tabular verification evidence to CSV files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from visual_verifier.exceptions import ReportWriteError
from visual_verifier.type_aliases import PathInput, ReportRow

CSV_ENCODING_TEXT = "utf-8-sig"
CSV_INCLUDE_INDEX_BOOL = False


def write_csv_report(
    report_rows_list: list[ReportRow],
    output_path_input: PathInput,
) -> Path:
    """Write ordered report rows to a CSV file.

    Args:
        report_rows_list: Report rows in the required output order.
        output_path_input: Destination path for the CSV report.

    Returns:
        Path to the generated CSV report.

    Raises:
        ReportWriteError: If the destination cannot be prepared or written.

    Warning:
        Column order follows the dictionaries supplied by the report builder.
        Callers should therefore construct rows with a stable key order.
    """

    output_path_obj = _prepare_output_path(output_path_input)
    report_dataframe_obj = _build_report_dataframe(report_rows_list)
    _write_report_dataframe(report_dataframe_obj, output_path_obj)
    return output_path_obj


def _prepare_output_path(output_path_input: PathInput) -> Path:
    """Create the destination directory for a CSV report.

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
            "Could not prepare the CSV report directory.",
            context_mapping={
                "output_path": str(output_path_obj),
                "cause_type": type(error_obj).__name__,
            },
        ) from error_obj
    return output_path_obj


def _build_report_dataframe(
    report_rows_list: list[ReportRow],
) -> pd.DataFrame:
    """Build a dataframe without changing row or column order.

    Args:
        report_rows_list: Ordered dictionaries containing report values.

    Returns:
        Dataframe ready for CSV serialization.
    """

    return pd.DataFrame(report_rows_list)


def _write_report_dataframe(
    report_dataframe_obj: pd.DataFrame,
    output_path_obj: Path,
) -> None:
    """Serialize a dataframe using the repository CSV convention.

    Args:
        report_dataframe_obj: Dataframe containing report evidence.
        output_path_obj: Destination path for the CSV report.

    Raises:
        ReportWriteError: If pandas cannot serialize or write the report.
    """

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
