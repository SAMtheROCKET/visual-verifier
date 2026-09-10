# Visual Verifier Roadmap

## V5.1b / 0.1.0a0 — complete

- Modular typed foundation
- Image and synchronized-video verification
- Region metrics, filtering, annotations, reports, CLI, and CI

## V5.2 / 0.2.0 — complete

- Deterministic IoU association
- Explicit track lifecycle and short-gap recovery
- Track IDs and temporal annotations
- Continuity, fragmentation, jitter, and stability metrics
- Split and merge lineage evidence
- Track, observation, and event reports
- Temporal unit and video regressions

## V5.3 / 0.3.0 — complete

- Reviewed target CSV schema
- Target validation and coordinate checks
- Missing-frame interpolation with explicit provenance
- Target-to-processing coverage
- Target continuity and per-target failures
- Review overlays and target reports
- The Anonymization Gap Benchmark, measuring the whole of the above
  against mean pixel difference, PSNR, and SSIM

## V5.4 — selectable policy system

Target mode today is *target coverage in addition to* the generic
every-frame requirement. That suits an anonymization pipeline expected
to alter every frame, but it is a fixed combination rather than a
choice. V5.4 makes the shape selectable:

- Typed policy protocol
- `generic_change_every_frame` — did anything change, everywhere
- `target_coverage_only` — verify only the declared regions
- `target_coverage_and_generic_change` — today's combined behaviour
- `target_temporal_continuity` — a target must persist, not merely appear
- Privacy-processing policy
- Explicit temporal continuity policy
- Stable policy configuration and serialization

Renaming the action's `fail-on-gap` input belongs here too: it gates
every policy failure, not only a processing gap, and the name should say
so once the policies are named.

## V5.5 — batch and integration layer

- Batch manifests and directory execution
- Aggregate summaries
- Optional pytest assertions
- Parallel deterministic execution

## V5.6 — robustness and calibration

- Frame-count, FPS, and resolution mismatch diagnostics
- Temporal alignment and resampling options
- Corrupted-media handling
- Performance benchmarks and public threshold calibration

## V6.0 public beta criteria

- Public benchmark dataset
- Stable output schema
- Documented error rates
- Cross-platform release validation
- PyPI distribution
