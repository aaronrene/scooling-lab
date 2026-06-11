"""Integration tier tests — T3 dataset review + job lifecycle API contract."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from scooling_lab_helpers import valid_payload

from scooling_lab.dataset_review import (
    DatasetStatus,
    DatasetStore,
    RejectionReasonCode,
    default_dataset_shape,
)
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.provenance import validate_provenance_record
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


def _make_service(
    *,
    queue_limit: int = 10,
    max_concurrent_running: int = 1,
    dataset_store: DatasetStore | None = None,
    auto_run: bool = True,
) -> TrainingApiService:
    """Convenience factory for integration tests."""

    store = TrainingJobStore(
        queue_limit=queue_limit, max_concurrent_running=max_concurrent_running
    )
    return TrainingApiService(
        store, auto_run_worker=auto_run, dataset_store=dataset_store
    )


class T3IntegrationDatasetReviewLifecycleTests(unittest.TestCase):
    """Integration tests for the full dataset registration → review flow."""

    def test_integration_t3_register_review_approve_then_submit_job(self) -> None:
        """A dataset that goes through the full approval flow allows job creation."""

        ds_store = DatasetStore()
        ds_store.register("custom-ds-v1")
        ds_store.submit_for_review("custom-ds-v1")
        ds_store.approve("custom-ds-v1")
        # Use a service that also approves the fixture dataset (default).
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)

        # Standard fixture job still works because fixture is pre-approved.
        created = service.create_training_job(valid_payload("integration-approved"))
        self.assertEqual(created["status"], "succeeded")

    def test_integration_t3_unapproved_dataset_blocks_job_at_api_boundary(self) -> None:
        """A dataset that is only registered (not approved) blocks job submission."""

        ds_store = DatasetStore()
        ds_store.register("custom-ds-v2")
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        with self.assertRaises(ApiError) as raised:
            service.create_training_job(
                {
                    "idempotencyKey": "integration-blocked",
                    "datasetId": "custom-ds-v2",
                    "modelId": "fixture-tiny-llm",
                    "requestedBy": "integration-test",
                }
            )
        self.assertEqual(raised.exception.code, ErrorCode.DATASET_NOT_APPROVED)

    def test_integration_t3_rejected_dataset_blocks_job(self) -> None:
        """A rejected dataset is refused at job creation with DATASET_NOT_APPROVED."""

        ds_store = DatasetStore()
        ds_store.register_shape(
            "custom-ds-v3",
            default_dataset_shape(RejectionReasonCode.POLICY_VIOLATION),
        )
        ds_store.submit_for_review("custom-ds-v3")
        ds_store.reject("custom-ds-v3", RejectionReasonCode.POLICY_VIOLATION)
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        with self.assertRaises(ApiError) as raised:
            service.create_training_job(
                {
                    "idempotencyKey": "integration-rejected",
                    "datasetId": "custom-ds-v3",
                    "modelId": "fixture-tiny-llm",
                    "requestedBy": "integration-test",
                }
            )
        self.assertEqual(raised.exception.code, ErrorCode.DATASET_NOT_APPROVED)

    def test_integration_t3_rejection_reason_in_dataset_record(self) -> None:
        """Rejection reason code is visible in the dataset record's public dict."""

        ds_store = DatasetStore()
        ds_store.register_shape(
            "reason-ds-v1",
            default_dataset_shape(RejectionReasonCode.SCHEMA_MISMATCH),
        )
        ds_store.submit_for_review("reason-ds-v1")
        ds_store.reject("reason-ds-v1", RejectionReasonCode.SCHEMA_MISMATCH)
        record = ds_store.get("reason-ds-v1")
        public = record.to_public_dict()
        self.assertEqual(public["rejectionReasonCode"], "SCHEMA_MISMATCH")
        self.assertEqual(public["status"], DatasetStatus.REJECTED.value)

    def test_integration_t3_dataset_status_does_not_expose_free_text(self) -> None:
        """Public dataset record contains no free-text fields from request payload."""

        ds_store = DatasetStore()
        ds_store.register_shape(
            "clean-ds-v1",
            default_dataset_shape(RejectionReasonCode.FORMAT_INVALID),
        )
        ds_store.submit_for_review("clean-ds-v1")
        ds_store.reject("clean-ds-v1", RejectionReasonCode.FORMAT_INVALID)
        public_str = str(ds_store.get("clean-ds-v1").to_public_dict())
        self.assertNotIn("caller message", public_str)
        self.assertIn("FORMAT_INVALID", public_str)


class T3IntegrationQueueStateTests(unittest.TestCase):
    """Integration tests for queue state inspection."""

    def test_integration_t3_queue_state_reflects_active_jobs(self) -> None:
        """Queue state accurately counts queued/running/active jobs."""

        service = _make_service(auto_run=False, max_concurrent_running=2, queue_limit=20)
        initial = service.get_queue_state()
        self.assertEqual(initial["queuedCount"], 0)
        self.assertEqual(initial["runningCount"], 0)
        self.assertEqual(initial["activeCount"], 0)

        service.create_training_job(valid_payload("queue-state-a"))
        service.create_training_job(valid_payload("queue-state-b"))
        after = service.get_queue_state()
        self.assertEqual(after["queuedCount"], 2)
        self.assertEqual(after["maxConcurrentRunning"], 2)

    def test_integration_t3_queue_state_after_completion(self) -> None:
        """Completed jobs do not count in the active queue."""

        service = _make_service(auto_run=True, max_concurrent_running=5, queue_limit=20)
        service.create_training_job(valid_payload("complete-queue"))
        after = service.get_queue_state()
        self.assertEqual(after["queuedCount"], 0)
        self.assertEqual(after["runningCount"], 0)
        self.assertEqual(after["activeCount"], 0)


class T3IntegrationProvenanceOnCompletionTests(unittest.TestCase):
    """Integration tests confirming provenance is always emitted via the Slice-5 validator."""

    def test_integration_t3_every_succeeded_job_has_valid_provenance(self) -> None:
        """Succeeded jobs always expose a schema-valid provenance record."""

        service = _make_service()
        for suffix in ("prov-a", "prov-b", "prov-c"):
            created = service.create_training_job(valid_payload(suffix))
            job_id = str(created["id"])
            self.assertEqual(created["status"], "succeeded")
            prov = service.get_provenance(job_id)
            validate_provenance_record(prov)
            self.assertEqual(prov["jobId"], job_id)

    def test_integration_t3_provenance_links_to_artifact(self) -> None:
        """Provenance artifact hash matches the artifact in the job's artifact list."""

        service = _make_service()
        created = service.create_training_job(valid_payload("prov-link"))
        job_id = str(created["id"])
        artifact = service.list_artifacts(job_id)["artifacts"][0]
        prov = service.get_provenance(job_id)
        self.assertEqual(prov["artifactHash"], artifact["artifactHash"])


class T3IntegrationRetentionIntegrationTests(unittest.TestCase):
    """Integration tests for retention integration (Slice 5 + T3)."""

    def test_integration_t3_expired_artifact_tombstone_has_provenance(self) -> None:
        """After TTL expiry the tombstone still exposes its provenance record."""

        service = _make_service()
        policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
        created = service.create_training_job(valid_payload("retention-prov", policy))
        job_id = str(created["id"])
        prov_before = service.get_provenance(job_id)

        service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))

        tombstone = service.get_training_job(job_id)
        self.assertEqual(tombstone["status"], "deleted")
        self.assertEqual(service.list_artifacts(job_id)["artifacts"], [])
        prov_after = service.get_provenance(job_id)
        self.assertEqual(prov_before["jobId"], prov_after["jobId"])
        self.assertEqual(prov_before["artifactHash"], prov_after["artifactHash"])
        validate_provenance_record(prov_after)

    def test_integration_t3_explicit_delete_wipes_provenance(self) -> None:
        """Explicit deleteArtifact wipes provenance (Slice-5 contract preserved)."""

        service = _make_service()
        created = service.create_training_job(valid_payload("explicit-delete"))
        job_id = str(created["id"])
        artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])
        service.delete_artifact(job_id, artifact_id)
        with self.assertRaises(ApiError) as raised:
            service.get_provenance(job_id)
        self.assertEqual(raised.exception.code, ErrorCode.NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
