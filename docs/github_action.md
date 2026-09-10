# GitHub Action

Add anonymization QA to a pull request in three lines. The action
installs Visual Verifier, runs the comparison, publishes a job summary
naming the failing frames, and uploads the evidence.

```yaml
- name: Verify anonymization coverage
  uses: SAMtheROCKET/visual-verifier@v0.3.0
  with:
    reference: fixtures/source.mp4
    candidate: build/anonymized.mp4
```

The job fails when any frame is left unprotected, so a pipeline that
silently skips a frame cannot merge.

## What the summary looks like

```text
❌ Visual Verifier — FAIL

3 of 15 frames failed. Cause: no accepted processing.

| Measurement         | Value                      |
| Policy              | generic_change_every_frame |
| Frames checked      | 15                         |
| Processing coverage | 80.0%                      |
| Frames unprotected  | 3                          |
| Failed frames       | 4, 8, 12                   |

Frame timeline
🟢🟢🟢🔴🟢🟢🟢🔴🟢🟢🟢🔴🟢🟢🟢
```

The timeline buckets itself on long videos, so a feature-length clip
still renders as a readable strip rather than thousands of cells. A
collapsed section lists tracked regions with their continuity, gaps, and
recoveries.

Reviewers who want more open `index.html` from the uploaded artifact,
which carries a before/after comparison of every unprotected frame.

## Pin the action

Verification thresholds are part of the result, so tracking a moving
branch would let a release change a verdict without any change to your
repository. Pin a tag:

```yaml
uses: SAMtheROCKET/visual-verifier@v0.3.0
```

Pinning the tag pins the verifier too. The `requirement` input defaults
to the exact package version each action tag was released with, so
`@v0.3.0` installs `visual-verifier==0.3.0` and keeps installing it a
year from now. Override `requirement` only when you deliberately want to
test a different version.

## Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `reference` | required | Original, unprocessed media |
| `candidate` | required | Processed media being verified |
| `mode` | `video` | `video` or `image` comparison |
| `output` | `visual-verifier-evidence` | Evidence directory |
| `options` | empty | Extra CLI options passed verbatim |
| `requirement` | `visual-verifier==0.3.0` | Pip requirement to install |
| `python-version` | `3.12` | Empty uses the runner interpreter |
| `targets` | empty | Reviewed target CSV of regions that must be anonymized |
| `target-min-coverage` | `0.9` | Fraction of a target processing must cover |
| `allow-uncovered-targets` | `false` | Record target coverage without gating |
| `fail-on-gap` | `true` | Fail the job on unprotected frames |
| `upload-evidence` | `true` | Upload the evidence as an artifact |
| `artifact-name` | `visual-verifier-evidence` | Artifact name |
| `comment-on-pull-request` | `false` | Post the summary as a comment |
| `github-token` | `github.token` | Token used to post that comment |

`options` is the escape hatch for anything the action does not name. Every
[command-line option](cli.md) is available through it:

```yaml
- uses: SAMtheROCKET/visual-verifier@v0.3.0
  with:
    reference: fixtures/source.mp4
    candidate: build/anonymized.mp4
    options: --min-severity 12 --no-annotated-video
```

`--no-annotated-video` is worth knowing about on a minimal runner. Some
container images ship an OpenCV build that cannot write MP4; verification
never needs an encoder, only the annotated evidence does.

## Outputs

| Output | Meaning |
| --- | --- |
| `status` | `PASS`, `FAIL`, or `ERROR` |
| `exit-code` | `0` passed, `1` incomplete, `2` failed |
| `failed-frame-count` | Number of unprotected frames |
| `processing-coverage-percent` | Percentage of frames with change |
| `target-coverage-percent` | Percentage of target frames covered |
| `uncovered-target-frame-count` | Target frames left uncovered |
| `uncovered-target-count` | Distinct targets missed at least once |
| `uncovered-target-ids` | Space-separated identifiers of those targets |
| `evidence-path` | Directory holding the evidence set |
| `summary-path` | Path to the generated `summary.json` |

Reading an output is the way to record a result without gating on it:

```yaml
- name: Verify anonymization coverage
  id: verify
  uses: SAMtheROCKET/visual-verifier@v0.3.0
  with:
    reference: fixtures/source.mp4
    candidate: build/anonymized.mp4
    fail-on-gap: "false"

- name: Gate on coverage instead
  env:
    VV_COVERAGE: ${{ steps.verify.outputs.processing-coverage-percent }}
  run: awk -v value="$VV_COVERAGE" 'BEGIN { exit !(value >= 99.5) }'
```

Read the value through the environment rather than interpolating it into
the script. That is the habit that keeps a step safe when the value comes
from somewhere less trustworthy than this action.

## Commenting on a pull request

The job summary needs no permissions. A comment does.

```yaml
permissions:
  contents: read
  pull-requests: write

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: SAMtheROCKET/visual-verifier@v0.3.0
        with:
          reference: fixtures/source.mp4
          candidate: build/anonymized.mp4
          comment-on-pull-request: "true"
```

The comment is rewritten in place on every run, so a long-lived pull
request gets one current result rather than a column of stale ones.

## Verifying an image instead

```yaml
- uses: SAMtheROCKET/visual-verifier@v0.3.0
  with:
    mode: image
    reference: fixtures/source.png
    candidate: build/redacted.png
```

## Verifying reviewed targets

Pass a target file and the check stops asking whether *anything* changed
and starts asking whether the *required region* changed:

```yaml
- name: Verify anonymization coverage
  id: verify
  uses: SAMtheROCKET/visual-verifier@v0.3.0
  with:
    reference: fixtures/source.mp4
    candidate: build/anonymized.mp4
    targets: reviewed-plates.csv
    target-min-coverage: "0.90"
```

A frame where two of three plates were blurred passes the generic check
and fails this one. The job summary then carries a `Required targets`
table naming which target was missed and where.

Target outputs let a workflow act on the detail:

```yaml
- name: Open a ticket for each missed target
  if: steps.verify.outputs.uncovered-target-count != '0'
  env:
    VV_IDS: ${{ steps.verify.outputs.uncovered-target-ids }}
  run: echo "Uncovered targets: $VV_IDS"
```

A target file the media cannot contain — a frame number past the end of
the video, or a box extending outside the frame — fails the step with
`TARGET_VALIDATION_ERROR` rather than being quietly skipped. See
[Target annotation](target_annotation.md).

## What the action does not change

The action is a convenience over the [exit-code contract](ci.md), not a
replacement for it. It runs the same command you would run yourself, and
a `PASS` carries the same meaning and the same limits.

Without targets:

> A `PASS` means accepted visual change was detected in every checked
> frame under the configured thresholds. It does not prove that a
> particular required object was transformed.

With targets:

> A `PASS` means every reviewed target was covered by accepted
> processing in every frame it was declared on. Coverage is geometric:
> it does not prove the region became unreadable to a human.

## How it is tested

`action.yml` is shell, so the test suite alone cannot prove it works. The
repository's own `Quality` workflow runs the action against both bundled
fixtures on every pull request and asserts the reported status, exit code,
failed-frame count, and coverage against the
[demo contract](output_schema.md). An untested action is a liability.
