"""Stress tier tests for duplicate creation and fixture queue limits."""

from __future__ import annotations

import concurrent.futures
import unittest

from scooling_lab_helpers import valid_payload

from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class ScoolingLabStressTests(unittest.TestCase):
    """Stress tests for deterministic idempotency and bounded queues."""

    def test_stress_concurrent_duplicate_create_is_deduplicated(self) -> None:
        """Many concurrent duplicate creates return one deterministic job id."""

        service = TrainingApiService(TrainingJobStore(), auto_run_worker=False)
        payload = valid_payload("duplicate")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(lambda _: service.create_training_job(payload), range(24))
            )

        job_ids = {result["id"] for result in results}
        self.assertEqual(len(job_ids), 1)
        self.assertEqual(results[0]["status"], "queued")

    def test_stress_many_fixture_jobs_respect_queue_limit(self) -> None:
        """The fixture queue rejects excess queued/running jobs deterministically."""

        service = TrainingApiService(
            TrainingJobStore(queue_limit=2), auto_run_worker=False
        )
        service.create_training_job(valid_payload("queue-a"))
        service.create_training_job(valid_payload("queue-b"))

        with self.assertRaises(ApiError) as raised:
            service.create_training_job(valid_payload("queue-c"))
        self.assertEqual(raised.exception.code, ErrorCode.QUEUE_LIMIT_EXCEEDED)


if __name__ == "__main__":
    unittest.main()
