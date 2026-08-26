"""Application service for Scooling Lab training API operations."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable

from scooling_lab.artifact_storage import (
    ArtifactStorageBackend,
    VolumeArtifactStorage,
    artifact_storage_from_env,
    local_tarball_path,
)
from scooling_lab.contracts import (
    GPU_PRODUCT_MODEL_ID,
    TrainingJobRequest,
    TrainingJobStatus,
    require_artifact_id,
    require_job_id,
)
from scooling_lab.dataset_review import (
    DatasetStatus,
    DatasetStore,
    dataset_shape_from_registration,
    validate_review_request,
)
from scooling_lab.download_auth import verify_download_auth
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.fake_worker import FakeTrainingWorker
from scooling_lab.gpu_worker import IsolatedGpuWorker
from scooling_lab.package_ingest import parse_package_ingest_request, write_package_files
from scooling_lab.server_auth import verify_ingest_auth
from scooling_lab.store import TrainingJobRecord, TrainingJobStore


class TrainingApiService:
    """Implements the T2/T3 API contract over a store, workers, and dataset store.

    Dataset approval is checked before any job is created.  A ``threading.Semaphore``
    enforces the ``max_concurrent_running`` bound from the store so that concurrent
    callers see at most that many jobs in the running state simultaneously.

    Wave A jobs (``fixture-tiny-llm``) use the in-process fake worker. Product GPU
    jobs (``scooling-lab-gpu-personal-v1``) use the isolated GPU worker subprocess.
    """

    def __init__(
        self,
        store: TrainingJobStore,
        auto_run_worker: bool = True,
        dataset_store: DatasetStore | None = None,
        artifact_storage: ArtifactStorageBackend | None = None,
    ) -> None:
        """Create a service with optional synchronous worker completion.

        If ``dataset_store`` is omitted a default store pre-approving the
        synthetic fixture dataset is used, so existing callers are unaffected.
        """

        self._artifact_storage = (
            artifact_storage
            if artifact_storage is not None
            else artifact_storage_from_env()
        )
        self._store = store
        if store._on_storage_delete is None and self._artifact_storage is not None:
            store._on_storage_delete = self._artifact_storage.delete
        self._fake_worker = FakeTrainingWorker(store)
        self._gpu_worker = IsolatedGpuWorker(store)
        self._auto_run_worker = auto_run_worker
        self._dataset_store = dataset_store if dataset_store is not None else DatasetStore()
        # Semaphore mirrors the store's max_concurrent_running for thread safety.
        self._run_semaphore = threading.Semaphore(store._max_concurrent_running)

    # ------------------------------------------------------------------ dataset

    def register_dataset(self, payload: dict[str, object]) -> dict[str, object]:
        """Register a dataset for the review lifecycle."""

        dataset_id, synthetic_shape = dataset_shape_from_registration(payload)
        record = self._dataset_store.register_shape(dataset_id, synthetic_shape)
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

    def ingest_dataset_package(
        self,
        dataset_id: str,
        payload: dict[str, object],
        authorization_header: str,
    ) -> dict[str, object]:
        """Write canonical training JSONL for a registered own:* dataset (server auth only)."""

        verify_ingest_auth(authorization_header, dataset_id)
        record = self._dataset_store.get(dataset_id)
        if record.status == DatasetStatus.REJECTED:
            raise ApiError(ErrorCode.CONFLICT, 409)
        rows, vault_scope, row_count = parse_package_ingest_request(payload)
        _, dataset_hash = write_package_files(
            dataset_id,
            rows,
            vault_scope,
            row_count,
        )
        return {
            "datasetId": dataset_id,
            "datasetHash": dataset_hash,
            "rowCount": row_count,
            "vaultScope": vault_scope,
        }

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
        job = self._run_if_configured(job.id)
        return job.to_public_dict()

    def get_training_job(self, job_id: str) -> dict[str, object]:
        """Return the public status for one training job."""

        require_job_id(job_id)
        return self._store.evaluate_expiry(job_id).to_public_dict()

    def cancel_training_job(self, job_id: str) -> dict[str, object]:
        """Cancel a queued or running training job."""

        require_job_id(job_id)
        return self._store.cancel(job_id).to_public_dict()

    def retry_training_job(self, job_id: str) -> dict[str, object]:
        """Retry a failed or cancelled job with a fresh lineage-linked job id."""

        require_job_id(job_id)
        retry = self._store.retry(job_id)
        retry = self._run_if_configured(retry.id)
        return retry.to_public_dict()

    def list_artifacts(self, job_id: str) -> dict[str, object]:
        """Return placeholder artifacts registered for one job."""

        require_job_id(job_id)
        self._store.evaluate_expiry(job_id)
        artifacts = self._store.list_artifacts(job_id)
        return {"jobId": job_id, "artifacts": artifacts}

    def get_provenance(self, job_id: str) -> dict[str, object]:
        """Return the validated provenance record for one completed fixture job.

        Provenance is also returned for expired (tombstone) jobs when the
        deletion was triggered by retention TTL, not an explicit delete call.
        """

        require_job_id(job_id)
        self._store.evaluate_expiry(job_id)
        return self._store.get_provenance(job_id).to_dict()

    def get_artifact_download(
        self,
        job_id: str,
        artifact_id: str,
        authorization_header: str,
    ) -> dict[str, object]:
        """Return a signed download URL for one stored artifact (server auth only)."""

        require_job_id(job_id)
        require_artifact_id(artifact_id)
        verify_download_auth(authorization_header, job_id, artifact_id)
        if self._artifact_storage is None:
            raise ApiError(ErrorCode.NOT_FOUND, 404)
        self._store.evaluate_expiry(job_id)
        record = self._store.get(job_id)
        artifact = next(
            (item for item in record.artifacts if item.id == artifact_id),
            None,
        )
        if artifact is None or artifact.storage_key is None:
            raise ApiError(ErrorCode.NOT_FOUND, 404)
        signed = self._artifact_storage.issue_download(
            job_id,
            artifact_id,
            artifact.storage_key,
        )
        return {
            "artifactId": artifact_id,
            "jobId": job_id,
            **signed.to_public_dict(),
        }

    def read_artifact_content(
        self,
        job_id: str,
        artifact_id: str,
        token: str,
    ) -> tuple[bytes, str]:
        """Stream artifact bytes for a volume signed-content token."""

        require_job_id(job_id)
        require_artifact_id(artifact_id)
        if not isinstance(self._artifact_storage, VolumeArtifactStorage):
            raise ApiError(ErrorCode.NOT_FOUND, 404)
        from scooling_lab.artifact_storage import verify_volume_content_token  # noqa: PLC0415

        storage_key = verify_volume_content_token(job_id, artifact_id, token)
        path = self._artifact_storage.resolve_path(storage_key)
        if not path.is_file():
            raise ApiError(ErrorCode.NOT_FOUND, 404)
        return path.read_bytes(), "application/gzip"

    def delete_artifact(self, job_id: str, artifact_id: str) -> dict[str, object]:
        """Delete an artifact and all derived content-bearing metadata."""

        require_job_id(job_id)
        require_artifact_id(artifact_id)
        receipt, _storage_key = self._store.delete_artifact(job_id, artifact_id)
        return receipt.to_dict()

    def sweep_expired_artifacts(self, now: datetime | None = None) -> dict[str, object]:
        """Evaluate all retention policies and delete expired artifacts."""

        summary, _storage_keys = self._store.sweep_expired(now)
        return summary

    def verify_deleted_artifact_absence(self, hash_values: Iterable[str]) -> bool:
        """Verify deleted artifact hashes are absent from all store outputs."""

        return self._store.verify_hash_absence(hash_values)

    def _run_if_configured(self, job_id: str) -> TrainingJobRecord:
        """Run a queued/running job through the matching worker when configured."""

        if not self._auto_run_worker:
            return self._store.get(job_id)
        job = self._store.get(job_id)
        if job.status not in {
            TrainingJobStatus.QUEUED,
            TrainingJobStatus.RUNNING,
        }:
            return job
        acquired = self._run_semaphore.acquire(blocking=True, timeout=10)
        try:
            if acquired:
                completed = self._dispatch_worker(job_id)
                if completed.status == TrainingJobStatus.SUCCEEDED:
                    self._upload_artifacts_for_job(job_id)
                return completed
            return self._store.get(job_id)
        finally:
            if acquired:
                self._run_semaphore.release()

    def _dispatch_worker(self, job_id: str) -> TrainingJobRecord:
        """Route Wave A jobs to the fake worker and GPU jobs to the isolated worker."""

        job = self._store.get(job_id)
        if job.request is None:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        if job.request.model_id == GPU_PRODUCT_MODEL_ID:
            return self._gpu_worker.run_job(job_id)
        return self._fake_worker.run_job(job_id)

    def _upload_artifacts_for_job(self, job_id: str) -> None:
        """Upload adapter tarballs to object storage when configured."""

        if self._artifact_storage is None:
            return
        record = self._store.get(job_id)
        tarball = local_tarball_path(job_id)
        if not tarball.is_file():
            return
        for artifact in record.artifacts:
            if artifact.storage_key is not None:
                continue
            storage_key = self._artifact_storage.upload(job_id, artifact.id, tarball)
            self._store.set_artifact_storage_key(job_id, artifact.id, storage_key)
