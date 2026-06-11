"""Stable, sanitized error model for the Scooling Lab API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    """Public API error codes that do not expose internals."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    MALFORMED_JSON = "MALFORMED_JSON"
    NOT_FOUND = "NOT_FOUND"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    QUEUE_LIMIT_EXCEEDED = "QUEUE_LIMIT_EXCEEDED"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATASET_NOT_APPROVED = "DATASET_NOT_APPROVED"


SAFE_ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.VALIDATION_ERROR: "The request is not accepted by the training contract.",
    ErrorCode.MALFORMED_JSON: "The request body must be valid JSON.",
    ErrorCode.NOT_FOUND: "The requested training resource was not found.",
    ErrorCode.INVALID_TRANSITION: "The requested job state change is not allowed.",
    ErrorCode.QUEUE_LIMIT_EXCEEDED: "The fixture training queue is full.",
    ErrorCode.METHOD_NOT_ALLOWED: "The HTTP method is not allowed for this route.",
    ErrorCode.CONFLICT: "The request conflicts with an existing training job.",
    ErrorCode.INTERNAL_ERROR: "The training service could not complete the request.",
    ErrorCode.DATASET_NOT_APPROVED: "The dataset has not been approved for job submission.",
}


@dataclass(frozen=True)
class ApiError(Exception):
    """Exception carrying only a stable public code and HTTP status."""

    code: ErrorCode
    status: int

    @property
    def message(self) -> str:
        """Return the public message for the error code."""

        return SAFE_ERROR_MESSAGES[self.code]


def error_payload(error: ApiError) -> dict[str, dict[str, str]]:
    """Build a safe JSON error payload with no request echo or paths."""

    return {
        "error": {
            "code": error.code.value,
            "message": error.message,
        }
    }
