"""Expose supported Visual Verifier configuration interfaces."""

from visual_verifier.config.defaults import DEFAULT_DETECTION_CONFIG
from visual_verifier.models import DetectionConfig

__all__ = [
    "DEFAULT_DETECTION_CONFIG",
    "DetectionConfig",
]
