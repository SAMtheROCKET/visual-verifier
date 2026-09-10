# Command line

```text
visual-verifier [--version] <command> [options]
```

Every option listed here is checked against the real argument parser by
`tests/test_documentation_coverage.py`, so this page cannot drift from the
installed program.

| Command | Purpose |
| --- | --- |
| [`doctor`](#doctor) | Check the local environment and codec support |
| [`demo`](#demo) | Generate a sample failure and verify it |
| [`inspect`](#inspect) | Print normalized metadata for one media file |
| [`image`](#image) | Verify one processed image |
| [`video`](#video) | Verify one processed video with temporal tracking |

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | Verification completed and passed |
| `1` | Verification could not be completed |
| `2` | Verification completed and failed |

Errors are printed on standard error as `ERROR [CODE]: message`, followed
by indented diagnostic context. The bracketed code is stable and matches
the raised exception, for example `MEDIA_READ_ERROR`,
`CONFIGURATION_ERROR`, or `REPORT_WRITE_ERROR`.

## Global options

| Option | Description |
| --- | --- |
| `--version` | Print the installed version and exit |
| `-h`, `--help` | Show help for the program or a command |

## doctor

Prints the installed version, Python, platform, OpenCV, NumPy, and pandas
versions, and probes whether this OpenCV build can write annotated video.

```bash
visual-verifier doctor
```

Reports `Environment status: OK`, or `DEGRADED` when no video codec is
available. Degraded is not a failure: verification never needs an encoder,
only annotated video evidence does. The command always exits `0`.

## demo

Generates a synthetic clip in which a licence plate is blurred on every
frame except three, verifies it, and writes the full evidence set.

```bash
visual-verifier demo [--output DIR]
```

| Option | Default | Description |
| --- | --- | --- |
| `--output DIR` | `./visual-verifier-demo` | Directory for the sample media and evidence |

Nothing is downloaded. Exits `0` when the demonstration reproduces its
documented result, and `1` if it does not.

## inspect

```bash
visual-verifier inspect <path>
```

Prints normalized metadata as JSON. The file type is chosen from the
filename suffix; `.mp4`, `.avi`, `.mov`, `.mkv`, and `.webm` are read as
video, and anything else as an image.

## image

```bash
visual-verifier image --reference PATH --candidate PATH [options]
```

| Option | Default | Description |
| --- | --- | --- |
| `--reference PATH` | required | Original, unprocessed reference image |
| `--candidate PATH` | required | Processed candidate image to verify |
| `--output DIR` | none | Directory for reports and annotated evidence |
| `--allow-no-processing` | off | Pass even when no accepted changed region is found |

Plus the [shared options](#shared-options) below.

## video

```bash
visual-verifier video --reference PATH --candidate PATH [options]
```

| Option | Default | Description |
| --- | --- | --- |
| `--reference PATH` | required | Original, unprocessed reference video |
| `--candidate PATH` | required | Processed candidate video to verify |
| `--output DIR` | none | Directory for reports and annotated evidence |
| `--allow-unprocessed-frames` | off | Pass even when some frames contain no accepted region |
| `--no-annotated-video` | off | Skip writing `annotated_video.mp4` |
| `--no-html-report` | off | Skip writing the self-contained `index.html` |
| `--no-tracking` | off | Skip temporal tracking; frame PASS/FAIL is unchanged |

### Temporal tracking options

| Option | Default | Description |
| --- | --- | --- |
| `--tracking-iou FLOAT` | `0.2` | Minimum IoU to associate a region with an active track |
| `--tracking-confirmation-hits INT` | `2` | Observations before a tentative track is confirmed |
| `--tracking-max-gap INT` | `3` | Consecutive missing frames tolerated before a track closes |
| `--lineage-overlap FLOAT` | `0.2` | Minimum overlap used to detect split and merge events |
| `--no-lineage-events` | off | Keep tracking but omit split and merge evidence |

See [Temporal tracking](temporal_tracking.md) for what each metric means.

### Target options

Supplying targets changes the question from *did anything change* to
*did the required region change*, so unlike tracking these options can
change the verdict.

| Option | Default | Description |
| --- | --- | --- |
| `--targets PATH` | none | Reviewed target CSV naming regions that must be anonymized |
| `--target-min-coverage FLOAT` | `0.9` | Fraction of a target accepted processing must cover |
| `--target-max-gap INT` | `5` | Longest run of missing frames interpolated between reviewed boxes |
| `--no-target-interpolation` | off | Check only reviewed frames, interpolating nothing |
| `--allow-uncovered-targets` | off | Record target coverage as evidence without failing the run |

See [Target annotation](target_annotation.md) for the file format.

## Shared options

Available on both `image` and `video`.

### Output format

| Option | Description |
| --- | --- |
| `--json` | Print the full machine-readable result as JSON |
| `-q`, `--quiet` | Suppress standard output and report only through the exit code |

The default output is a readable summary for humans and is **not** a stable
interface. Anything that parses results must use `--json`, which prints the
same document written to `summary.json`.

### Detection thresholds

| Option | Default | Description |
| --- | --- | --- |
| `--diff-threshold INT` | `30` | Absolute per-pixel difference required to mark a pixel changed |
| `--min-box-area INT` | `80` | Smallest accepted region area in pixels |
| `--min-changed-ratio FLOAT` | `0.03` | Smallest accepted changed-pixel ratio inside a region |
| `--min-mean-diff FLOAT` | `5.0` | Smallest accepted mean intensity difference inside a region |
| `--min-severity FLOAT` | `8.0` | Smallest accepted region severity score, from 0 to 100 |

Defaults come from the shipped `DetectionConfig`, so the help output and
the Python defaults cannot disagree. Every value used in a run is recorded
in `summary.json`.

Lowering thresholds detects weaker processing but admits more noise, since
compression and sensor noise also change pixels. See
[Anonymization QA](anonymization_qa.md#tuning-for-weak-or-subtle-processing).

## Examples

```bash
# Environment check, including codec support
visual-verifier doctor

# See a real failure without supplying any media
visual-verifier demo

# Verify, write full evidence, and fail the build on a gap
visual-verifier video \
    --reference raw.mp4 \
    --candidate anonymized.mp4 \
    --output artifacts/verification

# Machine-readable output only
visual-verifier video --reference raw.mp4 --candidate out.mp4 --json

# Fast check with no evidence written at all
visual-verifier video --reference raw.mp4 --candidate out.mp4 --quiet
```
