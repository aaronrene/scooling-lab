"""Performance tier tests — T3 queue operations and dataset lookup under load."""

from __future__ import annotations

import time
import unittest

from scooling_lab_helpers import valid_payload

from scooling_lab.dataset_review import (
    DatasetStore,
    RejectionReasonCode,
    default_dataset_shape,
)
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class T3PerformanceTests(unittest.TestCase):
    """Performance tests with generous wall-clock thresholds for CI robustness."""

    def test_performance_t3_dataset_store_lookups_are_constant_time(self) -> None:
        """10 000 is_approved checks complete under 1 second."""

        ds_store = DatasetStore()
        start = time.monotonic()
        for _ in range(10_000):
            ds_store.is_approved("fixture:synthetic-tiny-v1")
        elapsed = time.monotonic() - start
        self.assertLess(
            elapsed, 1.0, msg=f"10 000 is_approved calls took {elapsed:.3f}s"
        )

    def test_performance_t3_queue_state_is_fast_under_large_backlog(self) -> None:
        """queue_state call with 200 completed jobs finishes under 0.5 seconds."""

        service = TrainingApiService(TrainingJobStore(queue_limit=256))
        for index in range(200):
            service.create_training_job(valid_payload(f"perf-backlog-{index}"))

        start = time.monotonic()
        for _ in range(500):
            service.get_queue_state()
        elapsed = time.monotonic() - start
        self.assertLess(
            elapsed, 0.5, msg=f"500 queue_state calls took {elapsed:.3f}s"
        )

    def test_performance_t3_bulk_dataset_register_review_is_bounded(self) -> None:
        """Registering and reviewing 500 datasets completes under 3 seconds."""

        ds_store = DatasetStore()
        dataset_ids = [f"perf-ds-{i:05d}" for i in range(500)]
        start = time.monotonic()
        for did in dataset_ids:
            ds_store.register(did)
            ds_store.submit_for_review(did)
            ds_store.approve(did)
        elapsed = time.monotonic() - start
        self.assertLess(
            elapsed, 3.0, msg=f"500 register+review cycles took {elapsed:.3f}s"
        )
        for did in dataset_ids:
            self.assertTrue(ds_store.is_approved(did))

    def test_performance_t3_rejected_dataset_lookup_is_bounded(self) -> None:
        """1 000 is_approved calls on a rejected dataset finish under 0.2 seconds."""

        ds_store = DatasetStore()
        ds_store.register_shape(
            "perf-rejected-ds",
            default_dataset_shape(RejectionReasonCode.POLICY_VIOLATION),
        )
        ds_store.submit_for_review("perf-rejected-ds")
        ds_store.reject("perf-rejected-ds", RejectionReasonCode.POLICY_VIOLATION)

        start = time.monotonic()
        for _ in range(1_000):
            ds_store.is_approved("perf-rejected-ds")
        elapsed = time.monotonic() - start
        self.assertLess(
            elapsed, 0.2, msg=f"1 000 rejected checks took {elapsed:.3f}s"
        )


if __name__ == "__main__":
    unittest.main()
