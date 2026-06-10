"""Typed contracts for Scooling Lab training job boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class TrainingJobStatus(str, Enum):
    """Lifecycle states exposed by the training boundary."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


AdapterKind = Literal["lora", "qlora"]
ModelLocationPolicy = Literal["local", "cloud_policy"]


@dataclass(frozen=True, slots=True)
class TrainingDatasetRef:
    """Reviewed dataset reference approved by the main Scooling app."""

    dataset_id: str
    workspace_id: str
    source_commit: str
    approved_by: str


@dataclass(frozen=True, slots=True)
class TrainingJobRequest:
    """Server-side request accepted by Scooling Lab after approval gates pass."""

    job_id: str
    dataset: TrainingDatasetRef
    base_model: str
    adapter_kind: AdapterKind
    location_policy: ModelLocationPolicy


def validate_training_job_request(request: TrainingJobRequest) -> tuple[str, ...]:
    """Return deterministic validation errors for a training request."""

    errors: list[str] = []

    if request.job_id.strip() == "":
        errors.append("job_id is required")
    if request.dataset.dataset_id.strip() == "":
        errors.append("dataset.dataset_id is required")
    if request.dataset.workspace_id.strip() == "":
        errors.append("dataset.workspace_id is required")
    if request.dataset.source_commit.strip() == "":
        errors.append("dataset.source_commit is required")
    if request.dataset.approved_by.strip() == "":
        errors.append("dataset.approved_by is required")
    if request.base_model.strip() == "":
        errors.append("base_model is required")

    return tuple(errors)
