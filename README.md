# Visual Verifier

[![PyPI](https://img.shields.io/pypi/v/visual-verifier)](https://pypi.org/project/visual-verifier/)
[![Docs](https://img.shields.io/badge/docs-samtherocket.github.io-teal)](https://samtherocket.github.io/visual-verifier/)
[![Quality](https://github.com/SAMtheROCKET/visual-verifier/actions/workflows/quality.yml/badge.svg)](https://github.com/SAMtheROCKET/visual-verifier/actions/workflows/quality.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict%20typed-blue)](https://mypy-lang.org/)
[![Linted with Ruff](https://img.shields.io/badge/ruff-passing-brightgreen)](https://docs.astral.sh/ruff/)

### Anonymization QA for images and videos

**Test blur, redaction, masking, and other visual processing frame by
frame.** Get a deterministic PASS/FAIL, temporal evidence, and CI-ready
reports.

🔒 **Runs entirely on your machine. Your media is never uploaded** — the
package has no network dependency at all, and
[a test enforces it](tests/test_local_execution.py) on every commit.

```bash
pip install visual-verifier
visual-verifier demo
```

<p align="center">
  <img src="https://raw.githubusercontent.com/SAMtheROCKET/visual-verifier/main/docs/assets/pass_fail_comparison.png"
       alt="The same licence plate one frame apart: frame 3 blurred and passing, frame 4 readable and failing"
       width="720">
</p>

```text
FAIL
Frames missed: 4, 8, 12
```

---

## The problem

Your anonymizer says the video passed. Frame 4 still exposes the licence
plate.

A blur, redaction, or masking pipeline reports success. Three frames out of
fifteen were silently skipped. A global image metric averages the failure
away. Manual frame review does not scale and does not reproduce.

Visual Verifier finds the frames your privacy pipeline missed, and answers
one narrow question with evidence you can attach to a build:

> Did the expected visual processing occur, in every frame, and can I catch
> it in CI when it does not?

### Anonymization is the named use case, not the limit

The engine is a general **pixel-level change verifier**. It measures what
actually changed between a reference and a candidate — region by region,
frame by frame — so anything that alters pixels can be verified the same
way:

| Use it for | What a `FAIL` means |
| --- | --- |
| Blur, pixelation, redaction, masking | A frame was left unprotected |
| Watermark and overlay application | The mark is missing or too faint |
| Encoding, transcoding, filter chains | A stage silently did nothing |
| Compositing, inpainting, style transfer | The edit did not land everywhere |
| Any processed-media regression test | Output drifted from the reference |

Privacy work is where the failure is most expensive, so it is what the
documentation leads with. The verification contract itself makes no
assumption about *why* the pixels changed.

## What it looks like

Fifteen dashcam frames. A licence-plate blur that silently skipped three of
them. Watch the verdict flip on frames 4, 8, and 12:

<p align="center">
  <img src="https://raw.githubusercontent.com/SAMtheROCKET/visual-verifier/main/docs/assets/verification_demo.gif"
       alt="Animated verification of 15 frames, failing on frames 4, 8 and 12"
       width="640">
</p>

The same run on the command line:

```console
$ visual-verifier video \
    --reference examples/media/video_raw.mp4 \
    --candidate examples/media/video_blur_partial.mp4 \
    --output outputs/partial_check

Visual Verifier result
======================
Status:                    FAIL
Policy:                    generic_change_every_frame
Reference:                 examples/media/video_raw.mp4
Candidate:                 examples/media/video_blur_partial.mp4

Measurements
------------
Frames checked:            15
Frames with processing:    12
Frames without processing: 3
Processing coverage:       80.0%
Accepted regions:          32
Rejected regions:          0

Temporal tracking
-----------------
Tracks:                    15
Track observations:        32
Track events:              53
Tracks with gaps:          1
Mean continuity ratio:     0.986667

Failures
--------
UNPROCESSED_FRAMES: No accepted processing was detected in frames [4, 8, 12].
Failed frames:             4, 8, 12

Evidence
--------
annotated_video:           outputs/partial_check/annotated_video.mp4
frame_report:              outputs/partial_check/frame_report.csv
html_report:               outputs/partial_check/index.html
region_report:             outputs/partial_check/region_report.csv
rejected_region_report:    outputs/partial_check/rejected_region_report.csv
summary_json:              outputs/partial_check/summary.json
track_event_report:        outputs/partial_check/track_event_report.csv
track_observation_report:  outputs/partial_check/track_observation_report.csv
track_report:              outputs/partial_check/track_report.csv

$ echo $?
2
```

Frames `4`, `8`, and `12` were never blurred. The exit code fails the build,
the CSV reports say exactly where, and `annotated_video.mp4` shows a reviewer
the same thing in ten seconds.

## Install

Requires Python 3.10 or newer.

```bash
pip install visual-verifier
visual-verifier doctor
```

Or with `uv`:

```bash
uv tool install visual-verifier      # as a standalone CLI
uv add visual-verifier               # as a project dependency
```

To work on Visual Verifier itself, clone and run `uv sync`. On Windows
PowerShell a bootstrap script sets the same environment up:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Unblock-File ./scripts/bootstrap_uv.ps1
./scripts/bootstrap_uv.ps1
```

`visual-verifier doctor` reports your Python, OpenCV, and codec support, so
you can confirm the environment before trusting a result.

## Quick start

No clone, no fixtures to download, no media of your own required:

```bash
visual-verifier demo
```

That generates a short sample clip in which a licence plate is blurred on
every frame except three, verifies it, writes the full evidence set to
`./visual-verifier-demo/report/`, and prints the exact command to reproduce
it. The sample is synthesized locally, so nothing is fetched.

Then point it at your own media:

```bash
visual-verifier video \
    --reference raw.mp4 \
    --candidate anonymized.mp4 \
    --output outputs/check
```

Add `--json` for a machine-readable document, `--quiet` to report only
through the exit code, and `visual-verifier video --help` for every
threshold.

## Use it in CI

On GitHub, the bundled action installs the tool, runs the comparison,
writes a job summary, and uploads the evidence:

```yaml
- name: Verify anonymization coverage
  uses: SAMtheROCKET/visual-verifier@v0.2.0
  with:
    reference: fixtures/source.mp4
    candidate: build/anonymized.mp4
```

The summary names the failing frames, draws a frame timeline, and links
the evidence artifact, so a reviewer sees the answer without downloading
anything. [`docs/github_action.md`](docs/github_action.md) lists every
input and output.

Everywhere else the exit code is the contract, so no wrapper is required:

```yaml
- name: Verify anonymization coverage
  run: |
    visual-verifier video \
      --reference fixtures/source.mp4 \
      --candidate build/anonymized.mp4 \
      --output artifacts/verification \
      --quiet
```

| Exit code | Meaning |
| ---: | --- |
| `0` | Verification completed and passed |
| `1` | Verification could not be completed |
| `2` | Verification completed and failed |

Errors print a stable machine-greppable code, for example
`ERROR [MEDIA_READ_ERROR]`, so a failing build tells you whether the media was
bad or the processing was.

## Python API

```python
from visual_verifier import TrackingConfig, verify_video

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

print(result.status.value)          # FAIL
print(result.failed_frames)         # (4, 8, 12)
print(result.measurements["tracking"]["track_count"])
```

Use it as a test assertion:

```python
def test_every_frame_is_anonymized() -> None:
    verify_video("source.mp4", "anonymized.mp4").raise_for_failure()
```

Disable tracking while preserving frame-level verification:

```python
result = verify_video("reference.mp4", "candidate.mp4", enable_tracking=False)
```

The package is fully typed and ships `py.typed`. Everything you need is
exported from the top level: `verify_image`, `verify_video`,
`DetectionConfig`, `TrackingConfig`, `VerificationResult`,
`VerificationStatus`, and the structured error hierarchy rooted at
`VisualVerifierError`.

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

The bundled regression fixture is enforced by
[`examples/expected/demo_expectations.json`](examples/expected/demo_expectations.json),
which the test suite executes on every run so the table below cannot drift:

| Comparison | Status | Failed frames |
| --- | --- | --- |
| Raw vs. fully blurred | `PASS` | None |
| Raw vs. partially blurred | `FAIL` | `4, 8, 12` |

## Evidence outputs

Video verification with tracking enabled writes:

```text
index.html                   Self-contained report you can email to a reviewer
annotated_video.mp4          Candidate with persistent track labels (T001)
frame_report.csv             One row per synchronized frame
region_report.csv            One row per accepted changed region
rejected_region_report.csv   One row per rejected region, with reasons
track_report.csv             One row per completed track
track_observation_report.csv One row per region-to-track assignment
track_event_report.csv       Lifecycle and split/merge lineage events
summary.json                 The complete machine-readable result
```

Every panel below is generated from a real run by
[`scripts/generate_readme_assets.py`](scripts/generate_readme_assets.py),
with the region boxes read back from `track_observation_report.csv`:

<p align="center">
  <img src="https://raw.githubusercontent.com/SAMtheROCKET/visual-verifier/main/docs/assets/missed_frame_closeup.png"
       alt="Frame 4 failing, with the tracked region highlighted and the plate readable in both reference and candidate"
       width="640">
</p>

### The report you actually send someone

`index.html` opens in any browser and needs no explanation of CSV schemas.
It shows the verdict, a frame timeline where every unprotected frame links
to its own evidence, and a before/after wipe slider for each failure.

It references **nothing external** — no CDN, no web font, no linked image.
Thumbnails are embedded, so it works offline, survives being attached to a
ticket, and opening it cannot signal to anyone that a privacy report
exists. It is also deterministic, so two runs over the same media produce
identical documents and can be diffed.

The primary temporal measures are continuity ratio, fragmentation index,
missing frames and longest gap, mean and minimum association IoU, center
jitter, area stability, recovery count, and split/merge involvement. See
[`docs/temporal_tracking.md`](docs/temporal_tracking.md) and
[`docs/output_schema.md`](docs/output_schema.md).

## Current release

Version `0.2.0` is the V5.2 milestone: **Temporal Tracking and Integrity
Intelligence**. The package is early software: the API and report schemas
may still change, and the trove classifier remains `Pre-Alpha`.

- Image-to-image and synchronized video verification
- Multiple changed-region detection, filtering, and severity scoring
- Deterministic IoU-based temporal association
- Tentative, confirmed, lost, recovered, and closed track lifecycles
- Configurable short-gap tolerance and split/merge lineage evidence
- Track continuity, fragmentation, stability, and recovery metrics
- Typed Python API and a self-documenting CLI
- Linux, macOS, and Windows CI across Python 3.10–3.13

Tracking is evidence-only in V5.2. It never silently changes the established
frame-level verification policy.

## What this is not

A tracking ID represents a persistent changed region — not a proven face,
licence plate, person, or other semantic object. V5.2 assumes synchronized
media and performs no motion prediction, appearance re-identification,
camera-motion compensation, or automatic temporal alignment.

Visual Verifier is an engineering QA tool. It is not a regulatory
certificate and not a guarantee of anonymization. Read
[`docs/limitations.md`](docs/limitations.md) before relying on a `PASS`.

## Documentation

**Full documentation: <https://samtherocket.github.io/visual-verifier/>**

| Document | Purpose |
| --- | --- |
| [`docs/problem_statement.md`](docs/problem_statement.md) | Why the tool exists and what it deliberately excludes |
| [`docs/verification_contract.md`](docs/verification_contract.md) | The formal input/output contract |
| [`docs/architecture.md`](docs/architecture.md) | Module boundaries and dependency direction |
| [`docs/temporal_tracking.md`](docs/temporal_tracking.md) | Association, lifecycle, lineage, and metrics |
| [`docs/github_action.md`](docs/github_action.md) | Every action input, output, and permission |
| [`docs/output_schema.md`](docs/output_schema.md) | Every report field |
| [`docs/limitations.md`](docs/limitations.md) | Known failure modes and honest scope |
| [`docs/use_cases.md`](docs/use_cases.md) | Suitable uses and unsupportable claims |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Development setup and review requirements |

## Development

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy src --python-version 3.12
uv run pytest -q --cov=visual_verifier
```

Or run the same gate in one step:

```bash
./scripts/run_quality.sh      # Linux and macOS
```

```powershell
./scripts/run_quality.ps1     # Windows
```

Before a release, the full V5.2 gate additionally checks the exact video
regressions, temporal report generation, CLI health, wheel contents, and
package building:

```powershell
./scripts/validate_v5_2.ps1
```

Function length, line length, docstrings, annotations, control characters in
documentation, and the agreement between the Git tag, the package version,
and `CITATION.cff` are all enforced by Ruff and the test suite rather than by
review.

## Repository layout

```text
src/visual_verifier/           Active package
src/visual_verifier/tracking/  Temporal association and integrity analysis
tests/                         Unit and end-to-end regressions
examples/media/                Reproducible 15-frame fixtures
examples/expected/             Executable demo contract
docs/                          Architecture and behavior documentation
scripts/                       Bootstrap, quality, cleanup, and release gates
action.yml                     Composite GitHub Action wrapping the CLI
archive/legacy_cells/          Read-only historical prototypes
```

## Roadmap

V5.3 adds reviewed target-aware verification and target continuity while
preserving V5.2 as the stable generic temporal layer. See
[`ROADMAP.md`](ROADMAP.md).

## Licence and citation

Visual Verifier is licensed under Apache-2.0. Citation metadata is provided in
[`CITATION.cff`](CITATION.cff).
