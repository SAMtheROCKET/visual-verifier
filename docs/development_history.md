# Development History

Visual Verifier evolved from a sequence of image and video verification
prototypes.

## Historical progression

- Image-level difference and blur analysis
- Video-level frame comparison
- Region reports and crops
- Severity scoring
- JSON and text summaries
- IoU-based temporal tracking
- False-positive filtering
- Target-aware validation
- Manual target review
- Batch execution
- Standalone CLI
- Initial package skeleton

Historical scripts are preserved under `archive/legacy_cells/`.

## V5.1b refactor

The V5.1b foundation extracted the currently validated core into:

- Typed domain models
- Structured exceptions
- Media readers
- Geometry, pixel, and sharpness metrics
- Region extraction and filtering
- Image and video pipelines
- Evidence writers
- Public Python and CLI interfaces
- Regression tests and quality scripts

## Why historical features are not all active

Historical availability is not equivalent to package readiness. Tracking,
target-aware verification, policies, and batch execution require clean
extraction, explicit schemas, regression parity, and public documentation
before re-entry into the active package.
