"""Vault dataset package ingest — canonical JSONL write + content hash."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from scooling_lab.contracts import (
    FORBIDDEN_STRING_RE,
    is_own_data_dataset_id,
    require_safe_identifier,
)
from scooling_lab.dataset_review import SYNTHETIC_ROW_COUNT_MAX, SYNTHETIC_ROW_COUNT_MIN
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.gpu_worker import hash_file_bytes, package_root
from scooling_lab.server_auth import reject_forbidden_ingest_keys

_PACKAGE_ROOT_ENV = "SCOOLING_LAB_PACKAGE_ROOT"
_ALLOWED_PACKAGE_KEYS: frozenset[str] = frozenset({"rows", "vaultScope", "rowCount"})
_ALLOWED_ROW_KEYS: frozenset[str] = frozenset({"instruction", "input", "output"})
_VAULT_SCOPE_KINDS: frozenset[str] = frozenset(
    {"all", "folder", "tag", "selection", "youtube"}
)
_SCOPE_ID_LIST_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "folder": "folderIds",
        "tag": "tagIds",
        "selection": "noteIds",
        "youtube": "youtubeIds",
    }
)


def canonical_train_jsonl_bytes(rows: list[dict[str, str]]) -> bytes:
    """Serialize rows to canonical UTF-8 JSONL bytes (newline-terminated file)."""

    if not rows:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    lines = [
        json.dumps(row, separators=(",", ":"), sort_keys=True) for row in rows
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def validate_training_row(value: object) -> dict[str, str]:
    """Validate one training row with bounded string fields only."""

    if not isinstance(value, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    unknown = set(value).difference(_ALLOWED_ROW_KEYS)
    if unknown:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    row: dict[str, str] = {}
    for key in sorted(_ALLOWED_ROW_KEYS):
        if key not in value:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        field = value[key]
        if not isinstance(field, str):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        if len(field) > 16_384:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        if FORBIDDEN_STRING_RE.search(field):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        row[key] = field
    return row


def validate_vault_scope(value: object) -> dict[str, object]:
    """Validate content-free vault scope metadata (ids only on the wire)."""

    if not isinstance(value, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    reject_forbidden_ingest_keys(value)
    unknown = set(value).difference({"kind"}).difference(
        {key for key in _SCOPE_ID_LIST_KEYS.values()}
    )
    if unknown:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    kind = value.get("kind")
    if not isinstance(kind, str) or kind not in _VAULT_SCOPE_KINDS:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    public: dict[str, object] = {"kind": kind}
    if kind == "all":
        extra_keys = set(value).difference({"kind"})
        if extra_keys:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        return public
    list_key = _SCOPE_ID_LIST_KEYS[kind]
    if kind == "youtube" and list_key not in value:
        extra_keys = set(value).difference({"kind"})
        if extra_keys:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        return public
    ids = value.get(list_key)
    if not isinstance(ids, list) or not ids:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if len(ids) > 256:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    validated_ids: list[str] = []
    for entry in ids:
        validated_ids.append(require_safe_identifier(entry))
    public[list_key] = validated_ids
    return public


def parse_package_ingest_request(
    payload: Mapping[str, object],
) -> tuple[list[dict[str, str]], dict[str, object], int]:
    """Validate ingest JSON and return rows, vault scope, and row count."""

    reject_forbidden_ingest_keys(payload)
    unknown = set(payload).difference(_ALLOWED_PACKAGE_KEYS)
    if unknown:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    rows_value = payload.get("rows")
    if not isinstance(rows_value, list) or not rows_value:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    vault_scope = validate_vault_scope(payload.get("vaultScope"))
    rows = [validate_training_row(row) for row in rows_value]
    row_count = len(rows)
    if row_count < SYNTHETIC_ROW_COUNT_MIN or row_count > SYNTHETIC_ROW_COUNT_MAX:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    declared_count = payload.get("rowCount")
    if declared_count is not None:
        if not isinstance(declared_count, int) or isinstance(declared_count, bool):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        if declared_count != row_count:
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return rows, vault_scope, row_count


def resolve_package_dir(dataset_id: str) -> Path:
    """Map dataset id to package directory under env package root."""

    if not is_own_data_dataset_id(dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    raw = os.environ.get(_PACKAGE_ROOT_ENV, "").strip()
    if not raw:
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
    return Path(raw) / dataset_id


def write_package_files(
    dataset_id: str,
    rows: list[dict[str, str]],
    vault_scope: Mapping[str, object],
    row_count: int,
) -> tuple[Path, str]:
    """Write manifest + canonical train.jsonl atomically; return path and content hash."""

    package_dir = resolve_package_dir(dataset_id)
    canonical_bytes = canonical_train_jsonl_bytes(rows)
    dataset_hash = hashlib.sha256(canonical_bytes).hexdigest()
    tmp_dir = package_dir.parent / f"{dataset_id}.tmp-ingest"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    train_path = tmp_dir / "train.jsonl"
    train_path.write_bytes(canonical_bytes)
    manifest = {
        "datasetId": dataset_id,
        "rowCount": row_count,
        "vaultScope": dict(vault_scope),
        "datasetHash": dataset_hash,
        "packagedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (tmp_dir / "manifest.json").write_text(
        json.dumps(manifest, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    if package_dir.exists():
        shutil.rmtree(package_dir)
    tmp_dir.rename(package_dir)
    return package_dir, dataset_hash


def content_dataset_hash(dataset_id: str) -> str:
    """Return SHA-256 of on-disk train.jsonl for an own:* package."""

    train_path = package_root() / dataset_id / "train.jsonl"
    if not train_path.is_file():
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
    return hash_file_bytes(train_path)
