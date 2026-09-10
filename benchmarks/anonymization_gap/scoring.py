"""Score every method against the same ground truth, on the same terms.

The comparison is deliberately generous to the baselines. Each global
metric is swept over every threshold the benchmark data admits and keeps
the single threshold that maximizes its balanced accuracy *on the
benchmark itself*. That is an oracle a real user does not have: it
requires knowing the answers first. Visual Verifier runs at its shipped
defaults, tuned to nothing.

If a baseline still loses under those terms, the gap is real rather than
an artefact of threshold choice.
"""

from __future__ import annotations

from dataclasses import dataclass

MINIMUM_SCORE_COUNT_INT = 2


@dataclass(frozen=True, slots=True)
class ConfusionCounts:
    """Frame-level outcomes of one method over the whole benchmark.

    Attributes:
        true_positive_int: Exposed frames correctly flagged.
        false_negative_int: Exposed frames missed.
        false_positive_int: Protected frames wrongly flagged.
        true_negative_int: Protected frames correctly left alone.
    """

    true_positive_int: int = 0
    false_negative_int: int = 0
    false_positive_int: int = 0
    true_negative_int: int = 0

    def combined_with(self, other_obj: ConfusionCounts) -> ConfusionCounts:
        """Return the element-wise sum of two counts.

        Args:
            other_obj: Counts to add.

        Returns:
            The combined counts.
        """

        return ConfusionCounts(
            true_positive_int=(
                self.true_positive_int + other_obj.true_positive_int
            ),
            false_negative_int=(
                self.false_negative_int + other_obj.false_negative_int
            ),
            false_positive_int=(
                self.false_positive_int + other_obj.false_positive_int
            ),
            true_negative_int=(
                self.true_negative_int + other_obj.true_negative_int
            ),
        )

    @property
    def exposed_frame_recall(self) -> float:
        """Return the fraction of exposed frames that were flagged."""

        exposed_int = self.true_positive_int + self.false_negative_int
        if exposed_int == 0:
            return 0.0
        return self.true_positive_int / exposed_int

    @property
    def false_alarm_rate(self) -> float:
        """Return the fraction of protected frames wrongly flagged."""

        protected_int = self.false_positive_int + self.true_negative_int
        if protected_int == 0:
            return 0.0
        return self.false_positive_int / protected_int

    @property
    def balanced_accuracy(self) -> float:
        """Return the mean of recall and specificity."""

        return (
            self.exposed_frame_recall + (1.0 - self.false_alarm_rate)
        ) / 2.0

    @property
    def precision(self) -> float:
        """Return the fraction of flagged frames that were truly exposed."""

        flagged_int = self.true_positive_int + self.false_positive_int
        if flagged_int == 0:
            return 0.0
        return self.true_positive_int / flagged_int

    @property
    def f1_score(self) -> float:
        """Return the harmonic mean of precision and recall."""

        precision_float = self.precision
        recall_float = self.exposed_frame_recall
        if precision_float + recall_float <= 0.0:
            return 0.0
        return (
            2.0
            * precision_float
            * recall_float
            / (precision_float + recall_float)
        )


def count_outcomes(
    flagged_frames_frozenset: frozenset[int],
    exposed_frames_frozenset: frozenset[int],
    frame_count_int: int,
) -> ConfusionCounts:
    """Compare one method's frame decisions against the ground truth.

    Args:
        flagged_frames_frozenset: Frames the method called unprotected.
        exposed_frames_frozenset: Frames truly left exposed.
        frame_count_int: Frames compared in the sequence.

    Returns:
        Frame-level outcome counts for this sequence.
    """

    all_frames_range = range(1, frame_count_int + 1)
    true_positive_int = 0
    false_negative_int = 0
    false_positive_int = 0
    true_negative_int = 0

    for frame_int in all_frames_range:
        is_exposed_bool = frame_int in exposed_frames_frozenset
        is_flagged_bool = frame_int in flagged_frames_frozenset
        if is_exposed_bool and is_flagged_bool:
            true_positive_int += 1
        elif is_exposed_bool:
            false_negative_int += 1
        elif is_flagged_bool:
            false_positive_int += 1
        else:
            true_negative_int += 1

    return ConfusionCounts(
        true_positive_int=true_positive_int,
        false_negative_int=false_negative_int,
        false_positive_int=false_positive_int,
        true_negative_int=true_negative_int,
    )


@dataclass(frozen=True, slots=True)
class ScoredSequence:
    """One sequence's per-frame scores and its ground truth.

    Attributes:
        scenario_name_str: Family the sequence belongs to.
        scores_list: One exposure score per frame, in frame order.
        exposed_frames_frozenset: Frames truly left exposed.
    """

    scenario_name_str: str
    scores_list: list[float]
    exposed_frames_frozenset: frozenset[int]


def choose_oracle_threshold(
    scored_sequences_list: list[ScoredSequence],
) -> float:
    """Return the threshold maximizing balanced accuracy over the set.

    A frame is flagged when its score is greater than or equal to the
    threshold. Candidate thresholds are the observed scores themselves,
    which is sufficient because the decision only changes at one of them.

    Args:
        scored_sequences_list: Every scored sequence.

    Returns:
        The best threshold found, or infinity when there are no scores,
        which flags nothing.
    """

    candidate_thresholds_list = sorted(
        {
            score_float
            for sequence_obj in scored_sequences_list
            for score_float in sequence_obj.scores_list
        }
    )
    if len(candidate_thresholds_list) < MINIMUM_SCORE_COUNT_INT:
        return float("inf")

    best_threshold_float = candidate_thresholds_list[0]
    best_accuracy_float = -1.0

    for threshold_float in candidate_thresholds_list:
        counts_obj = _count_at_threshold(
            scored_sequences_list, threshold_float
        )
        accuracy_float = counts_obj.balanced_accuracy
        if accuracy_float > best_accuracy_float:
            best_accuracy_float = accuracy_float
            best_threshold_float = threshold_float

    return best_threshold_float


def _count_at_threshold(
    scored_sequences_list: list[ScoredSequence],
    threshold_float: float,
) -> ConfusionCounts:
    """Return outcome counts for one threshold across every sequence.

    Args:
        scored_sequences_list: Every scored sequence.
        threshold_float: Score at or above which a frame is flagged.

    Returns:
        The combined counts.
    """

    total_counts_obj = ConfusionCounts()
    for sequence_obj in scored_sequences_list:
        total_counts_obj = total_counts_obj.combined_with(
            count_outcomes(
                flagged_frames_at(sequence_obj, threshold_float),
                sequence_obj.exposed_frames_frozenset,
                len(sequence_obj.scores_list),
            )
        )
    return total_counts_obj


def flagged_frames_at(
    sequence_obj: ScoredSequence,
    threshold_float: float,
) -> frozenset[int]:
    """Return the frames one threshold flags in one sequence.

    Args:
        sequence_obj: Scored sequence.
        threshold_float: Score at or above which a frame is flagged.

    Returns:
        One-based frame numbers the threshold flags.
    """

    return frozenset(
        frame_index_int + 1
        for frame_index_int, score_float in enumerate(sequence_obj.scores_list)
        if score_float >= threshold_float
    )
