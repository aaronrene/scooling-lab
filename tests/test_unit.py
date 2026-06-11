"""Unit tier tests for Scooling Lab T0/T2 contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from scooling_lab_helpers import valid_payload

from scooling_lab.contracts import TrainingJobRequest, TrainingJobStatus
from scooling_lab.errors import ApiError, ErrorCode, error_payload
from scooling_lab.license_policy import BomEntry, LicensePolicyError, validate_entry
from scooling_lab.provenance import ProvenanceRecord, validate_provenance_record
from scooling_lab.retention import (
    RetentionPolicyClass,
    expires_at,
    is_expired,
    retention_policy_from_mapping,
)
from scooling_lab.service import TrainingApiService
from scooling_lab.state_machine import transition
from scooling_lab.store import TrainingJobStore


class ScoolingLabUnitTests(unittest.TestCase):
    """Unit tests for state transitions, schema, license policy, and errors."""

    def test_unit_state_transitions_are_explicit_and_idempotent(self) -> None:
        """queued -> running -> succeeded works and replay is a no-op."""

        self.assertEqual(
            transition(TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING),
            TrainingJobStatus.RUNNING,
        )
        self.assertEqual(
            transition(TrainingJobStatus.RUNNING, TrainingJobStatus.SUCCEEDED),
            TrainingJobStatus.SUCCEEDED,
        )
        self.assertEqual(
            transition(TrainingJobStatus.SUCCEEDED, TrainingJobStatus.SUCCEEDED),
            TrainingJobStatus.SUCCEEDED,
        )

    def test_unit_invalid_state_transition_raises_safe_error(self) -> None:
        """queued -> succeeded is not allowed by the transition table."""

        with self.assertRaises(ApiError) as raised:
            transition(TrainingJobStatus.QUEUED, TrainingJobStatus.SUCCEEDED)
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_TRANSITION)

    def test_unit_deleted_state_transition_is_terminal(self) -> None:
        """succeeded -> deleted works and deleted cannot transition elsewhere."""

        self.assertEqual(
            transition(TrainingJobStatus.SUCCEEDED, TrainingJobStatus.DELETED),
            TrainingJobStatus.DELETED,
        )
        self.assertEqual(
            transition(TrainingJobStatus.DELETED, TrainingJobStatus.DELETED),
            TrainingJobStatus.DELETED,
        )
        with self.assertRaises(ApiError):
            transition(TrainingJobStatus.DELETED, TrainingJobStatus.RUNNING)

    def test_unit_schema_rejects_unsafe_fields_and_unapproved_models(self) -> None:
        """Dangerous keys and unknown model ids fail in schema validation."""

        payload = valid_payload()
        payload["workerUrl"] = "https://attacker.invalid/worker"
        with self.assertRaises(ApiError):
            TrainingJobRequest.from_mapping(payload)

        model_payload = valid_payload()
        model_payload["modelId"] = "unapproved-model"
        with self.assertRaises(ApiError):
            TrainingJobRequest.from_mapping(model_payload)

    def test_unit_provenance_schema_rejects_free_text_paths_and_urls(self) -> None:
        """Provenance accepts only exact hashes, ids, timestamps, and schema version."""

        record = ProvenanceRecord(
            artifact_hash="b" * 64,
            base_model_id="fixture-tiny-llm",
            created_at="2026-06-11T00:00:00Z",
            dataset_hash="a" * 64,
            job_id="job_" + "1" * 24,
            training_config_hash="c" * 64,
        )
        validate_provenance_record(record)

        unsafe_values = (
            "prompt body with words",
            "../private/path",
            "https://attacker.invalid/model",
        )
        for unsafe in unsafe_values:
            payload = record.to_dict()
            payload["baseModelId"] = unsafe
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ApiError):
                    validate_provenance_record(payload)

    def test_unit_retention_ttl_math_is_bounded_and_deterministic(self) -> None:
        """Retention policies validate TTL bounds and evaluate expiry exactly."""

        policy = retention_policy_from_mapping(
            {"policyClass": "ephemeral", "ttlSeconds": 60}
        )
        self.assertEqual(policy.policy_class, RetentionPolicyClass.EPHEMERAL)
        self.assertEqual(expires_at("2026-06-11T00:00:00Z", policy), "2026-06-11T00:01:00Z")
        self.assertFalse(
            is_expired(
                "2026-06-11T00:00:00Z",
                policy,
                datetime(2026, 6, 11, 0, 0, 59, tzinfo=UTC),
            )
        )
        self.assertTrue(
            is_expired(
                "2026-06-11T00:00:00Z",
                policy,
                datetime(2026, 6, 11, 0, 1, 0, tzinfo=UTC),
            )
        )
        with self.assertRaises(ApiError):
            retention_policy_from_mapping({"policyClass": "ephemeral", "ttlSeconds": 59})

    def test_unit_deletion_state_transition_removes_content_fields(self) -> None:
        """deleteArtifact leaves a content-free deleted job tombstone."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("delete-unit"))
        job_id = str(created["id"])
        artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])

        first_delete = service.delete_artifact(job_id, artifact_id)
        second_delete = service.delete_artifact(job_id, artifact_id)
        tombstone = service.get_training_job(job_id)

        self.assertTrue(first_delete["deleted"])
        self.assertTrue(first_delete["verified"])
        self.assertTrue(second_delete["alreadyDeleted"])
        self.assertEqual(tombstone["status"], "deleted")
        self.assertNotIn("request", tombstone)
        self.assertNotIn("artifactHash", str(tombstone))

    def test_unit_license_policy_blocks_agpl_and_blocked_paths(self) -> None:
        """The BOM policy rejects AGPL licenses and Unsloth Studio/CLI paths."""

        validate_entry(
            BomEntry(
                name="safe",
                version="1.0.0",
                license="MIT",
                source_path="third_party/safe",
                evidence="fixture",
            )
        )
        with self.assertRaises(LicensePolicyError):
            validate_entry(
                BomEntry(
                    name="blocked",
                    version="1.0.0",
                    license="AGPL-3.0",
                    source_path="third_party/blocked",
                    evidence="fixture",
                )
            )
        with self.assertRaises(LicensePolicyError):
            validate_entry(
                BomEntry(
                    name="blocked-path",
                    version="1.0.0",
                    license="Apache-2.0",
                    source_path="vendor/unsloth_cli/main.py",
                    evidence="fixture",
                )
            )

    def test_unit_error_model_does_not_echo_payload_or_paths(self) -> None:
        """Safe errors expose only code and stable public message."""

        payload = error_payload(ApiError(ErrorCode.VALIDATION_ERROR, 400))
        text = str(payload)
        self.assertIn("VALIDATION_ERROR", text)
        self.assertNotIn("/Users/", text)
        self.assertNotIn("attacker.invalid", text)
        self.assertNotIn("payload", text.lower())


if __name__ == "__main__":
    unittest.main()
