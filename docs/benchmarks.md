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

Ground truth is the question a user actually has — *was the target left
exposed?* — not the narrower question Visual Verifier answers today.
That choice is what makes the results below show where it falls short.

## Results

78 generated sequences across 13 failure families. Reported on the
39-sequence evaluation half: 780 frames, 84 deliberately left exposed.

| Method | Missed-frame recall | False alarms | F1 | Operating point | Oracle F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| **Visual Verifier** | **79%** | **0.0%** | **0.88** | Shipped defaults | – |
| Mean pixel difference | 42% | 0.0% | 0.59 | Tuned on calibration | 0.72 |
| PSNR threshold | 42% | 0.0% | 0.59 | Tuned on calibration | 0.92 |
| SSIM threshold | 42% | 0.0% | 0.59 | Tuned on calibration | 0.70 |

Visual Verifier finds 66 of the 84 exposed frames. Every global metric
finds 35. None of the four raises a single false alarm.

| Method | Localizes frame | Localizes region | Temporal evidence | Needs tuning |
| --- | :-: | :-: | :-: | :-: |
| Visual Verifier | Yes | Yes | Yes | No |
| Mean pixel difference | Yes | No | No | Yes |
| PSNR threshold | Yes | No | No | Yes |
| SSIM threshold | Yes | No | No | Yes |

## Where the global metrics collapse

Missed-frame recall by family:

| Failure family | Visual Verifier | Mean diff | PSNR | SSIM |
| --- | ---: | ---: | ---: | ---: |
| `one_missed_frame` | 100% | 67% | 67% | 67% |
| `three_missed_frames` | 100% | 89% | 89% | 89% |
| `long_gap` | 100% | 67% | 67% | 67% |
| `fast_motion` | 100% | 100% | 100% | 100% |
| `small_target` | 100% | 100% | 100% | 100% |
| `offset_blur` | 100% | 0% | 0% | 0% |
| `compressed` | 100% | 0% | 0% | 0% |
| `compressed_small_target` | 100% | 0% | 0% | 0% |
| `sensor_noise` | 100% | 0% | 0% | 0% |
| `weak_blur` | 0% | 0% | 0% | 0% |
| `partial_region` | 0% | 0% | 0% | 0% |
| `multiple_targets` | 0% | 0% | 0% | 0% |

The pattern is the point. A global metric answers "did this frame change
enough?" — so anything that changes the whole frame drowns the signal.
Re-encode the video and every pixel moves; add capture noise and every
pixel moves. The missing blur is still there, but it is now a rounding
error in the average, and a threshold calibrated on clean footage no
longer separates anything.

Visual Verifier measures change **region by region**, so a compressed
frame and a noisy frame are still frames in which no region changed
enough to count as processing. That is why the bottom four rows read
100% against three zeros.

## Where Visual Verifier falls short

The last three rows are Visual Verifier's own failures, and they matter
more than the wins.

`weak_blur`, `partial_region`, and `multiple_targets` all describe a
frame in which **something was processed, but not the thing that
mattered**. Visual Verifier verifies that accepted visual change
occurred. It does not know which object was supposed to change. A frame
where two of three plates were blurred contains plenty of accepted
change, so it passes — correctly, under the contract, and uselessly,
under the user's actual question.

This is the semantic gap, and it is exactly what
[target-aware verification](target_annotation.md) is for.

One of the three is partly recoverable today. `weak_blur` is a real
region whose severity score is simply low, so raising the threshold
rejects it:

```bash
visual-verifier video --reference raw.mp4 --candidate out.mp4 \
    --min-severity 50
```

Measured on this benchmark, `--min-severity 50` catches every weak-blur
frame with no new false alarms on correctly anonymized footage. The
shipped default of `8.0` is deliberately permissive, because on real
footage a high severity floor rejects legitimate processing too. Raise it
when you know your pipeline applies a strong blur.

`partial_region` does not respond to any severity threshold: half a
covered plate is still a strong, accepted region. Neither does
`multiple_targets`. Both need to know what the target was.

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
- **The numbers are a snapshot.** They are produced by the code in this
  repository at the version documented in the changelog, and will move
  when detection defaults move.
