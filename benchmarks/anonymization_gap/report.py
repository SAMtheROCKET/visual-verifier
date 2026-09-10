"""Render a benchmark run as markdown and as a machine-readable document.

The markdown is written to be pasted into documentation unchanged, so it
carries the caveats alongside the numbers rather than below them.
"""

from __future__ import annotations

import json
from typing import Any

from benchmarks.anonymization_gap.runner import BenchmarkRun, MethodResult
from benchmarks.anonymization_gap.scenarios import SCENARIO_SPECS_TUPLE

YES_TEXT = "Yes"
NO_TEXT = "No"


def render_markdown(run_obj: BenchmarkRun) -> str:
    """Render one benchmark run as a markdown report.

    Args:
        run_obj: Completed benchmark run.

    Returns:
        Markdown suitable for the published documentation.
    """

    blocks_list = [
        _render_headline(run_obj),
        _render_headline_table(run_obj),
        _render_capability_table(run_obj),
        _render_per_scenario_table(run_obj),
        _render_scenario_key(),
    ]
    return "\n\n".join(block for block in blocks_list if block)


def _render_headline(run_obj: BenchmarkRun) -> str:
    """Render the run size and the scoring protocol."""

    evaluation_list = run_obj.evaluation_sequences_list
    exposed_int = sum(
        len(sequence_obj.exposed_frames_tuple)
        for sequence_obj in evaluation_list
    )
    frames_int = sum(
        sequence_obj.frame_count_int for sequence_obj in evaluation_list
    )
    return (
        f"{len(run_obj.sequences_list)} generated sequences across "
        f"{len(run_obj.scenario_names_list)} failure families. Results are "
        f"reported on the {len(evaluation_list)}-sequence evaluation half: "
        f"{frames_int} frames, {exposed_int} of them deliberately left "
        f"exposed. The other {len(run_obj.calibration_sequences_list)} "
        "sequences exist only so the baselines can choose a threshold "
        "without seeing the answers."
    )


def _render_headline_table(run_obj: BenchmarkRun) -> str:
    """Render the frame-level accuracy of every method."""

    lines_list = [
        "| Method | Missed-frame recall | False alarms | F1 | "
        "Operating point | Oracle F1 |",
        "| --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for method_obj in run_obj.method_results_list:
        counts_obj = method_obj.counts_obj
        oracle_obj = method_obj.oracle_counts_obj
        oracle_text = (
            "-" if oracle_obj is None else f"{oracle_obj.f1_score:.2f}"
        )
        lines_list.append(
            f"| {method_obj.name_str} "
            f"| {counts_obj.exposed_frame_recall:.0%} "
            f"| {counts_obj.false_alarm_rate:.1%} "
            f"| {counts_obj.f1_score:.2f} "
            f"| {method_obj.tuning_note_str} "
            f"| {oracle_text} |"
        )
    lines_list.append(
        "\n_Oracle F1_ is what a baseline would score if its threshold were "
        "chosen with the answers already in hand. Nobody can reach it in "
        "production. It is listed so the calibrated column cannot be read "
        "as the best these methods could ever do."
    )
    return "\n".join(lines_list)


def _render_capability_table(run_obj: BenchmarkRun) -> str:
    """Render what evidence each method can produce."""

    lines_list = [
        "| Method | Localizes frame | Localizes region | "
        "Temporal evidence | Needs tuning |",
        "| --- | :-: | :-: | :-: | :-: |",
    ]
    for method_obj in run_obj.method_results_list:
        capabilities_obj = method_obj.capabilities_obj
        lines_list.append(
            f"| {method_obj.name_str} "
            f"| {_yes_no(capabilities_obj.localizes_frame_bool)} "
            f"| {_yes_no(capabilities_obj.localizes_region_bool)} "
            f"| {_yes_no(capabilities_obj.temporal_evidence_bool)} "
            f"| {_yes_no(capabilities_obj.needs_tuning_bool)} |"
        )
    return "\n".join(lines_list)


def _render_per_scenario_table(run_obj: BenchmarkRun) -> str:
    """Render missed-frame recall for every family and method."""

    header_list = ["| Failure family |"]
    divider_list = ["| --- |"]
    for method_obj in run_obj.method_results_list:
        header_list.append(f" {_short_name(method_obj)} |")
        divider_list.append(" ---: |")

    lines_list = ["".join(header_list), "".join(divider_list)]
    for scenario_name_str in run_obj.scenario_names_list:
        row_list = [f"| `{scenario_name_str}` |"]
        for method_obj in run_obj.method_results_list:
            row_list.append(
                f" {_scenario_recall(method_obj, scenario_name_str)} |"
            )
        lines_list.append("".join(row_list))

    return (
        "Missed-frame recall by family. `fully_anonymized` has no exposed "
        "frames, so it is scored on false alarms instead and shown as a "
        "dash.\n\n" + "\n".join(lines_list)
    )


def _scenario_recall(
    method_obj: MethodResult,
    scenario_name_str: str,
) -> str:
    """Return one family's recall for one method, or a dash.

    Args:
        method_obj: Method being reported.
        scenario_name_str: Family to look up.

    Returns:
        A formatted percentage, or ``-`` when the family has no exposed
        frames to recall.
    """

    counts_obj = method_obj.per_scenario_counts_dict.get(scenario_name_str)
    if counts_obj is None:
        return "-"
    exposed_int = counts_obj.true_positive_int + counts_obj.false_negative_int
    if exposed_int == 0:
        return "-"
    return f"{counts_obj.exposed_frame_recall:.0%}"


def _render_scenario_key() -> str:
    """Render what each family probes."""

    lines_list = ["| Failure family | What it probes |", "| --- | --- |"]
    lines_list.extend(
        f"| `{spec_obj.name_str}` | {spec_obj.description_str} |"
        for spec_obj in SCENARIO_SPECS_TUPLE
    )
    return "\n".join(lines_list)


def _short_name(method_obj: MethodResult) -> str:
    """Return a compact column heading for one method."""

    return (
        method_obj.name_str.replace(" threshold", "")
        .replace("Mean pixel difference", "Mean diff")
        .replace("Visual Verifier + targets", "VV + targets")
        .replace("Visual Verifier", "VV")
    )


def _yes_no(value_bool: bool) -> str:
    """Return a table cell for one capability flag."""

    return YES_TEXT if value_bool else NO_TEXT


def render_json(run_obj: BenchmarkRun) -> str:
    """Render one benchmark run as a machine-readable document.

    Args:
        run_obj: Completed benchmark run.

    Returns:
        Pretty-printed JSON carrying every measured number.
    """

    document_dict: dict[str, Any] = {
        "schema_version": "1.0",
        "sequence_count": len(run_obj.sequences_list),
        "evaluation_sequence_count": len(run_obj.evaluation_sequences_list),
        "calibration_sequence_count": len(run_obj.calibration_sequences_list),
        "scenarios": list(run_obj.scenario_names_list),
        "methods": [
            _method_document(method_obj)
            for method_obj in run_obj.method_results_list
        ],
    }
    return json.dumps(document_dict, indent=2, sort_keys=True)


def _method_document(method_obj: MethodResult) -> dict[str, Any]:
    """Return one method's measurements as a serializable mapping.

    Args:
        method_obj: Method to serialize.

    Returns:
        Mapping carrying totals, capabilities, and per-family counts.
    """

    counts_obj = method_obj.counts_obj
    return {
        "name": method_obj.name_str,
        "exposed_frame_recall": round(counts_obj.exposed_frame_recall, 4),
        "false_alarm_rate": round(counts_obj.false_alarm_rate, 4),
        "precision": round(counts_obj.precision, 4),
        "f1_score": round(counts_obj.f1_score, 4),
        "true_positive": counts_obj.true_positive_int,
        "false_negative": counts_obj.false_negative_int,
        "false_positive": counts_obj.false_positive_int,
        "true_negative": counts_obj.true_negative_int,
        "localizes_frame": method_obj.capabilities_obj.localizes_frame_bool,
        "localizes_region": (
            method_obj.capabilities_obj.localizes_region_bool
        ),
        "temporal_evidence": (
            method_obj.capabilities_obj.temporal_evidence_bool
        ),
        "threshold_note": method_obj.tuning_note_str,
        "needs_tuning": method_obj.capabilities_obj.needs_tuning_bool,
        "oracle_f1_score": (
            None
            if method_obj.oracle_counts_obj is None
            else round(method_obj.oracle_counts_obj.f1_score, 4)
        ),
        "per_scenario_recall": {
            scenario_name_str: round(
                scenario_counts_obj.exposed_frame_recall, 4
            )
            for scenario_name_str, scenario_counts_obj in sorted(
                method_obj.per_scenario_counts_dict.items()
            )
        },
    }
