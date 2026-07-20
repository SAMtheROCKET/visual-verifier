# Visual Verifier Roadmap

This roadmap separates implemented behavior from planned extraction of
historical prototype capabilities.

## V5.1b foundation — complete

- Modular package under `src/visual_verifier/`
- Typed image and video APIs
- Synchronized video-frame reading
- Pixel, sharpness, and geometry metrics
- Changed-region extraction
- Severity scoring and region filtering
- Image and video evidence generation
- CSV and JSON reports
- CLI commands and CI-compatible exit codes
- PowerShell bootstrap and quality gates
- Package typing support
- Three-video regression suite

## V5.2 temporal parity

Goal: restore V2.1 temporal behavior as tested package modules.

- IoU-based region identity tracking
- Track lifecycle and gap handling
- Track confidence metrics
- Track report schema
- Temporal false-positive suppression
- Regression tests against historical outputs

## V5.3 target-aware parity

Goal: restore V3.0–V3.2 behavior without notebook dependencies.

- Reviewed target CSV loader
- Target schema validation
- Missing-frame interpolation
- Target-to-region coverage calculation
- Target-level PASS/FAIL decisions
- Manual review overlay
- Target report schema and tests

## V5.4 policy system

- Typed policy protocol
- Generic-change policy
- Privacy-blur policy
- Policy configuration serialization
- Independent policy tests
- Stable policy selection through API and CLI

## V5.5 batch and integration layer

- Batch directory and manifest execution
- Aggregate summaries
- Optional pytest assertions
- CI report artifacts
- Parallel execution with deterministic ordering

## V5.6 robustness

- Frame-count and FPS mismatch diagnostics
- Temporal alignment options
- Resolution and color-space mismatch reporting
- Corrupted-media handling
- Performance and memory benchmarks

## V6.0 public beta criteria

- Public benchmark dataset
- Calibrated default thresholds
- Documented false-positive and false-negative rates
- Stable output schema
- Cross-platform release testing
- PyPI distribution
- Migration and compatibility policy

## Long-term research

- Optional object detectors and segmenters
- Transformation-specific quality models
- Watermark and blackout verification
- Human-review workflows
- HTML evidence reports
- Dataset and model-provider integrations

Planned features are not part of the current public contract until they are
implemented, tested, documented, and exported.
