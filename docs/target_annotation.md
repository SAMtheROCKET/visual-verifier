# Target annotation

Frame-level verification answers *did something change here*. A target
answers the question a privacy reviewer actually has: *did the thing that
had to change, change*.

Without targets, a frame in which two of three licence plates were
blurred contains plenty of accepted processing, so it passes. Correctly,
under the contract — and uselessly, for the person who needed all three
blurred. Supplying a target says which region was required, and the
verdict follows the requirement instead of the pixels.

```bash
visual-verifier video \
    --reference raw.mp4 \
    --candidate anonymized.mp4 \
    --targets plates.csv \
    --output outputs/check
```

Targets are the one input Visual Verifier cannot check against the media.
Everything below follows from that: the file is validated strictly, a bad
row is rejected loudly, and a box this package generated is never
presented as one a human drew.

## The target file

A CSV with one row per target per frame.

```csv
frame_number,target_id,target_type,x1,y1,x2,y2,required,source
1,PLATE_A,plate,608,502,670,527,true,manual
2,PLATE_A,plate,605,503,661,526,true,manual
3,PLATE_A,plate,600,502,654,525,true,manual
```

| Column | Required | Meaning |
| --- | :-: | --- |
| `frame_number` | Yes | One-based frame number |
| `target_id` | Yes | Identifier stable across frames |
| `x1`, `y1` | Yes | Top-left coordinates, inclusive |
| `x2`, `y2` | Yes | Bottom-right coordinates, exclusive |
| `target_type` | No | Semantic category, such as `plate` or `face` |
| `required` | No | `false` measures a target without failing the run |
| `source` | No | `manual`, `interpolated`, or `detector` |

Coordinates use the reference-media coordinate system. Omitted optional
columns default to a required, manually reviewed target.

A shipped example is
[`examples/targets/demo_targets.csv`](https://github.com/SAMtheROCKET/visual-verifier/blob/main/examples/targets/demo_targets.csv),
which reproduces the demo contract: `PASS` against the fully blurred
clip, `FAIL` on frames 4, 8, and 12 against the partially blurred one.

## What is rejected

Validation happens in two passes, and both refuse the run rather than
verifying part of it.

**The file itself.** Each error names the line to fix.

- A missing required column
- A frame number below 1
- A box with no positive area, or a negative coordinate
- A non-numeric coordinate
- The same `target_id` declared twice in one frame, which would make
  coverage ambiguous
- An unrecognized `required` or `source` value

That last one matters more than it looks. Treating an unreadable flag as
`true` would be the safe-sounding choice and the wrong one: it would hide
a typo that a reviewer needs to see.

**The file against the media**, before any frame is read.

- A frame number the media does not have
- A box extending past the frame width or height

This second pass exists because of a real defect. A target declaring
frame 99 of a 15-frame video parses perfectly, and then the frame loop
never visits it: no coverage is measured, and a run that should fail
reports `PASS` with zero targets. **Verification that silently skips a
declared requirement is not verification.** Both faults now raise
`TARGET_VALIDATION_ERROR` and exit `1`, which the exit-code contract
already means *could not complete*.

```console
$ visual-verifier video --reference raw.mp4 --candidate out.mp4 \
      --targets plates.csv
ERROR [TARGET_VALIDATION_ERROR]: Targets do not fit the reference media.
  problem_count: 1
  problems: ["target 'PLATE_X' names frame 99, but the reference media
  has 15 frames"]
  reference_frame_count: 15
```

Repeated faults are collapsed. One bad box declared on every frame is
reported once, naming the frame span, rather than filling the error with
identical lines.

A third check runs *after* verification and confirms every declared
target really was measured. Media metadata can disagree with what a
decoder yields, so a target inside the declared frame count can still go
unvisited. That is the last chance to notice before a verdict is
returned, and it raises rather than returning one.

## Coverage

A target is covered when accepted processing regions overlap at least
`--target-min-coverage` of its area. The default is `0.9`.

Coverage is the **union** of every overlapping accepted region, not the
best single one. A pipeline that blurs a face in two overlapping passes
has covered it once; counting only the larger pass would under-report
real coverage, and summing both would report more than 100% and pass a
target that was never fully covered.

A rejected region never contributes. Processing that failed detection
filtering did not happen as far as the verdict is concerned.

## How precisely must a box be drawn?

A reviewer draws a box with margin around the object. A generated box is
exact. That difference matters, because coverage is a ratio: grow the box
and the same blur covers a smaller fraction of it.

Measured on the benchmark fixtures at the default
`--target-min-coverage 0.9`, growing every box symmetrically:

| Box drawn larger than the object | Correctly anonymized frames failing |
| ---: | ---: |
| up to 40% | none |
| 45% and beyond | all of them |

The cliff is sharp rather than gradual, and that is worth understanding.
Coverage is one ratio per target, so every frame crosses the threshold at
the same moment. You do not get a warning band; a slightly-too-loose
convention fails an entire run at once.

Practically:

- **Draw within about a third of the object's size** and the default
  threshold has room to spare.
- **If your review convention is looser than that**, lower
  `--target-min-coverage` rather than redrawing. A box drawn at twice the
  object's size needs roughly `0.25`.
- **A sudden all-frames failure after a review-tool change** is more
  likely a box convention change than a pipeline regression. Check
  `covered_ratio` in `target_report.csv`: a consistent value just under
  the threshold points at the boxes, not the blur.

These numbers come from synthetic fixtures where the blur is applied with
fixed padding. Real footage will shift them, so treat 40% as an
indication rather than a specification.

## Interpolation

Reviewers rarely annotate every frame. Boxes between two reviewed
positions of the same target are interpolated linearly and marked
`interpolated`.

Gaps longer than `--target-max-gap` (default `5`) are **not** filled. A
target can leave a scene and return, and a straight line between its two
appearances would place a box where nothing was — fabricated evidence
wearing the same clothes as measured evidence.

Pass `--no-target-interpolation` to check only frames a human reviewed.

Provenance survives into every output: the `source` column of
`target_report.csv`, the `interpolated_frame_count` of each summary, and
a `~` prefix on interpolated labels in the annotated video. A reviewer
can always tell which boxes a human actually drew.

## What it changes

| | Without targets | With targets |
| --- | --- | --- |
| Policy | `generic_change_every_frame` | `target_coverage_every_frame` |
| A frame fails when | no accepted region | no accepted region, **or** a required target is uncovered |
| Failure codes | `UNPROCESSED_FRAMES` | also `UNCOVERED_TARGETS` |
| Extra evidence | – | `target_report.csv`, `measurements.targets` |

The two failure kinds are reported **independently**, so a frame that
was skipped entirely *and* left a target uncovered carries both codes:

```text
Frame 4
├── UNPROCESSED_FRAMES   nothing was processed at all
└── UNCOVERED_TARGETS    PLATE_A was left exposed

Frame 7
├── (processing detected elsewhere in the frame)
└── UNCOVERED_TARGETS    PLATE_B was left exposed
```

That distinction is the point of supplying targets. `frames_without_processing`
counts only the first kind, so a run where every frame was processed but
a target was missed reports zero unprocessed frames, not one per
failure.

Supplying no targets changes nothing. A regression test asserts that
every result produced before this feature is produced identically.

To collect coverage without gating a build, pass
`--allow-uncovered-targets`.

## Reading the result

```python
from visual_verifier import verify_video

result = verify_video("raw.mp4", "out.mp4", targets="plates.csv")
targets = result.measurements["targets"]

print(targets["target_coverage_percent"])
for summary in targets["target_summaries"]:
    print(summary["target_id"], summary["uncovered_frames"])
```

`target_report.csv` carries one row per target per frame with its box,
provenance, measured `covered_ratio`, and whether it counted as covered.

## Automatic targets

`source` accepts `detector` so a detector's output can be measured, but
nothing in this package produces such boxes, and a detector box is not
ground truth. An unreviewed target can be wrong in both directions: it
can miss a plate that was never anonymized, and it can fail a build over
a region that was never sensitive.

If you feed a detector's output in, keep `source` set to `detector` so
every report says so.

## First run on real footage

The benchmark uses synthetic clips with exact boxes and a JPEG-style
re-encode. Real footage differs in three ways that change what you
should expect, and none of them is a defect:

**Your boxes will be looser than the generated ones.** See the section
above; `--target-min-coverage` is the knob, not the box.

**Real codecs are not a JPEG round trip.** H.264 spreads motion
artefacts across a frame in ways a still-image re-encode does not. If a
clean pipeline reports scattered failures, raise `--diff-threshold`
before suspecting the anonymizer.

**The severity default is deliberately permissive.** `--min-severity`
defaults to `8.0`, which accepts a blur too light to anonymize. The
benchmark measures `50` catching every weak-blur case with no new false
alarms. If you know your pipeline applies a strong blur, raise it; if
your pipeline uses light pixelation, leave it low and rely on targets.

A useful first run is deliberately boring: verify media you already
believe is correct, confirm `PASS`, and only then point it at a
suspected failure. A tool that fails on your known-good footage is
telling you about its thresholds, not your pipeline.

## Honest limits

- **A target says where, not what.** Coverage is geometric. A region that
  changed inside the target box counts, whatever the change was.
- **A weak blur still counts as coverage.** A blur too light to
  anonymize is a real accepted region covering the target. Raise
  `--min-severity` to reject it; the
  [benchmark](benchmarks.md) measures `--min-severity 50` catching every
  weak-blur case with no new false alarms.
- **Coverage is not legibility.** Neither this package nor any pixel
  metric can tell you a plate is unreadable to a human. It tells you the
  region you declared was measurably transformed.
