"""Expose the stable public interface for the Visual Verifier package.

Application code should import verification functions and result models from
this module rather than depending on internal pipeline implementations.
"""

from __future__ import annotations

from typing import Final

from visual_verifier.api import verify_image, verify_video
from visual_verifier.models import VerificationResult, VerificationStatus

__version__: Final[str] = "0.1.0a0"

__all__ = [
    "VerificationResult",
    "VerificationStatus",
    "__version__",
    "verify_image",
    "verify_video",
]
