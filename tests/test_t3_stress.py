"""Stress tier tests — T3 concurrent submissions, queue concurrency bound."""

from __future__ import annotations

import concurrent.futures
import threading
import unittest

from scooling_lab_helpers import valid_payload

from scooling_lab.dataset_review import DatasetStore
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


def _make_service(
    *,
    queue_limit: int = 256,
    max_concurrent_running: int = 1,
    auto_run: bool = True,
    dataset_store: DatasetStore | None = None,
) -> TrainingApiService:
    store = TrainingJobStore(
        queue_limit=queue_limit,
        max_concurrent_running=max_concurrent_running,
    )
    return TrainingApiService(
        store, auto_run_worker=auto_run, dataset_store=dataset_store
    )


class T3StressConcurrencyBoundTests(unittest.TestCase):
    """Stress tests verifying the running-job concurrency bound holds under load."""

    def test_stress_t3_concurrent_submissions_never_exceed_running_bound(self) -> None:
        """At most max_concurrent_running jobs are in running state at once.

        We track the peak concurrent running count by hooking into the store
        check; since the fake worker is synchronous the semaphore ensures the
        bound is never exceeded.
        """

        max_running = 2
        service = _make_service(
            max_concurrent_running=max_running, queue_limit=64, auto_run=True
        )
        observed_running: list[int] = []
        lock = threading.Lock()
        original_run_job = service._worker.run_job

        def instrumented_run(job_id: str) -> object:  # type: ignore[misc]
            snapshot = service._store.running_count()
            with lock:
                observed_running.append(snapshot)
            return original_run_job(job_id)

        service._worker.run_job = instrumented_run  # type: ignore[method-assign]

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            list(
                pool.map(
                    lambda i: service.create_training_job(valid_payload(f"conc-{i}")),
                    range(24),
                )
            )

        self.assertTrue(len(observed_running) > 0)
        peak = max(observed_running)
        self.assertLessEqual(
            peak,
            max_running,
            msg=f"Peak concurrent running {peak} exceeded bound {max_running}",
        )

    def test_stress_t3_concurrent_dataset_registrations_are_safe(self) -> None:
        """Concurrent registrations for distinct datasets are all stored correctly."""

        ds_store = DatasetStore()
        dataset_ids = [f"stress-ds-{i:04d}" for i in range(50)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            results = list(
                pool.map(lambda did: ds_store.register(did), dataset_ids)
            )

        self.assertEqual(len(results), 50)
        for did in dataset_ids:
            self.assertEqual(ds_store.get(did).dataset_id, did)

    def test_stress_t3_concurrent_review_decisions_are_stable(self) -> None:
        """Only the first review decision for a dataset wins; retries are idempotent."""

        ds_store = DatasetStore()
        ds_store.register("concurrent-review-ds")
        ds_store.submit_for_review("concurrent-review-ds")

        errors: list[ApiError] = []
        successes: list[str] = []
        lock = threading.Lock()

        def try_approve() -> None:
            try:
                record = ds_store.approve("concurrent-review-ds")
                with lock:
                    successes.append(record.status.value)
            except ApiError as exc:
                with lock:
                    errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: try_approve(), range(16)))

        final = ds_store.get("concurrent-review-ds")
        self.assertEqual(final.status.value, "approved")

    def test_stress_t3_queue_limit_still_enforced_under_concurrent_load(self) -> None:
        """QUEUE_LIMIT_EXCEEDED is returned reliably under concurrent pressure."""

        service = _make_service(
            queue_limit=3, max_concurrent_running=3, auto_run=False
        )
        service.create_training_job(valid_payload("ql-a"))
        service.create_training_job(valid_payload("ql-b"))
        service.create_training_job(valid_payload("ql-c"))

        limit_hits: list[bool] = []
        lock = threading.Lock()

        def try_create(suffix: str) -> None:
            try:
                service.create_training_job(valid_payload(f"ql-overflow-{suffix}"))
            except ApiError as exc:
                if exc.code == ErrorCode.QUEUE_LIMIT_EXCEEDED:
                    with lock:
                        limit_hits.append(True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(try_create, [str(i) for i in range(16)]))

        self.assertGreater(len(limit_hits), 0)


if __name__ == "__main__":
    unittest.main()
