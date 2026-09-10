# Getting started

## Install

Requires Python 3.10 or newer.

```bash
pip install visual-verifier
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install visual-verifier      # as a standalone CLI
uv add visual-verifier               # as a project dependency
```

Confirm the environment before you trust a result:

```bash
visual-verifier doctor
```

```text
Visual Verifier environment check
========================================
Visual Verifier: 0.2.0
Python:          3.12.13
Platform:        Windows-11-10.0.26200-SP0
OpenCV:          5.0.0
NumPy:           2.5.1
pandas:          3.0.3
Video codec:     mp4v

Environment status: OK
```

`Video codec` is the only host-dependent capability. If it reports
`unavailable`, verification still works — only annotated video evidence
cannot be written, and the status reads `DEGRADED` instead of `OK`.

## See a real failure in 60 seconds

```bash
visual-verifier demo
```

This generates a short sample clip in which a licence plate is blurred on
every frame **except three**, verifies it, and writes the full evidence
set. Nothing is downloaded; the sample is synthesized on your machine.

```text
Status:                    FAIL
Frames checked:            15
Frames with processing:    12
Frames without processing: 3
Processing coverage:       80.0%

Failures
--------
UNPROCESSED_FRAMES: No accepted processing was detected in frames [4, 8, 12].
Failed frames:             4, 8, 12
```

Open `visual-verifier-demo/report/index.html` in any browser. That is the
report you would send a colleague: a frame timeline, a before/after wipe
slider on each unprotected frame, and the tracked-region table.

## Verify your own media

```bash
visual-verifier video \
    --reference raw.mp4 \
    --candidate anonymized.mp4 \
    --output outputs/check
```

The two inputs must be the **same footage**: same frames, same order, same
timing. Visual Verifier compares them; it does not align them. See
[Limitations](limitations.md).

| Exit code | Meaning |
| ---: | --- |
| `0` | Verification completed and passed |
| `1` | Verification could not be completed |
| `2` | Verification completed and failed |

## What you get

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

`summary.json` names every file above in its `evidence_paths` field, so a
script only has to read one document to find the rest.

## Next steps

- [Anonymization QA](anonymization_qa.md) — the flagship use case, and what
  a `PASS` does and does not prove
- [Use it in CI](ci.md) — fail a build on an anonymization gap
- [Command line](cli.md) and [Python API](python_api.md) — every option
- [Limitations](limitations.md) — read this before relying on a `PASS`
