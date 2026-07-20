# Visual Verifier

**Reference-based quality assurance for processed images and videos.**

Visual Verifier compares original media with a processed candidate and returns
deterministic PASS/FAIL results, measurements, annotated evidence, and
machine-readable reports. It verifies processing; it does not perform the
processing itself.

## Current release

Version `0.2.0a0` is the V5.2 pre-alpha milestone: **Temporal Tracking and
Integrity Intelligence**.

The active package supports:

- Image-to-image verification
- Synchronized video frame comparison
- Multiple changed-region detection
- Region filtering and severity scoring
- Deterministic IoU-based temporal association
- Tentative, confirmed, lost, recovered, and closed track lifecycles
- Configurable short-gap tolerance
- Split and merge lineage evidence
- Track continuity, fragmentation, stability, and recovery metrics
- Persistent track labels in annotated video
- Frame, region, track, observation, event, and JSON reports
- Typed Python and command-line interfaces
- Linux and Windows CI

Tracking is evidence-only in V5.2. It does not silently change the established
frame-level verification policy.

## Verification contract

```text
Reference media
+ Candidate processed media
+ Detection configuration
+ Optional tracking configuration
= PASS/FAIL + measurements + temporal evidence
```

With processing required on every frame:

- `PASS`: every synchronized frame contains an accepted changed region.
- `FAIL`: one or more frames contain no accepted changed region.

The bundled regression fixture remains:

| Comparison | Status | Failed frames |
| --- | --- | --- |
| Raw vs. fully blurred | `PASS` | None |
| Raw vs. partially blurred | `FAIL` | `4, 8, 12` |

## Installation

Requirements:

- Python 3.10 or newer
- `uv`

```powershell
Set-ExecutionPolicy `
    -Scope Process `
    -ExecutionPolicy Bypass `
    -Force

Unblock-File .\scriptsootstrap_uv.ps1
.\scriptsootstrap_uv.ps1
```

## Python API

```python
from visual_verifier import verify_video
from visual_verifier.config import TrackingConfig

result = verify_video(
    reference="examples/media/video_raw.mp4",
    candidate="examples/media/video_blur_partial.mp4",
    output_dir="outputs/partial_check",
    tracking_config=TrackingConfig(
        association_iou_threshold=0.20,
        minimum_confirmation_hits=2,
        maximum_gap_frames=3,
        lineage_overlap_threshold=0.20,
    ),
)

print(result.status.value)
print(result.failed_frames)
print(result.measurements["tracking"])
```

Disable tracking while preserving frame-level verification:

```python
result = verify_video(
    reference="reference.mp4",
    candidate="candidate.mp4",
    enable_tracking=False,
)
```

## Command-line interface

```powershell
uv run visual-verifier video `
    --reference examples\mediaideo_raw.mp4 `
    --candidate examples\mediaideo_blur_partial.mp4 `
    --output outputs\partial_check `
    --tracking-iou 0.20 `
    --tracking-confirmation-hits 2 `
    --tracking-max-gap 3 `
    --lineage-overlap 0.20
```

Use `--no-tracking` to omit temporal analysis and `--no-lineage-events` to
retain tracking without split/merge evidence.

CLI exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | Verification completed and passed |
| `1` | Verification could not be completed |
| `2` | Verification completed and failed |

## Evidence outputs

Video verification with tracking enabled can write:

```text
annotated_video.mp4
frame_report.csv
region_report.csv
rejected_region_report.csv
track_report.csv
track_observation_report.csv
track_event_report.csv
summary.json
```

The primary temporal measures include:

- Continuity ratio
- Fragmentation index
- Missing frames and longest gap
- Mean and minimum association IoU
- Center jitter
- Area stability
- Recovery count
- Split and merge involvement

See `docs/temporal_tracking.md` and `docs/output_schema.md`.

## Development and validation

```powershell
.\scriptsalidate_v5_2.ps1
```

The V5.2 gate checks formatting, linting, typing, all tests, the exact video
regressions, temporal report generation, CLI health, and package building.

## Repository layout

```text
src/visual_verifier/     Active package
src/visual_verifier/tracking/
                         Temporal association and integrity analysis
tests/                   Unit and end-to-end regressions
examples/media/          Reproducible 15-frame fixtures
docs/                    Architecture and behavior documentation
scripts/                 Bootstrap, quality, cleanup, and release gates
archive/legacy_cells/    Read-only historical prototypes
```

## Limitations

A tracking ID represents a persistent changed region, not a proven face,
licence plate, person, or other semantic object. V5.2 assumes synchronized
media and does not perform motion prediction, appearance re-identification,
camera-motion compensation, or automatic temporal alignment.

Visual Verifier is an engineering QA tool, not a regulatory certificate or a
guarantee of anonymization.

## Roadmap

V5.3 will add reviewed target-aware verification and target continuity while
preserving V5.2 as the stable generic temporal layer. See `ROADMAP.md`.

## Licence and citation

Visual Verifier is licensed under Apache-2.0. Citation metadata is provided in
`CITATION.cff`.
