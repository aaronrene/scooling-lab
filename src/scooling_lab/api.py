"""Dependency-free HTTP API for the Scooling Lab T2 contract."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from scooling_lab.errors import ApiError, ErrorCode, error_payload
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


MAX_BODY_BYTES = 16_384


def parse_job_route(path: str, suffix: str = "") -> str | None:
    """Extract a safe job id from supported job subresource routes."""

    prefix = "/training/jobs/"
    if not path.startswith(prefix):
        return None
    remainder = path.removeprefix(prefix)
    if suffix:
        ending = f"/{suffix}"
        if not remainder.endswith(ending):
            return None
        remainder = remainder[: -len(ending)]
    if "/" in remainder or not remainder.startswith("job_"):
        return None
    return remainder


def make_handler(service: TrainingApiService) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to the supplied service."""

    class ScoolingLabRequestHandler(BaseHTTPRequestHandler):
        """HTTP handler exposing create/get/cancel/list artifact endpoints."""

        server_version = "ScoolingLab/0.1"

        def do_POST(self) -> None:
            """Handle createTrainingJob and cancelTrainingJob."""

            path = urlparse(self.path).path
            if path == "/training/jobs":
                self._handle_json(lambda: service.create_training_job(self._read_json()))
                return
            cancel_job_id = parse_job_route(path, "cancel")
            if cancel_job_id is not None:
                self._handle_json(lambda: service.cancel_training_job(cancel_job_id))
                return
            self._send_error(ApiError(ErrorCode.NOT_FOUND, 404))

        def do_GET(self) -> None:
            """Handle getTrainingJob and listArtifacts."""

            path = urlparse(self.path).path
            artifacts_job_id = parse_job_route(path, "artifacts")
            if artifacts_job_id is not None:
                self._handle_json(lambda: service.list_artifacts(artifacts_job_id))
                return
            job_id = parse_job_route(path)
            if job_id is not None:
                self._handle_json(lambda: service.get_training_job(job_id))
                return
            self._send_error(ApiError(ErrorCode.NOT_FOUND, 404))

        def do_PUT(self) -> None:
            """Reject unsupported mutation routes with a stable error."""

            self._send_error(ApiError(ErrorCode.METHOD_NOT_ALLOWED, 405))

        def do_DELETE(self) -> None:
            """Reject unsupported deletion routes with a stable error."""

            self._send_error(ApiError(ErrorCode.METHOD_NOT_ALLOWED, 405))

        def log_message(self, format: str, *args: object) -> None:
            """Suppress default request logging to avoid payload/path leakage."""

            return

        def _read_json(self) -> dict[str, object]:
            content_length = self.headers.get("Content-Length")
            if content_length is None:
                raise ApiError(ErrorCode.MALFORMED_JSON, 400)
            length = int(content_length)
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiError(ErrorCode.MALFORMED_JSON, 400) from exc
            if not isinstance(payload, dict):
                raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
            return payload

        def _handle_json(self, action: Callable[[], object]) -> None:
            try:
                result = action()
            except ApiError as error:
                self._send_error(error)
                return
            except Exception:
                self._send_error(ApiError(ErrorCode.INTERNAL_ERROR, 500))
                return
            self._send_json(result, HTTPStatus.OK)

        def _send_error(self, error: ApiError) -> None:
            self._send_json(error_payload(error), HTTPStatus(error.status))

        def _send_json(self, payload: object, status: HTTPStatus) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return ScoolingLabRequestHandler


def run_server(host: str, port: int, persistence_path: Path | None = None) -> None:
    """Run the Scooling Lab API server until interrupted."""

    service = TrainingApiService(TrainingJobStore(persistence_path=persistence_path))
    server = ThreadingHTTPServer((host, port), make_handler(service))
    server.serve_forever()


if __name__ == "__main__":
    run_server("127.0.0.1", 8080)
