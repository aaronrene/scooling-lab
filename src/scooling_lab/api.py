"""Dependency-free HTTP API for the Scooling Lab T2/T3 contract."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from typing import Callable
from urllib.parse import parse_qs, urlparse

from scooling_lab.errors import ApiError, ErrorCode, error_payload
from scooling_lab.runtime_config import resolve_state_path
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


MAX_BODY_BYTES = 16_384
MAX_PACKAGE_BODY_BYTES = 4_194_304
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


def parse_artifact_route(path: str, suffix: str = "") -> tuple[str, str] | None:
    """Extract safe job and artifact ids from artifact subresource routes."""

    prefix = "/training/jobs/"
    marker = "/artifacts/"
    if not path.startswith(prefix) or marker not in path:
        return None
    remainder = path.removeprefix(prefix)
    job_id, separator, tail = remainder.partition(marker)
    if separator != marker:
        return None
    if suffix:
        ending = f"/{suffix}"
        if not tail.endswith(ending):
            return None
        artifact_id = tail[: -len(ending)]
    else:
        artifact_id = tail
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
        """HTTP handler exposing job, artifact, queue, and dataset endpoints."""

        server_version = "ScoolingLab/0.1"

        def do_POST(self) -> None:
            """Handle createTrainingJob, cancelTrainingJob, and dataset routes."""

            path = urlparse(self.path).path
            if path == "/training/jobs":
                self._handle_json(lambda: service.create_training_job(self._read_json()))
                return
            retry_job_id = parse_job_route(path, "retry")
            if retry_job_id is not None:
                self._handle_json(lambda: service.retry_training_job(retry_job_id))
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
            package_dataset_id = parse_dataset_route(path, "package")
            if package_dataset_id is not None:
                _pid = package_dataset_id
                auth_header = self.headers.get("Authorization", "")
                self._handle_json(
                    lambda: service.ingest_dataset_package(
                        _pid,
                        self._read_json(MAX_PACKAGE_BODY_BYTES),
                        auth_header,
                    )
                )
                return
            self._send_error(ApiError(ErrorCode.NOT_FOUND, 404))

        def do_GET(self) -> None:
            """Handle getTrainingJob, listArtifacts, queue state, and dataset routes."""

            path = urlparse(self.path).path
            artifacts_job_id = parse_job_route(path, "artifacts")
            if artifacts_job_id is not None:
                self._handle_json(lambda: service.list_artifacts(artifacts_job_id))
                return
            download_route = parse_artifact_route(path, "download")
            if download_route is not None:
                job_id, artifact_id = download_route
                auth_header = self.headers.get("Authorization", "")
                self._handle_json(
                    lambda: service.get_artifact_download(
                        job_id,
                        artifact_id,
                        auth_header,
                    )
                )
                return
            content_route = parse_artifact_route(path, "content")
            if content_route is not None:
                job_id, artifact_id = content_route
                query = parse_qs(urlparse(self.path).query)
                token_values = query.get("token", [])
                token = token_values[0] if token_values else ""
                self._handle_binary(
                    lambda: service.read_artifact_content(job_id, artifact_id, token)
                )
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

        def _read_json(self, max_bytes: int = MAX_BODY_BYTES) -> dict[str, object]:
            content_length = self.headers.get("Content-Length")
            if content_length is None:
                raise ApiError(ErrorCode.MALFORMED_JSON, 400)
            length = int(content_length)
            if length <= 0 or length > max_bytes:
                raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiError(ErrorCode.MALFORMED_JSON, 400) from exc
            if not isinstance(payload, dict):
                raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
            return payload

        def _handle_binary(self, action: Callable[[], tuple[bytes, str]]) -> None:
            try:
                body, content_type = action()
            except ApiError as error:
                self._send_error(error)
                return
            except Exception:
                self._send_error(ApiError(ErrorCode.INTERNAL_ERROR, 500))
                return
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

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


def build_service(persistence_path: Path | None = None) -> TrainingApiService:
    """Construct the API service with durable state and artifact storage."""

    store = TrainingJobStore(persistence_path=persistence_path)
    return TrainingApiService(store)


def run_server(host: str, port: int, persistence_path: Path | None = None) -> None:
    """Run the Scooling Lab API server until interrupted."""

    service = build_service(persistence_path=persistence_path)
    server = ThreadingHTTPServer((host, port), make_handler(service))
    server.serve_forever()


def main() -> None:
    """CLI / platform entrypoint — bind all interfaces and honor ``PORT``."""

    import os

    host = os.environ.get("SCOOLING_LAB_HOST", "0.0.0.0")
    port_text = os.environ.get("PORT", "8080")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise SystemExit(f"Invalid PORT={port_text!r}") from exc
    if not 1 <= port <= 65_535:
        raise SystemExit(f"PORT out of range: {port}")

    persistence_path = resolve_state_path()
    run_server(host, port, persistence_path=persistence_path)


if __name__ == "__main__":
    main()
