"""Application service for Scooling Lab training API operations."""

from __future__ import annotations

from scooling_lab.contracts import TrainingJobRequest
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
        if self._auto_run_worker:
            job = self._worker.run_job(job.id)
        return job.to_public_dict()

    def get_training_job(self, job_id: str) -> dict[str, object]:
        """Return the public status for one training job."""

        return self._store.get(job_id).to_public_dict()

    def cancel_training_job(self, job_id: str) -> dict[str, object]:
        """Cancel a queued or running training job."""

        from scooling_lab.contracts import TrainingJobStatus

        return self._store.update_status(
            job_id, TrainingJobStatus.CANCELLED
        ).to_public_dict()

    def list_artifacts(self, job_id: str) -> dict[str, object]:
        """Return placeholder artifacts registered for one job."""

        artifacts = [artifact.to_dict() for artifact in self._store.list_artifacts(job_id)]
        return {"jobId": job_id, "artifacts": artifacts}
