"""Training API request contracts and schema-layer validation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from scooling_lab.errors import ApiError, ErrorCode


class TrainingJobStatus(str, Enum):
    """States allowed by the T2 training job state machine."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALLOWED_MODEL_IDS: frozenset[str] = frozenset({"fixture-tiny-llm"})
ALLOWED_DATASET_IDS: frozenset[str] = frozenset({"fixture:synthetic-tiny-v1"})
ALLOWED_REQUEST_KEYS: frozenset[str] = frozenset(
    {
        "idempotencyKey",
        "datasetId",
        "modelId",
        "requestedBy",
        "trainingParameters",
    }
)
FORBIDDEN_KEY_TERMS: tuple[str, ...] = (
    "url",
    "uri",
    "path",
    "file",
    "shell",
    "command",
    "callback",
    "webhook",
    "worker",
)
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]{3,96}$")
REQUESTER_RE = re.compile(r"^[A-Za-z0-9._:-]{3,80}$")
FORBIDDEN_STRING_RE = re.compile(
    r"(?i)(https?://|file://|ssh://|[;&|`$<>]|\.\./|/\w|[A-Za-z]:\\)"
)


@dataclass(frozen=True)
class TrainingJobRequest:
    """Validated createTrainingJob payload.

    The schema only accepts inert fixture identifiers, bounded numeric training
    parameters, and a caller-provided idempotency key. It rejects unknown keys so
    browser-supplied worker URLs, callback URLs, file paths, and shell strings
    fail before reaching the service layer.
    """

    idempotency_key: str
    dataset_id: str
    model_id: str
    requested_by: str
    training_parameters: Mapping[str, int | float | bool] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "TrainingJobRequest":
        """Validate and convert an untrusted JSON object into a request."""

        reject_forbidden_keys(payload)
        unknown_keys = set(payload).difference(ALLOWED_REQUEST_KEYS)
        if unknown_keys:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

        idempotency_key = require_safe_identifier(payload.get("idempotencyKey"))
        dataset_id = require_safe_identifier(payload.get("datasetId"))
        model_id = require_safe_identifier(payload.get("modelId"))
        requested_by = require_requester(payload.get("requestedBy"))
        training_parameters = validate_training_parameters(
            payload.get("trainingParameters", {})
        )

        if dataset_id not in ALLOWED_DATASET_IDS:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        if model_id not in ALLOWED_MODEL_IDS:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

        return cls(
            idempotency_key=idempotency_key,
            dataset_id=dataset_id,
            model_id=model_id,
            requested_by=requested_by,
            training_parameters=MappingProxyType(training_parameters),
        )

    def fingerprint(self) -> str:
        """Return a stable hash input for idempotent job creation."""

        return json.dumps(
            {
                "datasetId": self.dataset_id,
                "idempotencyKey": self.idempotency_key,
                "modelId": self.model_id,
                "requestedBy": self.requested_by,
                "trainingParameters": dict(sorted(self.training_parameters.items())),
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    def stable_job_id(self) -> str:
        """Return the deterministic job id for this request."""

        digest = hashlib.sha256(self.fingerprint().encode("utf-8")).hexdigest()[:24]
        return f"job_{digest}"

    def to_public_dict(self) -> dict[str, object]:
        """Serialize only safe, non-private request fields."""

        return {
            "datasetId": self.dataset_id,
            "modelId": self.model_id,
            "requestedBy": self.requested_by,
            "trainingParameters": dict(sorted(self.training_parameters.items())),
        }


def reject_forbidden_keys(payload: Mapping[str, object]) -> None:
    """Reject explicitly dangerous key shapes anywhere in a request payload."""

    for key, value in payload.items():
        lowered = key.lower()
        if any(term in lowered for term in FORBIDDEN_KEY_TERMS):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        if isinstance(value, Mapping):
            reject_forbidden_keys(value)


def require_safe_identifier(value: object) -> str:
    """Validate compact fixture identifiers and reject path or URL strings."""

    if not isinstance(value, str) or not SAFE_IDENTIFIER_RE.fullmatch(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if FORBIDDEN_STRING_RE.search(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return value


def require_requester(value: object) -> str:
    """Validate the non-secret caller label used for fixture audit context."""

    if not isinstance(value, str) or not REQUESTER_RE.fullmatch(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if FORBIDDEN_STRING_RE.search(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return value


def validate_training_parameters(value: object) -> dict[str, int | float | bool]:
    """Validate the bounded dry-run parameter set for the fake worker."""

    if not isinstance(value, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    allowed_keys = {"epochs", "learningRate", "dryRun"}
    if set(value).difference(allowed_keys):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    parameters: dict[str, int | float | bool] = {}
    if "epochs" in value:
        epochs = value["epochs"]
        if not isinstance(epochs, int) or isinstance(epochs, bool) or not 1 <= epochs <= 3:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        parameters["epochs"] = epochs
    if "learningRate" in value:
        learning_rate = value["learningRate"]
        if (
            not isinstance(learning_rate, (int, float))
            or isinstance(learning_rate, bool)
            or not 0 < float(learning_rate) <= 1
        ):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        parameters["learningRate"] = float(learning_rate)
    if "dryRun" in value:
        dry_run = value["dryRun"]
        if not isinstance(dry_run, bool) or dry_run is not True:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        parameters["dryRun"] = dry_run
    return parameters
