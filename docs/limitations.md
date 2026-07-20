# Limitations

## Generic change is not semantic verification

The detector identifies accepted visual differences. Track identity represents
persistence of those differences, not a proven face, licence plate, document,
watermark, person, or other semantic object.

## Alignment is assumed

Reference and candidate media should represent the same view and timing.
Camera motion, cropping, stabilization, encoding shifts, or dropped frames can
create false detections, false associations, or concealed failures.

## Threshold sensitivity

Default detection and tracking thresholds are validated against the bundled
regression fixture, not a broad public benchmark. Compression, resolution,
lighting, texture, motion, and transformation style can alter performance.

## Current video synchronization

Frames are paired in decode order. Verification stops when either stream ends.
The current release does not resample FPS or estimate temporal offset.

## Tracking is geometry-based

V5.2 uses box overlap without motion prediction or appearance embeddings. Fast
motion, occlusion, crossing regions, or abrupt box changes can fragment or
switch identities.

## Lineage events are review evidence

Split and merge events are based on geometric overlap. They are not semantic
proof that one real-world object divided or several objects combined.

## No target-aware decision

The current PASS result cannot prove that every intended object was processed.
Target CSV and detector-provider support remain planned work.

## Evidence can contain sensitive data

Annotated media and reports may preserve private content. Store and share
outputs under the same controls as input media.

## Not certification

Visual Verifier is not a regulatory certification product, legal opinion, or
guarantee of anonymization.
