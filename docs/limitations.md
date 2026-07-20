# Limitations

## Generic change is not semantic verification

The current detector identifies accepted visual differences. It does not
know whether a region is a face, licence plate, document, watermark, or
other intended target.

## Alignment is assumed

Reference and candidate media should represent the same view and timing.
Camera motion, cropping, stabilization, encoding shifts, or dropped frames
can create false detections or conceal failures.

## Threshold sensitivity

Default thresholds are validated against the bundled regression fixture,
not against a broad public benchmark. Compression, resolution, lighting,
texture, and transformation style can change performance.

## Current video synchronization

Frames are paired in decode order. Verification stops when either stream
ends. The current release does not resample FPS or estimate temporal offset.

## No temporal identity tracking

Regions are evaluated independently per frame. The package does not yet
assign track IDs or measure temporal continuity.

## No target-aware decision

The current PASS result cannot prove that every intended object was
processed. Target CSV and detector-provider support remain planned work.

## Evidence can contain sensitive data

Annotated media and reports may preserve private content. Store and share
outputs under the same controls as input media.

## Not certification

Visual Verifier is not a regulatory certification product, legal opinion,
or guarantee of anonymization.
