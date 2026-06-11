"""Thread-safe job and artifact store for the in-process fake worker."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from scooling_lab.contracts import (
    TrainingJobRequest,
    TrainingJobStatus,
    require_artifact_id,
    require_job_id,
)
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.provenance import ProvenanceRecord, validate_provenance_record
from scooling_lab.retention import (
    RetentionPolicy,
    expires_at,
    is_expired,
    retention_policy_from_mapping,
)
from scooling_lab.state_machine import transition


def utc_now_iso() -> str:
    """Return a UTC timestamp formatted for public metadata."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ArtifactMetadata:
    """Placeholder artifact metadata registered by the fake worker."""

    id: str
    job_id: str
    dataset_hash: str
    artifact_hash: str
    created_at: str
    provenance_id: str
    retention_policy: RetentionPolicy

    def to_dict(self) -> dict[str, object]:
        """Serialize the artifact metadata for API responses and persistence."""

        return {
            "id": self.id,
            "jobId": self.job_id,
            "datasetHash": self.dataset_hash,
            "artifactHash": self.artifact_hash,
            "createdAt": self.created_at,
            "expiresAt": expires_at(self.created_at, self.retention_policy),
            "provenanceRecordId": self.provenance_id,
            "retentionPolicy": self.retention_policy.to_public_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ArtifactMetadata":
        """Rehydrate persisted artifact metadata."""

        return cls(
            id=str(payload["id"]),
            job_id=str(payload["jobId"]),
            dataset_hash=str(payload["datasetHash"]),
            artifact_hash=str(payload["artifactHash"]),
            created_at=str(payload["createdAt"]),
            provenance_id=str(payload["provenanceRecordId"]),
            retention_policy=retention_policy_from_mapping(payload["retentionPolicy"]),
        )


@dataclass(frozen=True)
class DeletionReceipt:
    """Content-free result for idempotent artifact deletion."""

    job_id: str
    artifact_id: str
    deleted: bool
    already_deleted: bool
    verified: bool

    def to_dict(self) -> dict[str, str | bool]:
        """Serialize deletion status without hashes, paths, or request content."""

        return {
            "alreadyDeleted": self.already_deleted,
            "artifactId": self.artifact_id,
            "deleted": self.deleted,
            "jobId": self.job_id,
            "verified": self.verified,
        }


@dataclass
class TrainingJobRecord:
    """Internal record for one fixture training job."""

    id: str
    request: TrainingJobRequest | None
    status: TrainingJobStatus = TrainingJobStatus.QUEUED
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    artifacts: list[ArtifactMetadata] = field(default_factory=list)
    provenance: ProvenanceRecord | None = None
    deleted_at: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        """Serialize the safe job status shape for API responses."""

        if self.status == TrainingJobStatus.DELETED:
            payload: dict[str, object] = {
                "id": self.id,
                "status": self.status.value,
                "createdAt": self.created_at,
                "updatedAt": self.updated_at,
            }
            if self.deleted_at is not None:
                payload["deletedAt"] = self.deleted_at
            return payload
        if self.request is None:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        return {
            "id": self.id,
            "status": self.status.value,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "request": self.request.to_public_dict(),
        }

    def to_persisted_dict(self) -> dict[str, object]:
        """Serialize the full non-secret record to the server-controlled store."""

        if self.status == TrainingJobStatus.DELETED:
            payload: dict[str, object] = {
                "id": self.id,
                "status": self.status.value,
                "createdAt": self.created_at,
                "updatedAt": self.updated_at,
            }
            if self.deleted_at is not None:
                payload["deletedAt"] = self.deleted_at
            if self.provenance is not None:
                payload["provenance"] = self.provenance.to_dict()
            return payload
        if self.request is None:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        return {
            "id": self.id,
            "status": self.status.value,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "request": {
                "idempotencyKey": self.request.idempotency_key,
                "datasetId": self.request.dataset_id,
                "modelId": self.request.model_id,
                "requestedBy": self.request.requested_by,
                "retentionPolicy": self.request.retention_policy.to_public_dict(),
                "trainingParameters": dict(self.request.training_parameters),
            },
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "provenance": self.provenance.to_dict()
            if self.provenance is not None
            else None,
        }

    @classmethod
    def from_persisted_dict(cls, payload: dict[str, object]) -> "TrainingJobRecord":
        """Rehydrate a job record from server-controlled JSON."""

        status = TrainingJobStatus(str(payload["status"]))
        if status == TrainingJobStatus.DELETED:
            deleted_at = payload.get("deletedAt")
            provenance_payload = payload.get("provenance")
            provenance: ProvenanceRecord | None = None
            if provenance_payload is not None:
                if not isinstance(provenance_payload, dict):
                    raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
                provenance = ProvenanceRecord.from_mapping(provenance_payload)
            return cls(
                id=str(payload["id"]),
                request=None,
                status=status,
                created_at=str(payload["createdAt"]),
                updated_at=str(payload["updatedAt"]),
                deleted_at=str(deleted_at) if deleted_at is not None else None,
                provenance=provenance,
            )
        request_payload = payload["request"]
        if not isinstance(request_payload, dict):
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        artifacts_payload = payload.get("artifacts", [])
        if not isinstance(artifacts_payload, list):
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        provenance_payload = payload.get("provenance")
        provenance = None
        if provenance_payload is not None:
            if not isinstance(provenance_payload, dict):
                raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
            provenance = ProvenanceRecord.from_mapping(provenance_payload)
        return cls(
            id=str(payload["id"]),
            request=TrainingJobRequest.from_mapping(request_payload),
            status=status,
            created_at=str(payload["createdAt"]),
            updated_at=str(payload["updatedAt"]),
            artifacts=[
                ArtifactMetadata.from_dict(artifact)
                for artifact in artifacts_payload
                if isinstance(artifact, dict)
            ],
            provenance=provenance,
        )


class TrainingJobStore:
    """In-memory job store with optional server-controlled JSON persistence."""

    def __init__(
        self,
        persistence_path: Path | None = None,
        queue_limit: int = 5,
        max_concurrent_running: int = 1,
    ) -> None:
        """Create a store with bounded queued/running capacity and a concurrency limit.

        ``queue_limit`` caps the total number of queued+running jobs.
        ``max_concurrent_running`` caps how many jobs may be in the running
        state simultaneously (default 1 — FIFO serial execution).
        """

        self._lock = threading.RLock()
        self._jobs: dict[str, TrainingJobRecord] = {}
        self._persistence_path = persistence_path
        self._queue_limit = queue_limit
        self._max_concurrent_running = max_concurrent_running
        if persistence_path is not None and persistence_path.exists():
            self._load()

    def create(self, request: TrainingJobRequest) -> TrainingJobRecord:
        """Create or return the deterministic duplicate job for a request."""

        with self._lock:
            job_id = request.stable_job_id()
            existing = self._jobs.get(job_id)
            if existing is not None:
                return existing
            if self.active_count() >= self._queue_limit:
                raise ApiError(ErrorCode.QUEUE_LIMIT_EXCEEDED, 429)
            record = TrainingJobRecord(id=job_id, request=request)
            self._jobs[job_id] = record
            self._save()
            return record

    def get(self, job_id: str) -> TrainingJobRecord:
        """Return one job or raise a safe not-found error."""

        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise ApiError(ErrorCode.NOT_FOUND, 404)
            return record

    def update_status(
        self, job_id: str, target_status: TrainingJobStatus
    ) -> TrainingJobRecord:
        """Apply the state machine and persist the updated job."""

        with self._lock:
            record = self.get(job_id)
            next_status = transition(record.status, target_status)
            if next_status != record.status:
                record.status = next_status
                record.updated_at = utc_now_iso()
                self._save()
            return record

    def register_artifact(
        self, job_id: str, artifact: ArtifactMetadata, provenance: ProvenanceRecord
    ) -> TrainingJobRecord:
        """Attach a placeholder artifact once, preserving retry stability."""

        require_job_id(job_id)
        require_artifact_id(artifact.id)
        validate_provenance_record(provenance)
        with self._lock:
            record = self.get(job_id)
            if all(existing.id != artifact.id for existing in record.artifacts):
                record.artifacts.append(artifact)
                record.provenance = provenance
                record.updated_at = utc_now_iso()
                self._save()
            return record

    def list_artifacts(self, job_id: str) -> list[ArtifactMetadata]:
        """Return artifacts for one job with no cross-job scan exposure."""

        require_job_id(job_id)
        with self._lock:
            record = self.get(job_id)
            if record.status == TrainingJobStatus.DELETED:
                return []
            return list(record.artifacts)

    def get_provenance(self, job_id: str) -> ProvenanceRecord:
        """Return the validated provenance record for one completed job.

        Provenance is readable even for deleted tombstones when the deletion
        was triggered by retention expiry (the record retains its provenance).
        Explicitly deleted artifacts have provenance wiped and return NOT_FOUND.
        """

        require_job_id(job_id)
        with self._lock:
            record = self.get(job_id)
            if record.provenance is None:
                raise ApiError(ErrorCode.NOT_FOUND, 404)
            return record.provenance

    def evaluate_expiry(
        self, job_id: str, now: datetime | None = None
    ) -> TrainingJobRecord:
        """Evaluate a job's artifact expiry and delete it when TTL has elapsed."""

        require_job_id(job_id)
        with self._lock:
            record = self.get(job_id)
            self._delete_expired_artifact_locked(record, now or datetime.now(UTC))
            return record

    def sweep_expired(self, now: datetime | None = None) -> dict[str, object]:
        """Delete every expired artifact and return a content-free sweep summary."""

        deleted_job_ids: list[str] = []
        sweep_time = now or datetime.now(UTC)
        with self._lock:
            for record in sorted(self._jobs.values(), key=lambda item: item.id):
                receipt = self._delete_expired_artifact_locked(record, sweep_time)
                if receipt is not None and receipt.deleted:
                    deleted_job_ids.append(record.id)
            return {
                "deletedJobIds": deleted_job_ids,
                "deletedCount": len(deleted_job_ids),
            }

    def delete_artifact(self, job_id: str, artifact_id: str) -> DeletionReceipt:
        """Delete an artifact, provenance, and job content as an idempotent cascade."""

        require_job_id(job_id)
        require_artifact_id(artifact_id)
        with self._lock:
            record = self.get(job_id)
            if record.status == TrainingJobStatus.DELETED:
                return DeletionReceipt(
                    job_id=job_id,
                    artifact_id=artifact_id,
                    deleted=True,
                    already_deleted=True,
                    verified=True,
                )
            artifact = self._find_artifact(record, artifact_id)
            if artifact is None:
                raise ApiError(ErrorCode.NOT_FOUND, 404)
            return self._delete_artifact_locked(record, artifact)

    def verify_hash_absence(self, hash_values: Iterable[str]) -> bool:
        """Verify supplied hashes are absent from every store serialization."""

        hashes = tuple(value for value in hash_values if value)
        if not hashes:
            return False
        with self._lock:
            output = json.dumps(
                {
                    "artifacts": {
                        record.id: [artifact.to_dict() for artifact in record.artifacts]
                        for record in self._jobs.values()
                    },
                    "jobs": [
                        record.to_public_dict()
                        for record in sorted(self._jobs.values(), key=lambda item: item.id)
                    ],
                    "persisted": [
                        record.to_persisted_dict()
                        for record in sorted(self._jobs.values(), key=lambda item: item.id)
                    ],
                    "provenance": {
                        record.id: record.provenance.to_dict()
                        for record in self._jobs.values()
                        if record.provenance is not None
                    },
                },
                sort_keys=True,
            )
        return all(hash_value not in output for hash_value in hashes)

    def active_count(self) -> int:
        """Count queued and running jobs for quota enforcement."""

        return sum(
            1
            for record in self._jobs.values()
            if record.status
            in {TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING}
        )

    def running_count(self) -> int:
        """Count jobs currently in the running state."""

        return sum(
            1
            for record in self._jobs.values()
            if record.status == TrainingJobStatus.RUNNING
        )

    def can_run_now(self) -> bool:
        """Return True when the running-job slot is available."""

        return self.running_count() < self._max_concurrent_running

    def queue_state(self) -> dict[str, object]:
        """Return a content-free snapshot of the job queue state."""

        with self._lock:
            queued = sum(
                1
                for r in self._jobs.values()
                if r.status == TrainingJobStatus.QUEUED
            )
            running = self.running_count()
            return {
                "activeCount": queued + running,
                "maxConcurrentRunning": self._max_concurrent_running,
                "queueLimit": self._queue_limit,
                "queuedCount": queued,
                "runningCount": running,
            }

    def _delete_expired_artifact_locked(
        self, record: TrainingJobRecord, now: datetime
    ) -> DeletionReceipt | None:
        if record.status != TrainingJobStatus.SUCCEEDED:
            return None
        for artifact in record.artifacts:
            if is_expired(artifact.created_at, artifact.retention_policy, now):
                return self._delete_artifact_locked(
                    record, artifact, verify=False, retain_provenance=True
                )
        return None

    def _delete_artifact_locked(
        self,
        record: TrainingJobRecord,
        artifact: ArtifactMetadata,
        verify: bool = True,
        retain_provenance: bool = False,
    ) -> DeletionReceipt:
        hashes = self._hashes_for_artifact(record, artifact)
        record.status = transition(record.status, TrainingJobStatus.DELETED)
        record.request = None
        record.artifacts = []
        if not retain_provenance:
            record.provenance = None
        record.deleted_at = utc_now_iso()
        record.updated_at = record.deleted_at
        self._save()
        return DeletionReceipt(
            job_id=record.id,
            artifact_id=artifact.id,
            deleted=True,
            already_deleted=False,
            verified=self.verify_hash_absence(hashes) if verify else True,
        )

    def _find_artifact(
        self, record: TrainingJobRecord, artifact_id: str
    ) -> ArtifactMetadata | None:
        for artifact in record.artifacts:
            if artifact.id == artifact_id:
                return artifact
        return None

    def _hashes_for_artifact(
        self, record: TrainingJobRecord, artifact: ArtifactMetadata
    ) -> tuple[str, ...]:
        hashes = [artifact.dataset_hash, artifact.artifact_hash]
        if record.provenance is not None:
            hashes.extend(
                [
                    record.provenance.dataset_hash,
                    record.provenance.artifact_hash,
                    record.provenance.training_config_hash,
                ]
            )
        return tuple(hashes)

    def _save(self) -> None:
        if self._persistence_path is None:
            return
        payload = {
            "jobs": [
                record.to_persisted_dict()
                for record in sorted(self._jobs.values(), key=lambda item: item.id)
            ]
        }
        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        self._persistence_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _load(self) -> None:
        if self._persistence_path is None:
            return
        payload = json.loads(self._persistence_path.read_text(encoding="utf-8"))
        jobs = payload.get("jobs", [])
        if not isinstance(jobs, list):
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        self._jobs = {
            record.id: record
            for record in (
                TrainingJobRecord.from_persisted_dict(job)
                for job in jobs
                if isinstance(job, dict)
            )
        }
