"""Shared unittest helpers for Scooling Lab tests."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
FIXTURE_PACKAGE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "packages"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class GpuWorkerTestEnv:
    """Temp package/artifact roots and stub train mode for GPU worker tests."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.package_root = Path(self._tmpdir.name) / "packages"
        self.artifact_root = Path(self._tmpdir.name) / "artifacts"
        self.package_root.mkdir(parents=True)
        self.artifact_root.mkdir(parents=True)
        self._prior_env: dict[str, str | None] = {}

    def __enter__(self) -> "GpuWorkerTestEnv":
        for key, value in (
            ("SCOOLING_LAB_PACKAGE_ROOT", str(self.package_root)),
            ("SCOOLING_LAB_ARTIFACT_ROOT", str(self.artifact_root)),
            ("SCOOLING_LAB_GPU_TRAIN_MODE", "stub"),
        ):
            self._prior_env[key] = os.environ.get(key)
            os.environ[key] = value
        return self

    def __exit__(self, *args: object) -> None:
        for key, prior in self._prior_env.items():
            if prior is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior
        self._tmpdir.cleanup()

    def seed_package(
        self,
        dataset_id: str,
        *,
        lines: list[str] | None = None,
        copy_fixture: bool = False,
    ) -> None:
        """Write train.jsonl (+ optional manifest) under the package root."""

        target = self.package_root / dataset_id
        if copy_fixture and (FIXTURE_PACKAGE_ROOT / dataset_id).is_dir():
            shutil.copytree(FIXTURE_PACKAGE_ROOT / dataset_id, target)
            return
        target.mkdir(parents=True, exist_ok=True)
        if lines is not None:
            (target / "train.jsonl").write_text("".join(lines), encoding="utf-8")
            row_count = len(lines)
        else:
            from scooling_lab.package_ingest import canonical_train_jsonl_bytes

            rows = [{"instruction": "test", "input": "", "output": "ok"}]
            (target / "train.jsonl").write_bytes(canonical_train_jsonl_bytes(rows))
            row_count = len(rows)
        (target / "manifest.json").write_text(
            json.dumps({"datasetId": dataset_id, "rowCount": row_count}),
            encoding="utf-8",
        )


def valid_payload(
    suffix: str = "alpha", retention_policy: dict[str, object] | None = None
) -> dict[str, object]:
    """Return a valid fixture createTrainingJob payload."""

    payload: dict[str, object] = {
        "idempotencyKey": f"fixture-{suffix}-0001",
        "datasetId": "fixture:synthetic-tiny-v1",
        "modelId": "fixture-tiny-llm",
        "requestedBy": "unit-test",
        "trainingParameters": {
            "epochs": 1,
            "learningRate": 0.1,
            "dryRun": True,
        },
    }
    if retention_policy is not None:
        payload["retentionPolicy"] = retention_policy
    return payload


def valid_gpu_payload(
    suffix: str = "gpu",
    dataset_id: str = "own:gpu-packaged.notes_v1",
) -> dict[str, object]:
    """Return a valid product GPU createTrainingJob payload (schema only)."""

    return {
        "idempotencyKey": f"gpu-{suffix}-0001",
        "datasetId": dataset_id,
        "modelId": "scooling-lab-gpu-personal-v1",
        "requestedBy": "unit-test",
        "trainingParameters": {
            "epochs": 1,
            "learningRate": 0.1,
            "dryRun": False,
        },
    }


def valid_package_ingest_payload(
    *,
    rows: list[dict[str, str]] | None = None,
    vault_scope: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return a valid server-auth package ingest payload."""

    row_list = rows or [{"instruction": "vault note", "input": "", "output": "summary"}]
    scope = vault_scope or {"kind": "all"}
    return {
        "rows": row_list,
        "vaultScope": scope,
        "rowCount": len(row_list),
    }


def ingest_authorization_header(
    dataset_id: str,
    *,
    subject: str = "scooling.server",
    secret: str = "test-ingest-secret",
) -> str:
    """Mint a Bearer token for package ingest tests."""

    from scooling_lab.server_auth import sign_ingest_jwt

    prior = os.environ.get("SCOOLING_LAB_INGEST_AUTH_SECRET")
    os.environ["SCOOLING_LAB_INGEST_AUTH_SECRET"] = secret
    try:
        token = sign_ingest_jwt(dataset_id, subject, secret=secret)
    finally:
        if prior is None:
            os.environ.pop("SCOOLING_LAB_INGEST_AUTH_SECRET", None)
        else:
            os.environ["SCOOLING_LAB_INGEST_AUTH_SECRET"] = prior
    return f"Bearer {token}"