"""Expose stable reporting interfaces for Visual Verifier."""

from visual_verifier.reporting.annotations import annotate_frame
from visual_verifier.reporting.console import format_verification_summary
from visual_verifier.reporting.csv_report import write_csv_report
from visual_verifier.reporting.html_report import write_html_report
from visual_verifier.reporting.json_report import write_json_report
from visual_verifier.reporting.track_report import write_tracking_reports

__all__ = [
    "annotate_frame",
    "format_verification_summary",
    "write_csv_report",
    "write_html_report",
    "write_json_report",
    "write_tracking_reports",
]
