# Output Schema

Output schemas remain pre-alpha and may evolve before a stable release.

## `summary.json`

The top-level verification document includes status, paths, policy failures,
failed frames, measurements, and generated evidence paths.

When tracking is enabled, `measurements.tracking` contains:

- `config`
- `track_count`
- `observation_count`
- `event_count`
- `tracks_with_gaps`
- `mean_continuity_ratio`
- `track_summaries`

## Frame and region evidence

`frame_report.csv`
: One row per synchronized frame.

`region_report.csv`
: One row per accepted region.

`rejected_region_report.csv`
: One row per rejected region and rejection reasons.

## Temporal evidence

`track_report.csv`
: One row per completed track with lifecycle, continuity, fragmentation,
association, severity, motion, stability, recovery, split, and merge metrics.

`track_observation_report.csv`
: One row per observed region-to-track assignment, including frame, timestamp,
box, severity, lifecycle state, and association IoU.

`track_event_report.csv`
: One row per lifecycle or lineage event, including primary and related track
identities, frame number, gap length, and explanation.

`annotated_video.mp4`
: Candidate video with persistent track labels such as `T001`; tentative labels
include `?`.

## Compatibility rule

New optional fields may be added during pre-alpha development. Removing or
renaming fields requires a changelog entry and regression-test updates.
