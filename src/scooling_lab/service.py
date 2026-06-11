"""Application service for Scooling Lab training API operations."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Iterable

from scooling_lab.contracts import (
    TrainingJobRequest,
    TrainingJobStatus,
    require_artifact_id,
    require_job_id,
)
from scooling_lab.dataset_review import (
    DatasetStore,
    RejectionReasonCode,
    validate_review_request,
)
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.fake_worker import FakeTrainingWorker
from scooling_lab.store import TrainingJobStore


class TrainingApiService:
    """Implements the T2/T3 API contract over a store, fake worker, and dataset store.

    Dataset approval is checked before any job is created.  A ``threading.Semaphore``
    enforces the ``max_concurrent_running`` bound from the store so that concurrent
    callers see at most that many jobs in the running state simultaneously.
    """

    def __init__(
        self,
        store: TrainingJobStore,
        auto_run_worker: bool = True,
        dataset_store: DatasetStore | None = None,
    ) -> None:
        """Create a service with optional synchronous fake-worker completion.

        If ``dataset_store`` is omitted a default store pre-approving the
        synthetic fixture dataset is used, so existing callers are unaffected.
        """

        self._store = store
        self._worker = FakeTrainingWorker(store)
        self._auto_run_worker = auto_run_worker
        self._dataset_store = dataset_store if dataset_store is not None else DatasetStore()
        # Semaphore mirrors the store's max_concurrent_running for thread safety.
        self._run_semaphore = threading.Semaphore(store._max_concurrent_running)

    # ------------------------------------------------------------------ dataset

    def register_dataset(self, payload: dict[str, object]) -> dict[str, object]:
        """Register a dataset for the review lifecycle."""

        dataset_id_raw = payload.get("datasetId")
        if not isinstance(dataset_id_raw, str):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        record = self._dataset_store.register(dataset_id_raw)
        return record.to_public_dict()

    def submit_dataset_for_review(self, dataset_id: str) -> dict[str, object]:
        """Advance a registered dataset to pending_review."""

        record = self._dataset_store.submit_for_review(dataset_id)
        return record.to_public_dict()

    def review_dataset(
        self, dataset_id: str, payload: dict[str, object]
    ) -> dict[str, object]:
        """Apply an approve or reject decision to a pending-review dataset.

        The ``payload`` must contain ``action: "approve" | "reject"`` and, for
        rejections, a bounded ``reasonCode`` enum value.  No free text is
        accepted or echoed.
        """

        action, reason_code = validate_review_request(payload)
        if action == "approve":
            record = self._dataset_store.approve(dataset_id)
        else:
            assert reason_code is not None
            record = self._dataset_store.reject(dataset_id, reason_code)
        return record.to_public_dict()

    def get_dataset(self, dataset_id: str) -> dict[str, object]:
        """Return the current review status for one dataset."""

        return self._dataset_store.get(dataset_id).to_public_dict()

    # ------------------------------------------------------------------- queue

    def get_queue_state(self) -> dict[str, object]:
        """Return a content-free snapshot of the job queue state."""

        return self._store.queue_state()

    # -------------------------------------------------------------------- jobs

    def create_training_job(self, payload: dict[str, object]) -> dict[str, object]:
        """Validate, create, and optionally complete a fixture training job.

        Raises ``DATASET_NOT_APPROVED`` (403) if the requested dataset has not
        passed the review lifecycle.
        """

        request = TrainingJobRequest.from_mapping(payload)
        if not self._dataset_store.is_approved(request.dataset_id):
            raise ApiError(ErrorCode.DATASET_NOT_APPROVED, 403)
        job = self._store.create(request)
        if self._auto_run_worker and job.status in {
            TrainingJobStatus.QUEUED,
            TrainingJobStatus.RUNNING,
        }:
            acquired = self._run_semaphore.acquire(blocking=True, timeout=10)
            try:
                if acquired:
                    job = self._worker.run_job(job.id)
            finally:
                if acquired:
                    self._run_semaphore.release()
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
        """Return the validated provenance record for one completed fixture job.

        Provenance is also returned for expired (tombstone) jobs when the
        deletion was triggered by retention TTL, not an explicit delete call.
        """

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
