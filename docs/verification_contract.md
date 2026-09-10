# Verification Contract

Visual Verifier answers one of two questions, and which one it answers
depends on whether you supplied reviewed targets. The difference matters
enough that the two contracts are stated separately below.

## Inputs

A verification run receives:

- A reference image or video
- A candidate processed image or video
- A `DetectionConfig`
- Optional reviewed targets and a `TargetConfig`
- Optional evidence-output location
- A rule controlling whether processing is required

Reference and candidate videos are consumed as synchronized frame pairs.
The current implementation does not perform temporal alignment.

## Region acceptance

A candidate region must satisfy geometric constraints and the configured
minimums for changed-pixel ratio, mean difference, and severity.

Rejected contours remain available in video evidence reports, and a
rejected region never contributes to any decision below.

## Generic mode

Active when no targets are supplied. The policy name is
`generic_change_every_frame`.

```text
PASS = accepted visual processing was detected
       on every required frame
```

For images, with `expect_processing=True`:

- `PASS`: at least one accepted region exists
- `FAIL`: no accepted region exists

For video, with `expect_processing_every_frame=True`:

- `PASS`: every synchronized frame has at least one accepted region
- `FAIL`: one or more synchronized frames have no accepted region

With the corresponding flag set to `False`, absence of an accepted
region is permitted and still appears in frame reports.

## Target mode

Active when reviewed targets are supplied. The policy name is
`target_coverage_every_frame`.

```text
PASS = every reviewed required target met its
       geometric coverage requirement, on every
       frame it was declared on
       AND
       the generic every-frame rule still held
```

A frame fails when it has no accepted region **or** when a required
target was left uncovered. Both conditions are evaluated, and both are
reported, because they are different findings:

- `UNPROCESSED_FRAMES` — nothing was processed in this frame at all
- `UNCOVERED_TARGETS` — something was processed, but not the region
  that had to be

A frame exhibiting both carries both codes.

Coverage is the union of every accepted region overlapping a target,
measured against `TargetConfig.min_covered_ratio`.

Targets are validated against the reference media before any frame is
read. A target naming a frame the media does not have, or a box
extending past the frame, raises `TargetValidationError` rather than
being skipped. See [Target annotation](target_annotation.md).

!!! note "The generic rule still applies in target mode"

    Target mode today is *target coverage in addition to* the generic
    every-frame requirement, not target coverage alone. That suits an
    anonymization pipeline expected to alter every frame, but it is a
    combination rather than a choice.

    Making it selectable — target coverage only, generic only, or both —
    is [V5.4 policy system](policy_system.md) work. Until then, pass
    `expect_processing_every_frame=False` to relax the generic half
    while keeping target enforcement.

## Status and failures

`VerificationResult.status` is one of:

- `PASS`
- `FAIL`
- `ERROR`

Rule failures use:

- `NO_PROCESSING_DETECTED`
- `UNPROCESSED_FRAMES`
- `UNCOVERED_TARGETS`

Input and output problems raise structured exceptions instead of
returning a misleading PASS/FAIL result. That includes an unusable
target file: a requirement nobody could evaluate must never resolve to a
verdict.

## Important interpretation

**Generic mode** proves only that accepted visual change was detected
under the configured thresholds. It does not prove that a specific
semantic target was processed.

**Target mode** proves that the regions a reviewer declared were
geometrically covered by accepted processing. That is a materially
stronger claim, and it is still not a claim about meaning:

> Target coverage proves geometric transformation coverage. It does not
> prove semantic unreadability, and it does not prove irreversible
> anonymization.

Two consequences worth stating plainly:

- A blur too weak to anonymize is a real accepted region that does cover
  its target, so coverage alone accepts it. Raising `--min-severity`
  rejects it; the [benchmark](benchmarks.md) measures that.
- The correctness of a target-mode result depends on the correctness of
  the targets. An unreviewed or misplaced box produces a confident
  verdict about the wrong region.
