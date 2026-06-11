"""Data-integrity tier tests for provenance and deletion invariants."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.contracts import TrainingJobStatus
from scooling_lab.fake_worker import fixture_dataset_hash
from scooling_lab.provenance import validate_provenance_record
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


EXPECTED_UNSLOTH_NOTICE = (
    "Files under unsloth/*, tests/*, scripts/* are Apache 2.0 licensed.\n"
    "Files under studio/*, unsloth_cli/* which is optional to install are AGPLv3 licensed."
)


class ScoolingLabDataIntegrityTests(unittest.TestCase):
    """Data-integrity tests for stable hashes, reloads, and tombstones."""

    def test_data_integrity_provenance_hashes_stable_across_restarts(self) -> None:
        """Persisted jobs reload with the same provenance and artifact hashes."""

        with tempfile.TemporaryDirectory() as directory:
            store_path = Path(directory) / "store.json"
            service = TrainingApiService(TrainingJobStore(persistence_path=store_path))
            created = service.create_training_job(valid_payload("restart-stability"))
            job_id = str(created["id"])
            first_artifact = service.list_artifacts(job_id)["artifacts"][0]
            first_provenance = service.get_provenance(job_id)

            reloaded = TrainingApiService(TrainingJobStore(persistence_path=store_path))
            replayed = reloaded.create_training_job(valid_payload("restart-stability"))
            second_artifact = reloaded.list_artifacts(job_id)["artifacts"][0]
            second_provenance = reloaded.get_provenance(job_id)

            self.assertEqual(replayed["id"], job_id)
            self.assertEqual(first_artifact["artifactHash"], second_artifact["artifactHash"])
            self.assertEqual(first_artifact["datasetHash"], second_artifact["datasetHash"])
            self.assertEqual(first_provenance, second_provenance)

    def test_data_integrity_deletion_verification_finds_zero_residue(self) -> None:
        """Deletion verification proves deleted hashes are absent from store output."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("zero-residue"))
        job_id = str(created["id"])
        artifact = service.list_artifacts(job_id)["artifacts"][0]
        provenance = service.get_provenance(job_id)
        deleted_hashes = (
            str(artifact["datasetHash"]),
            str(artifact["artifactHash"]),
            str(provenance["trainingConfigHash"]),
        )

        service.delete_artifact(job_id, str(artifact["id"]))

        self.assertTrue(service.verify_deleted_artifact_absence(deleted_hashes))

    def test_data_integrity_tombstone_carries_no_content_fields(self) -> None:
        """Deleted job tombstones do not carry request, model, dataset, or hash fields."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("tombstone"))
        job_id = str(created["id"])
        artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])

        service.delete_artifact(job_id, artifact_id)
        tombstone_json = json.dumps(service.get_training_job(job_id), sort_keys=True)

        forbidden_terms = (
            "artifactHash",
            "datasetHash",
            "fixture-tiny-llm",
            "fixture:synthetic-tiny-v1",
            "request",
            "trainingParameters",
        )
        for forbidden in forbidden_terms:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, tombstone_json)

    def test_data_integrity_t4_retry_lineage_and_original_immutability(self) -> None:
        """Retry provenance is valid while the cancelled original remains unchanged."""

        store = TrainingJobStore()
        service = TrainingApiService(store, auto_run_worker=False)
        original = service.create_training_job(valid_payload("di-t4-original"))
        original_id = str(original["id"])
        cancelled = service.cancel_training_job(original_id)
        original_snapshot = json.dumps(
            service.get_training_job(original_id),
            sort_keys=True,
        )
        retry_service = TrainingApiService(store)

        retried = retry_service.retry_training_job(original_id)
        provenance = retry_service.get_provenance(str(retried["id"]))
        original_after_retry = json.dumps(
            retry_service.get_training_job(original_id),
            sort_keys=True,
        )

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(original_snapshot, original_after_retry)
        self.assertEqual(retried["retryOfJobId"], original_id)
        self.assertEqual(retried["status"], "succeeded")
        validate_provenance_record(provenance)
        self.assertEqual(provenance["jobId"], retried["id"])
        self.assertNotEqual(provenance["jobId"], original_id)

    def test_data_integrity_t4_cancelled_terminal_record_has_no_artifacts(self) -> None:
        """Cancelled jobs are terminal active-records without artifact metadata."""

        service = TrainingApiService(TrainingJobStore(), auto_run_worker=False)
        created = service.create_training_job(valid_payload("di-t4-cancelled"))
        job_id = str(created["id"])

        cancelled = service.cancel_training_job(job_id)

        self.assertEqual(cancelled["status"], TrainingJobStatus.CANCELLED.value)
        self.assertEqual(service.list_artifacts(job_id)["artifacts"], [])

    def test_data_integrity_job_and_artifact_hashes_survive_restart(self) -> None:
        """Job id, dataset hash, and artifact hash are stable after reload."""

        with tempfile.TemporaryDirectory() as directory:
            persistence_path = Path(directory) / "jobs.json"
            service = TrainingApiService(TrainingJobStore(persistence_path))
            created = service.create_training_job(valid_payload("restart"))
            job_id = str(created["id"])
            artifact = service.list_artifacts(job_id)["artifacts"][0]
            artifact_hash = str(artifact["artifactHash"])
            dataset_hash = str(artifact["datasetHash"])

            reloaded = TrainingApiService(TrainingJobStore(persistence_path))
            recreated = reloaded.create_training_job(valid_payload("restart"))
            reloaded_artifact = reloaded.list_artifacts(job_id)["artifacts"][0]

            self.assertEqual(recreated["id"], job_id)
            self.assertEqual(reloaded_artifact["datasetHash"], dataset_hash)
            self.assertEqual(reloaded_artifact["artifactHash"], artifact_hash)
            self.assertEqual(dataset_hash, fixture_dataset_hash())

    def test_data_integrity_unsloth_evidence_preserved_byte_for_byte(self) -> None:
        """CI-visible license evidence preserves the pinned candidate and notice."""

        evidence = (PROJECT_ROOT / "docs/UNSLOTH-LICENSE-EVIDENCE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("- Candidate version: `2026.6.1`.", evidence)
        self.assertIn(EXPECTED_UNSLOTH_NOTICE, evidence)


if __name__ == "__main__":
    unittest.main()
