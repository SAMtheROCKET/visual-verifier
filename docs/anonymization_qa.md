# Anonymization QA

Anonymization is the use case Visual Verifier leads with, because a missed
frame is expensive there in a way it is not elsewhere: one unblurred
licence plate in a ten-minute clip is a disclosure, no matter how good the
other 17,999 frames were.

## The failure this catches

Your anonymizer runs. It reports success. A per-frame detector missed the
plate on three frames because the vehicle was briefly occluded, or the
confidence dipped below threshold, or a worker crashed and a shard was
copied through unprocessed.

Nothing downstream notices. The output plays fine. A global metric such as
mean pixel difference or SSIM averages three bad frames into fifteen and
reports a healthy number.

<p align="center">
  <img src="../assets/pass_fail_comparison.png"
       alt="The same licence plate one frame apart: blurred and passing, then readable and failing"
       width="720">
</p>

Visual Verifier compares the original with the anonymized candidate frame
by frame, and fails the build naming frames `4, 8, 12`.

## How to use it

Keep an unprocessed reference of whatever you anonymize. That is the only
requirement, and it is usually satisfied already — the anonymizer had an
input.

```bash
visual-verifier video \
    --reference raw.mp4 \
    --candidate anonymized.mp4 \
    --output artifacts/anonymization-check
```

Exit code `2` means at least one frame contains no accepted visual change,
which for an anonymization pipeline means at least one frame was left as it
came in.

## What a PASS proves, exactly

This is the most important section on this site.

A `PASS` means:

> In every synchronized frame, at least one region changed enough to clear
> the configured detection thresholds.

A `PASS` does **not** mean:

- that a particular face, licence plate, person, or document was found
- that the thing which changed was the thing that needed protecting
- that the transformation is irreversible
- that you are compliant with any regulation

!!! warning "The semantic gap, and how to close it"

    The default policy is `generic_change_every_frame`. It verifies that
    processing happened, not that the **right region** was processed.

    Consider a frame where the licence plate was accidentally left sharp
    but the sky changed because of compression. If that sky change clears
    the thresholds, the frame passes while the plate is still readable.

    Supplying [reviewed targets](target_annotation.md) closes that gap.
    You declare the regions that had to be transformed, the policy
    becomes `target_coverage_every_frame`, and coverage is measured
    against those boxes rather than against the frame.

    ```bash
    visual-verifier video --reference raw.mp4 --candidate out.mp4 \
        --targets plates.csv
    ```

Without targets, treat a `PASS` as **"the pipeline did something
everywhere"**, which is a real and useful guarantee, and a `FAIL` as
**"the pipeline demonstrably did nothing on these frames"**, which is a
strong one.

With targets, a `PASS` means every declared region was covered in every
frame it was declared on. That is the stronger claim, and it is the one
the [benchmark](benchmarks.md) measures at 100% recall.

Neither claim is a statement about legibility. Coverage is geometric: it
does not prove a plate became unreadable to a human.

## Tuning for weak or subtle processing

Light blur on a small region may fall below the defaults. Every threshold
is adjustable from the command line:

```bash
visual-verifier video \
    --reference raw.mp4 \
    --candidate anonymized.mp4 \
    --min-severity 4.0 \
    --min-box-area 40 \
    --min-changed-ratio 0.02
```

Lowering thresholds finds weaker processing but admits more noise.
Compression artefacts, sensor noise, and encoder differences all change
pixels. Calibrate against media you understand, and record the values you
chose. They are written into `summary.json` for exactly that reason.

## Privacy of the evidence itself

Verification runs entirely on your machine. Nothing is uploaded, and the
package imports no networking library at all. A
[test enforces this](https://github.com/SAMtheROCKET/visual-verifier/blob/main/tests/test_local_execution.py)
on every commit.

The evidence, however, is derived from your media:

- `annotated_video.mp4` contains the candidate footage
- `index.html` embeds thumbnails of the **original, unprocessed** frames
  for the before/after comparison

Those thumbnails are the whole point, since they show a reviewer what was
exposed, but they mean the report inherits the sensitivity of the input.
Store and share evidence directories under the same controls as the source
media. The HTML report itself loads nothing from the network, so opening it
does not signal to anyone that it exists.

## Related

- [Limitations](limitations.md) — every known failure mode
- [Use cases](use_cases.md) — supported uses and unsupportable claims
- [Target annotation](target_annotation.md) — the planned V5.3 schema
