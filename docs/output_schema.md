# Output Schema

Output schemas remain pre-alpha and may evolve before a stable release.

## Console output

`visual-verifier image` and `visual-verifier video` print a readable
summary by default. Sections with no content are omitted, so a clean pass
prints only the status header.

The summary is for humans and is **not** a stable interface. Anything that
parses results must use `--json`, which prints the same document written to
`summary.json`, or read the CSV reports.

Errors are printed on standard error as `ERROR [CODE]: message`, followed
by indented diagnostic context. The bracketed code is stable and matches
the `error_code` of the raised exception, for example `MEDIA_READ_ERROR`,
`CONFIGURATION_ERROR`, or `REPORT_WRITE_ERROR`.

## `summary.json`

The top-level verification document includes status, paths, policy failures,
failed frames, measurements, and generated evidence paths.

`evidence_paths` names every file written beside `summary.json`, including
`html_report`, so a machine consumer can discover the whole evidence set
from the one document it already reads.

When tracking is enabled, `measurements.tracking` contains:

- `config`
- `track_count`
- `observation_count`
- `event_count`
- `tracks_with_gaps`
- `mean_continuity_ratio`
- `track_summaries`

## `index.html`

A self-contained HTML evidence report written beside the machine-readable
files. It carries a status banner, headline measurements, a frame timeline
in which every unprotected frame links to its own evidence card, a
before/after wipe comparison for each captured failing frame, the tracked
region table, and the command that reproduces the run.

Three properties are part of its contract and are enforced by tests:

- **Self-contained.** It references no CDN, web font, or linked image.
  Thumbnails are embedded as base64 JPEG data URIs, so the file can be
  attached to a ticket and opened offline, and opening it cannot signal to
  anyone that the report exists.
- **Deterministic.** It carries no timestamp and no generated identifiers,
  so two runs over the same media produce identical documents.
- **Bounded.** Only failing frames are captured, up to 24 of them. A long
  video does not produce an unopenable file.

The rendered text is for humans and is not a stable interface. Parse
`summary.json` or the CSV reports instead.

## Target evidence

Written only when `--targets` is supplied.

`target_report.csv`
: One row per target per frame, carrying the box, `target_type`,
`source`, `required`, the measured `covered_ratio`, whether it counted as
`covered`, how many accepted regions contributed, and whether it is a
failure.

`measurements.targets` in `summary.json` contains:

- `config`
- `target_count`
- `target_frame_count`
- `covered_target_frame_count`
- `uncovered_target_frame_count`
- `interpolated_frame_count`
- `target_coverage_percent`
- `target_summaries`

Each entry of `target_summaries` carries `target_id`, `target_type`,
`first_frame`, `last_frame`, `frame_count`, `covered_frame_count`,
`uncovered_frames`, `coverage_ratio`, `mean_covered_ratio`,
`interpolated_frame_count`, and `required`.

`measurements.targets_enabled` is always present and is `false` when no
targets were supplied.

Supplying targets changes `policy_name` from `generic_change_every_frame`
to `target_coverage_every_frame`, and adds an `UNCOVERED_TARGETS` failure
alongside the existing `UNPROCESSED_FRAMES` one. The two are reported
separately so a reviewer can tell a skipped frame from a frame that was
processed in the wrong place. See
[Target annotation](target_annotation.md).

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

## Example contract

`examples/expected/demo_expectations.json` declares the status, failed
frames, and processing coverage of both bundled comparisons.
`tests/test_demo_contract.py` executes it, so the published example results
in this repository are measured rather than asserted by hand.

## Compatibility rule

New optional fields may be added during pre-alpha development. Removing or
renaming fields requires a changelog entry and regression-test updates.
