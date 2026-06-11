"""Performance tier tests for Scooling Lab bounded local operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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

    def test_performance_provenance_emission_is_constant_time_bounded(self) -> None:
        """Repeated provenance emission remains inside a fixed local budget."""

        service = TrainingApiService(TrainingJobStore(queue_limit=1_200))

        start = time.perf_counter()
        for index in range(1_000):
            created = service.create_training_job(valid_payload(f"provenance-{index}"))
            provenance = service.get_provenance(str(created["id"]))
            self.assertTrue(str(provenance["artifactHash"]))
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 3.0)

    def test_performance_sweep_is_bounded_over_ten_thousand_fixture_jobs(self) -> None:
        """Retention sweep over N=10k fixture jobs completes inside CI budget."""

        service = TrainingApiService(TrainingJobStore(queue_limit=10_500))
        payload_policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
        for index in range(10_000):
            service.create_training_job(valid_payload(f"sweep-{index}", payload_policy))

        start = time.perf_counter()
        summary = service.sweep_expired_artifacts(
            datetime.now(UTC) + timedelta(seconds=120)
        )
        elapsed = time.perf_counter() - start

        self.assertEqual(summary["deletedCount"], 10_000)
        self.assertLess(elapsed, 5.0)

    def test_performance_t4_cancel_retry_and_validation_are_bounded(self) -> None:
        """Cancel, retry, and dataset shape validation stay inside a local budget."""

        store = TrainingJobStore(queue_limit=1_600, max_concurrent_running=2)
        service = TrainingApiService(store, auto_run_worker=False)
        created = [
            service.create_training_job(valid_payload(f"perf-t4-{index}"))
            for index in range(1_000)
        ]

        start = time.perf_counter()
        for job in created[:300]:
            service.cancel_training_job(str(job["id"]))
        for job in created[:300]:
            retry = service.retry_training_job(str(job["id"]))
            self.assertEqual(retry["retryOfJobId"], job["id"])
        for index in range(300):
            dataset_id = f"perf-dataset-{index}"
            service.register_dataset(
                {
                    "datasetId": dataset_id,
                    "rowCount": 8,
                    "declaredSchema": {
                        "exampleId": "string",
                        "inputTokenCount": "integer",
                        "outputTokenCount": "integer",
                        "split": "string",
                    },
                }
            )
            decision = service.submit_dataset_for_review(dataset_id)
            self.assertEqual(decision["status"], "approved")
        elapsed = time.perf_counter() - start

        self.assertLessEqual(service.get_queue_state()["runningCount"], 2)
        self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
