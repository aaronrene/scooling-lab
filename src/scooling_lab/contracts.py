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
from scooling_lab.retention import (
    RetentionPolicy,
    default_retention_policy,
    retention_policy_from_mapping,
)


class TrainingJobStatus(str, Enum):
    """States allowed by the T2 training job state machine."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DELETED = "deleted"


WAVE_A_MODEL_ID: str = "fixture-tiny-llm"
GPU_PRODUCT_MODEL_ID: str = "scooling-lab-gpu-personal-v1"
ALLOWED_MODEL_IDS: frozenset[str] = frozenset({WAVE_A_MODEL_ID, GPU_PRODUCT_MODEL_ID})
FIXTURE_DATASET_ID: str = "fixture:synthetic-tiny-v1"
# Back-compat alias — prefer is_allowed_training_dataset_id() for dual-class Wave A.
ALLOWED_DATASET_IDS: frozenset[str] = frozenset({FIXTURE_DATASET_ID})
OWN_DATA_DATASET_ID_RE = re.compile(r"^own:[A-Za-z0-9._-]{3,64}$")
ALLOWED_REQUEST_KEYS: frozenset[str] = frozenset(
    {
        "idempotencyKey",
        "datasetId",
        "modelId",
        "requestedBy",
        "retentionPolicy",
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
JOB_ID_RE = re.compile(r"^job_[a-f0-9]{24}$")
ARTIFACT_ID_RE = re.compile(r"^artifact_[a-f0-9]{24}$")
FORBIDDEN_STRING_RE = re.compile(
    r"(?i)(https?://|file://|ssh://|[;&|`$<>]|\.\./|/\w|[A-Za-z]:\\)"
)


@dataclass(frozen=True)
class TrainingJobRequest:
    """Validated createTrainingJob payload.

    The schema accepts practice fixture ids or product own-data ids
    (``^own:[A-Za-z0-9._-]{3,64}$``) with one of two model shapes:

    * Wave A — ``fixture-tiny-llm``; product ``own:*`` requires ``dryRun: true``.
    * GPU — ``scooling-lab-gpu-personal-v1`` + ``dryRun: false`` for approved
      ``own:*`` only (practice fixture + GPU is refused).

    Unknown keys (worker URLs, callbacks, paths, shell strings) fail before the
    service layer.
    """

    idempotency_key: str
    dataset_id: str
    model_id: str
    requested_by: str
    retention_policy: RetentionPolicy = field(default_factory=default_retention_policy)
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
        dataset_id = require_training_dataset_id(payload.get("datasetId"))
        model_id = require_safe_identifier(payload.get("modelId"))
        requested_by = require_requester(payload.get("requestedBy"))
        retention_policy = retention_policy_from_mapping(payload.get("retentionPolicy"))
        if model_id not in ALLOWED_MODEL_IDS:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

        is_own = is_own_data_dataset_id(dataset_id)
        if model_id == GPU_PRODUCT_MODEL_ID:
            # GPU shape: approved own:* only; practice fixture is refuse-closed.
            if not is_own:
                raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
            training_parameters = validate_training_parameters(
                payload.get("trainingParameters", {}),
                dry_run_mode="gpu",
            )
        else:
            training_parameters = validate_training_parameters(
                payload.get("trainingParameters", {}),
                dry_run_mode="wave_a",
                require_dry_run=is_own,
            )

        return cls(
            idempotency_key=idempotency_key,
            dataset_id=dataset_id,
            model_id=model_id,
            requested_by=requested_by,
            retention_policy=retention_policy,
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
                "retentionPolicy": self.retention_policy.to_public_dict(),
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
            "retentionPolicy": self.retention_policy.to_public_dict(),
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


def is_own_data_dataset_id(value: str) -> bool:
    """Return True when value is a Wave A own-data dataset id."""

    return OWN_DATA_DATASET_ID_RE.fullmatch(value) is not None


def is_allowed_training_dataset_id(value: str) -> bool:
    """Practice fixture or product own-data id only (SITE-FINISH-LAB-HOSTED Wave A)."""

    return value == FIXTURE_DATASET_ID or is_own_data_dataset_id(value)


def require_training_dataset_id(value: object) -> str:
    """Accept fixture practice id or exact own:* product id; refuse all others."""

    dataset_id = require_safe_identifier(value)
    if not is_allowed_training_dataset_id(dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return dataset_id


def require_requester(value: object) -> str:
    """Validate the non-secret caller label used for fixture audit context."""

    if not isinstance(value, str) or not REQUESTER_RE.fullmatch(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if FORBIDDEN_STRING_RE.search(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return value


def require_job_id(value: object) -> str:
    """Validate a server-generated job id before any store lookup."""

    if not isinstance(value, str) or not JOB_ID_RE.fullmatch(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return value


def require_artifact_id(value: object) -> str:
    """Validate a server-generated artifact id before any mutation."""

    if not isinstance(value, str) or not ARTIFACT_ID_RE.fullmatch(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return value


def validate_training_parameters(
    value: object,
    *,
    require_dry_run: bool = False,
    dry_run_mode: str = "wave_a",
) -> dict[str, int | float | bool]:
    """Validate the bounded training parameter set for Wave A or GPU shapes.

    ``dry_run_mode``:

    * ``wave_a`` — when ``dryRun`` is present it must be ``true``; when
      ``require_dry_run`` is True (own-data Wave A), ``dryRun: true`` is required.
    * ``gpu`` — ``dryRun: false`` is required (product GPU path only).
    """

    if dry_run_mode not in {"wave_a", "gpu"}:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
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
    if dry_run_mode == "gpu":
        if "dryRun" not in value:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        dry_run = value["dryRun"]
        if not isinstance(dry_run, bool) or dry_run is not False:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        parameters["dryRun"] = False
        return parameters

    if "dryRun" in value:
        dry_run = value["dryRun"]
        if not isinstance(dry_run, bool) or dry_run is not True:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        parameters["dryRun"] = dry_run
    elif require_dry_run:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return parameters
