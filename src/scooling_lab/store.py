"""Thread-safe job and artifact store for the in-process fake worker."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from scooling_lab.contracts import TrainingJobRequest, TrainingJobStatus
from scooling_lab.errors import ApiError, ErrorCode
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

    def to_dict(self) -> dict[str, str]:
        """Serialize the artifact metadata for API responses and persistence."""

        return {
            "id": self.id,
            "jobId": self.job_id,
            "datasetHash": self.dataset_hash,
            "artifactHash": self.artifact_hash,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "ArtifactMetadata":
        """Rehydrate persisted artifact metadata."""

        return cls(
            id=payload["id"],
            job_id=payload["jobId"],
            dataset_hash=payload["datasetHash"],
            artifact_hash=payload["artifactHash"],
            created_at=payload["createdAt"],
        )


@dataclass
class TrainingJobRecord:
    """Internal record for one fixture training job."""

    id: str
    request: TrainingJobRequest
    status: TrainingJobStatus = TrainingJobStatus.QUEUED
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    artifacts: list[ArtifactMetadata] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, object]:
        """Serialize the safe job status shape for API responses."""

        return {
            "id": self.id,
            "status": self.status.value,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "request": self.request.to_public_dict(),
        }

    def to_persisted_dict(self) -> dict[str, object]:
        """Serialize the full non-secret record to the server-controlled store."""

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
                "trainingParameters": dict(self.request.training_parameters),
            },
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }

    @classmethod
    def from_persisted_dict(cls, payload: dict[str, object]) -> "TrainingJobRecord":
        """Rehydrate a job record from server-controlled JSON."""

        request_payload = payload["request"]
        if not isinstance(request_payload, dict):
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        artifacts_payload = payload.get("artifacts", [])
        if not isinstance(artifacts_payload, list):
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        return cls(
            id=str(payload["id"]),
            request=TrainingJobRequest.from_mapping(request_payload),
            status=TrainingJobStatus(str(payload["status"])),
            created_at=str(payload["createdAt"]),
            updated_at=str(payload["updatedAt"]),
            artifacts=[
                ArtifactMetadata.from_dict(artifact)
                for artifact in artifacts_payload
                if isinstance(artifact, dict)
            ],
        )


class TrainingJobStore:
    """In-memory job store with optional server-controlled JSON persistence."""

    def __init__(self, persistence_path: Path | None = None, queue_limit: int = 5) -> None:
        """Create a store with a bounded queued/running fixture capacity."""

        self._lock = threading.RLock()
        self._jobs: dict[str, TrainingJobRecord] = {}
        self._persistence_path = persistence_path
        self._queue_limit = queue_limit
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
        self, job_id: str, artifact: ArtifactMetadata
    ) -> TrainingJobRecord:
        """Attach a placeholder artifact once, preserving retry stability."""

        with self._lock:
            record = self.get(job_id)
            if all(existing.id != artifact.id for existing in record.artifacts):
                record.artifacts.append(artifact)
                record.updated_at = utc_now_iso()
                self._save()
            return record

    def list_artifacts(self, job_id: str) -> list[ArtifactMetadata]:
        """Return artifacts for one job with no cross-job scan exposure."""

        with self._lock:
            return list(self.get(job_id).artifacts)

    def active_count(self) -> int:
        """Count queued and running jobs for quota enforcement."""

        return sum(
            1
            for record in self._jobs.values()
            if record.status
            in {TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING}
        )

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
