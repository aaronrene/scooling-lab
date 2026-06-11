"""Integration tier tests for Scooling Lab API and BOM generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.bom import collect_entries, render_markdown
from scooling_lab.errors import ApiError
from scooling_lab.provenance import validate_provenance_record
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class ScoolingLabIntegrationTests(unittest.TestCase):
    """Integration tests spanning service, fake worker, store, and BOM."""

    def test_integration_api_to_fake_worker_lifecycle(self) -> None:
        """createTrainingJob completes through the fake worker and lists metadata."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("integration"))
        self.assertEqual(created["status"], "succeeded")
        job_id = str(created["id"])

        fetched = service.get_training_job(job_id)
        self.assertEqual(fetched["id"], job_id)
        self.assertEqual(fetched["status"], "succeeded")

        artifacts = service.list_artifacts(job_id)
        self.assertEqual(len(artifacts["artifacts"]), 1)
        artifact = artifacts["artifacts"][0]
        self.assertEqual(artifact["jobId"], job_id)
        self.assertTrue(str(artifact["datasetHash"]))
        self.assertTrue(str(artifact["artifactHash"]))
        self.assertTrue(str(artifact["provenanceRecordId"]))

    def test_integration_fake_worker_emits_valid_provenance(self) -> None:
        """Worker completion writes a schema-valid provenance record."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("provenance-integration"))
        job_id = str(created["id"])

        provenance = service.get_provenance(job_id)

        validate_provenance_record(provenance)
        self.assertEqual(provenance["jobId"], job_id)
        self.assertEqual(provenance["baseModelId"], "fixture-tiny-llm")

    def test_integration_deletion_cascades_store_and_provenance(self) -> None:
        """deleteArtifact removes artifact metadata and provenance together."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("delete-integration"))
        job_id = str(created["id"])
        artifact = service.list_artifacts(job_id)["artifacts"][0]
        artifact_id = str(artifact["id"])
        deleted_hashes = (
            str(artifact["datasetHash"]),
            str(artifact["artifactHash"]),
            str(service.get_provenance(job_id)["trainingConfigHash"]),
        )

        receipt = service.delete_artifact(job_id, artifact_id)

        self.assertTrue(receipt["deleted"])
        self.assertTrue(service.verify_deleted_artifact_absence(deleted_hashes))
        self.assertEqual(service.list_artifacts(job_id)["artifacts"], [])
        with self.assertRaises(ApiError):
            service.get_provenance(job_id)

    def test_integration_sweep_over_mixed_policy_fixtures(self) -> None:
        """Explicit sweep deletes expired artifacts and keeps unexpired artifacts."""

        service = TrainingApiService(TrainingJobStore())
        expired = service.create_training_job(
            valid_payload(
                "sweep-expired",
                {"policyClass": "ephemeral", "ttlSeconds": 60},
            )
        )
        retained = service.create_training_job(
            valid_payload(
                "sweep-retained",
                {"policyClass": "extended", "ttlSeconds": 86_400},
            )
        )
        sweep_at = datetime.now(UTC) + timedelta(seconds=120)

        summary = service.sweep_expired_artifacts(sweep_at)

        self.assertEqual(summary["deletedCount"], 1)
        self.assertEqual(service.get_training_job(str(expired["id"]))["status"], "deleted")
        self.assertEqual(service.get_training_job(str(retained["id"]))["status"], "succeeded")

    def test_integration_bom_generation_over_real_project_files(self) -> None:
        """The real project pyproject and lockfile generate an allowlisted BOM."""

        entries = collect_entries(PROJECT_ROOT)
        markdown = render_markdown(entries)
        self.assertIn("scooling-lab", markdown)
        self.assertIn("Apache-2.0", markdown)
        self.assertNotIn("AGPL-3.0 |", markdown)


if __name__ == "__main__":
    unittest.main()
