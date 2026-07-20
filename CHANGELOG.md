# Changelog

All notable changes to Visual Verifier are documented here.

## [Unreleased]

### Planned

- Reviewed target annotations and target-level temporal coverage
- Target continuity and required-object failure policies
- Batch verification and aggregate reports
- Alignment and synchronization diagnostics

## [0.2.0a0] - 2026-07-21

### Added

- Deterministic one-to-one IoU association
- Tentative, confirmed, lost, recovered, and closed lifecycle states
- Configurable confirmation and short-gap tolerance
- Monotonic non-reused track and event IDs
- Split and merge lineage evidence using overlap coefficients
- Continuity, fragmentation, association, motion, and stability metrics
- `track_report.csv`
- `track_observation_report.csv`
- `track_event_report.csv`
- Persistent track labels in annotated video
- Public `TrackingConfig`
- Python API and CLI tracking controls
- Dedicated temporal tracking documentation
- V5.2 unit and example-video regression tests
- V5.2 release-validation script

### Changed

- Video verification enables temporal tracking evidence by default
- Package version advanced to `0.2.0a0`
- Video evidence sets now include three temporal CSV reports
- Package and release validation inspect active tracking modules

### Preserved

- Raw vs. fully blurred video remains `PASS`
- Raw vs. partially blurred video remains `FAIL`
- Failed frames remain exactly `4`, `8`, and `12`
- Tracking does not change the frame-level policy decision

## [0.1.0a0] - 2026-07-20

### Added

- Typed image and video verification APIs
- Multi-region detection, filtering, severity, reports, and annotations
- CLI, quality scripts, package typing, and 23-test V5.1b foundation
