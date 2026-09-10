"""Protect the benchmark's arithmetic and its fairness protocol.

The benchmark makes a public claim about how Visual Verifier compares to
simpler methods. A defect here does not crash anything; it publishes a
wrong number under a claim of rigour, which is worse. These checks cover
the scoring, the threshold search, and the calibration split, all of
which are pure logic and cheap to test.

Generating video is not cheap, so the end-to-end generation check builds
a single short sequence rather than the whole benchmark.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from benchmarks.anonymization_gap.baselines import (
    BASELINES_TUPLE,
    mean_absolute_difference_score,
    peak_signal_noise_ratio_score,
    structural_similarity_score,
)
from benchmarks.anonymization_gap.runner import split_sequences
from benchmarks.anonymization_gap.scenarios import (
    SCENARIO_SPECS_TUPLE,
    BenchmarkSequence,
    Protection,
    SceneSpec,
    build_sequences,
    render_frame,
    target_boxes,
)
from benchmarks.anonymization_gap.scoring import (
    ConfusionCounts,
    ScoredSequence,
    choose_oracle_threshold,
    count_outcomes,
    flagged_frames_at,
)


def _sequence(
    scenario_name_str: str,
    seed_int: int,
    *,
    is_calibration_bool: bool,
) -> BenchmarkSequence:
    """Return a sequence record with placeholder media paths.

    Args:
        scenario_name_str: Family name.
        seed_int: Layout seed.
        is_calibration_bool: Whether the family may be tuned on.

    Returns:
        A sequence usable by logic that never opens the media.
    """

    return BenchmarkSequence(
        scenario_name_str=scenario_name_str,
        sequence_id_str=f"{scenario_name_str}_seed{seed_int:02d}",
        reference_path=Path("reference.mp4"),
        candidate_path=Path("candidate.mp4"),
        exposed_frames_tuple=(4,),
        frame_count_int=10,
        seed_int=seed_int,
        is_calibration_family_bool=is_calibration_bool,
        targets_path=Path("targets.csv"),
    )


def test_outcomes_are_counted_against_the_ground_truth() -> None:
    """Confirm each frame lands in exactly one confusion cell."""

    counts_obj = count_outcomes(
        flagged_frames_frozenset=frozenset({2, 3}),
        exposed_frames_frozenset=frozenset({3, 4}),
        frame_count_int=5,
    )

    assert counts_obj.true_positive_int == 1
    assert counts_obj.false_positive_int == 1
    assert counts_obj.false_negative_int == 1
    assert counts_obj.true_negative_int == 2


def test_recall_and_false_alarms_use_the_right_denominators() -> None:
    """Confirm recall divides by exposed frames, not by every frame."""

    counts_obj = ConfusionCounts(
        true_positive_int=3,
        false_negative_int=1,
        false_positive_int=2,
        true_negative_int=8,
    )

    assert counts_obj.exposed_frame_recall == pytest.approx(0.75)
    assert counts_obj.false_alarm_rate == pytest.approx(0.2)
    assert counts_obj.precision == pytest.approx(0.6)
    assert counts_obj.balanced_accuracy == pytest.approx(0.775)


def test_a_method_that_finds_nothing_scores_zero() -> None:
    """Confirm an empty result is not rewarded by a divide-by-zero."""

    counts_obj = ConfusionCounts(false_negative_int=5, true_negative_int=10)

    assert counts_obj.exposed_frame_recall == 0.0
    assert counts_obj.precision == 0.0
    assert counts_obj.f1_score == 0.0


def test_threshold_search_finds_a_perfect_separation() -> None:
    """Confirm the sweep picks a threshold that separates the classes."""

    scored_list = [
        ScoredSequence(
            scenario_name_str="synthetic",
            scores_list=[0.1, 0.2, 0.9, 0.15],
            exposed_frames_frozenset=frozenset({3}),
        )
    ]

    threshold_float = choose_oracle_threshold(scored_list)
    flagged_frozenset = flagged_frames_at(scored_list[0], threshold_float)

    assert flagged_frozenset == frozenset({3})


def test_threshold_search_survives_an_empty_benchmark() -> None:
    """Confirm no scores yields a threshold that flags nothing."""

    scored_list = [
        ScoredSequence(
            scenario_name_str="empty",
            scores_list=[],
            exposed_frames_frozenset=frozenset(),
        )
    ]

    threshold_float = choose_oracle_threshold(scored_list)

    assert threshold_float == float("inf")
    assert flagged_frames_at(scored_list[0], threshold_float) == frozenset()


def test_flagging_is_inclusive_at_the_threshold() -> None:
    """Confirm a frame scoring exactly at the threshold is flagged."""

    sequence_obj = ScoredSequence(
        scenario_name_str="synthetic",
        scores_list=[1.0, 2.0, 3.0],
        exposed_frames_frozenset=frozenset({2, 3}),
    )

    assert flagged_frames_at(sequence_obj, 2.0) == frozenset({2, 3})


def test_calibration_never_shares_a_sequence_with_evaluation() -> None:
    """Confirm nothing is both tuned on and scored."""

    sequences_list = [
        _sequence("clean", seed_int, is_calibration_bool=True)
        for seed_int in range(4)
    ] + [
        _sequence("hard", seed_int, is_calibration_bool=False)
        for seed_int in range(4)
    ]

    calibration_list, evaluation_list = split_sequences(sequences_list, 4)

    calibration_ids = {
        sequence_obj.sequence_id_str for sequence_obj in calibration_list
    }
    evaluation_ids = {
        sequence_obj.sequence_id_str for sequence_obj in evaluation_list
    }

    assert calibration_ids
    assert evaluation_ids
    assert not calibration_ids & evaluation_ids


def test_only_calibration_families_may_be_tuned_on() -> None:
    """Confirm hard footage is never offered to a baseline for tuning.

    A baseline allowed to tune on compressed footage would transfer far
    better than any real threshold does, which would quietly turn the
    published comparison into a flattering one.
    """

    sequences_list = [
        _sequence("clean", seed_int, is_calibration_bool=True)
        for seed_int in range(4)
    ] + [
        _sequence("hard", seed_int, is_calibration_bool=False)
        for seed_int in range(4)
    ]

    calibration_list, evaluation_list = split_sequences(sequences_list, 4)

    assert all(
        sequence_obj.is_calibration_family_bool
        for sequence_obj in calibration_list
    )
    assert any(
        not sequence_obj.is_calibration_family_bool
        for sequence_obj in evaluation_list
    )


def test_evaluation_covers_every_family() -> None:
    """Confirm no failure family is tuned on and then never measured."""

    sequences_list = [
        _sequence(name_str, seed_int, is_calibration_bool=True)
        for name_str in ("clean", "hard")
        for seed_int in range(4)
    ]

    _, evaluation_list = split_sequences(sequences_list, 4)
    evaluated_names = {
        sequence_obj.scenario_name_str for sequence_obj in evaluation_list
    }

    assert evaluated_names == {"clean", "hard"}


def test_every_declared_family_is_reachable() -> None:
    """Confirm the published family list has no duplicate names."""

    names_list = [spec_obj.name_str for spec_obj in SCENARIO_SPECS_TUPLE]

    assert len(names_list) == len(set(names_list))
    assert "fully_anonymized" in names_list


def test_some_families_are_withheld_from_calibration() -> None:
    """Confirm the protocol keeps hard footage out of tuning."""

    withheld_list = [
        spec_obj.name_str
        for spec_obj in SCENARIO_SPECS_TUPLE
        if not spec_obj.is_calibration_family_bool
    ]

    assert "compressed" in withheld_list
    assert "multiple_targets" in withheld_list


def test_only_a_strong_blur_counts_as_protection() -> None:
    """Confirm every partial treatment is labelled as still exposed."""

    assert not Protection.STRONG.leaves_target_exposed
    for protection_obj in (
        Protection.NONE,
        Protection.WEAK,
        Protection.OFFSET,
        Protection.PARTIAL,
    ):
        assert protection_obj.leaves_target_exposed


def test_baselines_rank_an_unchanged_frame_as_most_exposed() -> None:
    """Confirm every baseline obeys the shared score direction.

    Scoring treats all methods identically, which is only valid if a
    higher score always means "more likely to be exposed".
    """

    reference_ndarray = np.full((64, 64, 3), 120, dtype=np.uint8)
    unchanged_ndarray = reference_ndarray.copy()
    changed_ndarray = reference_ndarray.copy()
    changed_ndarray[16:48, 16:48] = 20

    for baseline_obj in BASELINES_TUPLE:
        unchanged_float = baseline_obj.scorer(
            reference_ndarray, unchanged_ndarray
        )
        changed_float = baseline_obj.scorer(reference_ndarray, changed_ndarray)
        assert unchanged_float > changed_float, baseline_obj.name_str


def test_identical_frames_score_at_the_metric_ceilings() -> None:
    """Confirm the metric implementations agree with their definitions."""

    frame_ndarray = np.full((32, 32, 3), 200, dtype=np.uint8)

    assert mean_absolute_difference_score(
        frame_ndarray, frame_ndarray
    ) == pytest.approx(0.0)
    assert peak_signal_noise_ratio_score(frame_ndarray, frame_ndarray) > 50.0
    assert structural_similarity_score(
        frame_ndarray, frame_ndarray
    ) == pytest.approx(1.0, abs=1e-6)


def test_structural_similarity_falls_for_a_blurred_region() -> None:
    """Confirm the SSIM implementation responds to real structure loss."""

    generator_obj = np.random.default_rng(0)
    reference_ndarray = generator_obj.integers(
        0, 255, (64, 64, 3), dtype=np.uint8
    )
    blurred_ndarray = reference_ndarray.copy()
    blurred_ndarray[:] = 128

    assert (
        structural_similarity_score(reference_ndarray, blurred_ndarray) < 0.5
    )


def test_scene_rendering_is_deterministic() -> None:
    """Confirm the same seed renders the same pixels.

    A benchmark whose media drifted between runs would publish numbers
    that could not be reproduced.
    """

    scene_spec = SceneSpec()
    first_ndarray = render_frame(5, scene_spec, 2)
    second_ndarray = render_frame(5, scene_spec, 2)

    assert np.array_equal(first_ndarray, second_ndarray)


def test_seeds_move_the_target() -> None:
    """Confirm repeating a family with a new seed changes the layout."""

    scene_spec = SceneSpec()

    assert target_boxes(5, scene_spec, 0) != target_boxes(5, scene_spec, 1)


def test_scene_spec_controls_target_count_and_size() -> None:
    """Confirm the parameters the families rely on actually apply."""

    single_list = target_boxes(3, SceneSpec(), 0)
    triple_list = target_boxes(3, SceneSpec(target_count_int=3), 0)
    small_list = target_boxes(3, SceneSpec(target_scale_float=0.25), 0)

    assert len(single_list) == 1
    assert len(triple_list) == 3
    assert _box_width(small_list[0]) < _box_width(single_list[0])


def _box_width(box_tuple: tuple[int, int, int, int]) -> int:
    """Return the width of one target box."""

    return box_tuple[2] - box_tuple[0]


def test_one_family_generates_a_labelled_pair(tmp_path: Path) -> None:
    """Confirm generation writes playable media with its ground truth."""

    sequences_list = build_sequences(tmp_path, (0,))
    first_obj = sequences_list[0]

    assert len(sequences_list) == len(SCENARIO_SPECS_TUPLE)
    assert first_obj.reference_path.is_file()
    assert first_obj.candidate_path.is_file()
    assert first_obj.reference_path.stat().st_size > 0
    assert first_obj.frame_count_int > 0


def test_generated_ground_truth_matches_the_declared_family(
    tmp_path: Path,
) -> None:
    """Confirm a generated sequence carries its family's labels."""

    sequences_list = build_sequences(tmp_path, (0,))
    by_name_dict = {
        sequence_obj.scenario_name_str: sequence_obj
        for sequence_obj in sequences_list
    }

    assert by_name_dict["fully_anonymized"].exposed_frames_tuple == ()
    assert by_name_dict["one_missed_frame"].exposed_frames_tuple == (9,)
    assert by_name_dict["long_gap"].exposed_frames_tuple == (
        8,
        9,
        10,
        11,
        12,
    )
