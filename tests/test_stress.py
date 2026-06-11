"""Stress tier tests for duplicate creation and fixture queue limits."""

from __future__ import annotations

import concurrent.futures
from datetime import UTC, datetime, timedelta
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

    def test_stress_many_jobs_interleave_deletes_and_sweeps(self) -> None:
        """Many completed jobs can be deleted and swept without resurrecting data."""

        service = TrainingApiService(TrainingJobStore(queue_limit=256))
        job_ids: list[str] = []
        artifact_ids: list[str] = []
        for index in range(120):
            policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
            created = service.create_training_job(valid_payload(f"stress-{index}", policy))
            job_id = str(created["id"])
            artifact = service.list_artifacts(job_id)["artifacts"][0]
            job_ids.append(job_id)
            artifact_ids.append(str(artifact["id"]))

        for job_id, artifact_id in zip(job_ids[::3], artifact_ids[::3], strict=True):
            service.delete_artifact(job_id, artifact_id)
        summary = service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))

        self.assertGreater(summary["deletedCount"], 0)
        for job_id in job_ids:
            self.assertEqual(service.get_training_job(job_id)["status"], "deleted")
            self.assertEqual(service.list_artifacts(job_id)["artifacts"], [])

    def test_stress_concurrent_delete_and_read_never_resurrects_data(self) -> None:
        """Concurrent delete and read operations settle on a deleted tombstone."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("stress-race"))
        job_id = str(created["id"])
        artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])

        def delete_once() -> str:
            result = service.delete_artifact(job_id, artifact_id)
            return str(result["deleted"])

        def read_once() -> str:
            try:
                return str(service.get_training_job(job_id)["status"])
            except ApiError as error:
                return error.code.value

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(delete_once if index % 2 == 0 else read_once)
                for index in range(40)
            ]
            results = [future.result() for future in futures]

        self.assertIn("True", results)
        self.assertEqual(service.get_training_job(job_id)["status"], "deleted")
        self.assertEqual(service.list_artifacts(job_id)["artifacts"], [])


if __name__ == "__main__":
    unittest.main()
