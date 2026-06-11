"""In-process fake worker for the T2 training API contract."""

from __future__ import annotations

import hashlib
import importlib.resources
import json

from scooling_lab.contracts import TrainingJobStatus
from scooling_lab.store import ArtifactMetadata, TrainingJobRecord, TrainingJobStore, utc_now_iso

FIXTURE_DATASET_RESOURCE = "synthetic_training_dataset.jsonl"


def fixture_dataset_bytes() -> bytes:
    """Read the committed synthetic fixture dataset from package resources."""

    return (
        importlib.resources.files("scooling_lab.fixtures")
        .joinpath(FIXTURE_DATASET_RESOURCE)
        .read_bytes()
    )


def fixture_dataset_hash() -> str:
    """Return the stable SHA-256 hash for the synthetic fixture dataset."""

    return hashlib.sha256(fixture_dataset_bytes()).hexdigest()


def placeholder_artifact_hash(job: TrainingJobRecord, dataset_hash: str) -> str:
    """Return a stable hash for the placeholder artifact metadata."""

    payload = json.dumps(
        {
            "datasetHash": dataset_hash,
            "jobId": job.id,
            "modelId": job.request.model_id,
            "placeholder": "scooling-lab-fake-artifact-v1",
            "trainingParameters": dict(sorted(job.request.training_parameters.items())),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FakeTrainingWorker:
    """Synchronous fake worker that performs no real training and writes no models."""

    def __init__(self, store: TrainingJobStore) -> None:
        """Bind the worker to a server-owned job store."""

        self._store = store

    def run_job(self, job_id: str) -> TrainingJobRecord:
        """Move a queued job through running to succeeded and register metadata."""

        job = self._store.get(job_id)
        if job.status == TrainingJobStatus.SUCCEEDED:
            return job
        self._store.update_status(job_id, TrainingJobStatus.RUNNING)
        running_job = self._store.get(job_id)
        dataset_hash = fixture_dataset_hash()
        artifact_hash = placeholder_artifact_hash(running_job, dataset_hash)
        artifact_id = f"artifact_{artifact_hash[:24]}"
        self._store.register_artifact(
            job_id,
            ArtifactMetadata(
                id=artifact_id,
                job_id=job_id,
                dataset_hash=dataset_hash,
                artifact_hash=artifact_hash,
                created_at=utc_now_iso(),
            ),
        )
        return self._store.update_status(job_id, TrainingJobStatus.SUCCEEDED)
