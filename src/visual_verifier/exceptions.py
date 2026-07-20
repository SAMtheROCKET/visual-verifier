"""Define structured exceptions for Visual Verifier operations."""

from __future__ import annotations

from collections.abc import Mapping


class VisualVerifierError(Exception):
    """Represent a recoverable Visual Verifier execution error.

    The base exception stores a readable message and optional structured
    context. Subclasses identify the failing subsystem through a stable
    ``error_code`` value.

    Args:
        message_str: Human-readable explanation of the failure.
        context_mapping: Optional machine-readable diagnostic context.

    Warning:
        Context values should remain serializable when the exception is
        written to JSON reports or application logs.
    """

    error_code = "VISUAL_VERIFIER_ERROR"

    def __init__(
        self,
        message_str: str,
        *,
        context_mapping: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize the exception message and diagnostic context.

        Args:
            message_str: Human-readable explanation of the failure.
            context_mapping: Optional machine-readable diagnostic context.
        """

        super().__init__(message_str)
        self.message_str = message_str
        self.context_dict = dict(context_mapping or {})

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable representation of the exception.

        Returns:
            Dictionary containing the error code, message, and context.
        """

        return {
            "error_code": self.error_code,
            "message": self.message_str,
            "context": self.context_dict.copy(),
        }


class ConfigurationError(VisualVerifierError):
    """Indicate an invalid or incomplete verification configuration."""

    error_code = "CONFIGURATION_ERROR"


class MediaReadError(VisualVerifierError):
    """Indicate that reference or candidate media could not be decoded."""

    error_code = "MEDIA_READ_ERROR"


class MediaCompatibilityError(VisualVerifierError):
    """Indicate that two media inputs cannot be compared safely."""

    error_code = "MEDIA_COMPATIBILITY_ERROR"


class TargetValidationError(VisualVerifierError):
    """Indicate invalid, incomplete, or inconsistent target definitions."""

    error_code = "TARGET_VALIDATION_ERROR"


class PolicyEvaluationError(VisualVerifierError):
    """Indicate that a verification policy could not be evaluated."""

    error_code = "POLICY_EVALUATION_ERROR"


class ReportWriteError(VisualVerifierError):
    """Indicate that verification evidence could not be written."""

    error_code = "REPORT_WRITE_ERROR"


class VerificationFailedError(VisualVerifierError):
    """Indicate a completed verification result that violated policy."""

    error_code = "VERIFICATION_FAILED"


__all__ = [
    "ConfigurationError",
    "MediaCompatibilityError",
    "MediaReadError",
    "PolicyEvaluationError",
    "ReportWriteError",
    "TargetValidationError",
    "VerificationFailedError",
    "VisualVerifierError",
]
