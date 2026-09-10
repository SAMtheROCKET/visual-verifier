"""Provide the command-line interface for Visual Verifier."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from visual_verifier import __version__
from visual_verifier.api import verify_image, verify_video
from visual_verifier.config.defaults import DEFAULT_DETECTION_CONFIG
from visual_verifier.config.tracking import (
    DEFAULT_TRACKING_CONFIG,
    TrackingConfig,
)
from visual_verifier.demo import DemonstrationResult, run_demonstration
from visual_verifier.exceptions import VisualVerifierError
from visual_verifier.media.metadata import (
    read_image_metadata,
    read_video_metadata,
)
from visual_verifier.media.video_writer import find_supported_codec
from visual_verifier.models import (
    DetectionConfig,
    MediaMetadata,
    VerificationResult,
)
from visual_verifier.reporting.console import format_verification_summary


@dataclass(frozen=True, slots=True)
class _NumericArgumentSpec:
    """Describe one numeric threshold argument shared by subcommands.

    Attributes:
        flag_text: Long option string, such as ``--min-severity``.
        value_type: Converter applied to the raw command-line string.
        default_value: Value taken from the shipped configuration object.
        metavar_text: Placeholder shown in help output.
        help_text: Sentence describing the threshold.
    """

    flag_text: str
    value_type: type[int] | type[float]
    default_value: int | float
    metavar_text: str
    help_text: str


EXIT_SUCCESS_INT = 0
EXIT_EXECUTION_ERROR_INT = 1
EXIT_VERIFICATION_FAILED_INT = 2
DOCTOR_DIVIDER_TEXT = "=" * 40
VIDEO_SUFFIXES_FROZENSET = frozenset({".mp4", ".avi", ".mov", ".mkv", ".webm"})
MISSING_CODEC_TEXT = "unavailable"
HEALTHY_STATUS_TEXT = "Environment status: OK"
DEMO_INTRODUCTION_TEXT = (
    "Generating a synthetic 15-frame clip in which a licence plate is\n"
    "blurred on every frame except 4, 8, and 12, then verifying it.\n"
    "Nothing is downloaded and nothing leaves this machine.\n"
)
DEMO_SUCCESS_TEXT = (
    "The demonstration behaved as documented: the three unprocessed "
    "frames were found."
)
DEMO_UNEXPECTED_TEXT = (
    "The demonstration did not reproduce the documented result. Please "
    "report this with the output of `visual-verifier doctor`."
)
DEGRADED_STATUS_TEXT = (
    "Environment status: DEGRADED - verification works, but annotated "
    "video evidence cannot be written by this OpenCV build."
)
DETECTION_ARGUMENT_SPECS_TUPLE: tuple[_NumericArgumentSpec, ...] = (
    _NumericArgumentSpec(
        "--diff-threshold",
        int,
        DEFAULT_DETECTION_CONFIG.diff_threshold,
        "INT",
        "Absolute per-pixel difference required to mark a pixel as "
        "changed (default: %(default)s).",
    ),
    _NumericArgumentSpec(
        "--min-box-area",
        int,
        DEFAULT_DETECTION_CONFIG.min_box_area,
        "INT",
        "Smallest accepted region area (default: %(default)s px).",
    ),
    _NumericArgumentSpec(
        "--min-changed-ratio",
        float,
        DEFAULT_DETECTION_CONFIG.min_changed_ratio,
        "FLOAT",
        "Smallest accepted changed-pixel ratio inside a region "
        "(default: %(default)s).",
    ),
    _NumericArgumentSpec(
        "--min-mean-diff",
        float,
        DEFAULT_DETECTION_CONFIG.min_mean_diff,
        "FLOAT",
        "Smallest accepted mean intensity difference inside a region "
        "(default: %(default)s).",
    ),
    _NumericArgumentSpec(
        "--min-severity",
        float,
        DEFAULT_DETECTION_CONFIG.min_severity_score,
        "FLOAT",
        "Smallest accepted region severity score from 0 to 100 "
        "(default: %(default)s).",
    ),
)
TRACKING_ARGUMENT_SPECS_TUPLE: tuple[_NumericArgumentSpec, ...] = (
    _NumericArgumentSpec(
        "--tracking-iou",
        float,
        DEFAULT_TRACKING_CONFIG.association_iou_threshold,
        "FLOAT",
        "Minimum intersection-over-union used to associate a region "
        "with an active track (default: %(default)s).",
    ),
    _NumericArgumentSpec(
        "--tracking-confirmation-hits",
        int,
        DEFAULT_TRACKING_CONFIG.minimum_confirmation_hits,
        "INT",
        "Observations required before a tentative track is confirmed "
        "(default: %(default)s).",
    ),
    _NumericArgumentSpec(
        "--tracking-max-gap",
        int,
        DEFAULT_TRACKING_CONFIG.maximum_gap_frames,
        "INT",
        "Consecutive missing frames tolerated before a track closes "
        "(default: %(default)s).",
    ),
    _NumericArgumentSpec(
        "--lineage-overlap",
        float,
        DEFAULT_TRACKING_CONFIG.lineage_overlap_threshold,
        "FLOAT",
        "Minimum overlap used to detect split and merge lineage "
        "events (default: %(default)s).",
    ),
)
CLI_DESCRIPTION_TEXT = (
    "Reference-based QA for processed image and video media. Visual "
    "Verifier compares an original reference with a processed candidate "
    "and returns deterministic PASS/FAIL evidence."
)
CLI_EPILOG_TEXT = (
    "exit codes:\n"
    "  0  verification completed and passed\n"
    "  1  verification could not be completed\n"
    "  2  verification completed and failed\n"
    "\n"
    "examples:\n"
    "  visual-verifier doctor\n"
    "  visual-verifier inspect examples/media/video_raw.mp4\n"
    "  visual-verifier video --reference raw.mp4 --candidate blurred.mp4\n"
    "  visual-verifier video --reference raw.mp4 --candidate out.mp4 "
    "--output outputs/run --json\n"
)


def run_doctor() -> int:
    """Print dependency, platform, and codec capability information.

    Annotated-video output is the only capability that depends on how
    OpenCV was built, so the check probes it rather than assuming it.

    Returns:
        Process exit code. Always ``0``; a missing codec is reported as a
        degraded environment because verification itself still works.
    """

    supported_codec_str = find_supported_codec()
    print("Visual Verifier environment check")
    print(DOCTOR_DIVIDER_TEXT)
    print(f"Visual Verifier: {__version__}")
    print(f"Python:          {platform.python_version()}")
    print(f"Platform:        {platform.platform()}")
    print(f"OpenCV:          {cv2.__version__}")
    print(f"NumPy:           {np.__version__}")
    print(f"pandas:          {pd.__version__}")
    print(f"Video codec:     {supported_codec_str or MISSING_CODEC_TEXT}")
    print()
    if supported_codec_str is None:
        print(DEGRADED_STATUS_TEXT)
    else:
        print(HEALTHY_STATUS_TEXT)
    return EXIT_SUCCESS_INT


def run_demo(arguments_namespace: argparse.Namespace) -> int:
    """Generate a sample anonymization failure and verify it.

    Args:
        arguments_namespace: Parsed ``demo`` command arguments.

    Returns:
        Process exit code. ``0`` when the demonstration found exactly the
        gaps it created, and ``1`` when it did not.
    """

    print("Visual Verifier demonstration")
    print(DOCTOR_DIVIDER_TEXT)
    print(DEMO_INTRODUCTION_TEXT)
    demonstration_obj = run_demonstration(arguments_namespace.output)
    print(format_verification_summary(demonstration_obj.verification_result))
    print()
    if not demonstration_obj.behaved_as_documented:
        print(DEMO_UNEXPECTED_TEXT, file=sys.stderr)
        return EXIT_EXECUTION_ERROR_INT
    print(DEMO_SUCCESS_TEXT)
    _print_demonstration_reproduction(demonstration_obj)
    return EXIT_SUCCESS_INT


def _print_demonstration_reproduction(
    demonstration_obj: DemonstrationResult,
) -> None:
    """Print the exact command that reproduces the demonstration.

    Args:
        demonstration_obj: Completed demonstration and its artefact paths.
    """

    print()
    print("Reproduce it yourself:")
    print("  visual-verifier video \\")
    print(f"      --reference {demonstration_obj.reference_path} \\")
    print(f"      --candidate {demonstration_obj.candidate_path} \\")
    print(f"      --output {demonstration_obj.report_directory}")


def run_inspect(arguments_namespace: argparse.Namespace) -> int:
    """Inspect one media file and print normalized metadata.

    Args:
        arguments_namespace: Parsed ``inspect`` command arguments.

    Returns:
        Process exit code for the completed inspection.
    """

    metadata_obj = _read_requested_metadata(arguments_namespace.path)
    _print_json(metadata_obj.to_dict())
    return EXIT_SUCCESS_INT


def run_image(arguments_namespace: argparse.Namespace) -> int:
    """Verify one processed image and report the result.

    Args:
        arguments_namespace: Parsed ``image`` command arguments.

    Returns:
        Process exit code derived from the verification status.
    """

    result_obj = verify_image(
        arguments_namespace.reference,
        arguments_namespace.candidate,
        output_dir=arguments_namespace.output,
        expect_processing=not arguments_namespace.allow_no_processing,
        config=_build_detection_config(arguments_namespace),
    )
    _emit_verification_result(result_obj, arguments_namespace)
    return _verification_exit_code(result_obj)


def run_video(arguments_namespace: argparse.Namespace) -> int:
    """Verify one processed video and report temporal evidence.

    Args:
        arguments_namespace: Parsed ``video`` command arguments.

    Returns:
        Process exit code derived from the verification status.
    """

    result_obj = verify_video(
        arguments_namespace.reference,
        arguments_namespace.candidate,
        output_dir=arguments_namespace.output,
        expect_processing_every_frame=(
            not arguments_namespace.allow_unprocessed_frames
        ),
        save_annotated_video=(not arguments_namespace.no_annotated_video),
        save_html_report=(not arguments_namespace.no_html_report),
        config=_build_detection_config(arguments_namespace),
        enable_tracking=(not arguments_namespace.no_tracking),
        tracking_config=_build_tracking_config(arguments_namespace),
    )
    _emit_verification_result(result_obj, arguments_namespace)
    return _verification_exit_code(result_obj)


def _build_detection_config(
    arguments_namespace: argparse.Namespace,
) -> DetectionConfig:
    """Build validated detection thresholds from shared CLI arguments.

    Args:
        arguments_namespace: Parsed verification-command arguments.

    Returns:
        Immutable detection configuration for the requested run.

    Raises:
        ConfigurationError: When a supplied threshold is invalid.
    """

    return DetectionConfig(
        diff_threshold=arguments_namespace.diff_threshold,
        min_box_area=arguments_namespace.min_box_area,
        min_changed_ratio=arguments_namespace.min_changed_ratio,
        min_mean_diff=arguments_namespace.min_mean_diff,
        min_severity_score=arguments_namespace.min_severity,
    )


def _build_tracking_config(
    arguments_namespace: argparse.Namespace,
) -> TrackingConfig:
    """Build validated tracking settings from video CLI arguments.

    Args:
        arguments_namespace: Parsed ``video`` command arguments.

    Returns:
        Immutable temporal tracking configuration for the requested run.

    Raises:
        ConfigurationError: When a supplied threshold is invalid.
    """

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
    """Build the complete command-line argument parser.

    Returns:
        Parser exposing the doctor, inspect, image, and video commands.
    """

    parser_obj = argparse.ArgumentParser(
        prog="visual-verifier",
        description=CLI_DESCRIPTION_TEXT,
        epilog=CLI_EPILOG_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser_obj.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Print the installed Visual Verifier version and exit.",
    )
    subparsers_action = parser_obj.add_subparsers(
        dest="command",
        metavar="command",
        required=True,
        help="Verification and diagnostic command to run.",
    )
    _add_doctor_parser(subparsers_action)
    _add_demo_parser(subparsers_action)
    _add_inspect_parser(subparsers_action)
    _add_image_parser(subparsers_action)
    _add_video_parser(subparsers_action)
    return parser_obj


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Visual Verifier command-line interface.

    Args:
        argv: Optional argument vector. Defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code. ``0`` passed, ``1`` execution error, and ``2``
        verification failed.
    """

    parser_obj = build_parser()
    arguments_namespace = parser_obj.parse_args(argv)
    try:
        return _dispatch_command(arguments_namespace, parser_obj)
    except VisualVerifierError as domain_error_obj:
        _print_structured_error(domain_error_obj)
        return EXIT_EXECUTION_ERROR_INT
    except Exception as unexpected_error_obj:
        _print_unexpected_error(unexpected_error_obj)
        return EXIT_EXECUTION_ERROR_INT


def _dispatch_command(
    arguments_namespace: argparse.Namespace,
    parser_obj: argparse.ArgumentParser,
) -> int:
    """Dispatch parsed arguments to the requested command handler.

    Args:
        arguments_namespace: Parsed command-line arguments.
        parser_obj: Parser used to print help for unknown commands.

    Returns:
        Process exit code produced by the selected command.
    """

    command_str = str(arguments_namespace.command)
    if command_str == "doctor":
        return run_doctor()
    if command_str == "demo":
        return run_demo(arguments_namespace)
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
        path_input: User-supplied media path.

    Returns:
        Normalized metadata for the inspected media file.
    """

    if _suffix_from_path(path_input) in VIDEO_SUFFIXES_FROZENSET:
        return read_video_metadata(path_input)
    return read_image_metadata(path_input)


def _suffix_from_path(path_input: str) -> str:
    """Return a lowercase filename suffix without resolving the path.

    Args:
        path_input: User-supplied media path.

    Returns:
        Lowercase suffix including the leading dot, or an empty string.
    """

    return Path(path_input).suffix.lower()


def _emit_verification_result(
    result_obj: VerificationResult,
    arguments_namespace: argparse.Namespace,
) -> None:
    """Print one verification result in the requested output format.

    Args:
        result_obj: Completed verification result.
        arguments_namespace: Parsed arguments carrying output options.
    """

    if arguments_namespace.quiet:
        return
    if arguments_namespace.json_output:
        _print_json(result_obj.to_dict())
        return
    print(format_verification_summary(result_obj))


def _print_json(payload_mapping: Mapping[str, object]) -> None:
    """Print a mapping as consistently formatted JSON.

    Args:
        payload_mapping: Serializable payload to print on standard output.
    """

    print(json.dumps(payload_mapping, indent=2, default=str))


def _print_structured_error(error_obj: VisualVerifierError) -> None:
    """Print a structured Visual Verifier error on standard error.

    Args:
        error_obj: Raised domain error carrying a code and context.
    """

    print(
        f"ERROR [{error_obj.error_code}]: {error_obj.message_str}",
        file=sys.stderr,
    )
    for context_name_str, context_value_obj in sorted(
        error_obj.context_dict.items()
    ):
        print(f"  {context_name_str}: {context_value_obj}", file=sys.stderr)


def _print_unexpected_error(error_obj: Exception) -> None:
    """Print an unexpected failure on standard error.

    Args:
        error_obj: Exception raised outside the documented error model.
    """

    print(
        f"ERROR [UNEXPECTED_ERROR] {type(error_obj).__name__}: {error_obj}",
        file=sys.stderr,
    )


def _verification_exit_code(result_obj: VerificationResult) -> int:
    """Convert a verification result into a process exit code.

    Args:
        result_obj: Completed verification result.

    Returns:
        ``0`` when the result passed and ``2`` when it failed.
    """

    if result_obj.passed:
        return EXIT_SUCCESS_INT
    return EXIT_VERIFICATION_FAILED_INT


def _add_doctor_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the environment-check command parser.

    Args:
        subparsers_action: Subparser registry for the root parser.
    """

    subparsers_action.add_parser(
        "doctor",
        help="Check the local environment and print dependency versions.",
    )


def _add_demo_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the self-contained demonstration command parser.

    Args:
        subparsers_action: Subparser registry for the root parser.
    """

    demo_parser_obj = subparsers_action.add_parser(
        "demo",
        help="Generate a sample anonymization failure and verify it.",
    )
    demo_parser_obj.add_argument(
        "--output",
        default=None,
        metavar="DIR",
        help=(
            "Directory for the generated sample media and evidence "
            "(default: ./visual-verifier-demo)."
        ),
    )


def _add_inspect_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the media-inspection command parser.

    Args:
        subparsers_action: Subparser registry for the root parser.
    """

    inspect_parser_obj = subparsers_action.add_parser(
        "inspect",
        help="Print normalized metadata for one image or video file.",
    )
    inspect_parser_obj.add_argument(
        "path",
        help="Path to the image or video file to inspect.",
    )


def _add_image_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add the image-verification command parser.

    Args:
        subparsers_action: Subparser registry for the root parser.
    """

    image_parser_obj = subparsers_action.add_parser(
        "image",
        help="Verify one processed image against its reference.",
    )
    _add_common_verification_arguments(image_parser_obj)
    image_parser_obj.add_argument(
        "--allow-no-processing",
        action="store_true",
        help=(
            "Pass even when no accepted changed region is detected. Use "
            "this when processing is optional for the candidate."
        ),
    )


def _add_video_parser(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Add video verification and temporal tracking arguments.

    Args:
        subparsers_action: Subparser registry for the root parser.
    """

    video_parser_obj = subparsers_action.add_parser(
        "video",
        help="Verify one processed video with temporal tracking evidence.",
    )
    _add_common_verification_arguments(video_parser_obj)
    video_parser_obj.add_argument(
        "--allow-unprocessed-frames",
        action="store_true",
        help=(
            "Pass even when some synchronized frames contain no accepted "
            "changed region."
        ),
    )
    video_parser_obj.add_argument(
        "--no-annotated-video",
        action="store_true",
        help="Skip writing annotated_video.mp4 evidence.",
    )
    video_parser_obj.add_argument(
        "--no-html-report",
        action="store_true",
        help="Skip writing the self-contained index.html report.",
    )
    video_parser_obj.add_argument(
        "--no-tracking",
        action="store_true",
        help="Skip temporal tracking. Frame PASS/FAIL stays unchanged.",
    )
    _add_tracking_threshold_arguments(video_parser_obj)


def _add_common_verification_arguments(
    verification_parser_obj: argparse.ArgumentParser,
) -> None:
    """Add input, output, and detection arguments shared by both commands.

    Args:
        verification_parser_obj: Image or video subcommand parser.
    """

    verification_parser_obj.add_argument(
        "--reference",
        required=True,
        metavar="PATH",
        help="Path to the original, unprocessed reference media.",
    )
    verification_parser_obj.add_argument(
        "--candidate",
        required=True,
        metavar="PATH",
        help="Path to the processed candidate media being verified.",
    )
    verification_parser_obj.add_argument(
        "--output",
        default=None,
        metavar="DIR",
        help=(
            "Directory for reports and annotated evidence. Omit to verify "
            "without writing any files."
        ),
    )
    _add_output_format_arguments(verification_parser_obj)
    _add_detection_threshold_arguments(verification_parser_obj)


def _add_output_format_arguments(
    verification_parser_obj: argparse.ArgumentParser,
) -> None:
    """Add console output-format arguments shared by both commands.

    Args:
        verification_parser_obj: Image or video subcommand parser.
    """

    verification_parser_obj.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print the full machine-readable result as JSON.",
    )
    verification_parser_obj.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress standard output and report only the exit code.",
    )


def _add_detection_threshold_arguments(
    verification_parser_obj: argparse.ArgumentParser,
) -> None:
    """Add region-detection threshold arguments shared by both commands.

    Args:
        verification_parser_obj: Image or video subcommand parser.
    """

    _add_numeric_arguments(
        verification_parser_obj,
        DETECTION_ARGUMENT_SPECS_TUPLE,
    )


def _add_tracking_threshold_arguments(
    video_parser_obj: argparse.ArgumentParser,
) -> None:
    """Add temporal association and lifecycle threshold arguments.

    Args:
        video_parser_obj: Video subcommand parser.
    """

    _add_numeric_arguments(video_parser_obj, TRACKING_ARGUMENT_SPECS_TUPLE)
    video_parser_obj.add_argument(
        "--no-lineage-events",
        action="store_true",
        help="Keep tracking but omit split and merge lineage evidence.",
    )


def _add_numeric_arguments(
    parser_obj: argparse.ArgumentParser,
    argument_specs_tuple: tuple[_NumericArgumentSpec, ...],
) -> None:
    """Register every described numeric threshold on one parser.

    Args:
        parser_obj: Subcommand parser receiving the arguments.
        argument_specs_tuple: Ordered threshold descriptions.
    """

    for argument_spec_obj in argument_specs_tuple:
        parser_obj.add_argument(
            argument_spec_obj.flag_text,
            type=argument_spec_obj.value_type,
            default=argument_spec_obj.default_value,
            metavar=argument_spec_obj.metavar_text,
            help=argument_spec_obj.help_text,
        )


__all__ = [
    "build_parser",
    "main",
    "run_demo",
    "run_doctor",
    "run_image",
    "run_inspect",
    "run_video",
]


if __name__ == "__main__":
    raise SystemExit(main())
