"""Seven-tier tests for T5 vault dataset package ingest."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scooling_lab_helpers import (
    ingest_authorization_header,
    valid_gpu_payload,
    valid_package_ingest_payload,
)

from scooling_lab.api import make_handler
from scooling_lab.dataset_review import DatasetStore
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.gpu_worker import hash_file_bytes, package_dataset_hash
from scooling_lab.package_ingest import canonical_train_jsonl_bytes, parse_package_ingest_request
from scooling_lab.server_auth import sign_ingest_jwt, verify_ingest_auth
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore

_INGEST_SECRET = "t5-test-ingest-secret"


class PackageIngestEnv:
    """Temp package root + ingest auth secret for T5 tests."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.package_root = self._tmpdir.name + "/packages"
        os.makedirs(self.package_root, exist_ok=True)
        self._prior: dict[str, str | None] = {}

    def __enter__(self) -> "PackageIngestEnv":
        for key, value in (
            ("SCOOLING_LAB_PACKAGE_ROOT", self.package_root),
            ("SCOOLING_LAB_INGEST_AUTH_SECRET", _INGEST_SECRET),
        ):
            self._prior[key] = os.environ.get(key)
            os.environ[key] = value
        return self

    def __exit__(self, *args: object) -> None:
        for key, prior in self._prior.items():
            if prior is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior
        self._tmpdir.cleanup()


def _register_own(ds_store: DatasetStore, dataset_id: str) -> None:
    ds_store.register(dataset_id)


class T5PackageUnitTests(unittest.TestCase):
    """1. Unit — canonical bytes, scope validation, JWT envelope."""

    def test_unit_canonical_jsonl_bytes_stable(self) -> None:
        """Canonical serialization is deterministic."""

        rows = [{"instruction": "a", "input": "b", "output": "c"}]
        first = canonical_train_jsonl_bytes(rows)
        second = canonical_train_jsonl_bytes(rows)
        self.assertEqual(first, second)
        self.assertTrue(first.endswith(b"\n"))

    def test_unit_parse_package_rejects_path_keys(self) -> None:
        """Browser-style path keys are refused at schema validation."""

        payload = valid_package_ingest_payload()
        payload["filePath"] = "/tmp/train.jsonl"
        with self.assertRaises(ApiError) as ctx:
            parse_package_ingest_request(payload)
        self.assertEqual(ctx.exception.code, ErrorCode.VALIDATION_ERROR)

    def test_unit_jwt_dataset_binding(self) -> None:
        """JWT datasetId must match the route dataset id."""

        with PackageIngestEnv():
            dataset_id = "own:pkg-unit-v1"
            token = sign_ingest_jwt("own:other-v1", "scooling.server", secret=_INGEST_SECRET)
            with self.assertRaises(ApiError) as ctx:
                verify_ingest_auth(f"Bearer {token}", dataset_id)
            self.assertEqual(ctx.exception.code, ErrorCode.UNAUTHORIZED)


class T5PackageIntegrationTests(unittest.TestCase):
    """2. Integration — service writes package and GPU provenance matches hash."""

    def test_integration_ingest_then_gpu_job_hash_matches(self) -> None:
        """Ingested package drives content-based datasetHash in provenance."""

        with PackageIngestEnv() as env:
            ds_store = DatasetStore()
            dataset_id = "own:pkg-int-v1"
            _register_own(ds_store, dataset_id)
            service = TrainingApiService(
                TrainingJobStore(),
                dataset_store=ds_store,
                auto_run_worker=False,
            )
            payload = valid_package_ingest_payload()
            auth = ingest_authorization_header(dataset_id, secret=_INGEST_SECRET)
            result = service.ingest_dataset_package(dataset_id, payload, auth)
            train_path = Path(env.package_root) / dataset_id / "train.jsonl"
            self.assertEqual(result["datasetHash"], hash_file_bytes(train_path))

            ds_store.submit_for_review(dataset_id)
            ds_store.approve(dataset_id)
            os.environ["SCOOLING_LAB_ARTIFACT_ROOT"] = env.package_root + "/artifacts"
            os.environ["SCOOLING_LAB_GPU_TRAIN_MODE"] = "stub"
            os.makedirs(os.environ["SCOOLING_LAB_ARTIFACT_ROOT"], exist_ok=True)
            created = service.create_training_job(
                valid_gpu_payload("pkg-int", dataset_id=dataset_id)
            )
            from scooling_lab.gpu_worker import IsolatedGpuWorker

            worker = IsolatedGpuWorker(service._store)
            worker.run_job(str(created["id"]))
            provenance = service.get_provenance(str(created["id"]))
            self.assertEqual(provenance["datasetHash"], result["datasetHash"])


class T5PackageE2ETests(unittest.TestCase):
    """3. E2E — HTTP POST /datasets/{id}/package with Bearer auth."""

    def setUp(self) -> None:
        self._env = PackageIngestEnv()
        self._env.__enter__()
        self._ds = DatasetStore()
        self._dataset_id = "own:pkg-e2e-v1"
        _register_own(self._ds, self._dataset_id)
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
        self._env.__exit__(None, None, None)

    def _post_package(self, body: dict, auth: str | None) -> dict:
        headers = {"Content-Type": "application/json"}
        if auth is not None:
            headers["Authorization"] = auth
        data = json.dumps(body).encode("utf-8")
        req = Request(
            f"{self._base}/datasets/{self._dataset_id}/package",
            data=data,
            method="POST",
            headers=headers,
        )
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_e2e_http_package_ingest_success(self) -> None:
        """Authorized package ingest returns datasetHash without paths."""

        auth = ingest_authorization_header(self._dataset_id, secret=_INGEST_SECRET)
        result = self._post_package(valid_package_ingest_payload(), auth)
        self.assertEqual(result["datasetId"], self._dataset_id)
        self.assertEqual(len(result["datasetHash"]), 64)
        self.assertNotIn("path", json.dumps(result))

    def test_e2e_http_package_without_auth_refused(self) -> None:
        """Missing Authorization header returns UNAUTHORIZED."""

        with self.assertRaises(HTTPError) as ctx:
            self._post_package(valid_package_ingest_payload(), None)
        self.assertEqual(ctx.exception.code, 401)


class T5PackageStressTests(unittest.TestCase):
    """4. Stress — concurrent ingest requests for distinct datasets."""

    def test_stress_concurrent_package_ingest(self) -> None:
        """Ten concurrent ingests succeed without corrupting package dirs."""

        with PackageIngestEnv():
            ds_store = DatasetStore()
            service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)

            def _ingest(index: int) -> str:
                dataset_id = f"own:pkg-stress-{index}"
                _register_own(ds_store, dataset_id)
                auth = ingest_authorization_header(dataset_id, secret=_INGEST_SECRET)
                result = service.ingest_dataset_package(
                    dataset_id,
                    valid_package_ingest_payload(
                        rows=[
                            {
                                "instruction": f"row-{index}",
                                "input": "",
                                "output": "ok",
                            }
                        ]
                    ),
                    auth,
                )
                return str(result["datasetHash"])

            with ThreadPoolExecutor(max_workers=8) as pool:
                hashes = list(pool.map(_ingest, range(10)))
            self.assertEqual(len(set(hashes)), 10)


class T5PackageDataIntegrityTests(unittest.TestCase):
    """5. Data integrity — on-disk bytes match returned datasetHash."""

    def test_data_integrity_written_bytes_match_hash(self) -> None:
        """train.jsonl on disk hashes to the API datasetHash."""

        with PackageIngestEnv() as env:
            ds_store = DatasetStore()
            dataset_id = "own:pkg-di-v1"
            _register_own(ds_store, dataset_id)
            service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
            auth = ingest_authorization_header(dataset_id, secret=_INGEST_SECRET)
            result = service.ingest_dataset_package(
                dataset_id,
                valid_package_ingest_payload(),
                auth,
            )
            train_path = Path(env.package_root) / dataset_id / "train.jsonl"
            self.assertEqual(result["datasetHash"], hash_file_bytes(train_path))
            self.assertEqual(
                package_dataset_hash(dataset_id),
                result["datasetHash"],
            )


class T5PackagePerformanceTests(unittest.TestCase):
    """6. Performance — single ingest completes under a local budget."""

    def test_performance_package_ingest_under_budget(self) -> None:
        """One ingest with ten rows completes in under two seconds."""

        with PackageIngestEnv():
            ds_store = DatasetStore()
            dataset_id = "own:pkg-perf-v1"
            _register_own(ds_store, dataset_id)
            service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
            rows = [
                {
                    "instruction": f"note-{index}",
                    "input": "",
                    "output": "summary",
                }
                for index in range(10)
            ]
            auth = ingest_authorization_header(dataset_id, secret=_INGEST_SECRET)
            started = time.perf_counter()
            service.ingest_dataset_package(
                dataset_id,
                valid_package_ingest_payload(rows=rows),
                auth,
            )
            elapsed = time.perf_counter() - started
            self.assertLess(elapsed, 2.0)


class T5PackageSecurityTests(unittest.TestCase):
    """7. Security — reject forged JWT, path injection, and scope url keys."""

    def test_security_rejects_forged_jwt(self) -> None:
        """Wrong secret refuses package ingest."""

        with PackageIngestEnv():
            ds_store = DatasetStore()
            dataset_id = "own:pkg-sec-v1"
            _register_own(ds_store, dataset_id)
            service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
            bad_auth = ingest_authorization_header(
                dataset_id,
                secret="wrong-secret-value",
            )
            with self.assertRaises(ApiError) as ctx:
                service.ingest_dataset_package(
                    dataset_id,
                    valid_package_ingest_payload(),
                    bad_auth,
                )
            self.assertEqual(ctx.exception.code, ErrorCode.UNAUTHORIZED)

    def test_security_rejects_url_in_vault_scope_ids(self) -> None:
        """Scope id lists cannot carry URL-shaped values."""

        payload = valid_package_ingest_payload(
            vault_scope={"kind": "folder", "folderIds": ["https://evil.invalid"]},
        )
        with self.assertRaises(ApiError):
            parse_package_ingest_request(payload)

    def test_security_rejects_browser_path_in_rows(self) -> None:
        """Training rows cannot include path-shaped instruction text."""

        payload = valid_package_ingest_payload(
            rows=[{"instruction": "/etc/passwd", "input": "", "output": "x"}],
        )
        with self.assertRaises(ApiError):
            parse_package_ingest_request(payload)


if __name__ == "__main__":
    unittest.main()
