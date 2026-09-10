"""Run every method over every sequence and collect the results.

The protocol is deliberately generous to the baselines, because a
comparison that flatters the tool publishing it is worthless.

Seeds are split into a calibration half and an evaluation half. Each
global metric picks the single threshold that maximizes its balanced
accuracy on the calibration half, then is measured on the evaluation
half it has never seen. That is the fair analogue of a team tuning a
threshold on the footage they had and shipping it.

Each baseline is *also* reported at its oracle threshold: the best
threshold on the evaluation half itself, chosen with the answers in
hand. No real user can reach that number, so it stands as an upper
bound rather than a result.

Visual Verifier runs at shipped defaults on the same evaluation half,
tuned to nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from benchmarks.anonymization_gap.baselines import (
    BASELINES_TUPLE,
    Baseline,
    score_sequence,
)
from benchmarks.anonymization_gap.scenarios import (
    BenchmarkSequence,
    build_sequences,
)
from benchmarks.anonymization_gap.scoring import (
    ConfusionCounts,
    ScoredSequence,
    choose_oracle_threshold,
    count_outcomes,
    flagged_frames_at,
)
from visual_verifier.api import verify_video

VISUAL_VERIFIER_NAME_STR = "Visual Verifier"
DEFAULT_SEED_COUNT_INT = 6
NO_TUNING_NOTE_STR = "Shipped defaults"
CALIBRATED_NOTE_STR = "Tuned on held-out calibration half"


@dataclass(frozen=True, slots=True)
class MethodCapabilities:
    """What evidence a method can produce beyond a frame verdict.

    Attributes:
        localizes_frame_bool: Names which frames failed.
        localizes_region_bool: Names where in the frame the gap is.
        temporal_evidence_bool: Reports continuity across frames.
        needs_tuning_bool: Requires a threshold chosen from labelled
            footage before it can be trusted.
    """

    localizes_frame_bool: bool
    localizes_region_bool: bool
    temporal_evidence_bool: bool
    needs_tuning_bool: bool


@dataclass(frozen=True, slots=True)
class MethodResult:
    """One method's measured performance on the evaluation half.

    Attributes:
        name_str: Display name.
        counts_obj: Frame-level outcomes over the evaluation sequences.
        per_scenario_counts_dict: Outcomes broken down by family.
        capabilities_obj: Evidence the method can produce.
        tuning_note_str: How the operating point was chosen.
        oracle_counts_obj: Outcomes at the unachievable oracle
            threshold, or ``None`` for a method with no threshold.
    """

    name_str: str
    counts_obj: ConfusionCounts
    per_scenario_counts_dict: dict[str, ConfusionCounts]
    capabilities_obj: MethodCapabilities
    tuning_note_str: str
    oracle_counts_obj: ConfusionCounts | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    """Everything one benchmark execution produced.

    Attributes:
        sequences_list: Every generated sequence.
        evaluation_sequences_list: Sequences results are reported on.
        calibration_sequences_list: Sequences baselines were tuned on.
        method_results_list: One entry per method, Visual Verifier first.
        scenario_names_list: Family names in report order.
    """

    sequences_list: list[BenchmarkSequence]
    evaluation_sequences_list: list[BenchmarkSequence]
    calibration_sequences_list: list[BenchmarkSequence]
    method_results_list: list[MethodResult] = field(default_factory=list)
    scenario_names_list: list[str] = field(default_factory=list)


def split_sequences(
    sequences_list: list[BenchmarkSequence],
    seed_count_int: int,
) -> tuple[list[BenchmarkSequence], list[BenchmarkSequence]]:
    """Split sequences into what may be tuned on and what is measured.

    The split is deliberately asymmetric, because a realistic one is.
    Calibration holds only the straightforward families a team would
    plausibly have when choosing a threshold: clean footage where a
    frame was simply skipped. Evaluation holds every family, including
    the compressed, noisy, weakly blurred, and multi-target footage a
    pipeline meets later.

    Splitting on seed as well keeps the two sides disjoint, so no
    sequence is ever both tuned on and scored.

    Args:
        sequences_list: Every generated sequence.
        seed_count_int: Number of seeds each family was repeated with.

    Returns:
        The calibration sequences and the evaluation sequences.
    """

    calibration_seed_count_int = max(1, seed_count_int // 2)
    calibration_seeds_frozenset = frozenset(range(calibration_seed_count_int))

    calibration_list: list[BenchmarkSequence] = []
    evaluation_list: list[BenchmarkSequence] = []
    for sequence_obj in sequences_list:
        if sequence_obj.seed_int not in calibration_seeds_frozenset:
            evaluation_list.append(sequence_obj)
        elif sequence_obj.is_calibration_family_bool:
            calibration_list.append(sequence_obj)

    if not evaluation_list:
        return [], calibration_list
    return calibration_list, evaluation_list


def run_benchmark(
    working_directory_path: Path,
    seed_count_int: int = DEFAULT_SEED_COUNT_INT,
) -> BenchmarkRun:
    """Generate the benchmark, run every method, and score the results.

    Args:
        working_directory_path: Directory for generated media and
            per-sequence evidence.
        seed_count_int: Layouts each failure family is repeated with.

    Returns:
        The completed run.
    """

    media_directory_path = working_directory_path / "media"
    sequences_list = build_sequences(
        media_directory_path, tuple(range(max(2, seed_count_int)))
    )
    calibration_list, evaluation_list = split_sequences(
        sequences_list, max(2, seed_count_int)
    )

    method_results_list = [
        _run_visual_verifier(
            evaluation_list, working_directory_path / "evidence"
        )
    ]
    method_results_list.extend(
        _run_baseline(baseline_obj, calibration_list, evaluation_list)
        for baseline_obj in BASELINES_TUPLE
    )

    return BenchmarkRun(
        sequences_list=sequences_list,
        evaluation_sequences_list=evaluation_list,
        calibration_sequences_list=calibration_list,
        method_results_list=method_results_list,
        scenario_names_list=_ordered_scenario_names(evaluation_list),
    )


def _ordered_scenario_names(
    sequences_list: list[BenchmarkSequence],
) -> list[str]:
    """Return family names in first-seen order.

    Args:
        sequences_list: Sequences to read names from.

    Returns:
        Unique family names, preserving generation order.
    """

    names_list: list[str] = []
    for sequence_obj in sequences_list:
        if sequence_obj.scenario_name_str not in names_list:
            names_list.append(sequence_obj.scenario_name_str)
    return names_list


def _accumulate(
    per_scenario_counts_dict: dict[str, ConfusionCounts],
    scenario_name_str: str,
    counts_obj: ConfusionCounts,
) -> None:
    """Add one sequence's outcomes into the per-family totals.

    Args:
        per_scenario_counts_dict: Totals updated in place.
        scenario_name_str: Family the sequence belongs to.
        counts_obj: Outcomes to add.
    """

    per_scenario_counts_dict[scenario_name_str] = per_scenario_counts_dict.get(
        scenario_name_str, ConfusionCounts()
    ).combined_with(counts_obj)


def _run_visual_verifier(
    sequences_list: list[BenchmarkSequence],
    evidence_directory_path: Path,
) -> MethodResult:
    """Run Visual Verifier at shipped defaults over every sequence.

    Args:
        sequences_list: Evaluation sequences.
        evidence_directory_path: Directory for per-sequence evidence.

    Returns:
        The measured result.
    """

    per_scenario_counts_dict: dict[str, ConfusionCounts] = {}
    total_counts_obj = ConfusionCounts()

    for sequence_obj in sequences_list:
        result_obj = verify_video(
            sequence_obj.reference_path,
            sequence_obj.candidate_path,
            output_dir=evidence_directory_path / sequence_obj.sequence_id_str,
            save_annotated_video=False,
            save_html_report=False,
        )
        counts_obj = count_outcomes(
            frozenset(result_obj.failed_frames),
            frozenset(sequence_obj.exposed_frames_tuple),
            sequence_obj.frame_count_int,
        )
        total_counts_obj = total_counts_obj.combined_with(counts_obj)
        _accumulate(
            per_scenario_counts_dict,
            sequence_obj.scenario_name_str,
            counts_obj,
        )

    return MethodResult(
        name_str=VISUAL_VERIFIER_NAME_STR,
        counts_obj=total_counts_obj,
        per_scenario_counts_dict=per_scenario_counts_dict,
        capabilities_obj=MethodCapabilities(
            localizes_frame_bool=True,
            localizes_region_bool=True,
            temporal_evidence_bool=True,
            needs_tuning_bool=False,
        ),
        tuning_note_str=NO_TUNING_NOTE_STR,
    )


def _score_all(
    baseline_obj: Baseline,
    sequences_list: list[BenchmarkSequence],
) -> list[ScoredSequence]:
    """Score every sequence with one baseline.

    Args:
        baseline_obj: Method to score with.
        sequences_list: Sequences to score.

    Returns:
        One scored sequence per input sequence.
    """

    return [
        ScoredSequence(
            scenario_name_str=sequence_obj.scenario_name_str,
            scores_list=score_sequence(
                sequence_obj.reference_path,
                sequence_obj.candidate_path,
                baseline_obj,
            ),
            exposed_frames_frozenset=frozenset(
                sequence_obj.exposed_frames_tuple
            ),
        )
        for sequence_obj in sequences_list
    ]


def _evaluate_at(
    scored_sequences_list: list[ScoredSequence],
    threshold_float: float,
) -> tuple[ConfusionCounts, dict[str, ConfusionCounts]]:
    """Measure one threshold over already-scored sequences.

    Args:
        scored_sequences_list: Scored evaluation sequences.
        threshold_float: Score at or above which a frame is flagged.

    Returns:
        The combined counts and the per-family counts.
    """

    per_scenario_counts_dict: dict[str, ConfusionCounts] = {}
    total_counts_obj = ConfusionCounts()

    for scored_obj in scored_sequences_list:
        counts_obj = count_outcomes(
            flagged_frames_at(scored_obj, threshold_float),
            scored_obj.exposed_frames_frozenset,
            len(scored_obj.scores_list),
        )
        total_counts_obj = total_counts_obj.combined_with(counts_obj)
        _accumulate(
            per_scenario_counts_dict,
            scored_obj.scenario_name_str,
            counts_obj,
        )

    return total_counts_obj, per_scenario_counts_dict


def _run_baseline(
    baseline_obj: Baseline,
    calibration_list: list[BenchmarkSequence],
    evaluation_list: list[BenchmarkSequence],
) -> MethodResult:
    """Tune one global metric on the calibration half, then measure it.

    Args:
        baseline_obj: Method to run.
        calibration_list: Sequences the threshold may be tuned on.
        evaluation_list: Sequences the result is reported on.

    Returns:
        The measured result, carrying its oracle upper bound.
    """

    calibration_scored_list = _score_all(baseline_obj, calibration_list)
    evaluation_scored_list = _score_all(baseline_obj, evaluation_list)

    transferred_threshold_float = choose_oracle_threshold(
        calibration_scored_list
    )
    oracle_threshold_float = choose_oracle_threshold(evaluation_scored_list)

    total_counts_obj, per_scenario_counts_dict = _evaluate_at(
        evaluation_scored_list, transferred_threshold_float
    )
    oracle_counts_obj, _ = _evaluate_at(
        evaluation_scored_list, oracle_threshold_float
    )

    return MethodResult(
        name_str=baseline_obj.name_str,
        counts_obj=total_counts_obj,
        per_scenario_counts_dict=per_scenario_counts_dict,
        capabilities_obj=MethodCapabilities(
            localizes_frame_bool=True,
            localizes_region_bool=False,
            temporal_evidence_bool=False,
            needs_tuning_bool=True,
        ),
        tuning_note_str=CALIBRATED_NOTE_STR,
        oracle_counts_obj=oracle_counts_obj,
    )
