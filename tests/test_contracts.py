"""Unit tests for Scooling Lab training contracts."""

from unittest import TestCase

from scooling_lab.contracts import (
    TrainingDatasetRef,
    TrainingJobRequest,
    TrainingJobStatus,
    validate_training_job_request,
)


class TrainingContractTests(TestCase):
    """Validate stable request and status behavior."""

    def test_valid_training_job_request_has_no_errors(self) -> None:
        dataset = TrainingDatasetRef(
            dataset_id="dataset_001",
            workspace_id="workspace_001",
            source_commit="sha256:abc123",
            approved_by="reviewer_001",
        )
        request = TrainingJobRequest(
            job_id="job_001",
            dataset=dataset,
            base_model="gemma-family",
            adapter_kind="lora",
            location_policy="local",
        )

        self.assertEqual(validate_training_job_request(request), ())

    def test_blank_required_fields_are_reported_deterministically(self) -> None:
        dataset = TrainingDatasetRef(
            dataset_id="",
            workspace_id="",
            source_commit="",
            approved_by="",
        )
        request = TrainingJobRequest(
            job_id="",
            dataset=dataset,
            base_model="",
            adapter_kind="qlora",
            location_policy="cloud_policy",
        )

        self.assertEqual(
            validate_training_job_request(request),
            (
                "job_id is required",
                "dataset.dataset_id is required",
                "dataset.workspace_id is required",
                "dataset.source_commit is required",
                "dataset.approved_by is required",
                "base_model is required",
            ),
        )

    def test_training_status_values_are_stable(self) -> None:
        self.assertEqual(TrainingJobStatus.QUEUED.value, "queued")
        self.assertEqual(TrainingJobStatus.SUCCEEDED.value, "succeeded")
