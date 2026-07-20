# Problem Statement

Media-processing systems often report that they completed a task without
independently proving that the produced image or video is acceptable.

For privacy processing, a pipeline may blur most frames but miss a few.
For masking or redaction, the intended area may remain visible. A global
image metric can hide these local failures, while manual frame review is
slow and difficult to reproduce.

Visual Verifier addresses a narrower problem:

> Given original media and a processed candidate, measure meaningful
> visual changes and return reproducible evidence about whether the current
> verification rule passed.

## Current scope

The active package compares aligned media with matching content. It detects
changed regions, filters weak regions, measures severity, and evaluates a
generic presence-of-processing rule.

## Desired properties

- Deterministic local execution
- Typed Python and CLI interfaces
- Machine-readable results
- Human-reviewable evidence
- Explicit failure codes
- Reproducible thresholds
- No dependence on archived notebook state

## Non-goals of the current release

- Performing the transformation
- Identifying semantic objects
- Proving privacy compliance
- Correcting alignment automatically
- Replacing human review in high-risk workflows
