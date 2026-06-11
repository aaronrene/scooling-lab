"""Dependency-free HTTP API for the Scooling Lab T2/T3 contract."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from typing import Callable
from urllib.parse import urlparse

from scooling_lab.errors import ApiError, ErrorCode, error_payload
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


MAX_BODY_BYTES = 16_384
JOB_ID_RE = re.compile(r"^job_[a-f0-9]{24}$")
ARTIFACT_ID_RE = re.compile(r"^artifact_[a-f0-9]{24}$")
DATASET_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{3,96}$")


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
    if "/" in remainder or not JOB_ID_RE.fullmatch(remainder):
        return None
    return remainder


def parse_artifact_route(path: str) -> tuple[str, str] | None:
    """Extract safe job and artifact ids from artifact deletion routes."""

    prefix = "/training/jobs/"
    marker = "/artifacts/"
    if not path.startswith(prefix) or marker not in path:
        return None
    remainder = path.removeprefix(prefix)
    job_id, separator, artifact_id = remainder.partition(marker)
    if separator != marker:
        return None
    if "/" in artifact_id:
        return None
    if not JOB_ID_RE.fullmatch(job_id) or not ARTIFACT_ID_RE.fullmatch(artifact_id):
        return None
    return job_id, artifact_id


def parse_dataset_route(path: str, suffix: str = "") -> str | None:
    """Extract a safe dataset id from supported dataset subresource routes."""

    prefix = "/datasets/"
    if not path.startswith(prefix):
        return None
    remainder = path.removeprefix(prefix)
    if suffix:
        ending = f"/{suffix}"
        if not remainder.endswith(ending):
            return None
        remainder = remainder[: -len(ending)]
    if "/" in remainder or not DATASET_ID_RE.fullmatch(remainder):
        return None
    return remainder


def make_handler(service: TrainingApiService) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to the supplied service."""

    class ScoolingLabRequestHandler(BaseHTTPRequestHandler):
        """HTTP handler exposing create/get/cancel/list artifact endpoints."""

        server_version = "ScoolingLab/0.1"

        def do_POST(self) -> None:
            """Handle createTrainingJob, cancelTrainingJob, and dataset routes."""

            path = urlparse(self.path).path
            if path == "/training/jobs":
                self._handle_json(lambda: service.create_training_job(self._read_json()))
                return
            cancel_job_id = parse_job_route(path, "cancel")
            if cancel_job_id is not None:
                self._handle_json(lambda: service.cancel_training_job(cancel_job_id))
                return
            if path == "/datasets":
                self._handle_json(lambda: service.register_dataset(self._read_json()))
                return
            review_dataset_id = parse_dataset_route(path, "review")
            if review_dataset_id is not None:
                _id = review_dataset_id
                self._handle_json(
                    lambda: service.review_dataset(_id, self._read_json())
                )
                return
            submit_dataset_id = parse_dataset_route(path, "submit")
            if submit_dataset_id is not None:
                _sid = submit_dataset_id
                self._handle_json(lambda: service.submit_dataset_for_review(_sid))
                return
            self._send_error(ApiError(ErrorCode.NOT_FOUND, 404))

        def do_GET(self) -> None:
            """Handle getTrainingJob, listArtifacts, queue state, and dataset routes."""

            path = urlparse(self.path).path
            artifacts_job_id = parse_job_route(path, "artifacts")
            if artifacts_job_id is not None:
                self._handle_json(lambda: service.list_artifacts(artifacts_job_id))
                return
            provenance_job_id = parse_job_route(path, "provenance")
            if provenance_job_id is not None:
                self._handle_json(lambda: service.get_provenance(provenance_job_id))
                return
            job_id = parse_job_route(path)
            if job_id is not None:
                self._handle_json(lambda: service.get_training_job(job_id))
                return
            if path == "/training/queue":
                self._handle_json(service.get_queue_state)
                return
            dataset_id = parse_dataset_route(path)
            if dataset_id is not None:
                _did = dataset_id
                self._handle_json(lambda: service.get_dataset(_did))
                return
            self._send_error(ApiError(ErrorCode.NOT_FOUND, 404))

        def do_PUT(self) -> None:
            """Reject unsupported mutation routes with a stable error."""

            self._send_error(ApiError(ErrorCode.METHOD_NOT_ALLOWED, 405))

        def do_DELETE(self) -> None:
            """Handle idempotent deleteArtifact routes."""

            path = urlparse(self.path).path
            artifact_route = parse_artifact_route(path)
            if artifact_route is not None:
                job_id, artifact_id = artifact_route
                self._handle_json(lambda: service.delete_artifact(job_id, artifact_id))
                return
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
