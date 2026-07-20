# Temporal Tracking and Integrity Intelligence

## Purpose

V5.2 converts independent accepted regions into persistent temporal entities.
The tracker explains whether detected processing remains continuous, briefly
disappears, recovers, splits, or merges across synchronized frames.

Tracking remains evidence-only. Frame-level PASS/FAIL decisions continue to
use the established processing-presence rule.

## Association

For each frame, the tracker calculates IoU between active track boxes and
accepted current detections. Candidate pairs below the configured threshold
are rejected. Remaining pairs are sorted by:

1. Highest IoU
2. Lowest track ID
3. Lowest detection index

Pairs are greedily accepted while enforcing one track and one detection per
match. This ordering makes the result deterministic across platforms.

## Lifecycle

```text
TENTATIVE
    | enough observations
    v
CONFIRMED
    | missing observation
    v
LOST
    | matched within tolerance
    +--------------------> CONFIRMED
    |
    | gap exceeds tolerance
    v
CLOSED
```

Track IDs are monotonically allocated as `T001`, `T002`, and so on. IDs are
never reused within one verification run.

Default settings preserve historical parity:

```text
association_iou_threshold = 0.20
minimum_confirmation_hits = 2
maximum_gap_frames = 3
lineage_overlap_threshold = 0.20
```

## Lineage evidence

Split and merge candidates use the overlap coefficient: intersection area
divided by the smaller box area. This is more suitable than IoU when one box
becomes multiple smaller boxes or several boxes become one larger box.

Events include:

- `TRACK_CREATED`
- `TRACK_CONFIRMED`
- `TRACK_LOST`
- `TRACK_RECOVERED`
- `TRACK_CLOSED`
- `TRACK_SPLIT`
- `TRACK_MERGED`

Repeated split or merge signatures are suppressed within one run.

## Integrity metrics

For every track, V5.2 reports:

- First and last observed frames
- Observation count and active span
- Missing frame list
- Gap count and longest consecutive gap
- Continuity ratio
- Fragmentation index
- Mean and minimum association IoU
- Mean and maximum severity
- Mean changed-pixel ratio
- Mean region area
- Center jitter in pixels
- Minimum-to-maximum area stability ratio
- Recovery count
- Split and merge event involvement

### Continuity ratio

```text
observation_count / active_span_frames
```

### Fragmentation index

```text
gap_count / max(observation_count - 1, 1)
```

### Area stability ratio

```text
minimum_observed_area / maximum_observed_area
```

## Interpretation

A continuous track indicates persistent detected processing. It does not prove
that the same semantic object was processed. Low IoU, high center jitter, low
area stability, or repeated gaps should be treated as review signals rather
than automatic policy failures in V5.2.
