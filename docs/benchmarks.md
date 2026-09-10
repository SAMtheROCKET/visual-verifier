# Benchmark

A test suite says an implementation behaves the way it was designed to.
It cannot say whether the design solves a problem that a simpler method
would not. That is what this benchmark is for.

The Anonymization Gap Benchmark measures how reliably a method finds the
frames where a target that should have been anonymized was left exposed,
and what evidence it can produce about the failure.

```bash
uv run python -m benchmarks.run_anonymization_gap --output results
```

## The protocol

The comparison is deliberately generous to the alternatives, because a
benchmark that flatters the tool publishing it is worthless.

**The sequences are generated, not collected.** Real anonymized footage
cannot be published without creating the exact privacy problem this tool
exists to catch, and a generated scene lets each failure mode be varied
one at a time with exact ground truth. Every sequence is deterministic.

**The baselines get a held-out calibration set.** Each global metric
picks the single threshold that maximizes its balanced accuracy on
calibration footage, then is measured on evaluation footage it has never
seen. Calibration deliberately contains only the straightforward case a
team would plausibly have in hand when setting a threshold: clean
footage where a frame was simply skipped. Evaluation contains everything,
including the compressed, noisy, and multi-target footage a real pipeline
meets later.

**The baselines are also reported at an oracle threshold** chosen on the
evaluation set itself, with the answers in hand. No real user can reach
that number. It is published so the calibrated column cannot be mistaken
for the best these methods could ever do.

**Visual Verifier runs at shipped defaults**, tuned to nothing.

Ground truth is the question a user actually has: *was the target left
exposed?* That is deliberately broader than what change detection alone
can answer, which is what makes the results below show where each method
falls short rather than only where it wins.

## Results

78 generated sequences across 13 failure families. Reported on the
39-sequence evaluation half: 780 frames, 84 deliberately left exposed.

| Method | Missed-frame recall | False alarms | F1 | Operating point | Oracle F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| **Visual Verifier + targets** | **100%** | **0.0%** | **1.00** | Reviewed targets, `--min-severity 50` | – |
| **Visual Verifier** | **79%** | **0.0%** | **0.88** | Shipped defaults | – |
| Mean pixel difference | 42% | 0.0% | 0.59 | Tuned on calibration | 0.72 |
| PSNR threshold | 42% | 0.0% | 0.59 | Tuned on calibration | 0.92 |
| SSIM threshold | 42% | 0.0% | 0.59 | Tuned on calibration | 0.70 |

Visual Verifier finds 66 of the 84 exposed frames at shipped defaults.
Every global metric finds 35. Given a reviewed target file, Visual
Verifier finds all 84. None of the five raises a single false alarm.

The target row is **not** a like-for-like comparison, and is labelled
that way deliberately. It receives a reviewed box naming the region that
had to be anonymized, which is information no baseline is given and
which a human had to produce. It measures what the
[target-aware workflow](target_annotation.md) buys, not a cleverer
metric.

| Method | Localizes frame | Localizes region | Temporal evidence | Operating point |
| --- | :-: | :-: | :-: | --- |
| Visual Verifier + targets | Yes | Yes | Yes | Reviewed targets, `--min-severity 50` |
| Visual Verifier | Yes | Yes | Yes | Shipped defaults |
| Mean pixel difference | Yes | No | No | Threshold tuned on calibration |
| PSNR threshold | Yes | No | No | Threshold tuned on calibration |
| SSIM threshold | Yes | No | No | Threshold tuned on calibration |

The operating point is stated rather than reduced to a yes-or-no "needs
tuning" column, because the 100% row reaches that number only with a
raised severity floor. Calling it untuned would be untrue.

## Where the global metrics collapse

Missed-frame recall by family:

| Failure family | VV | VV + targets | Mean diff | PSNR | SSIM |
| --- | ---: | ---: | ---: | ---: | ---: |
| `one_missed_frame` | 100% | 100% | 67% | 67% | 67% |
| `three_missed_frames` | 100% | 100% | 89% | 89% | 89% |
| `long_gap` | 100% | 100% | 67% | 67% | 67% |
| `fast_motion` | 100% | 100% | 100% | 100% | 100% |
| `small_target` | 100% | 100% | 100% | 100% | 100% |
| `offset_blur` | 100% | 100% | 0% | 0% | 0% |
| `compressed` | 100% | 100% | 0% | 0% | 0% |
| `compressed_small_target` | 100% | 100% | 0% | 0% | 0% |
| `sensor_noise` | 100% | 100% | 0% | 0% | 0% |
| `weak_blur` | 0% | 100% | 0% | 0% | 0% |
| `partial_region` | 0% | 100% | 0% | 0% | 0% |
| `multiple_targets` | 0% | 100% | 0% | 0% | 0% |

The pattern is the point. A global metric answers "did this frame change
enough?" — so anything that changes the whole frame drowns the signal.
Re-encode the video and every pixel moves; add capture noise and every
pixel moves. The missing blur is still there, but it is now a rounding
error in the average, and a threshold calibrated on clean footage no
longer separates anything.

Visual Verifier measures change **region by region**, so a compressed
frame and a noisy frame are still frames in which no region changed
enough to count as processing. That is why the four nuisance-change
families — `offset_blur`, `compressed`, `compressed_small_target`, and
`sensor_noise` — read 100% against three zeros.

## The semantic gap, and what closes it

The last three rows are the interesting ones. Without targets, Visual
Verifier scores **0%** on all of them, and so does every baseline.

`weak_blur`, `partial_region`, and `multiple_targets` all describe a
frame in which **something was processed, but not the thing that
mattered**. Change detection verifies that accepted visual change
occurred. It cannot know which object was supposed to change. A frame
where two of three plates were blurred contains plenty of accepted
change, so it passes: correctly, under the contract, and uselessly,
under the user's actual question.

No threshold fixes this. Half a covered plate is still a strong,
accepted region, and so is a correctly blurred plate beside a missed
one. The missing information is not a number. It is *which region was
required*.

Supplying it closes all three:

```bash
visual-verifier video --reference raw.mp4 --candidate out.mp4 \
    --targets plates.csv --min-severity 50
```

`--targets` fixes `partial_region` and `multiple_targets`, because
coverage is then measured against the declared box rather than against
the frame.

`--min-severity 50` is what fixes `weak_blur`, and the reason is worth
being precise about: a blur too light to anonymize is still a real
accepted region covering the target, so coverage alone accepts it.
Raising the severity floor rejects it. Measured here, that catches every
weak-blur frame with no new false alarms. The shipped default of `8.0`
stays permissive because on real footage a high floor rejects legitimate
processing; raise it when you know your pipeline applies a strong blur.

Together they take the benchmark from 79% to 100%.

## Reproducing it

```bash
uv run python -m benchmarks.run_anonymization_gap --output results
```

The run writes `results.md`, a machine-readable `results.json`, every
generated clip, and the per-sequence evidence, so a surprising number can
be opened and inspected rather than taken on trust. It takes about a
minute.

`--seeds` controls how many layouts each family is repeated with. Half
calibrate the baselines and half are evaluated, so the smallest
meaningful value is `2`.

## Honest limits of this benchmark

- **The footage is synthetic.** The scenes are clean renders with a
  known target. Real dashcam footage has motion blur, rolling shutter,
  varying exposure, and occlusion, none of which appear here.
- **The baselines are simple by construction.** They are the checks
  teams actually reach for first, not the best published change
  detectors. A method built for this task would do better.
- **It measures one target per sequence.** The scored plate is always
  the first one, so `multiple_targets` measures whether a method notices
  a specific missed object, not how it ranks several.
- **The target row is given information nobody else gets.** Its reviewed
  boxes come from the same scene description that places the plate, so
  they are exact. A real reviewer's boxes are approximate, and producing
  them is work the other rows never have to do.
- **The numbers are a snapshot.** They are produced by the code in this
  repository at the version documented in the changelog, and will move
  when detection defaults move.
