"""Expose the stable Python entry points for Visual Verifier."""

from __future__ import annotations

from visual_verifier.config.defaults import DEFAULT_DETECTION_CONFIG
from visual_verifier.config.tracking import (
    DEFAULT_TRACKING_CONFIG,
    TrackingConfig,
)
from visual_verifier.models import DetectionConfig, VerificationResult
from visual_verifier.pipeline.image_pipeline import verify_image_pipeline
from visual_verifier.pipeline.video_pipeline import verify_video_pipeline
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
    config: DetectionConfig = DEFAULT_DETECTION_CONFIG,
    enable_tracking: bool = True,
    tracking_config: TrackingConfig = DEFAULT_TRACKING_CONFIG,
) -> VerificationResult:
    """Verify one candidate video and produce temporal integrity evidence.

    Args:
        reference: Path to the original video.
        candidate: Path to the processed video being verified.
        output_dir: Optional directory for reports and annotated evidence.
        expect_processing_every_frame: Require an accepted changed region
            in every synchronized frame.
        save_annotated_video: Write annotated MP4 evidence when output is set.
        config: Region-detection and severity thresholds.
        enable_tracking: Associate accepted regions through time.
        tracking_config: Temporal association and lifecycle settings.

    Returns:
        Immutable verification result containing frame and track evidence.
    """

    return verify_video_pipeline(
        reference,
        candidate,
        output_dir=output_dir,
        expect_processing_every_frame=expect_processing_every_frame,
        save_annotated_video=save_annotated_video,
        config=config,
        enable_tracking=enable_tracking,
        tracking_config=tracking_config,
    )


__all__ = [
    "verify_image",
    "verify_video",
]
