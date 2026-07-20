"""Expose stable media utilities for Visual Verifier."""

from visual_verifier.media.metadata import (
    read_image_metadata,
    read_video_metadata,
)
from visual_verifier.media.normalization import (
    get_spatial_dimensions,
    have_matching_spatial_dimensions,
    resize_candidate_to_reference,
    resize_image,
)
from visual_verifier.media.video_reader import iter_video_pairs

__all__ = [
    "get_spatial_dimensions",
    "have_matching_spatial_dimensions",
    "iter_video_pairs",
    "read_image_metadata",
    "read_video_metadata",
    "resize_candidate_to_reference",
    "resize_image",
]
