"""Run the Anonymization Gap Benchmark and print its report.

    uv run python -m benchmarks.run_anonymization_gap --output results

Run it from the repository root, which is what puts `benchmarks` on the
import path.

Generated media and per-sequence evidence are written under the output
directory, so a surprising number can be opened and inspected rather than
taken on trust.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmarks.anonymization_gap.report import render_json, render_markdown
from benchmarks.anonymization_gap.runner import (
    DEFAULT_SEED_COUNT_INT,
    run_benchmark,
)

DEFAULT_OUTPUT_DIRECTORY_NAME_STR = "benchmark-results"
MARKDOWN_FILENAME_STR = "results.md"
JSON_FILENAME_STR = "results.json"


def build_parser() -> argparse.ArgumentParser:
    """Return the benchmark argument parser.

    Returns:
        Parser accepting the output directory and the seed count.
    """

    parser_obj = argparse.ArgumentParser(
        prog="run_anonymization_gap.py",
        description=(
            "Measure Visual Verifier and global-metric baselines against "
            "labelled anonymization failures."
        ),
    )
    parser_obj.add_argument(
        "--output",
        metavar="DIR",
        default=DEFAULT_OUTPUT_DIRECTORY_NAME_STR,
        help=(
            "Directory for generated media, evidence, and reports "
            f"(default: {DEFAULT_OUTPUT_DIRECTORY_NAME_STR})."
        ),
    )
    parser_obj.add_argument(
        "--seeds",
        metavar="INT",
        type=int,
        default=DEFAULT_SEED_COUNT_INT,
        help=(
            "Layouts to repeat each failure family with. Half "
            "calibrate the baselines and half are evaluated "
            f"(default: {DEFAULT_SEED_COUNT_INT})."
        ),
    )
    return parser_obj


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark and write its reports.

    Args:
        argv: Optional argument vector.

    Returns:
        Process exit code. ``0`` on success.
    """

    arguments_obj = build_parser().parse_args(argv)
    output_path_obj = Path(arguments_obj.output).expanduser()
    output_path_obj.mkdir(parents=True, exist_ok=True)

    run_obj = run_benchmark(output_path_obj, arguments_obj.seeds)

    markdown_str = render_markdown(run_obj)
    (output_path_obj / MARKDOWN_FILENAME_STR).write_text(
        markdown_str + "\n", encoding="utf-8"
    )
    (output_path_obj / JSON_FILENAME_STR).write_text(
        render_json(run_obj) + "\n", encoding="utf-8"
    )

    sys.stdout.reconfigure(encoding="utf-8")
    print(markdown_str)
    print(f"\nWritten to {output_path_obj}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
