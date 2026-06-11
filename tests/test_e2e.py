"""End-to-end tier tests for the Scooling Lab HTTP API contract."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.api import make_handler
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class ScoolingLabE2ETests(unittest.TestCase):
    """E2E tests for create -> poll -> completed -> listArtifacts."""

    def test_e2e_http_create_poll_completed_and_list_artifacts(self) -> None:
        """The dependency-free HTTP API completes the fake-worker fixture flow."""

        service = TrainingApiService(TrainingJobStore())
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            created = post_json(f"{base_url}/training/jobs", valid_payload("e2e"))
            self.assertEqual(created["status"], "succeeded")
            job_id = str(created["id"])

            fetched = get_json(f"{base_url}/training/jobs/{job_id}")
            self.assertEqual(fetched["status"], "succeeded")

            artifacts = get_json(f"{base_url}/training/jobs/{job_id}/artifacts")
            self.assertEqual(len(artifacts["artifacts"]), 1)
            self.assertEqual(artifacts["artifacts"][0]["jobId"], job_id)
        finally:
            server.shutdown()
            server.server_close()

    def test_e2e_ci_workflow_runs_lab_chain(self) -> None:
        """The CI workflow contains unittest, secret scan, and BOM audit steps."""

        workflow = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("python -m unittest discover", workflow)
        self.assertIn("gitleaks detect", workflow)
        self.assertIn("python -m scooling_lab.bom", workflow)


def post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    """POST JSON and return decoded JSON without external network use."""

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise AssertionError("expected JSON object")
    return result


def get_json(url: str) -> dict[str, object]:
    """GET JSON from the local fixture server."""

    with urllib.request.urlopen(url, timeout=5) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise AssertionError("expected JSON object")
    return result


if __name__ == "__main__":
    unittest.main()
