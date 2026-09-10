"""Expose the stable public interface for the Visual Verifier package.

Application code should import verification functions, configuration
objects, result models, and structured errors from this module rather than
depending on internal pipeline implementations.
"""

from __future__ import annotations

from typing import Final

from visual_verifier.api import verify_image, verify_video
from visual_verifier.config.defaults import DEFAULT_DETECTION_CONFIG
from visual_verifier.config.targets import (
    DEFAULT_TARGET_CONFIG,
    TargetConfig,
)
from visual_verifier.config.tracking import (
    DEFAULT_TRACKING_CONFIG,
    TrackingConfig,
)
from visual_verifier.exceptions import (
    ConfigurationError,
    MediaCompatibilityError,
    MediaReadError,
    PolicyEvaluationError,
    ReportWriteError,
    TargetValidationError,
    VerificationFailedError,
    VisualVerifierError,
)
from visual_verifier.models import (
    BoundingBox,
    DetectionConfig,
    FrameVerification,
    MediaMetadata,
    RegionMeasurement,
    VerificationFailure,
    VerificationResult,
    VerificationStatus,
)
from visual_verifier.targets.models import (
    Target,
    TargetCoverage,
    TargetSource,
    TargetSummary,
)

__version__: Final[str] = "0.3.0"

__all__ = [
    "DEFAULT_DETECTION_CONFIG",
    "DEFAULT_TARGET_CONFIG",
    "DEFAULT_TRACKING_CONFIG",
    "BoundingBox",
    "ConfigurationError",
    "DetectionConfig",
    "FrameVerification",
    "MediaCompatibilityError",
    "MediaMetadata",
    "MediaReadError",
    "PolicyEvaluationError",
    "RegionMeasurement",
    "ReportWriteError",
    "Target",
    "TargetConfig",
    "TargetCoverage",
    "TargetSource",
    "TargetSummary",
    "TargetValidationError",
    "TrackingConfig",
    "VerificationFailedError",
    "VerificationFailure",
    "VerificationResult",
    "VerificationStatus",
    "VisualVerifierError",
    "__version__",
    "verify_image",
    "verify_video",
]
