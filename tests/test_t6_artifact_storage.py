"""Seven-tier tests for T6 artifact storage and durable job state."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from scooling_lab_helpers import (
    GpuWorkerTestEnv,
    ingest_authorization_header,
    valid_gpu_payload,
)

from scooling_lab.api import build_service, make_handler
from scooling_lab.artifact_storage import (
    VolumeArtifactStorage,
    artifact_storage_from_env,
    sign_volume_content_token,
    storage_object_key,
    verify_volume_content_token,
)
from scooling_lab.dataset_review import DatasetStore
from scooling_lab.download_auth import sign_download_jwt, verify_download_auth
from scooling_lab.gpu_worker import hash_file_bytes
from scooling_lab.runtime_config import dev_fixtures_enabled, is_production_runtime, resolve_state_path
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore

_DOWNLOAD_SECRET = "t6-test-download-secret"
_INGEST_SECRET = "t6-test-ingest-secret"


class T6StorageEnv:
    """Temp state, volume storage, and auth secrets for T6 tests."""

    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        base = Path(self._tmpdir.name)
        self.state_path = base / "state" / "jobs.json"
        self.storage_root = base / "object-storage"
        self.artifact_root = base / "gpu-artifacts"
        self.package_root = base / "packages"
        self.public_base_url = "http://127.0.0.1:9"
        self.storage_root.mkdir(parents=True)
        self.artifact_root.mkdir(parents=True)
        self.package_root.mkdir(parents=True)
        self._prior: dict[str, str | None] = {}

    def __enter__(self) -> "T6StorageEnv":
        for key, value in (
            ("SCOOLING_LAB_DEV_FIXTURES", "1"),
            ("SCOOLING_LAB_STATE_PATH", str(self.state_path)),
            ("SCOOLING_LAB_ARTIFACT_STORAGE_BACKEND", "volume"),
            ("SCOOLING_LAB_ARTIFACT_STORAGE_ROOT", str(self.storage_root)),
            ("SCOOLING_LAB_PUBLIC_BASE_URL", self.public_base_url),
            ("SCOOLING_LAB_ARTIFACT_ROOT", str(self.artifact_root)),
            ("SCOOLING_LAB_PACKAGE_ROOT", str(self.package_root)),
            ("SCOOLING_LAB_GPU_TRAIN_MODE", "stub"),
            ("SCOOLING_LAB_INGEST_AUTH_SECRET", _INGEST_SECRET),
            ("SCOOLING_LAB_DOWNLOAD_AUTH_SECRET", _DOWNLOAD_SECRET),
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

    def volume_storage(self) -> VolumeArtifactStorage:
        return VolumeArtifactStorage(self.storage_root, self.public_base_url)

    def build_service(self, dataset_store: DatasetStore | None = None) -> TrainingApiService:
        store = TrainingJobStore(persistence_path=self.state_path)
        ds = dataset_store if dataset_store is not None else DatasetStore()
        return TrainingApiService(
            store,
            artifact_storage=self.volume_storage(),
            dataset_store=ds,
        )


def _approve_gpu_dataset(
    env: T6StorageEnv,
    service: TrainingApiService,
    dataset_id: str = "own:gpu-packaged.notes_v1",
) -> None:
    service.register_dataset({"datasetId": dataset_id})
    service.submit_dataset_for_review(dataset_id)
    service.review_dataset(dataset_id, {"action": "approve"})
    target = Path(env.package_root) / dataset_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "train.jsonl").write_text(
        '{"instruction":"x","input":"","output":"y"}\n',
        encoding="utf-8",
    )
    (target / "manifest.json").write_text(
        json.dumps({"datasetId": dataset_id, "rowCount": 1}),
        encoding="utf-8",
    )


def _download_auth_header(job_id: str, artifact_id: str) -> str:
    token = sign_download_jwt(
        job_id,
        artifact_id,
        "scooling.server",
        secret=_DOWNLOAD_SECRET,
    )
    return f"Bearer {token}"


class T6ArtifactUnitTests(unittest.TestCase):
    """1. Unit — storage keys, tokens, production config."""

    def test_unit_storage_object_key_shape(self) -> None:
        """Storage keys are content-free and deterministic."""

        key = storage_object_key(
            "job_a1b2c3d4e5f6789012345678",
            "artifact_b2c3d4e5f678901234567890",
        )
        self.assertIn("job_", key)
        self.assertIn("artifact_", key)
        self.assertTrue(key.endswith("artifact.tar.gz"))

    def test_unit_volume_content_token_round_trip(self) -> None:
        """Signed content tokens validate job and artifact binding."""

        with T6StorageEnv() as env:
            expires = datetime.now(UTC) + timedelta(minutes=5)
            token = sign_volume_content_token(
                "job_a1b2c3d4e5f6789012345678",
                "artifact_b2c3d4e5f678901234567890",
                "job_x/artifact_y/artifact.tar.gz",
                expires_at=expires,
            )
            storage_key = verify_volume_content_token(
                "job_a1b2c3d4e5f6789012345678",
                "artifact_b2c3d4e5f678901234567890",
                token,
            )
            self.assertEqual(storage_key, "job_x/artifact_y/artifact.tar.gz")

    def test_unit_production_requires_state_path(self) -> None:
        """Production-like runtime refuses to start without durable state."""

        prior_dev = os.environ.get("SCOOLING_LAB_DEV_FIXTURES")
        prior_state = os.environ.get("SCOOLING_LAB_STATE_PATH")
        prior_railway = os.environ.get("RAILWAY_ENVIRONMENT")
        try:
            os.environ.pop("SCOOLING_LAB_DEV_FIXTURES", None)
            os.environ.pop("SCOOLING_LAB_STATE_PATH", None)
            os.environ["RAILWAY_ENVIRONMENT"] = "production"
            self.assertTrue(is_production_runtime())
            with self.assertRaises(SystemExit):
                resolve_state_path()
        finally:
            if prior_dev is None:
                os.environ.pop("SCOOLING_LAB_DEV_FIXTURES", None)
            else:
                os.environ["SCOOLING_LAB_DEV_FIXTURES"] = prior_dev
            if prior_state is None:
                os.environ.pop("SCOOLING_LAB_STATE_PATH", None)
            else:
                os.environ["SCOOLING_LAB_STATE_PATH"] = prior_state
            if prior_railway is None:
                os.environ.pop("RAILWAY_ENVIRONMENT", None)
            else:
                os.environ["RAILWAY_ENVIRONMENT"] = prior_railway

    def test_unit_dev_fixtures_allows_missing_state(self) -> None:
        """CI dev fixtures mode permits in-memory defaults."""

        prior = os.environ.get("SCOOLING_LAB_DEV_FIXTURES")
        try:
            os.environ["SCOOLING_LAB_DEV_FIXTURES"] = "1"
            self.assertTrue(dev_fixtures_enabled())
            self.assertIsNone(resolve_state_path())
        finally:
            if prior is None:
                os.environ.pop("SCOOLING_LAB_DEV_FIXTURES", None)
            else:
                os.environ["SCOOLING_LAB_DEV_FIXTURES"] = prior


class T6ArtifactIntegrationTests(unittest.TestCase):
    """2. Integration — upload, download URL, persistence."""

    def test_integration_gpu_job_uploads_tarball_to_volume(self) -> None:
        """Succeeded GPU jobs upload tarball bytes to object storage."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-upload"))
            job_id = str(created["id"])
            artifact = service.list_artifacts(job_id)["artifacts"][0]
            artifact_id = str(artifact["id"])
            download = service.get_artifact_download(
                job_id,
                artifact_id,
                _download_auth_header(job_id, artifact_id),
            )
            self.assertIn("downloadUrl", download)
            self.assertIn("expiresAt", download)
            storage_key = storage_object_key(job_id, artifact_id)
            stored = env.storage_root / storage_key
            self.assertTrue(stored.is_file())
            tarball = env.artifact_root / job_id / "artifact.tar.gz"
            self.assertEqual(hash_file_bytes(stored), hash_file_bytes(tarball))

    def test_integration_job_store_survives_restart(self) -> None:
        """Durable state reloads queued and completed jobs."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-restart"))
            job_id = str(created["id"])

            reloaded = env.build_service()
            fetched = reloaded.get_training_job(job_id)
            self.assertEqual(fetched["status"], "succeeded")
            artifacts = reloaded.list_artifacts(job_id)["artifacts"]
            self.assertEqual(len(artifacts), 1)


class T6ArtifactE2ETests(unittest.TestCase):
    """3. E2E — HTTP download route with server auth."""

    def test_e2e_http_download_returns_signed_url(self) -> None:
        """GET download issues signed URL; content route streams bytes."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-e2e"))
            job_id = str(created["id"])
            artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])

            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                make_handler(service),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            base = f"http://{host}:{port}"

            try:
                download_req = Request(
                    f"{base}/training/jobs/{job_id}/artifacts/{artifact_id}/download",
                    headers={"Authorization": _download_auth_header(job_id, artifact_id)},
                )
                with urlopen(download_req, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["jobId"], job_id)
                self.assertEqual(payload["artifactId"], artifact_id)
                download_url = str(payload["downloadUrl"])
                parsed = urlparse(download_url)
                content_url = f"{base}{parsed.path}?{parsed.query}"

                content_req = Request(content_url)
                with urlopen(content_req, timeout=5) as response:
                    body = response.read()
                tarball = env.artifact_root / job_id / "artifact.tar.gz"
                self.assertEqual(body, tarball.read_bytes())
            finally:
                server.shutdown()
                thread.join(timeout=2)


class T6ArtifactStressTests(unittest.TestCase):
    """4. Stress — concurrent download URL issuance."""

    def test_stress_concurrent_download_auth(self) -> None:
        """Concurrent authorized download requests remain stable."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-stress"))
            job_id = str(created["id"])
            artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])

            def issue() -> dict[str, object]:
                return service.get_artifact_download(
                    job_id,
                    artifact_id,
                    _download_auth_header(job_id, artifact_id),
                )

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: issue(), range(16)))
            self.assertEqual(len(results), 16)
            for item in results:
                self.assertIn("downloadUrl", item)


class T6ArtifactDataIntegrityTests(unittest.TestCase):
    """5. Data-integrity — retention sweep deletes storage + metadata."""

    def test_data_integrity_retention_sweep_deletes_storage_bytes(self) -> None:
        """Expired artifacts remove tarball from object storage."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            payload = valid_gpu_payload("t6-sweep")
            payload["retentionPolicy"] = {"policyClass": "ephemeral", "ttlSeconds": 60}
            created = service.create_training_job(payload)
            job_id = str(created["id"])
            artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])
            storage_key = storage_object_key(job_id, artifact_id)
            self.assertTrue((env.storage_root / storage_key).is_file())

            service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))

            self.assertFalse((env.storage_root / storage_key).is_file())
            tombstone = service.get_training_job(job_id)
            self.assertEqual(tombstone["status"], "deleted")
            self.assertEqual(service.list_artifacts(job_id)["artifacts"], [])
            self.assertIn("artifactHash", service.get_provenance(job_id))

    def test_data_integrity_explicit_delete_removes_storage(self) -> None:
        """Explicit delete cascades to object storage."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-delete"))
            job_id = str(created["id"])
            artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])
            storage_key = storage_object_key(job_id, artifact_id)

            service.delete_artifact(job_id, artifact_id)

            self.assertFalse((env.storage_root / storage_key).is_file())
            self.assertEqual(service.get_training_job(job_id)["status"], "deleted")


class T6ArtifactPerformanceTests(unittest.TestCase):
    """6. Performance — download URL issuance stays bounded."""

    def test_performance_download_url_under_budget(self) -> None:
        """Signed URL issuance completes within a small wall-time budget."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-perf"))
            job_id = str(created["id"])
            artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])
            auth = _download_auth_header(job_id, artifact_id)

            start = time.monotonic()
            for _ in range(50):
                service.get_artifact_download(job_id, artifact_id, auth)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, 2.0)


class T6ArtifactSecurityTests(unittest.TestCase):
    """7. Security — server auth only; no storage paths on public wire."""

    def test_security_download_requires_bearer_jwt(self) -> None:
        """Download URL route rejects missing or invalid auth."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-sec"))
            job_id = str(created["id"])
            artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])

            with self.assertRaises(ApiError) as ctx:
                service.get_artifact_download(job_id, artifact_id, "")
            self.assertEqual(ctx.exception.code.value, "UNAUTHORIZED")

    def test_security_list_artifacts_omits_storage_key(self) -> None:
        """Public artifact metadata never exposes storage internals."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-wire"))
            job_id = str(created["id"])
            wire = json.dumps(service.list_artifacts(job_id), sort_keys=True)
            self.assertNotIn("storageKey", wire)
            self.assertNotIn(str(env.storage_root), wire)

    def test_security_http_download_rejects_anonymous(self) -> None:
        """HTTP download route returns 401 without Bearer token."""

        with T6StorageEnv() as env:
            service = env.build_service()
            _approve_gpu_dataset(env, service)
            created = service.create_training_job(valid_gpu_payload("t6-http-sec"))
            job_id = str(created["id"])
            artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])

            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                req = Request(
                    f"http://{host}:{port}/training/jobs/{job_id}/artifacts/{artifact_id}/download"
                )
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(req, timeout=5)
                self.assertEqual(ctx.exception.code, 401)
            finally:
                server.shutdown()
                thread.join(timeout=2)


# Late import for ApiError used in security tests
from scooling_lab.errors import ApiError  # noqa: E402


if __name__ == "__main__":
    unittest.main()
