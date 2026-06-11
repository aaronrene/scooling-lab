"""Data-integrity tier tests — T3 provenance/tombstone invariants."""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta

from scooling_lab_helpers import valid_payload

from scooling_lab.dataset_review import DatasetStore, RejectionReasonCode
from scooling_lab.errors import ApiError
from scooling_lab.provenance import validate_provenance_record
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class T3DataIntegrityTests(unittest.TestCase):
    """Data-integrity tests for T3 provenance retention and tombstone content."""

    def test_data_integrity_t3_expired_tombstone_provenance_matches_original(
        self,
    ) -> None:
        """Provenance retained after expiry is byte-for-byte the original record."""

        service = TrainingApiService(TrainingJobStore())
        policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
        created = service.create_training_job(valid_payload("di-expiry-match", policy))
        job_id = str(created["id"])
        prov_before = service.get_provenance(job_id)

        service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))

        prov_after = service.get_provenance(job_id)
        self.assertEqual(
            json.dumps(prov_before, sort_keys=True),
            json.dumps(prov_after, sort_keys=True),
        )
        validate_provenance_record(prov_after)

    def test_data_integrity_t3_expired_tombstone_carries_no_content_bytes(
        self,
    ) -> None:
        """Expired tombstone does not include artifact content, request, or model fields."""

        service = TrainingApiService(TrainingJobStore())
        policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
        created = service.create_training_job(valid_payload("di-expiry-clean", policy))
        job_id = str(created["id"])

        service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))
        tombstone_json = json.dumps(service.get_training_job(job_id), sort_keys=True)

        forbidden = (
            "fixture-tiny-llm",
            "fixture:synthetic-tiny-v1",
            "trainingParameters",
            "request",
        )
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term, tombstone_json)

    def test_data_integrity_t3_expired_tombstone_has_no_artifact_list(self) -> None:
        """Artifact list is empty after TTL expiry."""

        service = TrainingApiService(TrainingJobStore())
        policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
        created = service.create_training_job(valid_payload("di-expiry-arts", policy))
        job_id = str(created["id"])

        service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))

        arts = service.list_artifacts(job_id)
        self.assertEqual(arts["artifacts"], [])

    def test_data_integrity_t3_explicit_delete_hash_absence_verified(self) -> None:
        """Explicit delete still removes hashes from every store serialization."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("di-explicit-delete"))
        job_id = str(created["id"])
        artifact = service.list_artifacts(job_id)["artifacts"][0]
        hashes = (
            str(artifact["datasetHash"]),
            str(artifact["artifactHash"]),
            str(service.get_provenance(job_id)["trainingConfigHash"]),
        )
        service.delete_artifact(job_id, str(artifact["id"]))
        self.assertTrue(service.verify_deleted_artifact_absence(hashes))

    def test_data_integrity_t3_rejection_reason_is_enum_not_free_text(self) -> None:
        """Rejection records expose only enum codes, never caller-supplied text."""

        ds_store = DatasetStore()
        ds_store.register("di-rejection-check")
        ds_store.submit_for_review("di-rejection-check")
        ds_store.reject("di-rejection-check", RejectionReasonCode.SYNTHETIC_LIMIT)
        public = ds_store.get("di-rejection-check").to_public_dict()
        reason_value = str(public.get("rejectionReasonCode", ""))
        self.assertIn(reason_value, {c.value for c in RejectionReasonCode})
        self.assertNotIn("caller supplied reason text", str(public))

    def test_data_integrity_t3_provenance_schema_version_preserved_through_expiry(
        self,
    ) -> None:
        """schemaVersion on retained provenance equals the canonical value."""

        from scooling_lab.provenance import PROVENANCE_SCHEMA_VERSION

        service = TrainingApiService(TrainingJobStore())
        policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
        created = service.create_training_job(valid_payload("di-schema-ver", policy))
        job_id = str(created["id"])
        service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))

        prov = service.get_provenance(job_id)
        self.assertEqual(prov["schemaVersion"], PROVENANCE_SCHEMA_VERSION)

    def test_data_integrity_t3_expiry_does_not_affect_other_jobs(self) -> None:
        """Sweeping one expired job does not touch a job with a long retention TTL."""

        service = TrainingApiService(TrainingJobStore())
        short_policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
        long_policy = {"policyClass": "extended", "ttlSeconds": 86_400}

        short = service.create_training_job(valid_payload("di-short", short_policy))
        long_ = service.create_training_job(valid_payload("di-long", long_policy))

        service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))

        self.assertEqual(service.get_training_job(str(short["id"]))["status"], "deleted")
        self.assertEqual(service.get_training_job(str(long_["id"]))["status"], "succeeded")
        arts_long = service.list_artifacts(str(long_["id"]))
        self.assertEqual(len(arts_long["artifacts"]), 1)


if __name__ == "__main__":
    unittest.main()
