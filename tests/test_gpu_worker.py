"""Seven-tier tests for Lab GPU shape accept + isolated worker (T4)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scooling_lab_helpers import SRC_ROOT, GpuWorkerTestEnv, valid_gpu_payload, valid_payload

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
    audit_installed_unsloth_paths,
    clamp_training_parameters,
    execute_gpu_worker_envelope,
    gpu_worker_timeout_seconds,
    hash_file_bytes,
    package_dataset_hash,
)
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore

try:
    import torch

    HAS_CUDA = torch.cuda.is_available()
except ImportError:
    HAS_CUDA = False

requires_gpu = unittest.skipUnless(HAS_CUDA, "CUDA required for real Unsloth train")


def _approve_own(ds_store: DatasetStore, dataset_id: str) -> None:
    ds_store.register(dataset_id)
    ds_store.submit_for_review(dataset_id)
    ds_store.approve(dataset_id)


def _gpu_envelope(
    job_id: str = "job_" + "a" * 24,
    dataset_id: str = "own:gpu-packaged.notes_v1",
) -> dict[str, object]:
    return {
        "jobId": job_id,
        "modelId": GPU_PRODUCT_MODEL_ID,
        "datasetId": dataset_id,
        "retentionPolicy": {"policyClass": "standard", "ttlSeconds": 2592000},
        "trainingParameters": {"dryRun": False, "epochs": 1, "learningRate": 0.1},
    }


class GpuWorkerEnvMixin:
    """Mixin that seeds package roots for GPU worker integration tests."""

    def setUp(self) -> None:
        self._gpu_env = GpuWorkerTestEnv()
        self._gpu_env.__enter__()

    def tearDown(self) -> None:
        self._gpu_env.__exit__(None, None, None)

    def seed_gpu_package(self, dataset_id: str) -> None:
        self._gpu_env.seed_package(dataset_id)


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

    def test_unit_training_param_clamps(self) -> None:
        """Worker clamps epochs and learning rate to T4 bounds."""

        clamped = clamp_training_parameters(
            {"dryRun": False, "epochs": 9, "learningRate": 0.9}
        )
        self.assertEqual(clamped["epochs"], 3)
        self.assertAlmostEqual(clamped["learningRate"], 5e-4)

    def test_unit_gpu_timeout_reads_env(self) -> None:
        """API driver timeout is env-driven with a safe default."""

        prior = os.environ.get("SCOOLING_LAB_GPU_TIMEOUT_SECONDS")
        try:
            os.environ["SCOOLING_LAB_GPU_TIMEOUT_SECONDS"] = "7200"
            self.assertEqual(gpu_worker_timeout_seconds(), 7200)
        finally:
            if prior is None:
                os.environ.pop("SCOOLING_LAB_GPU_TIMEOUT_SECONDS", None)
            else:
                os.environ["SCOOLING_LAB_GPU_TIMEOUT_SECONDS"] = prior

    def test_unit_gpu_envelope_pins_base_model_and_tarball_hash(self) -> None:
        """Stub train writes tarball; artifactHash is SHA-256 of tarball bytes."""

        with GpuWorkerTestEnv() as env:
            env.seed_package("own:gpu-packaged.notes_v1")
            result = execute_gpu_worker_envelope(_gpu_envelope())
            job_id = "job_" + "a" * 24
            artifact_dir = env.artifact_root / job_id
            tarball = artifact_dir / "artifact.tar.gz"
            self.assertTrue(tarball.is_file())
            self.assertEqual(result["artifactHash"], hash_file_bytes(tarball))
            self.assertEqual(
                result["datasetHash"],
                package_dataset_hash("own:gpu-packaged.notes_v1"),
            )
        self.assertEqual(result["baseModelId"], GPU_PRODUCT_MODEL_ID)
        self.assertEqual(len(result["artifactHash"]), 64)

    def test_unit_missing_train_jsonl_fails_closed(self) -> None:
        """Worker refuses when package train.jsonl is absent."""

        with GpuWorkerTestEnv() as env:
            (env.package_root / "own:empty-v1").mkdir(parents=True)
            with self.assertRaises(ApiError):
                execute_gpu_worker_envelope(
                    _gpu_envelope(dataset_id="own:empty-v1")
                )


class LabGpuIntegrationTests(GpuWorkerEnvMixin, unittest.TestCase):
    """2. Integration — service routes GPU jobs to isolated worker."""

    def test_integration_gpu_job_succeeds_via_isolated_worker(self) -> None:
        """Approved own:* GPU job completes with GPU provenance baseModelId."""

        self.seed_gpu_package("own:gpu-int-v1")
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


class LabGpuE2ETests(GpuWorkerEnvMixin, unittest.TestCase):
    """3. End-to-end — HTTP create GPU job + Wave A non-regression."""

    def setUp(self) -> None:
        super().setUp()
        self._ds = DatasetStore()
        _approve_own(self._ds, "own:gpu-e2e-v1")
        self.seed_gpu_package("own:gpu-e2e-v1")
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
        super().tearDown()

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


class LabGpuStressTests(GpuWorkerEnvMixin, unittest.TestCase):
    """4. Stress — concurrent GPU creates stay within queue / success bounds."""

    def test_stress_concurrent_gpu_jobs(self) -> None:
        """Ten concurrent GPU creates succeed without crashing the service."""

        ds_store = DatasetStore()
        for index in range(10):
            dataset_id = f"own:gpu-stress-{index}"
            _approve_own(ds_store, dataset_id)
            self.seed_gpu_package(dataset_id)
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


class LabGpuDataIntegrityTests(GpuWorkerEnvMixin, unittest.TestCase):
    """5. Data integrity — stable package hashes and tarball invariants."""

    def test_data_integrity_package_hash_matches_train_jsonl_bytes(self) -> None:
        """datasetHash is SHA-256 of canonical train.jsonl on disk."""

        self.seed_gpu_package("own:gpu-integrity-v1")
        train_path = self._gpu_env.package_root / "own:gpu-integrity-v1" / "train.jsonl"
        file_hash = hash_file_bytes(train_path)
        self.assertEqual(package_dataset_hash("own:gpu-integrity-v1"), file_hash)

        ds_store = DatasetStore()
        _approve_own(ds_store, "own:gpu-integrity-v1")
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        created = service.create_training_job(
            valid_gpu_payload("integrity", dataset_id="own:gpu-integrity-v1")
        )
        provenance = service.get_provenance(str(created["id"]))
        serialized = json.dumps(provenance)
        for banned in ("http://", "file://", "/Users/", "\\"):
            self.assertNotIn(banned, serialized)
        self.assertEqual(provenance["datasetHash"], file_hash)

    def test_data_integrity_different_content_different_hash(self) -> None:
        """Distinct train.jsonl bytes produce distinct dataset hashes."""

        self.seed_gpu_package("own:gpu-hash-a")
        self._gpu_env.seed_package(
            "own:gpu-hash-b",
            lines=['{"instruction":"other","input":"","output":"x"}\n'],
        )
        hash_a = package_dataset_hash("own:gpu-hash-a")
        hash_b = package_dataset_hash("own:gpu-hash-b")
        self.assertNotEqual(hash_a, hash_b)

    def test_data_integrity_tarball_hash_matches_on_disk(self) -> None:
        """artifactHash equals SHA-256 of artifact.tar.gz on disk."""

        self.seed_gpu_package("own:gpu-tar-v1")
        job_id = "job_" + "b" * 24
        result = execute_gpu_worker_envelope(
            _gpu_envelope(job_id=job_id, dataset_id="own:gpu-tar-v1")
        )
        tarball = self._gpu_env.artifact_root / job_id / "artifact.tar.gz"
        self.assertEqual(result["artifactHash"], hash_file_bytes(tarball))


class LabGpuPerformanceTests(GpuWorkerEnvMixin, unittest.TestCase):
    """6. Performance — GPU completion stays within a tight local bound."""

    def test_performance_gpu_job_completes_under_budget(self) -> None:
        """Single GPU stub job completes in under five seconds."""

        self.seed_gpu_package("own:gpu-perf-v1")
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


class LabGpuSecurityTests(GpuWorkerEnvMixin, unittest.TestCase):
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

        self.seed_gpu_package("own:gpu-sec-sub-v1")
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

    def test_security_worker_logs_exclude_jsonl_and_secrets(self) -> None:
        """Worker logs carry ids/phases only — never JSONL bodies or HF_TOKEN."""

        secret_line = "super-secret-training-note-body"
        prior_token = os.environ.get("HF_TOKEN")
        os.environ["HF_TOKEN"] = "hf_test_secret_token_value"
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        target = logging.getLogger("scooling_lab.gpu_worker")
        target.addHandler(handler)
        target.setLevel(logging.INFO)
        try:
            with GpuWorkerTestEnv() as env:
                env.seed_package(
                    "own:gpu-log-v1",
                    lines=[json.dumps({"instruction": secret_line, "output": "x"}) + "\n"],
                )
                execute_gpu_worker_envelope(
                    _gpu_envelope(dataset_id="own:gpu-log-v1")
                )
            logged = stream.getvalue()
            self.assertIn("job_id=", logged)
            self.assertNotIn(secret_line, logged)
            self.assertNotIn("hf_test_secret_token_value", logged)
        finally:
            target.removeHandler(handler)
            if prior_token is None:
                os.environ.pop("HF_TOKEN", None)
            else:
                os.environ["HF_TOKEN"] = prior_token

    def test_security_unsloth_wheel_path_audit_when_installed(self) -> None:
        """Installed unsloth tree must not contain AGPL studio/unsloth_cli segments."""

        violations = audit_installed_unsloth_paths()
        self.assertEqual(violations, [])


class LabGpuRealTrainTests(unittest.TestCase):
    """@gpu — real Unsloth QLoRA on CUDA hosts only."""

    @requires_gpu
    def test_gpu_real_unsloth_train_writes_adapter(self) -> None:
        """Real train mode produces adapter files under artifact root."""

        with GpuWorkerTestEnv() as env:
            os.environ["SCOOLING_LAB_GPU_TRAIN_MODE"] = "real"
            env.seed_package("own:gpu-real-v1", copy_fixture=True)
            job_id = "job_" + "c" * 24
            result = execute_gpu_worker_envelope(
                _gpu_envelope(job_id=job_id, dataset_id="own:gpu-real-v1")
            )
            artifact_dir = env.artifact_root / job_id
            adapter_dir = artifact_dir / "adapter"
            self.assertTrue((adapter_dir / "adapter_config.json").is_file())
            self.assertTrue(any(adapter_dir.glob("*.safetensors")))
            tarball = artifact_dir / "artifact.tar.gz"
            self.assertEqual(result["artifactHash"], hash_file_bytes(tarball))


if __name__ == "__main__":
    unittest.main()
