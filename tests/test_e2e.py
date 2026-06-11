"""End-to-end tier tests for Scooling Lab HTTP training routes."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.api import make_handler
from scooling_lab.contracts import TrainingJobRequest, TrainingJobStatus
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class ScoolingLabEndToEndTests(unittest.TestCase):
    """E2E tests across the local dependency-free HTTP API surface."""

    def test_e2e_create_fetch_provenance_delete_and_verify_absence(self) -> None:
        """A completed artifact can be fetched, deleted, and verified absent."""

        service = TrainingApiService(TrainingJobStore())
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            created = self._json_request(
                f"{base_url}/training/jobs",
                "POST",
                valid_payload("e2e-provenance-delete"),
            )
            job_id = str(created["id"])
            artifacts = self._json_request(
                f"{base_url}/training/jobs/{job_id}/artifacts", "GET"
            )
            artifact = artifacts["artifacts"][0]
            artifact_id = str(artifact["id"])
            provenance = self._json_request(
                f"{base_url}/training/jobs/{job_id}/provenance", "GET"
            )
            deleted_hashes = (
                str(artifact["datasetHash"]),
                str(artifact["artifactHash"]),
                str(provenance["trainingConfigHash"]),
            )

            deletion = self._json_request(
                f"{base_url}/training/jobs/{job_id}/artifacts/{artifact_id}", "DELETE"
            )
            job_after_delete = self._json_request(
                f"{base_url}/training/jobs/{job_id}", "GET"
            )
            artifacts_after_delete = self._json_request(
                f"{base_url}/training/jobs/{job_id}/artifacts", "GET"
            )

            self.assertTrue(deletion["verified"])
            self.assertTrue(service.verify_deleted_artifact_absence(deleted_hashes))
            self.assertEqual(job_after_delete["status"], "deleted")
            self.assertEqual(artifacts_after_delete["artifacts"], [])
            with self.assertRaises(HTTPError) as raised:
                self._json_request(
                    f"{base_url}/training/jobs/{job_id}/provenance", "GET"
                )
            self.assertEqual(raised.exception.code, 404)
            raised.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            thread.join(timeout=2)

    def _json_request(
        self, url: str, method: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers=headers, method=method)
        with urlopen(request, timeout=5) as response:
            decoded = json.loads(response.read().decode("utf-8"))
        if not isinstance(decoded, dict):
            raise AssertionError("expected JSON object")
        return decoded

    def test_e2e_http_create_poll_completed_and_list_artifacts(self) -> None:
        """The dependency-free HTTP API completes the fake-worker fixture flow."""

        service = TrainingApiService(TrainingJobStore())
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            created = self._json_request(
                f"{base_url}/training/jobs", "POST", valid_payload("e2e")
            )
            self.assertEqual(created["status"], "succeeded")
            job_id = str(created["id"])

            fetched = self._json_request(f"{base_url}/training/jobs/{job_id}", "GET")
            self.assertEqual(fetched["status"], "succeeded")

            artifacts = self._json_request(
                f"{base_url}/training/jobs/{job_id}/artifacts", "GET"
            )
            self.assertEqual(len(artifacts["artifacts"]), 1)
            self.assertEqual(artifacts["artifacts"][0]["jobId"], job_id)
        finally:
            server.shutdown()
            server.server_close()

    def test_e2e_t4_cancel_retry_to_success_and_success_retry_refusal(self) -> None:
        """HTTP routes cover cancellation, retry success, and success retry refusal."""

        store = TrainingJobStore(queue_limit=6)
        cancelled_request = TrainingJobRequest.from_mapping(valid_payload("e2e-cancel"))
        failed_request = TrainingJobRequest.from_mapping(valid_payload("e2e-failed"))
        cancellable = store.create(cancelled_request)
        failed = store.create(failed_request)
        store.update_status(failed.id, TrainingJobStatus.FAILED)
        service = TrainingApiService(store)
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            cancelled = self._json_request(
                f"{base_url}/training/jobs/{cancellable.id}/cancel", "POST"
            )
            retried = self._json_request(
                f"{base_url}/training/jobs/{failed.id}/retry", "POST"
            )
            succeeded = self._json_request(
                f"{base_url}/training/jobs",
                "POST",
                valid_payload("e2e-retry-refused"),
            )

            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(retried["status"], "succeeded")
            self.assertEqual(retried["retryOfJobId"], failed.id)
            self.assertNotEqual(retried["id"], failed.id)
            with self.assertRaises(HTTPError) as raised:
                self._json_request(
                    f"{base_url}/training/jobs/{succeeded['id']}/retry", "POST"
                )
            self.assertEqual(raised.exception.code, 409)
            raised.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_e2e_ci_workflow_runs_lab_chain(self) -> None:
        """The CI workflow contains unittest, secret scan, and BOM audit steps."""

        workflow = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("python -m unittest discover", workflow)
        self.assertIn("gitleaks detect", workflow)
        self.assertIn("python -m scooling_lab.bom", workflow)


if __name__ == "__main__":
    unittest.main()
