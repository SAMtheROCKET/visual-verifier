"""Central type aliases shared across the Visual Verifier package."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

ImageArray: TypeAlias = NDArray[np.uint8]
"""Three-channel or single-channel unsigned 8-bit image array."""

MaskArray: TypeAlias = NDArray[np.uint8]
"""Single-channel unsigned 8-bit binary or grayscale mask array."""

PathInput: TypeAlias = str | Path
"""Filesystem path accepted from either Python or command-line callers."""

ReportRow: TypeAlias = dict[str, object]
"""One machine-readable row written to a CSV or tabular report."""

VideoFramePair: TypeAlias = tuple[int, ImageArray, ImageArray]
"""Frame number, reference frame, and candidate frame tuple."""

__all__ = [
    "ImageArray",
    "MaskArray",
    "PathInput",
    "ReportRow",
    "VideoFramePair",
]
