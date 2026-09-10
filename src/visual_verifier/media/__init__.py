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
from visual_verifier.media.video_writer import (
    find_supported_codec,
    open_annotated_writer,
)

__all__ = [
    "find_supported_codec",
    "get_spatial_dimensions",
    "have_matching_spatial_dimensions",
    "iter_video_pairs",
    "open_annotated_writer",
    "read_image_metadata",
    "read_video_metadata",
    "resize_candidate_to_reference",
    "resize_image",
]
