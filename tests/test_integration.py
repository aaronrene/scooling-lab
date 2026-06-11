"""Integration tier tests for Scooling Lab API and BOM generation."""

from __future__ import annotations

import unittest

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.bom import collect_entries, render_markdown
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

    def test_integration_bom_generation_over_real_project_files(self) -> None:
        """The real project pyproject and lockfile generate an allowlisted BOM."""

        entries = collect_entries(PROJECT_ROOT)
        markdown = render_markdown(entries)
        self.assertIn("scooling-lab", markdown)
        self.assertIn("Apache-2.0", markdown)
        self.assertNotIn("AGPL-3.0 |", markdown)


if __name__ == "__main__":
    unittest.main()
