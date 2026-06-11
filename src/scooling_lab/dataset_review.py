"""Dataset registration and review lifecycle for the Scooling Lab training API.

Datasets move through a bounded state machine before any job can reference them:
    registered → pending_review → approved | rejected

Only approved datasets are eligible for job submission.  Rejection is communicated
as a machine-readable ``RejectionReasonCode`` enum; no caller-supplied text is ever
echoed back in API responses or logs.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from scooling_lab.errors import ApiError, ErrorCode


DATASET_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{3,96}$")
FORBIDDEN_STRING_RE = re.compile(
    r"(?i)(https?://|file://|ssh://|[;&|`$<>]|\.\./|/\w|[A-Za-z]:\\)"
)
FORBIDDEN_FIELD_TERMS: tuple[str, ...] = (
    "content",
    "credential",
    "document",
    "email",
    "file",
    "instruction",
    "message",
    "password",
    "path",
    "prompt",
    "secret",
    "text",
    "url",
)
SYNTHETIC_ROW_COUNT_MIN = 1
SYNTHETIC_ROW_COUNT_MAX = 10_000
SYNTHETIC_DATASET_SCHEMA: MappingProxyType[str, str] = MappingProxyType(
    {
        "exampleId": "string",
        "inputTokenCount": "integer",
        "outputTokenCount": "integer",
        "split": "string",
    }
)
ALLOWED_DATASET_REGISTRATION_KEYS: frozenset[str] = frozenset(
    {"datasetId", "rowCount", "declaredSchema"}
)

# The fixture dataset is pre-approved so existing tests require no changes.
FIXTURE_APPROVED_DATASET_IDS: frozenset[str] = frozenset(
    {"fixture:synthetic-tiny-v1"}
)


class DatasetStatus(str, Enum):
    """States in the dataset review lifecycle."""

    REGISTERED = "registered"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RejectionReasonCode(str, Enum):
    """Bounded machine-readable reason codes for dataset rejection.

    Free text is never accepted or echoed.  Only one of these values may
    appear in a review decision.
    """

    SYNTHETIC_LIMIT = "SYNTHETIC_LIMIT"
    FORMAT_INVALID = "FORMAT_INVALID"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    DUPLICATE_SUBMISSION = "DUPLICATE_SUBMISSION"


@dataclass(frozen=True)
class SyntheticDatasetShape:
    """Content-free metadata used to validate a synthetic dataset submission."""

    row_count: int
    declared_schema: Mapping[str, str]
    parse_reason: RejectionReasonCode | None = None


_DATASET_TRANSITIONS: MappingProxyType[
    DatasetStatus, frozenset[DatasetStatus]
] = MappingProxyType(
    {
        DatasetStatus.REGISTERED: frozenset({DatasetStatus.PENDING_REVIEW}),
        DatasetStatus.PENDING_REVIEW: frozenset(
            {DatasetStatus.APPROVED, DatasetStatus.REJECTED}
        ),
        DatasetStatus.APPROVED: frozenset(),
        DatasetStatus.REJECTED: frozenset(),
    }
)


def dataset_transition(
    current: DatasetStatus, target: DatasetStatus
) -> DatasetStatus:
    """Apply the dataset review state machine or raise for invalid moves.

    Idempotent same-state replay is allowed for every state.
    """

    if current == target:
        return current
    if target in _DATASET_TRANSITIONS[current]:
        return target
    raise ApiError(ErrorCode.INVALID_TRANSITION, 409)


def require_dataset_id(value: object) -> str:
    """Validate a dataset id against the safe-identifier contract."""

    if not isinstance(value, str) or not DATASET_ID_RE.fullmatch(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if FORBIDDEN_STRING_RE.search(value):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return value


def require_rejection_reason(value: object) -> RejectionReasonCode:
    """Validate a rejection reason code; reject unknown or free-text values."""

    if not isinstance(value, str):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    try:
        return RejectionReasonCode(value)
    except ValueError as exc:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400) from exc


def dataset_shape_from_registration(
    payload: Mapping[str, object],
) -> tuple[str, SyntheticDatasetShape]:
    """Validate dataset registration metadata without storing content.

    The dataset id is still schema-validated as a request contract.  The optional
    synthetic shape metadata is stored only as bounded counts and schema labels;
    submit-time validation converts malformed or policy-unsafe shapes into
    ``RejectionReasonCode`` values without echoing caller-provided text.
    """

    dataset_id = require_dataset_id(payload.get("datasetId"))
    unknown_keys = set(payload).difference(ALLOWED_DATASET_REGISTRATION_KEYS)
    if unknown_keys:
        return dataset_id, default_dataset_shape(RejectionReasonCode.FORMAT_INVALID)

    has_shape_metadata = "rowCount" in payload or "declaredSchema" in payload
    if not has_shape_metadata:
        return dataset_id, default_dataset_shape()

    row_count = payload.get("rowCount")
    declared_schema = payload.get("declaredSchema")
    if (
        not isinstance(row_count, int)
        or isinstance(row_count, bool)
        or not isinstance(declared_schema, Mapping)
    ):
        return dataset_id, default_dataset_shape(RejectionReasonCode.FORMAT_INVALID)

    parsed_schema: dict[str, str] = {}
    for field_name, field_type in declared_schema.items():
        if not isinstance(field_name, str) or not isinstance(field_type, str):
            return dataset_id, default_dataset_shape(RejectionReasonCode.FORMAT_INVALID)
        parsed_schema[field_name] = field_type

    return dataset_id, SyntheticDatasetShape(
        row_count=row_count,
        declared_schema=MappingProxyType(parsed_schema),
    )


def default_dataset_shape(
    parse_reason: RejectionReasonCode | None = None,
) -> SyntheticDatasetShape:
    """Return the default valid synthetic shape used by compatibility fixtures."""

    return SyntheticDatasetShape(
        row_count=SYNTHETIC_ROW_COUNT_MIN,
        declared_schema=SYNTHETIC_DATASET_SCHEMA,
        parse_reason=parse_reason,
    )


def validate_synthetic_dataset_shape(
    shape: SyntheticDatasetShape,
) -> RejectionReasonCode | None:
    """Return a bounded rejection code for invalid synthetic dataset metadata."""

    if shape.parse_reason is not None:
        return shape.parse_reason
    if not SYNTHETIC_ROW_COUNT_MIN <= shape.row_count <= SYNTHETIC_ROW_COUNT_MAX:
        return RejectionReasonCode.SYNTHETIC_LIMIT
    for field_name, field_type in shape.declared_schema.items():
        if has_forbidden_field_term(field_name) or has_forbidden_field_term(field_type):
            return RejectionReasonCode.POLICY_VIOLATION
    if dict(shape.declared_schema) != dict(SYNTHETIC_DATASET_SCHEMA):
        return RejectionReasonCode.SCHEMA_MISMATCH
    return None


def has_forbidden_field_term(value: str) -> bool:
    """Return true when a schema label carries unsafe or content-bearing terms."""

    lowered = value.lower()
    return FORBIDDEN_STRING_RE.search(value) is not None or any(
        term in lowered for term in FORBIDDEN_FIELD_TERMS
    )


def _utc_now_iso() -> str:
    """Return a UTC timestamp formatted for public metadata."""

    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class DatasetRecord:
    """Internal record for one registered fixture dataset."""

    dataset_id: str
    status: DatasetStatus = DatasetStatus.REGISTERED
    registered_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    rejection_reason: RejectionReasonCode | None = None
    synthetic_shape: SyntheticDatasetShape = field(default_factory=default_dataset_shape)

    def to_public_dict(self) -> dict[str, object]:
        """Serialize the safe dataset status shape for API responses."""

        payload: dict[str, object] = {
            "datasetId": self.dataset_id,
            "status": self.status.value,
            "registeredAt": self.registered_at,
            "updatedAt": self.updated_at,
        }
        if self.rejection_reason is not None:
            payload["rejectionReasonCode"] = self.rejection_reason.value
        return payload


class DatasetStore:
    """Thread-safe, in-memory store for dataset review lifecycle records.

    The store is pre-populated with the fixture dataset IDs from
    ``FIXTURE_APPROVED_DATASET_IDS`` so that existing job submission flows
    continue to work without an explicit registration step.
    """

    def __init__(self) -> None:
        """Create a store pre-approving all fixture dataset ids."""

        self._lock = threading.RLock()
        self._datasets: dict[str, DatasetRecord] = {}
        ts = _utc_now_iso()
        for dataset_id in FIXTURE_APPROVED_DATASET_IDS:
            self._datasets[dataset_id] = DatasetRecord(
                dataset_id=dataset_id,
                status=DatasetStatus.APPROVED,
                registered_at=ts,
                updated_at=ts,
            )

    def register(self, dataset_id: str) -> DatasetRecord:
        """Register a dataset; idempotent if already registered.

        Raises ``CONFLICT`` (409) if the same id has already been approved or
        rejected so that callers cannot silently re-enter a terminal-path
        dataset into review.
        """

        require_dataset_id(dataset_id)
        return self.register_shape(dataset_id, default_dataset_shape())

    def register_shape(
        self, dataset_id: str, synthetic_shape: SyntheticDatasetShape
    ) -> DatasetRecord:
        """Register a dataset with bounded synthetic validation metadata."""

        with self._lock:
            existing = self._datasets.get(dataset_id)
            if existing is not None:
                if existing.status in {DatasetStatus.APPROVED, DatasetStatus.REJECTED}:
                    raise ApiError(ErrorCode.CONFLICT, 409)
                return existing
            record = DatasetRecord(
                dataset_id=dataset_id,
                synthetic_shape=synthetic_shape,
            )
            self._datasets[dataset_id] = record
            return record

    def submit_for_review(self, dataset_id: str) -> DatasetRecord:
        """Validate a registered dataset and record the deterministic decision."""

        require_dataset_id(dataset_id)
        with self._lock:
            record = self._get_locked(dataset_id)
            record.status = dataset_transition(
                record.status, DatasetStatus.PENDING_REVIEW
            )
            rejection_reason = validate_synthetic_dataset_shape(record.synthetic_shape)
            if rejection_reason is None:
                record.status = dataset_transition(record.status, DatasetStatus.APPROVED)
                record.rejection_reason = None
            else:
                record.status = dataset_transition(record.status, DatasetStatus.REJECTED)
                record.rejection_reason = rejection_reason
            record.updated_at = _utc_now_iso()
            return record

    def approve(self, dataset_id: str) -> DatasetRecord:
        """Approve a dataset that is pending review."""

        require_dataset_id(dataset_id)
        with self._lock:
            record = self._get_locked(dataset_id)
            record.status = dataset_transition(record.status, DatasetStatus.APPROVED)
            record.updated_at = _utc_now_iso()
            return record

    def reject(
        self, dataset_id: str, reason_code: RejectionReasonCode
    ) -> DatasetRecord:
        """Reject a dataset that is pending review with a bounded reason code."""

        require_dataset_id(dataset_id)
        with self._lock:
            record = self._get_locked(dataset_id)
            if record.status == DatasetStatus.REJECTED:
                return record
            record.status = dataset_transition(record.status, DatasetStatus.REJECTED)
            record.rejection_reason = reason_code
            record.updated_at = _utc_now_iso()
            return record

    def get(self, dataset_id: str) -> DatasetRecord:
        """Return one dataset record or raise a safe not-found error."""

        require_dataset_id(dataset_id)
        with self._lock:
            return self._get_locked(dataset_id)

    def is_approved(self, dataset_id: str) -> bool:
        """Return True only if the dataset is in the approved state."""

        try:
            require_dataset_id(dataset_id)
        except ApiError:
            return False
        with self._lock:
            record = self._datasets.get(dataset_id)
            return record is not None and record.status == DatasetStatus.APPROVED

    def _get_locked(self, dataset_id: str) -> DatasetRecord:
        record = self._datasets.get(dataset_id)
        if record is None:
            raise ApiError(ErrorCode.NOT_FOUND, 404)
        return record


def validate_review_request(payload: Mapping[str, object]) -> tuple[str, RejectionReasonCode | None]:
    """Parse and validate a dataset review action payload.

    Returns ``(action, reason_code)`` where ``reason_code`` is non-None only
    when ``action == "reject"``.  No caller-supplied text is echoed.
    """

    allowed_keys = {"action", "reasonCode"}
    if not isinstance(payload, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    unknown = set(payload) - allowed_keys
    if unknown:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    action = payload.get("action")
    if action not in {"approve", "reject"}:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    reason_code: RejectionReasonCode | None = None
    if action == "reject":
        raw_reason = payload.get("reasonCode")
        if raw_reason is None:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        reason_code = require_rejection_reason(raw_reason)
    else:
        if "reasonCode" in payload:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    return str(action), reason_code
