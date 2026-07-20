# Development History

Visual Verifier evolved from a sequence of image and video verification
prototypes preserved under `archive/legacy_cells/`.

## Historical progression

- Image-level difference and blur analysis
- Video-level frame comparison
- Region reports, severity, and JSON summaries
- IoU-based temporal tracking
- False-positive filtering
- Target-aware validation and manual review
- Batch execution and standalone CLI experiments

## V5.1b foundation

The first validated package milestone extracted:

- Typed domain models and structured exceptions
- Media readers and normalization
- Geometry, pixel, and sharpness metrics
- Region extraction and filtering
- Image and video pipelines
- Evidence writers
- Public Python and CLI interfaces
- Regression tests and release scripts

## V5.2 temporal extraction

V5.2 reintroduced historical temporal tracking as a tested package subsystem:

- Deterministic one-to-one association
- Explicit lifecycle and short-gap recovery
- Immutable tracking evidence
- Split and merge lineage signals
- Continuity, fragmentation, jitter, and stability analysis
- Track, observation, and event reports
- Track-aware annotated video

Target-aware verification, selectable policies, and batch execution still
require clean extraction and independent regression parity before becoming
active public capabilities.
