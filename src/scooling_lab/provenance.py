"""Content-free provenance records for completed fixture artifacts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.retention import parse_utc_timestamp


PROVENANCE_SCHEMA_VERSION = "scooling-lab.provenance.v1"
PROVENANCE_KEYS: frozenset[str] = frozenset(
    {
        "jobId",
        "datasetHash",
        "artifactHash",
        "baseModelId",
        "trainingConfigHash",
        "createdAt",
        "schemaVersion",
    }
)
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
JOB_ID_RE = re.compile(r"^job_[a-f0-9]{24}$")
SAFE_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{3,96}$")
UNSAFE_FREE_TEXT_RE = re.compile(r"(?i)(https?://|file://|ssh://|\.\./|/|\\|[;&|`$<>]|\s)")


@dataclass(frozen=True)
class ProvenanceRecord:
    """Validated, content-free provenance for one completed fixture artifact."""

    job_id: str
    dataset_hash: str
    artifact_hash: str
    base_model_id: str
    training_config_hash: str
    created_at: str
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, str]:
        """Serialize the provenance record in the public wire shape."""

        return {
            "artifactHash": self.artifact_hash,
            "baseModelId": self.base_model_id,
            "createdAt": self.created_at,
            "datasetHash": self.dataset_hash,
            "jobId": self.job_id,
            "schemaVersion": self.schema_version,
            "trainingConfigHash": self.training_config_hash,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "ProvenanceRecord":
        """Validate and rehydrate a provenance record from untrusted data."""

        validate_provenance_mapping(payload)
        return cls(
            artifact_hash=str(payload["artifactHash"]),
            base_model_id=str(payload["baseModelId"]),
            created_at=str(payload["createdAt"]),
            dataset_hash=str(payload["datasetHash"]),
            job_id=str(payload["jobId"]),
            schema_version=str(payload["schemaVersion"]),
            training_config_hash=str(payload["trainingConfigHash"]),
        )


def validate_provenance_mapping(payload: Mapping[str, object]) -> None:
    """Reject provenance records that contain text, paths, URLs, or extra fields."""

    if set(payload) != PROVENANCE_KEYS:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    for key, value in payload.items():
        if not isinstance(value, str):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        if key != "createdAt" and UNSAFE_FREE_TEXT_RE.search(value):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    if not JOB_ID_RE.fullmatch(str(payload["jobId"])):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    for key in ("datasetHash", "artifactHash", "trainingConfigHash"):
        if not HASH_RE.fullmatch(str(payload[key])):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if not SAFE_MODEL_ID_RE.fullmatch(str(payload["baseModelId"])):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if payload["schemaVersion"] != PROVENANCE_SCHEMA_VERSION:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    try:
        parse_utc_timestamp(str(payload["createdAt"]))
    except (ApiError, ValueError) as exc:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400) from exc


def validate_provenance_record(record: ProvenanceRecord | Mapping[str, object]) -> None:
    """Validate any provenance record against the content-free schema."""

    if isinstance(record, ProvenanceRecord):
        validate_provenance_mapping(record.to_dict())
        return
    validate_provenance_mapping(record)


def load_provenance_file(path: Path) -> ProvenanceRecord:
    """Read and validate one JSON provenance record from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return ProvenanceRecord.from_mapping(payload)


def self_check() -> None:
    """Run validator acceptance and rejection checks for CI."""

    valid = {
        "artifactHash": "b" * 64,
        "baseModelId": "fixture-tiny-llm",
        "createdAt": "2026-06-11T00:00:00Z",
        "datasetHash": "a" * 64,
        "jobId": "job_" + "1" * 24,
        "schemaVersion": PROVENANCE_SCHEMA_VERSION,
        "trainingConfigHash": "c" * 64,
    }
    validate_provenance_mapping(valid)
    rejected = dict(valid)
    rejected["baseModelId"] = "fixture model with prompt text"
    try:
        validate_provenance_mapping(rejected)
    except ApiError:
        return
    raise ApiError(ErrorCode.VALIDATION_ERROR, 400)


def build_parser() -> argparse.ArgumentParser:
    """Build the offline provenance validator CLI parser."""

    parser = argparse.ArgumentParser(description="Validate Scooling Lab provenance records")
    parser.add_argument("--record", action="append", type=Path, default=[])
    parser.add_argument("--self-check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run offline provenance validation for files and CI self-checks."""

    args = build_parser().parse_args(argv)
    if args.self_check:
        self_check()
    for record_path in args.record:
        load_provenance_file(record_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ApiError, json.JSONDecodeError) as exc:
        raise SystemExit(f"provenance validation failed: {exc}") from exc
