"""Data-integrity tier tests for stable Scooling Lab evidence and hashes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.fake_worker import fixture_dataset_hash
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


EXPECTED_UNSLOTH_NOTICE = (
    "Files under unsloth/*, tests/*, scripts/* are Apache 2.0 licensed.\n"
    "Files under studio/*, unsloth_cli/* which is optional to install are AGPLv3 licensed."
)


class ScoolingLabDataIntegrityTests(unittest.TestCase):
    """Data-integrity tests for retries, restarts, and license evidence."""

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
