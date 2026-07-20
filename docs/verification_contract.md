# Verification Contract

## Inputs

A verification run receives:

- A reference image or video
- A candidate processed image or video
- A `DetectionConfig`
- Optional evidence-output location
- A rule controlling whether processing is required

Reference and candidate videos are consumed as synchronized frame pairs.
The current implementation does not perform temporal alignment.

## Region acceptance

A candidate region must satisfy geometric constraints and the configured
minimums for changed-pixel ratio, mean difference, and severity.

Rejected contours remain available in video evidence reports.

## Image decision

With `expect_processing=True`:

- `PASS`: at least one accepted region exists
- `FAIL`: no accepted region exists

With `expect_processing=False`, absence of an accepted region is permitted.

## Video decision

With `expect_processing_every_frame=True`:

- `PASS`: every synchronized frame has at least one accepted region
- `FAIL`: one or more synchronized frames have no accepted region

With `expect_processing_every_frame=False`, unprocessed frames are
permitted and still appear in frame reports.

## Status and failures

`VerificationResult.status` is one of:

- `PASS`
- `FAIL`
- `ERROR`

Current rule failures use:

- `NO_PROCESSING_DETECTED`
- `UNPROCESSED_FRAMES`

Input and output problems raise structured exceptions instead of returning
a misleading PASS/FAIL result.

## Important interpretation

The current contract proves only that accepted visual change was detected
under configured thresholds. It does not prove that a specific semantic
target was processed.
