"""End-to-end tier tests — T3 full lifecycle including rejection path and expiry tombstone."""

from __future__ import annotations

import json
import threading
import unittest
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scooling_lab_helpers import valid_payload

from scooling_lab.api import make_handler
from scooling_lab.dataset_review import DatasetStore, RejectionReasonCode
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class T3EndToEndTests(unittest.TestCase):
    """E2E HTTP tests for the T3 dataset review and retention lifecycle."""

    def setUp(self) -> None:
        """Start a fresh server for each test."""

        self._service = TrainingApiService(TrainingJobStore())
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self._service)
        )
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        self._base = f"http://127.0.0.1:{self._server.server_port}"

    def tearDown(self) -> None:
        """Shut down the server."""

        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    # ----------------------------------------------------------------- helpers

    def _json(
        self, url: str, method: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, timeout=5) as resp:
            decoded = json.loads(resp.read().decode("utf-8"))
        if not isinstance(decoded, dict):
            raise AssertionError("expected JSON object")
        return decoded

    # ------------------------------------------------------------------ tests

    def test_e2e_t3_register_approve_submit_job_over_http(self) -> None:
        """Full dataset review flow works end-to-end via HTTP."""

        # Register a new dataset.
        reg = self._json(
            f"{self._base}/datasets",
            "POST",
            {"datasetId": "e2e-dataset-v1"},
        )
        self.assertEqual(reg["status"], "registered")

        # Submit for review.
        submitted = self._json(
            f"{self._base}/datasets/e2e-dataset-v1/submit", "POST"
        )
        self.assertEqual(submitted["status"], "pending_review")

        # Approve it.
        approved = self._json(
            f"{self._base}/datasets/e2e-dataset-v1/review",
            "POST",
            {"action": "approve"},
        )
        self.assertEqual(approved["status"], "approved")

        # Read back.
        fetched = self._json(f"{self._base}/datasets/e2e-dataset-v1", "GET")
        self.assertEqual(fetched["status"], "approved")

    def test_e2e_t3_rejection_path_over_http(self) -> None:
        """Dataset rejection carries enum reason code; no free text reflected."""

        self._json(
            f"{self._base}/datasets",
            "POST",
            {"datasetId": "e2e-rejected-v1"},
        )
        self._json(f"{self._base}/datasets/e2e-rejected-v1/submit", "POST")
        rejected = self._json(
            f"{self._base}/datasets/e2e-rejected-v1/review",
            "POST",
            {"action": "reject", "reasonCode": "DUPLICATE_SUBMISSION"},
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["rejectionReasonCode"], "DUPLICATE_SUBMISSION")
        # Confirm no free text in the response body.
        self.assertNotIn("caller message", json.dumps(rejected))

    def test_e2e_t3_queue_state_endpoint_returns_counts(self) -> None:
        """GET /training/queue returns a JSON object with queue metrics."""

        state = self._json(f"{self._base}/training/queue", "GET")
        self.assertIn("queuedCount", state)
        self.assertIn("runningCount", state)
        self.assertIn("activeCount", state)
        self.assertIn("maxConcurrentRunning", state)

    def test_e2e_t3_expiry_tombstone_provenance_readable_over_http(self) -> None:
        """After TTL expiry the provenance endpoint still returns 200."""

        policy = {"policyClass": "ephemeral", "ttlSeconds": 60}
        created = self._json(
            f"{self._base}/training/jobs",
            "POST",
            valid_payload("e2e-expiry-prov", policy),
        )
        job_id = str(created["id"])
        prov_before = self._json(
            f"{self._base}/training/jobs/{job_id}/provenance", "GET"
        )

        # Trigger expiry via the service (direct call, not via HTTP).
        self._service.sweep_expired_artifacts(datetime.now(UTC) + timedelta(seconds=120))

        tombstone = self._json(f"{self._base}/training/jobs/{job_id}", "GET")
        self.assertEqual(tombstone["status"], "deleted")

        prov_after = self._json(
            f"{self._base}/training/jobs/{job_id}/provenance", "GET"
        )
        self.assertEqual(prov_before["jobId"], prov_after["jobId"])
        self.assertEqual(
            prov_before["artifactHash"], prov_after["artifactHash"]
        )

    def test_e2e_t3_explicit_delete_wipes_provenance_over_http(self) -> None:
        """After explicit DELETE the provenance endpoint returns 404."""

        created = self._json(
            f"{self._base}/training/jobs",
            "POST",
            valid_payload("e2e-explicit-delete"),
        )
        job_id = str(created["id"])
        arts = self._json(
            f"{self._base}/training/jobs/{job_id}/artifacts", "GET"
        )
        artifact_id = str(arts["artifacts"][0]["id"])

        self._json(
            f"{self._base}/training/jobs/{job_id}/artifacts/{artifact_id}",
            "DELETE",
        )
        with self.assertRaises(HTTPError) as raised:
            self._json(
                f"{self._base}/training/jobs/{job_id}/provenance", "GET"
            )
        self.assertEqual(raised.exception.code, 404)
        raised.exception.close()

    def test_e2e_t3_unapproved_dataset_returns_403_over_http(self) -> None:
        """Job submission against an unapproved dataset returns HTTP 403."""

        ds_store = DatasetStore()
        ds_store.register("unapproved-e2e-ds")
        service = TrainingApiService(
            TrainingJobStore(), dataset_store=ds_store
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with self.assertRaises(HTTPError) as raised:
                self._json(
                    f"{base}/training/jobs",
                    "POST",
                    {
                        "idempotencyKey": "e2e-403-test",
                        "datasetId": "unapproved-e2e-ds",
                        "modelId": "fixture-tiny-llm",
                        "requestedBy": "e2e-test",
                    },
                )
            self.assertEqual(raised.exception.code, 403)
            raised.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
