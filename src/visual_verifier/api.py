"""Expose the stable Python entry points for Visual Verifier."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from visual_verifier.config.defaults import DEFAULT_DETECTION_CONFIG
from visual_verifier.config.targets import (
    DEFAULT_TARGET_CONFIG,
    TargetConfig,
)
from visual_verifier.config.tracking import (
    DEFAULT_TRACKING_CONFIG,
    TrackingConfig,
)
from visual_verifier.models import DetectionConfig, VerificationResult
from visual_verifier.pipeline.image_pipeline import verify_image_pipeline
from visual_verifier.pipeline.video_pipeline import verify_video_pipeline
from visual_verifier.targets.loading import load_targets
from visual_verifier.targets.models import Target
from visual_verifier.type_aliases import PathInput


def verify_image(
    reference: PathInput,
    candidate: PathInput,
    *,
    output_dir: PathInput | None = None,
    expect_processing: bool = True,
    config: DetectionConfig = DEFAULT_DETECTION_CONFIG,
) -> VerificationResult:
    """Verify one candidate image against one reference image."""

    return verify_image_pipeline(
        reference,
        candidate,
        output_dir=output_dir,
        expect_processing=expect_processing,
        config=config,
    )


def verify_video(
    reference: PathInput,
    candidate: PathInput,
    *,
    output_dir: PathInput | None = None,
    expect_processing_every_frame: bool = True,
    save_annotated_video: bool = True,
    save_html_report: bool = True,
    config: DetectionConfig = DEFAULT_DETECTION_CONFIG,
    enable_tracking: bool = True,
    tracking_config: TrackingConfig = DEFAULT_TRACKING_CONFIG,
    targets: PathInput | Sequence[Target] | None = None,
    target_config: TargetConfig = DEFAULT_TARGET_CONFIG,
) -> VerificationResult:
    """Verify one candidate video and produce temporal integrity evidence.

    Args:
        reference: Path to the original video.
        candidate: Path to the processed video being verified.
        output_dir: Optional directory for reports and annotated evidence.
        expect_processing_every_frame: Require change in every frame.
        save_annotated_video: Write annotated MP4 evidence when set.
        save_html_report: Write ``index.html`` when output is set.
        config: Region-detection and severity thresholds.
        enable_tracking: Associate accepted regions through time.
        tracking_config: Temporal association and lifecycle settings.
        targets: Reviewed targets that must be anonymized, as a target
            CSV path or a loaded sequence. These can change the verdict.
        target_config: Target coverage and interpolation settings.

    Returns:
        Immutable verification result containing frame and track evidence.

    Raises:
        TargetValidationError: When a target file cannot be loaded.
    """

    return verify_video_pipeline(
        reference,
        candidate,
        output_dir=output_dir,
        expect_processing_every_frame=expect_processing_every_frame,
        save_annotated_video=save_annotated_video,
        save_html_report=save_html_report,
        config=config,
        enable_tracking=enable_tracking,
        tracking_config=tracking_config,
        targets=_resolve_targets(targets),
        target_config=target_config,
    )


def _resolve_targets(
    targets: PathInput | Sequence[Target] | None,
) -> tuple[Target, ...]:
    """Accept either a target file path or already-loaded targets.

    Args:
        targets: Path to a target CSV file, a sequence of targets, or
            ``None``.

    Returns:
        The targets to verify against, empty when none were supplied.

    Raises:
        TargetValidationError: When a supplied file cannot be loaded.
    """

    if targets is None:
        return ()
    if isinstance(targets, str | Path):
        return load_targets(targets)
    return tuple(targets)


__all__ = [
    "verify_image",
    "verify_video",
]
