# Visual Verifier

**Reference-based quality assurance for processed images and videos.**

Visual Verifier compares original media with a processed candidate and
returns deterministic PASS/FAIL results, measurements, and reviewable
evidence. It is a checker, not an image or video processor.

## Current status

Visual Verifier is a pre-alpha package at version `0.1.0a0`. The active
implementation currently supports:

- Image-to-image verification
- Synchronized video frame comparison
- Multiple changed-region detection
- Region filtering and severity scoring
- Annotated image and video evidence
- CSV and JSON reports
- A typed Python API
- A command-line interface suitable for CI
- A fixed three-video regression fixture

The active package does **not** yet provide selectable policy objects,
temporal tracking, target CSV validation, automatic target detection,
batch execution, alignment, or a pytest plugin. Historical versions of
some of those capabilities are preserved under `archive/legacy_cells/`
for future extraction and validation.

## Verification contract

```text
Reference media
+ Candidate processed media
+ Detection configuration
= PASS/FAIL + measurements + evidence
```

The current image rule passes when at least one accepted changed region is
detected, unless processing is explicitly optional.

The current video rule passes when every synchronized frame contains at
least one accepted changed region, unless unprocessed frames are explicitly
allowed.

These rules are intentionally generic. They do not prove that a specific
face, licence plate, or private object was anonymized.

## Installation with uv

Requirements:

- Python 3.10 or newer
- `uv`

On Windows PowerShell:

```powershell
git clone <repository-url>
Set-Location visual-verifier

Set-ExecutionPolicy `
    -Scope Process `
    -ExecutionPolicy Bypass `
    -Force

Unblock-File .\scripts\bootstrap_uv.ps1
.\scripts\bootstrap_uv.ps1
```

The bootstrap script installs or selects Python 3.12, synchronizes the
environment, checks dependencies, formats the repository, runs Ruff and
Mypy, and executes the test suite.

## Python API

### Verify an image

```python
from visual_verifier import verify_image

result = verify_image(
    reference="reference.png",
    candidate="processed.png",
    output_dir="outputs/image_check",
)

print(result.status.value)
print(result.measurements)
result.raise_for_failure()
```

### Verify a video

```python
from visual_verifier import verify_video

result = verify_video(
    reference="examples/media/video_raw.mp4",
    candidate="examples/media/video_blur_partial.mp4",
    output_dir="outputs/video_check",
)

print(result.status.value)
print(result.failed_frames)
```

To permit frames without detected processing:

```python
result = verify_video(
    reference="reference.mp4",
    candidate="candidate.mp4",
    output_dir="outputs/video_check",
    expect_processing_every_frame=False,
)
```

### Configure detection thresholds

```python
from visual_verifier import verify_image
from visual_verifier.config import DetectionConfig

config = DetectionConfig(
    diff_threshold=30,
    min_box_area=80,
    min_changed_ratio=0.03,
    min_mean_diff=5.0,
    min_severity_score=8.0,
)

result = verify_image(
    reference="reference.png",
    candidate="candidate.png",
    config=config,
)
```

## Command-line interface

Check the environment:

```powershell
uv run visual-verifier doctor
```

Inspect media metadata:

```powershell
uv run visual-verifier inspect `
    examples\media\video_raw.mp4
```

Verify an image:

```powershell
uv run visual-verifier image `
    --reference reference.png `
    --candidate processed.png `
    --output outputs\image_check
```

Verify a video:

```powershell
uv run visual-verifier video `
    --reference examples\media\video_raw.mp4 `
    --candidate examples\media\video_blur_partial.mp4 `
    --output outputs\video_check
```

CLI exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | Verification completed and passed |
| `1` | Verification could not be completed |
| `2` | Verification completed and failed |

## Evidence outputs

Image verification can write:

```text
annotated_image.png
region_report.csv
summary.json
```

Video verification can write:

```text
annotated_video.mp4
frame_report.csv
region_report.csv
rejected_region_report.csv
summary.json
```

See `docs/output_schema.md` for the field-level contract.

## Regression fixture

The repository includes three 15-frame example videos:

```text
examples/media/video_raw.mp4
examples/media/video_blur.mp4
examples/media/video_blur_partial.mp4
```

Expected results:

| Comparison | Expected status | Failed frames |
| --- | --- | --- |
| Raw vs. fully blurred | `PASS` | None |
| Raw vs. partially blurred | `FAIL` | `4, 8, 12` |

## Repository layout

```text
src/visual_verifier/     Active package
tests/                   Unit and regression tests
examples/                Reproducible media fixtures
docs/                    Architecture and behavior documentation
scripts/                 Bootstrap, quality, cleanup, release checks
archive/legacy_cells/    Read-only historical prototypes
```

`archive/legacy_cells/` is not imported by the active package and must not
be edited during normal development.

## Development checks

```powershell
.\scripts\run_quality.ps1
```

Equivalent commands:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src --python-version 3.12
uv run pytest -q
```

## Limitations and safety

Visual Verifier is an engineering QA tool. It is not a regulatory
certification system, a guaranteed anonymization detector, or a substitute
for human review in high-risk privacy or safety workflows.

Read:

- `docs/limitations.md`
- `docs/verification_contract.md`
- `SECURITY.md`

## Roadmap

The next major work is validated extraction of temporal tracking,
target-aware verification, selectable policies, and batch execution from
the historical prototypes. See `ROADMAP.md`.

## Licence and citation

Visual Verifier is licensed under the Apache License 2.0.

Citation metadata is available in `CITATION.cff`.
