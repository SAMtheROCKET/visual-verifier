# Python API

The package is fully typed and ships `py.typed`, so editors and `mypy` see
every signature. Everything you need is exported from the top level.

```python
from visual_verifier import (
    DetectionConfig,
    TrackingConfig,
    VerificationResult,
    VerificationStatus,
    VisualVerifierError,
    verify_image,
    verify_video,
)
```

## verify_video

```python
def verify_video(
    reference: str | Path,
    candidate: str | Path,
    *,
    output_dir: str | Path | None = None,
    expect_processing_every_frame: bool = True,
    save_annotated_video: bool = True,
    save_html_report: bool = True,
    config: DetectionConfig = DEFAULT_DETECTION_CONFIG,
    enable_tracking: bool = True,
    tracking_config: TrackingConfig = DEFAULT_TRACKING_CONFIG,
    targets: str | Path | Sequence[Target] | None = None,
    target_config: TargetConfig = DEFAULT_TARGET_CONFIG,
) -> VerificationResult
```

| Argument | Purpose |
| --- | --- |
| `reference` | Path to the original video |
| `candidate` | Path to the processed video being verified |
| `output_dir` | Directory for evidence. Omit to verify without writing files |
| `expect_processing_every_frame` | Require an accepted region in every frame |
| `save_annotated_video` | Write `annotated_video.mp4` |
| `save_html_report` | Write the self-contained `index.html` |
| `config` | Region-detection and severity thresholds |
| `enable_tracking` | Associate accepted regions through time |
| `tracking_config` | Temporal association and lifecycle settings |
| `targets` | Reviewed targets, as a CSV path or a loaded sequence |
| `target_config` | Target coverage and interpolation settings |

```python
from visual_verifier import verify_video

result = verify_video(
    reference="raw.mp4",
    candidate="anonymized.mp4",
    output_dir="outputs/check",
)

print(result.status.value)   # "FAIL"
print(result.failed_frames)  # (4, 8, 12)
print(result.passed)         # False
```

## verify_image

```python
def verify_image(
    reference: str | Path,
    candidate: str | Path,
    *,
    output_dir: str | Path | None = None,
    expect_processing: bool = True,
    config: DetectionConfig = DEFAULT_DETECTION_CONFIG,
) -> VerificationResult
```

## VerificationResult

Immutable. Every field is safe to keep and to serialize.

| Member | Type | Description |
| --- | --- | --- |
| `status` | `VerificationStatus` | `PASS`, `FAIL`, or `ERROR` |
| `passed` / `failed` / `errored` | `bool` | Status convenience properties |
| `reference_path` / `candidate_path` | `Path` | Resolved inputs |
| `policy_name` | `str` | Rule that produced the decision |
| `failed_frames` | `tuple[int, ...]` | Frames that violated the policy |
| `failures` | `tuple[VerificationFailure, ...]` | Coded policy violations |
| `measurements` | `dict[str, object]` | Metadata, coverage, and tracking metrics |
| `evidence_paths` | `dict[str, Path]` | Every generated file, by name |

```python
result.to_dict()          # JSON-ready document, same as summary.json
result.raise_for_failure() # raises VerificationFailedError when failed
```

### Using it as a test assertion

```python
from visual_verifier import verify_video


def test_every_frame_is_anonymized() -> None:
    result = verify_video("fixtures/source.mp4", "build/anonymized.mp4")
    result.raise_for_failure()
```

## Configuration

Both configuration objects are frozen dataclasses that validate on
construction, so an invalid threshold fails immediately rather than
producing a misleading result.

```python
from visual_verifier import ConfigurationError, DetectionConfig, TrackingConfig

config = DetectionConfig(
    diff_threshold=30,
    min_box_area=80,
    min_changed_ratio=0.03,
    min_mean_diff=5.0,
    min_severity_score=8.0,
)

tracking = TrackingConfig(
    association_iou_threshold=0.20,
    minimum_confirmation_hits=2,
    maximum_gap_frames=3,
    lineage_overlap_threshold=0.20,
)

try:
    DetectionConfig(min_box_area=-1)
except ConfigurationError as error:
    print(error.error_code)              # "CONFIGURATION_ERROR"
    print(error.context_dict["invalid_fields"])  # ["min_box_area"]
```

## Errors

Every error raised by the package derives from `VisualVerifierError` and
carries a stable `error_code` plus serializable context.

| Exception | `error_code` |
| --- | --- |
| `ConfigurationError` | `CONFIGURATION_ERROR` |
| `MediaReadError` | `MEDIA_READ_ERROR` |
| `MediaCompatibilityError` | `MEDIA_COMPATIBILITY_ERROR` |
| `ReportWriteError` | `REPORT_WRITE_ERROR` |
| `PolicyEvaluationError` | `POLICY_EVALUATION_ERROR` |
| `TargetValidationError` | `TARGET_VALIDATION_ERROR` |
| `VerificationFailedError` | `VERIFICATION_FAILED` |

```python
from visual_verifier import VisualVerifierError, verify_video

try:
    result = verify_video("raw.mp4", "missing.mp4")
except VisualVerifierError as error:
    print(error.error_code)
    print(error.to_dict())   # {"error_code": ..., "message": ..., "context": {...}}
```

## Verifying reviewed targets

Supplying targets changes the question from *did anything change* to
*did the required region change*, and can therefore change the verdict.
Everything else about the call is unchanged.

```python
from visual_verifier import verify_video

result = verify_video(
    reference="raw.mp4",
    candidate="anonymized.mp4",
    targets="plates.csv",
    output_dir="outputs/check",
)

print(result.policy_name)  # "target_coverage_every_frame"

targets = result.measurements["targets"]
print(targets["target_coverage_percent"])

for summary in targets["target_summaries"]:
    print(summary["target_id"], summary["uncovered_frames"])
```

Targets can also be built in memory, which is useful when they come from
a review tool rather than a file:

```python
from visual_verifier import BoundingBox, Target, verify_video

targets = [
    Target(
        frame_number=frame,
        target_id="PLATE_A",
        box=BoundingBox(x1=608, y1=502, x2=670, y2=527),
        target_type="plate",
    )
    for frame in range(1, 16)
]

result = verify_video("raw.mp4", "out.mp4", targets=targets)
```

`TargetConfig` controls how strictly coverage is judged and how far
interpolation may reach:

```python
from visual_verifier import TargetConfig, verify_video

result = verify_video(
    "raw.mp4",
    "out.mp4",
    targets="plates.csv",
    target_config=TargetConfig(
        min_covered_ratio=0.95,
        max_interpolation_gap=3,
        fail_on_uncovered_target=False,
    ),
)
```

An invalid target file raises `TargetValidationError` before any media
is read, with the offending line number in its context. See
[Target annotation](target_annotation.md).

## Reading tracking metrics

```python
tracking = result.measurements["tracking"]

print(tracking["track_count"])
print(tracking["mean_continuity_ratio"])

for summary in tracking["track_summaries"]:
    print(
        summary["track_label"],
        summary["continuity_ratio"],
        summary["missing_frames"],
    )
```

Field meanings are documented in [Output schema](output_schema.md) and
[Temporal tracking](temporal_tracking.md).

## Running the demonstration from Python

```python
from visual_verifier.demo import run_demonstration

demonstration = run_demonstration("visual-verifier-demo")
print(demonstration.verification_result.failed_frames)  # (4, 8, 12)
print(demonstration.behaved_as_documented)              # True
```
