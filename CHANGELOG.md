# Changelog

All notable changes to Visual Verifier are documented here.

The format follows Keep a Changelog, and the project uses semantic
versioning once public release stability begins.

## [Unreleased]

### Planned

- Temporal region tracking with tested identity continuity
- Reviewed target CSV support and target coverage validation
- Selectable policy objects
- Batch verification
- Alignment and synchronization diagnostics
- Optional pytest integration
- Public benchmark datasets and threshold calibration

## [0.1.0a0] - 2026-07-20

### Added

- Typed `verify_image()` and `verify_video()` Python APIs
- Image and synchronized-video verification pipelines
- Changed-region extraction using OpenCV morphology and contours
- Pixel, geometry, and sharpness metric modules
- Severity scoring and false-positive filtering
- Structured domain models and exception hierarchy
- Annotated image and video evidence
- CSV and JSON report writers
- `doctor`, `inspect`, `image`, and `video` CLI commands
- PowerShell bootstrap and quality scripts
- Package typing marker
- Three-video regression fixture
- Regression contract for failed frames `4`, `8`, and `12`
- Automated quality workflow
- Architecture, output, limitation, and development documentation

### Changed

- Refactored legacy notebook-style logic into focused package modules
- Limited public exports to implemented and tested behavior
- Standardized Python 3.12 development checks
- Standardized 79-character source lines and typed public interfaces
- Replaced long orchestration functions with focused helpers
- Removed unused runtime dependencies

### Removed

- Generated caches, bytecode, package metadata, and build artifacts
- Empty placeholder modules that implied unsupported functionality

### Not yet supported

- Target-aware validation
- Temporal tracking
- Selectable policy implementations
- Batch execution
- Pytest plugin integration
