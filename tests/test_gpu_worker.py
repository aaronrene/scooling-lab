"""Seven-tier tests for Lab GPU shape accept + isolated worker (LAB-GPU-TRAIN S0)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scooling_lab_helpers import SRC_ROOT, valid_gpu_payload, valid_payload

from scooling_lab.api import make_handler
from scooling_lab.contracts import (
    GPU_PRODUCT_MODEL_ID,
    TrainingJobRequest,
    WAVE_A_MODEL_ID,
)
from scooling_lab.dataset_review import DatasetStore
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.gpu_worker import (
    IsolatedGpuWorker,
    execute_gpu_worker_envelope,
    package_dataset_hash,
)
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


def _approve_own(ds_store: DatasetStore, dataset_id: str) -> None:
    ds_store.register(dataset_id)
    ds_store.submit_for_review(dataset_id)
    ds_store.approve(dataset_id)


class LabGpuUnitTests(unittest.TestCase):
    """1. Unit — schema pins and envelope validation."""

    def test_unit_gpu_shape_accepted_for_own_only(self) -> None:
        """GPU model + dryRun false parses for own:*; fixture+GPU refuses."""

        parsed = TrainingJobRequest.from_mapping(valid_gpu_payload())
        self.assertEqual(parsed.model_id, GPU_PRODUCT_MODEL_ID)
        self.assertFalse(parsed.training_parameters["dryRun"])

        fixture_gpu = valid_gpu_payload()
        fixture_gpu["datasetId"] = "fixture:synthetic-tiny-v1"
        with self.assertRaises(ApiError) as ctx:
            TrainingJobRequest.from_mapping(fixture_gpu)
        self.assertEqual(ctx.exception.code, ErrorCode.VALIDATION_ERROR)

    def test_unit_gpu_rejects_mismatched_dry_run_and_wave_a_false(self) -> None:
        """GPU+dryRun true and Wave A+dryRun false both refuse-closed."""

        gpu_true = valid_gpu_payload()
        gpu_true["trainingParameters"] = {
            "epochs": 1,
            "learningRate": 0.1,
            "dryRun": True,
        }
        with self.assertRaises(ApiError):
            TrainingJobRequest.from_mapping(gpu_true)

        wave_false = valid_payload("wave-false")
        wave_false["datasetId"] = "own:wave-false-v1"
        wave_false["trainingParameters"] = {
            "epochs": 1,
            "learningRate": 0.1,
            "dryRun": False,
        }
        with self.assertRaises(ApiError):
            TrainingJobRequest.from_mapping(wave_false)

    def test_unit_gpu_envelope_pins_base_model(self) -> None:
        """Isolated envelope completion pins baseModelId to the GPU product model."""

        result = execute_gpu_worker_envelope(
            {
                "jobId": "job_" + "a" * 24,
                "modelId": GPU_PRODUCT_MODEL_ID,
                "datasetId": "own:gpu-packaged.notes_v1",
                "retentionPolicy": {"policyClass": "standard", "ttlSeconds": 2592000},
                "trainingParameters": {"dryRun": False, "epochs": 1, "learningRate": 0.1},
            }
        )
        self.assertEqual(result["baseModelId"], GPU_PRODUCT_MODEL_ID)
        self.assertEqual(result["datasetHash"], package_dataset_hash("own:gpu-packaged.notes_v1"))
        self.assertEqual(len(result["artifactHash"]), 64)


class LabGpuIntegrationTests(unittest.TestCase):
    """2. Integration — service routes GPU jobs to isolated worker."""

    def test_integration_gpu_job_succeeds_via_isolated_worker(self) -> None:
        """Approved own:* GPU job completes with GPU provenance baseModelId."""

        ds_store = DatasetStore()
        _approve_own(ds_store, "own:gpu-int-v1")
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        created = service.create_training_job(
            valid_gpu_payload("int", dataset_id="own:gpu-int-v1")
        )
        self.assertEqual(created["status"], "succeeded")
        self.assertEqual(created["request"]["modelId"], GPU_PRODUCT_MODEL_ID)
        self.assertFalse(created["request"]["trainingParameters"]["dryRun"])
        provenance = service.get_provenance(str(created["id"]))
        self.assertEqual(provenance["baseModelId"], GPU_PRODUCT_MODEL_ID)

    def test_integration_wave_a_non_regression(self) -> None:
        """Wave A fixture and own:* dry-run jobs still succeed on the fake worker."""

        service = TrainingApiService(TrainingJobStore())
        fixture = service.create_training_job(valid_payload("wave-a-nr"))
        self.assertEqual(fixture["status"], "succeeded")
        self.assertEqual(fixture["request"]["modelId"], WAVE_A_MODEL_ID)

        ds_store = DatasetStore()
        _approve_own(ds_store, "own:wave-a-nr-v1")
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        own = service.create_training_job(
            {
                "idempotencyKey": "wave-a-own-nr",
                "datasetId": "own:wave-a-nr-v1",
                "modelId": WAVE_A_MODEL_ID,
                "requestedBy": "unit-test",
                "trainingParameters": {"dryRun": True, "epochs": 1},
            }
        )
        self.assertEqual(own["status"], "succeeded")
        self.assertTrue(own["request"]["trainingParameters"]["dryRun"])


class LabGpuE2ETests(unittest.TestCase):
    """3. End-to-end — HTTP create GPU job + Wave A non-regression."""

    def setUp(self) -> None:
        self._ds = DatasetStore()
        _approve_own(self._ds, "own:gpu-e2e-v1")
        self._service = TrainingApiService(TrainingJobStore(), dataset_store=self._ds)
        handler = make_handler(self._service)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._port = self._httpd.server_address[1]
        self._base = f"http://127.0.0.1:{self._port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def tearDown(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def _json(self, path: str, method: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(
            f"{self._base}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_e2e_gpu_http_job_and_wave_a(self) -> None:
        """HTTP accepts GPU shape for approved own:* and keeps Wave A working."""

        gpu = self._json(
            "/training/jobs",
            "POST",
            valid_gpu_payload("e2e", dataset_id="own:gpu-e2e-v1"),
        )
        self.assertEqual(gpu["status"], "succeeded")
        self.assertEqual(gpu["request"]["modelId"], GPU_PRODUCT_MODEL_ID)
        provenance = self._json(f"/training/jobs/{gpu['id']}/provenance", "GET")
        self.assertEqual(provenance["baseModelId"], GPU_PRODUCT_MODEL_ID)

        wave = self._json("/training/jobs", "POST", valid_payload("e2e-wave"))
        self.assertEqual(wave["status"], "succeeded")
        self.assertEqual(wave["request"]["modelId"], WAVE_A_MODEL_ID)

        with self.assertRaises(HTTPError) as ctx:
            self._json(
                "/training/jobs",
                "POST",
                {
                    "idempotencyKey": "e2e-fixture-gpu",
                    "datasetId": "fixture:synthetic-tiny-v1",
                    "modelId": GPU_PRODUCT_MODEL_ID,
                    "requestedBy": "e2e-test",
                    "trainingParameters": {
                        "dryRun": False,
                        "epochs": 1,
                        "learningRate": 0.1,
                    },
                },
            )
        self.assertEqual(ctx.exception.code, 400)


class LabGpuStressTests(unittest.TestCase):
    """4. Stress — concurrent GPU creates stay within queue / success bounds."""

    def test_stress_concurrent_gpu_jobs(self) -> None:
        """Ten concurrent GPU creates succeed without crashing the service."""

        ds_store = DatasetStore()
        for index in range(10):
            _approve_own(ds_store, f"own:gpu-stress-{index}")
        service = TrainingApiService(
            TrainingJobStore(queue_limit=20, max_concurrent_running=2),
            dataset_store=ds_store,
        )

        def _create(index: int) -> str:
            job = service.create_training_job(
                valid_gpu_payload(f"stress-{index}", dataset_id=f"own:gpu-stress-{index}")
            )
            return str(job["status"])

        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(_create, range(10)))
        self.assertEqual(statuses.count("succeeded"), 10)


class LabGpuDataIntegrityTests(unittest.TestCase):
    """5. Data integrity — stable package hashes and no private content in artifacts."""

    def test_data_integrity_package_hash_stable_and_content_free(self) -> None:
        """Package dataset hash is stable and provenance omits free text / paths."""

        first = package_dataset_hash("own:gpu-integrity-v1")
        second = package_dataset_hash("own:gpu-integrity-v1")
        self.assertEqual(first, second)
        self.assertNotEqual(first, package_dataset_hash("own:gpu-integrity-v2"))

        ds_store = DatasetStore()
        _approve_own(ds_store, "own:gpu-integrity-v1")
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        created = service.create_training_job(
            valid_gpu_payload("integrity", dataset_id="own:gpu-integrity-v1")
        )
        provenance = service.get_provenance(str(created["id"]))
        serialized = json.dumps(provenance)
        for banned in ("http://", "file://", "prompt", "note body", "/Users/", "\\"):
            self.assertNotIn(banned, serialized)
        self.assertEqual(provenance["datasetHash"], first)


class LabGpuPerformanceTests(unittest.TestCase):
    """6. Performance — GPU completion stays within a tight local bound."""

    def test_performance_gpu_job_completes_under_budget(self) -> None:
        """Single GPU job completes in under five seconds on local stdlib worker."""

        ds_store = DatasetStore()
        _approve_own(ds_store, "own:gpu-perf-v1")
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        started = time.perf_counter()
        created = service.create_training_job(
            valid_gpu_payload("perf", dataset_id="own:gpu-perf-v1")
        )
        elapsed = time.perf_counter() - started
        self.assertEqual(created["status"], "succeeded")
        self.assertLess(elapsed, 5.0)


class LabGpuSecurityTests(unittest.TestCase):
    """7. Security — forbidden keys, unapproved ids, subprocess isolation."""

    def test_security_rejects_worker_urls_and_paths_on_gpu_payload(self) -> None:
        """GPU payloads still reject worker URLs, callbacks, and path-like keys."""

        for key, value in (
            ("workerUrl", "https://attacker.invalid/worker"),
            ("callbackUrl", "https://attacker.invalid/cb"),
            ("modelPath", "/tmp/weights.bin"),
            ("shellCommand", "rm -rf /"),
        ):
            payload = valid_gpu_payload(f"sec-{key}")
            payload[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ApiError) as ctx:
                    TrainingJobRequest.from_mapping(payload)
                self.assertEqual(ctx.exception.code, ErrorCode.VALIDATION_ERROR)

    def test_security_gpu_worker_is_subprocess_not_in_process_only(self) -> None:
        """IsolatedGpuWorker completes GPU jobs; module entrypoint fails closed."""

        ds_store = DatasetStore()
        _approve_own(ds_store, "own:gpu-sec-sub-v1")
        store = TrainingJobStore()
        service = TrainingApiService(store, auto_run_worker=False, dataset_store=ds_store)
        created = service.create_training_job(
            valid_gpu_payload("sec-sub", dataset_id="own:gpu-sec-sub-v1")
        )
        job_id = str(created["id"])
        self.assertEqual(created["status"], "queued")

        worker = IsolatedGpuWorker(store)
        completed = worker.run_job(job_id)
        self.assertEqual(completed.status.value, "succeeded")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        proc = subprocess.run(
            [sys.executable, "-m", "scooling_lab.gpu_worker"],
            input=json.dumps({"jobId": "bad"}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
