# Output Schema

Output schemas are pre-alpha and may change before a stable release.

## `summary.json`

The JSON document is produced from `VerificationResult.to_dict()` and
includes:

- `status`
- `passed`
- `errored`
- `reference_path`
- `candidate_path`
- `policy_name`
- `failures`
- `failed_frames`
- `measurements`
- `reference_metadata`
- `candidate_metadata`
- `frame_results`
- `evidence_paths`

Paths are serialized as strings.

## Image evidence

`annotated_image.png`
: Candidate image with accepted regions and the overall status.

`region_report.csv`
: One row per accepted or rejected region, including bounding-box geometry,
  difference metrics, sharpness metrics, severity, and rejection reasons.

## Video evidence

`annotated_video.mp4`
: Candidate frames with accepted-region overlays and frame status.

`frame_report.csv`
: One row per synchronized frame, including timestamp, status, accepted and
  rejected region counts, and failure state.

`region_report.csv`
: One row per accepted region.

`rejected_region_report.csv`
: One row per rejected region and its rejection reasons.

## Compatibility rule

New optional fields may be added during pre-alpha development. Renaming or
removing fields requires a changelog entry and regression-test updates.
