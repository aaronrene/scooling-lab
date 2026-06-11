"""Application service for Scooling Lab training API operations."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from scooling_lab.contracts import (
    TrainingJobRequest,
    TrainingJobStatus,
    require_artifact_id,
    require_job_id,
)
from scooling_lab.fake_worker import FakeTrainingWorker
from scooling_lab.store import TrainingJobStore


class TrainingApiService:
    """Implements the T2 API contract over a store and fake worker."""

    def __init__(self, store: TrainingJobStore, auto_run_worker: bool = True) -> None:
        """Create a service with optional synchronous fake-worker completion."""

        self._store = store
        self._worker = FakeTrainingWorker(store)
        self._auto_run_worker = auto_run_worker

    def create_training_job(self, payload: dict[str, object]) -> dict[str, object]:
        """Validate, create, and optionally complete a fixture training job."""

        request = TrainingJobRequest.from_mapping(payload)
        job = self._store.create(request)
        if self._auto_run_worker and job.status in {
            TrainingJobStatus.QUEUED,
            TrainingJobStatus.RUNNING,
        }:
            job = self._worker.run_job(job.id)
        return job.to_public_dict()

    def get_training_job(self, job_id: str) -> dict[str, object]:
        """Return the public status for one training job."""

        require_job_id(job_id)
        return self._store.evaluate_expiry(job_id).to_public_dict()

    def cancel_training_job(self, job_id: str) -> dict[str, object]:
        """Cancel a queued or running training job."""

        require_job_id(job_id)
        return self._store.update_status(
            job_id, TrainingJobStatus.CANCELLED
        ).to_public_dict()

    def list_artifacts(self, job_id: str) -> dict[str, object]:
        """Return placeholder artifacts registered for one job."""

        require_job_id(job_id)
        self._store.evaluate_expiry(job_id)
        artifacts = [artifact.to_dict() for artifact in self._store.list_artifacts(job_id)]
        return {"jobId": job_id, "artifacts": artifacts}

    def get_provenance(self, job_id: str) -> dict[str, object]:
        """Return the validated provenance record for one completed fixture job."""

        require_job_id(job_id)
        self._store.evaluate_expiry(job_id)
        return self._store.get_provenance(job_id).to_dict()

    def delete_artifact(self, job_id: str, artifact_id: str) -> dict[str, object]:
        """Delete an artifact and all derived content-bearing metadata."""

        require_job_id(job_id)
        require_artifact_id(artifact_id)
        return self._store.delete_artifact(job_id, artifact_id).to_dict()

    def sweep_expired_artifacts(self, now: datetime | None = None) -> dict[str, object]:
        """Evaluate all retention policies and delete expired artifacts."""

        return self._store.sweep_expired(now)

    def verify_deleted_artifact_absence(self, hash_values: Iterable[str]) -> bool:
        """Verify deleted artifact hashes are absent from all store outputs."""

        return self._store.verify_hash_absence(hash_values)
