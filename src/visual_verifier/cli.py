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
    """Print dependency and platform information.

    Returns:
        Successful process exit code.
    """

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
    """Inspect one media file and print normalized metadata.

    Args:
        arguments_namespace: Parsed command-line arguments.

    Returns:
        Successful process exit code.

    Raises:
        MediaReadError: When the media file cannot be decoded.
    """

    metadata_obj = _read_requested_metadata(arguments_namespace.path)
    _print_json(metadata_obj.to_dict())
    return EXIT_SUCCESS_INT


def run_image(arguments_namespace: argparse.Namespace) -> int:
    """Verify one processed image and print the result.

    Args:
        arguments_namespace: Parsed command-line arguments.

    Returns:
        Zero for PASS or two for a completed verification failure.

    Raises:
        VisualVerifierError: When image verification cannot be completed.
    """

    result_obj = verify_image(
        arguments_namespace.reference,
        arguments_namespace.candidate,
        output_dir=arguments_namespace.output,
        expect_processing=not arguments_namespace.allow_no_processing,
    )
    _print_verification_result(result_obj)
    return _verification_exit_code(result_obj)


def run_video(arguments_namespace: argparse.Namespace) -> int:
    """Verify one processed video and print the result.

    Args:
        arguments_namespace: Parsed command-line arguments.

    Returns:
        Zero for PASS or two for a completed verification failure.

    Raises:
        VisualVerifierError: When video verification cannot be completed.
    """

    result_obj = verify_video(
        arguments_namespace.reference,
        arguments_namespace.candidate,
        output_dir=arguments_namespace.output,
        expect_processing_every_frame=(
            not arguments_namespace.allow_unprocessed_frames
        ),
        save_annotated_video=(not arguments_namespace.no_annotated_video),
    )
    _print_verification_result(result_obj)
    return _verification_exit_code(result_obj)


def build_parser() -> argparse.ArgumentParser:
    """Build the complete command-line argument parser.

    Returns:
        Configured top-level argument parser.
    """

    parser_obj = argparse.ArgumentParser(
        prog="visual-verifier",
        description=(
            "Policy-based QA for image and video processing pipelines."
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
    """Run the Visual Verifier command-line interface.

    Args:
        argv: Optional argument sequence excluding the executable name.

    Returns:
        Process exit code: zero for PASS, one for execution errors, and two
        for completed verification failures.

    Warning:
        Unexpected exceptions are converted to a concise stderr message so
        the CLI remains suitable for shell scripts and CI jobs.
    """

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
    """Dispatch parsed arguments to the requested command handler.

    Args:
        arguments_namespace: Parsed command-line arguments.
        parser_obj: Top-level parser used for fallback help output.

    Returns:
        Command-specific process exit code.
    """

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
    """Read image or video metadata based on the filename suffix.

    Args:
        path_input: Media path supplied through the command line.

    Returns:
        Normalized media metadata.

    Raises:
        MediaReadError: When the media cannot be decoded.
    """

    suffix_str = _suffix_from_path(path_input)
    if suffix_str in VIDEO_SUFFIXES_FROZENSET:
        return read_video_metadata(path_input)
    return read_image_metadata(path_input)


def _suffix_from_path(path_input: str) -> str:
    """Return a lowercase filename suffix without resolving the path.

    Args:
        path_input: Media path supplied through the command line.

    Returns:
        Lowercase suffix including its leading period.
    """

    return Path(path_input).suffix.lower()


def _print_verification_result(result_obj: VerificationResult) -> None:
    """Print one verification result as formatted JSON.

    Args:
        result_obj: Completed verification result.
    """

    _print_json(result_obj.to_dict())


def _print_json(payload_mapping: Mapping[str, object]) -> None:
    """Print a mapping as consistently formatted JSON.

    Args:
        payload_mapping: Serializable mapping to print.
    """

    print(json.dumps(payload_mapping, indent=2, default=str))


def _verification_exit_code(result_obj: VerificationResult) -> int:
    """Convert a verification result into a process exit code.

    Args:
        result_obj: Completed verification result.

    Returns:
        Zero for PASS or two for FAIL and ERROR results.
    """

    if result_obj.passed:
        return EXIT_SUCCESS_INT
    return EXIT_VERIFICATION_FAILED_INT


def _add_doctor_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the environment-check command parser.

    Args:
        subparsers_action: Parent subparser collection.
    """

    subparsers_action.add_parser(
        "doctor",
        help="Check the local environment.",
    )


def _add_inspect_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the media-inspection command parser.

    Args:
        subparsers_action: Parent subparser collection.
    """

    inspect_parser_obj = subparsers_action.add_parser(
        "inspect",
        help="Inspect media metadata.",
    )
    inspect_parser_obj.add_argument("path")


def _add_image_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the image-verification command parser.

    Args:
        subparsers_action: Parent subparser collection.
    """

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
    """Add the video-verification command parser.

    Args:
        subparsers_action: Parent subparser collection.
    """

    video_parser_obj = subparsers_action.add_parser(
        "video",
        help="Verify one processed video.",
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
