"""Performance tier tests for Scooling Lab bounded local operations."""

from __future__ import annotations

import time
import unittest

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.bom import main as bom_main
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class ScoolingLabPerformanceTests(unittest.TestCase):
    """Performance tests for status/list endpoints and BOM scan budget."""

    def test_performance_status_and_list_artifacts_are_bounded(self) -> None:
        """Repeated status and artifact reads remain inside a local budget."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("performance"))
        job_id = str(created["id"])

        start = time.perf_counter()
        for _ in range(200):
            self.assertEqual(service.get_training_job(job_id)["status"], "succeeded")
            self.assertEqual(len(service.list_artifacts(job_id)["artifacts"]), 1)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 1.0)

    def test_performance_bom_scan_runs_inside_ci_budget(self) -> None:
        """The real BOM check completes within the configured CI budget."""

        start = time.perf_counter()
        exit_code = bom_main(
            [
                "--root",
                str(PROJECT_ROOT),
                "--output",
                "DEPENDENCIES.md",
                "--check",
                "--budget-seconds",
                "30",
            ]
        )
        elapsed = time.perf_counter() - start

        self.assertEqual(exit_code, 0)
        self.assertLess(elapsed, 30)


if __name__ == "__main__":
    unittest.main()
