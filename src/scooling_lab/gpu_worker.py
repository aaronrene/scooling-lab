"""Isolated Lab-owned GPU worker for product GPU train jobs.

Process isolation: the API service never runs GPU job completion in-process.
It spawns ``python -m scooling_lab.gpu_worker`` with a content-free JSON envelope
on stdin and reads a content-free result on stdout. Worker addresses never appear
on the HTTP wire.

Honesty bounds (LAB-GPU-TRAIN / SD-31):

* Completes ``scooling-lab-gpu-personal-v1`` + ``dryRun: false`` jobs with
  content-free provenance (``baseModelId`` pinned to the GPU model id).
* Does **not** load private learner note bodies, install Unsloth, or write model
  weights. Unsloth core remains evidence-only until legal review + lockfile.
* Apache-2.0 stdlib only — no AGPL Studio/CLI paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

import scooling_lab
from scooling_lab.contracts import (
    GPU_PRODUCT_MODEL_ID,
    TrainingJobStatus,
    is_own_data_dataset_id,
)
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.provenance import ProvenanceRecord, validate_provenance_record
from scooling_lab.store import ArtifactMetadata, TrainingJobRecord, TrainingJobStore, utc_now_iso

GPU_ARTIFACT_PLACEHOLDER = "scooling-lab-gpu-worker-v1"
GPU_WORKER_TIMEOUT_SECONDS = 30


def package_dataset_hash(dataset_id: str) -> str:
    """Return a content-free hash of an approved ``own:*`` package id.

    Private note bodies never enter this hash — only the package identifier.
    """

    if not is_own_data_dataset_id(dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    payload = f"scooling-lab-gpu-package:{dataset_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gpu_artifact_hash(
    job_id: str,
    model_id: str,
    dataset_hash: str,
    training_parameters: Mapping[str, int | float | bool],
) -> str:
    """Stable content-free artifact hash for a GPU worker completion."""

    payload = json.dumps(
        {
            "datasetHash": dataset_hash,
            "jobId": job_id,
            "modelId": model_id,
            "placeholder": GPU_ARTIFACT_PLACEHOLDER,
            "trainingParameters": dict(sorted(training_parameters.items())),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gpu_training_config_hash(
    model_id: str,
    retention_policy: Mapping[str, object],
    training_parameters: Mapping[str, int | float | bool],
) -> str:
    """Content-free training-config hash for GPU provenance."""

    payload = json.dumps(
        {
            "modelId": model_id,
            "retentionPolicy": dict(sorted(retention_policy.items())),
            "trainingParameters": dict(sorted(training_parameters.items())),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def execute_gpu_worker_envelope(envelope: Mapping[str, object]) -> dict[str, str]:
    """Validate a worker envelope and return content-free completion fields.

    Used by the subprocess entrypoint and by unit tests that inject the envelope
    without spawning a process.
    """

    job_id = envelope.get("jobId")
    model_id = envelope.get("modelId")
    dataset_id = envelope.get("datasetId")
    training_parameters = envelope.get("trainingParameters")
    retention_policy = envelope.get("retentionPolicy")
    if not isinstance(job_id, str) or not isinstance(model_id, str):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if not isinstance(dataset_id, str) or not is_own_data_dataset_id(dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if model_id != GPU_PRODUCT_MODEL_ID:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if not isinstance(training_parameters, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if training_parameters.get("dryRun") is not False:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if not isinstance(retention_policy, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    params: dict[str, int | float | bool] = {}
    for key, value in training_parameters.items():
        if not isinstance(key, str) or not isinstance(value, (int, float, bool)):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        params[key] = value
    retention: dict[str, object] = {
        str(key): value for key, value in retention_policy.items()
    }

    dataset_hash = package_dataset_hash(dataset_id)
    artifact_hash = gpu_artifact_hash(job_id, model_id, dataset_hash, params)
    config_hash = gpu_training_config_hash(model_id, retention, params)
    return {
        "artifactHash": artifact_hash,
        "baseModelId": GPU_PRODUCT_MODEL_ID,
        "datasetHash": dataset_hash,
        "jobId": job_id,
        "trainingConfigHash": config_hash,
    }


class IsolatedGpuWorker:
    """API-side driver that completes GPU jobs via an isolated subprocess."""

    def __init__(self, store: TrainingJobStore) -> None:
        """Bind the worker driver to a server-owned job store."""

        self._store = store

    def run_job(self, job_id: str) -> TrainingJobRecord:
        """Move a queued GPU job through running to succeeded via subprocess.

        If the subprocess or provenance validation fails the job is marked
        ``failed`` rather than raising, so the caller always receives a terminal
        job record.
        """

        job = self._store.get(job_id)
        if job.status in {
            TrainingJobStatus.SUCCEEDED,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
            TrainingJobStatus.DELETED,
        }:
            return job
        self._store.update_status(job_id, TrainingJobStatus.RUNNING)
        running_job = self._store.get(job_id)
        if running_job.request is None:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        if running_job.request.model_id != GPU_PRODUCT_MODEL_ID:
            return self._store.update_status(job_id, TrainingJobStatus.FAILED)
        if running_job.request.training_parameters.get("dryRun") is not False:
            return self._store.update_status(job_id, TrainingJobStatus.FAILED)

        envelope = {
            "datasetId": running_job.request.dataset_id,
            "jobId": job_id,
            "modelId": running_job.request.model_id,
            "retentionPolicy": running_job.request.retention_policy.to_public_dict(),
            "trainingParameters": dict(running_job.request.training_parameters),
        }
        try:
            result = self._invoke_isolated_process(envelope)
        except (ApiError, OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError):
            return self._store.update_status(job_id, TrainingJobStatus.FAILED)

        created_at = utc_now_iso()
        artifact_hash = result["artifactHash"]
        artifact_id = f"artifact_{artifact_hash[:24]}"
        provenance = ProvenanceRecord(
            artifact_hash=artifact_hash,
            base_model_id=result["baseModelId"],
            created_at=created_at,
            dataset_hash=result["datasetHash"],
            job_id=job_id,
            training_config_hash=result["trainingConfigHash"],
        )
        try:
            validate_provenance_record(provenance)
        except ApiError:
            return self._store.update_status(job_id, TrainingJobStatus.FAILED)
        self._store.register_artifact(
            job_id,
            ArtifactMetadata(
                id=artifact_id,
                job_id=job_id,
                dataset_hash=result["datasetHash"],
                artifact_hash=artifact_hash,
                created_at=created_at,
                provenance_id=f"provenance_{job_id}",
                retention_policy=running_job.request.retention_policy,
            ),
            provenance,
        )
        return self._store.update_status(job_id, TrainingJobStatus.SUCCEEDED)

    def _invoke_isolated_process(self, envelope: dict[str, object]) -> dict[str, str]:
        """Spawn the GPU worker module in a separate process; no in-process fallback."""

        env = os.environ.copy()
        # Never inherit browser-supplied worker URLs; strip common injection keys.
        for key in list(env):
            lowered = key.lower()
            if any(term in lowered for term in ("callback", "webhook", "worker_url", "proxy")):
                env.pop(key, None)
        # Ensure ``python -m scooling_lab.gpu_worker`` resolves under src layout and
        # editable installs (tests add SRC_ROOT to sys.path but not always PYTHONPATH).
        src_root = str(Path(scooling_lab.__file__).resolve().parent.parent)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            src_root if not existing else f"{src_root}{os.pathsep}{existing}"
        )

        completed = subprocess.run(
            [sys.executable, "-m", "scooling_lab.gpu_worker"],
            input=json.dumps(envelope, separators=(",", ":"), sort_keys=True),
            capture_output=True,
            text=True,
            timeout=GPU_WORKER_TIMEOUT_SECONDS,
            check=False,
            env=env,
            cwd=None,
        )
        if completed.returncode != 0:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict):
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        required = {
            "artifactHash",
            "baseModelId",
            "datasetHash",
            "jobId",
            "trainingConfigHash",
        }
        if set(payload) != required:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        return {key: str(payload[key]) for key in required}


def main() -> int:
    """Subprocess entrypoint: read envelope on stdin, write result on stdout."""

    try:
        raw = sys.stdin.read()
        envelope = json.loads(raw)
        if not isinstance(envelope, Mapping):
            return 1
        result = execute_gpu_worker_envelope(envelope)
        sys.stdout.write(json.dumps(result, separators=(",", ":"), sort_keys=True))
        sys.stdout.write("\n")
        return 0
    except (ApiError, json.JSONDecodeError, TypeError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
