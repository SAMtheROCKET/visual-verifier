"""Provide the command-line interface for Visual Verifier."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from visual_verifier import __version__
from visual_verifier.api import verify_image, verify_video
from visual_verifier.config.tracking import TrackingConfig
from visual_verifier.media.metadata import (
    read_image_metadata,
    read_video_metadata,
)
from visual_verifier.models import MediaMetadata, VerificationResult

EXIT_SUCCESS_INT = 0
EXIT_EXECUTION_ERROR_INT = 1
EXIT_VERIFICATION_FAILED_INT = 2
DOCTOR_DIVIDER_TEXT = "=" * 40
VIDEO_SUFFIXES_FROZENSET = frozenset({".mp4", ".avi", ".mov", ".mkv", ".webm"})


def run_doctor() -> int:
    """Print dependency and platform information."""

    print("Visual Verifier environment check")
    print(DOCTOR_DIVIDER_TEXT)
    print(f"Visual Verifier: {__version__}")
    print(f"Python:          {platform.python_version()}")
    print(f"Platform:        {platform.platform()}")
    print(f"OpenCV:          {cv2.__version__}")
    print(f"NumPy:           {np.__version__}")
    print(f"pandas:          {pd.__version__}")
    print()
    print("Environment status: OK")
    return EXIT_SUCCESS_INT


def run_inspect(arguments_namespace: argparse.Namespace) -> int:
    """Inspect one media file and print normalized metadata."""

    metadata_obj = _read_requested_metadata(arguments_namespace.path)
    _print_json(metadata_obj.to_dict())
    return EXIT_SUCCESS_INT


def run_image(arguments_namespace: argparse.Namespace) -> int:
    """Verify one processed image and print the result."""

    result_obj = verify_image(
        arguments_namespace.reference,
        arguments_namespace.candidate,
        output_dir=arguments_namespace.output,
        expect_processing=not arguments_namespace.allow_no_processing,
    )
    _print_verification_result(result_obj)
    return _verification_exit_code(result_obj)


def run_video(arguments_namespace: argparse.Namespace) -> int:
    """Verify one processed video and print temporal evidence."""

    result_obj = verify_video(
        arguments_namespace.reference,
        arguments_namespace.candidate,
        output_dir=arguments_namespace.output,
        expect_processing_every_frame=(
            not arguments_namespace.allow_unprocessed_frames
        ),
        save_annotated_video=(not arguments_namespace.no_annotated_video),
        enable_tracking=(not arguments_namespace.no_tracking),
        tracking_config=_build_tracking_config(arguments_namespace),
    )
    _print_verification_result(result_obj)
    return _verification_exit_code(result_obj)


def _build_tracking_config(
    arguments_namespace: argparse.Namespace,
) -> TrackingConfig:
    """Build validated tracking settings from video CLI arguments."""

    return TrackingConfig(
        association_iou_threshold=arguments_namespace.tracking_iou,
        minimum_confirmation_hits=(
            arguments_namespace.tracking_confirmation_hits
        ),
        maximum_gap_frames=arguments_namespace.tracking_max_gap,
        lineage_overlap_threshold=(arguments_namespace.lineage_overlap),
        detect_lineage_events=(not arguments_namespace.no_lineage_events),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the complete command-line argument parser."""

    parser_obj = argparse.ArgumentParser(
        prog="visual-verifier",
        description=(
            "Reference-based QA for processed image and video media."
        ),
    )
    parser_obj.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers_action = parser_obj.add_subparsers(
        dest="command",
        required=True,
    )
    _add_doctor_parser(subparsers_action)
    _add_inspect_parser(subparsers_action)
    _add_image_parser(subparsers_action)
    _add_video_parser(subparsers_action)
    return parser_obj


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Visual Verifier command-line interface."""

    parser_obj = build_parser()
    arguments_namespace = parser_obj.parse_args(argv)
    try:
        return _dispatch_command(arguments_namespace, parser_obj)
    except Exception as error_obj:
        print(f"ERROR: {error_obj}", file=sys.stderr)
        return EXIT_EXECUTION_ERROR_INT


def _dispatch_command(
    arguments_namespace: argparse.Namespace,
    parser_obj: argparse.ArgumentParser,
) -> int:
    """Dispatch parsed arguments to the requested command handler."""

    command_str = str(arguments_namespace.command)
    if command_str == "doctor":
        return run_doctor()
    if command_str == "inspect":
        return run_inspect(arguments_namespace)
    if command_str == "image":
        return run_image(arguments_namespace)
    if command_str == "video":
        return run_video(arguments_namespace)
    parser_obj.print_help()
    return EXIT_EXECUTION_ERROR_INT


def _read_requested_metadata(path_input: str) -> MediaMetadata:
    """Read image or video metadata based on the filename suffix."""

    if _suffix_from_path(path_input) in VIDEO_SUFFIXES_FROZENSET:
        return read_video_metadata(path_input)
    return read_image_metadata(path_input)


def _suffix_from_path(path_input: str) -> str:
    """Return a lowercase filename suffix without resolving the path."""

    return Path(path_input).suffix.lower()


def _print_verification_result(result_obj: VerificationResult) -> None:
    """Print one verification result as formatted JSON."""

    _print_json(result_obj.to_dict())


def _print_json(payload_mapping: Mapping[str, object]) -> None:
    """Print a mapping as consistently formatted JSON."""

    print(json.dumps(payload_mapping, indent=2, default=str))


def _verification_exit_code(result_obj: VerificationResult) -> int:
    """Convert a verification result into a process exit code."""

    if result_obj.passed:
        return EXIT_SUCCESS_INT
    return EXIT_VERIFICATION_FAILED_INT


def _add_doctor_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the environment-check command parser."""

    subparsers_action.add_parser(
        "doctor",
        help="Check the local environment.",
    )


def _add_inspect_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the media-inspection command parser."""

    inspect_parser_obj = subparsers_action.add_parser(
        "inspect",
        help="Inspect media metadata.",
    )
    inspect_parser_obj.add_argument("path")


def _add_image_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the image-verification command parser."""

    image_parser_obj = subparsers_action.add_parser(
        "image",
        help="Verify one processed image.",
    )
    image_parser_obj.add_argument("--reference", required=True)
    image_parser_obj.add_argument("--candidate", required=True)
    image_parser_obj.add_argument("--output", required=True)
    image_parser_obj.add_argument(
        "--allow-no-processing",
        action="store_true",
    )


def _add_video_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add video verification and temporal tracking arguments."""

    video_parser_obj = subparsers_action.add_parser(
        "video",
        help="Verify one processed video with temporal tracking.",
    )
    video_parser_obj.add_argument("--reference", required=True)
    video_parser_obj.add_argument("--candidate", required=True)
    video_parser_obj.add_argument("--output", required=True)
    video_parser_obj.add_argument(
        "--allow-unprocessed-frames",
        action="store_true",
    )
    video_parser_obj.add_argument(
        "--no-annotated-video",
        action="store_true",
    )
    video_parser_obj.add_argument("--no-tracking", action="store_true")
    _add_tracking_threshold_arguments(video_parser_obj)


def _add_tracking_threshold_arguments(
    video_parser_obj: argparse.ArgumentParser,
) -> None:
    """Add temporal association and lifecycle threshold arguments."""

    video_parser_obj.add_argument(
        "--tracking-iou",
        type=float,
        default=0.20,
    )
    video_parser_obj.add_argument(
        "--tracking-confirmation-hits",
        type=int,
        default=2,
    )
    video_parser_obj.add_argument(
        "--tracking-max-gap",
        type=int,
        default=3,
    )
    video_parser_obj.add_argument(
        "--lineage-overlap",
        type=float,
        default=0.20,
    )
    video_parser_obj.add_argument(
        "--no-lineage-events",
        action="store_true",
    )


__all__ = [
    "build_parser",
    "main",
    "run_doctor",
    "run_image",
    "run_inspect",
    "run_video",
]


if __name__ == "__main__":
    raise SystemExit(main())
