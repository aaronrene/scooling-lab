"""Artifact object storage — volume and S3-compatible backends (stdlib only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Mapping
from urllib.parse import quote, urlencode, urlparse

from scooling_lab.contracts import require_artifact_id, require_job_id
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.retention import utc_timestamp

_BACKEND_ENV = "SCOOLING_LAB_ARTIFACT_STORAGE_BACKEND"
_VOLUME_ROOT_ENV = "SCOOLING_LAB_ARTIFACT_STORAGE_ROOT"
_S3_BUCKET_ENV = "SCOOLING_LAB_ARTIFACT_STORAGE_BUCKET"
_S3_ENDPOINT_ENV = "SCOOLING_LAB_ARTIFACT_STORAGE_ENDPOINT"
_S3_ACCESS_KEY_ENV = "SCOOLING_LAB_ARTIFACT_STORAGE_ACCESS_KEY_ID"
_S3_SECRET_KEY_ENV = "SCOOLING_LAB_ARTIFACT_STORAGE_SECRET_ACCESS_KEY"
_S3_REGION_ENV = "SCOOLING_LAB_ARTIFACT_STORAGE_REGION"
_PUBLIC_BASE_URL_ENV = "SCOOLING_LAB_PUBLIC_BASE_URL"
_CONTENT_TOKEN_SECRET_ENV = "SCOOLING_LAB_ARTIFACT_CONTENT_TOKEN_SECRET"
_DEFAULT_DOWNLOAD_TTL_SECONDS = 300
_OBJECT_NAME = "artifact.tar.gz"


def storage_object_key(job_id: str, artifact_id: str) -> str:
    """Return the canonical storage key for one artifact tarball."""

    require_job_id(job_id)
    require_artifact_id(artifact_id)
    return f"{job_id}/{artifact_id}/{_OBJECT_NAME}"


def content_token_secret() -> str:
    """Return the HMAC secret for volume content delivery tokens."""

    raw = os.environ.get(_CONTENT_TOKEN_SECRET_ENV, "").strip()
    if raw:
        return raw
    from scooling_lab.download_auth import download_auth_secret  # noqa: PLC0415

    return download_auth_secret()


@dataclass(frozen=True)
class SignedDownload:
    """Content-free signed download descriptor returned to authorized callers."""

    download_url: str
    expires_at: str

    def to_public_dict(self) -> dict[str, str]:
        """Serialize for JSON API responses — no storage paths or secrets."""

        return {
            "downloadUrl": self.download_url,
            "expiresAt": self.expires_at,
        }


class ArtifactStorageBackend(ABC):
    """Upload, delete, and sign download URLs for adapter tarballs."""

    @abstractmethod
    def upload(self, job_id: str, artifact_id: str, tarball_path: Path) -> str:
        """Upload tarball bytes; return the storage object key."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Delete stored object bytes when retention or explicit delete runs."""

    @abstractmethod
    def issue_download(
        self,
        job_id: str,
        artifact_id: str,
        storage_key: str,
        *,
        ttl_seconds: int = _DEFAULT_DOWNLOAD_TTL_SECONDS,
    ) -> SignedDownload:
        """Return a time-limited signed download URL."""


class VolumeArtifactStorage(ArtifactStorageBackend):
    """Local volume backend — copies tarballs under an operator-controlled root."""

    def __init__(self, root: Path, public_base_url: str) -> None:
        self._root = root
        self._public_base_url = public_base_url.rstrip("/")

    def upload(self, job_id: str, artifact_id: str, tarball_path: Path) -> str:
        key = storage_object_key(job_id, artifact_id)
        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tarball_path, target)
        return key

    def delete(self, storage_key: str) -> None:
        target = self._root / storage_key
        if target.is_file():
            target.unlink()
        parent = target.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
        grandparent = parent.parent
        if grandparent.is_dir() and not any(grandparent.iterdir()):
            grandparent.rmdir()

    def resolve_path(self, storage_key: str) -> Path:
        """Return the on-disk path for a stored object key."""

        return self._root / storage_key

    def issue_download(
        self,
        job_id: str,
        artifact_id: str,
        storage_key: str,
        *,
        ttl_seconds: int = _DEFAULT_DOWNLOAD_TTL_SECONDS,
    ) -> SignedDownload:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        token = sign_volume_content_token(
            job_id,
            artifact_id,
            storage_key,
            expires_at=expires_at,
        )
        query = urlencode(
            {
                "exp": str(int(expires_at.timestamp())),
                "token": token,
            }
        )
        download_url = (
            f"{self._public_base_url}/training/jobs/{job_id}"
            f"/artifacts/{artifact_id}/content?{query}"
        )
        return SignedDownload(
            download_url=download_url,
            expires_at=utc_timestamp(expires_at),
        )


class S3CompatibleArtifactStorage(ArtifactStorageBackend):
    """S3 or Cloudflare R2 backend using stdlib HTTP and SigV4 presigning."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
    ) -> None:
        self._bucket = bucket
        self._endpoint = endpoint.rstrip("/")
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._region = region

    def upload(self, job_id: str, artifact_id: str, tarball_path: Path) -> str:
        key = storage_object_key(job_id, artifact_id)
        body = tarball_path.read_bytes()
        url = f"{self._endpoint}/{self._bucket}/{quote(key, safe='/')}"
        headers = _s3_signed_headers(
            method="PUT",
            url=url,
            region=self._region,
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            payload_hash=hashlib.sha256(body).hexdigest(),
            content_type="application/gzip",
        )
        request = urllib.request.Request(url, data=body, method="PUT")
        for header_name, header_value in headers.items():
            request.add_header(header_name, header_value)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status not in {200, 201, 204}:
                    raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        except urllib.error.URLError as exc:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500) from exc
        return key

    def delete(self, storage_key: str) -> None:
        url = f"{self._endpoint}/{self._bucket}/{quote(storage_key, safe='/')}"
        headers = _s3_signed_headers(
            method="DELETE",
            url=url,
            region=self._region,
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            payload_hash=hashlib.sha256(b"").hexdigest(),
        )
        request = urllib.request.Request(url, method="DELETE")
        for header_name, header_value in headers.items():
            request.add_header(header_name, header_value)
        try:
            with urllib.request.urlopen(request, timeout=30):
                return
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500) from exc
        except urllib.error.URLError as exc:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500) from exc

    def issue_download(
        self,
        job_id: str,
        artifact_id: str,
        storage_key: str,
        *,
        ttl_seconds: int = _DEFAULT_DOWNLOAD_TTL_SECONDS,
    ) -> SignedDownload:
        _ = (job_id, artifact_id)
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        url = f"{self._endpoint}/{self._bucket}/{quote(storage_key, safe='/')}"
        download_url = _s3_presigned_get_url(
            url=url,
            region=self._region,
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            expires_seconds=ttl_seconds,
        )
        return SignedDownload(
            download_url=download_url,
            expires_at=utc_timestamp(expires_at),
        )


def sign_volume_content_token(
    job_id: str,
    artifact_id: str,
    storage_key: str,
    *,
    expires_at: datetime,
) -> str:
    """Return an HMAC token authorizing one volume content download."""

    require_job_id(job_id)
    require_artifact_id(artifact_id)
    payload = json.dumps(
        {
            "artifactId": artifact_id,
            "exp": int(expires_at.timestamp()),
            "jobId": job_id,
            "storageKey": storage_key,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hmac.new(
        content_token_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{digest}".encode("utf-8")).decode("ascii")


def verify_volume_content_token(
    job_id: str,
    artifact_id: str,
    token: str,
) -> str:
    """Validate a volume content token and return the storage key."""

    require_job_id(job_id)
    require_artifact_id(artifact_id)
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        payload_text, digest = decoded.rsplit(":", 1)
        payload = json.loads(payload_text)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401) from None
    if not isinstance(payload, dict):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    expected_digest = hmac.new(
        content_token_secret().encode("utf-8"),
        payload_text.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(digest, expected_digest):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    if payload.get("jobId") != job_id or payload.get("artifactId") != artifact_id:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    exp = payload.get("exp")
    if not isinstance(exp, int) or isinstance(exp, bool):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    if exp < int(time.time()) - 60:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    storage_key = payload.get("storageKey")
    if not isinstance(storage_key, str) or not storage_key:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    return storage_key


def artifact_storage_from_env() -> ArtifactStorageBackend | None:
    """Construct the configured storage backend, or None when unset (dev only)."""

    backend = os.environ.get(_BACKEND_ENV, "").strip().lower() or "volume"
    if backend == "none":
        return None
    if backend == "volume":
        root_raw = os.environ.get(_VOLUME_ROOT_ENV, "").strip()
        public_base = os.environ.get(_PUBLIC_BASE_URL_ENV, "").strip()
        if not root_raw or not public_base:
            return None
        return VolumeArtifactStorage(Path(root_raw), public_base)
    if backend in {"s3", "r2"}:
        bucket = os.environ.get(_S3_BUCKET_ENV, "").strip()
        endpoint = os.environ.get(_S3_ENDPOINT_ENV, "").strip()
        access_key = os.environ.get(_S3_ACCESS_KEY_ENV, "").strip()
        secret_key = os.environ.get(_S3_SECRET_KEY_ENV, "").strip()
        region = os.environ.get(_S3_REGION_ENV, "auto").strip() or "auto"
        if not all((bucket, endpoint, access_key, secret_key)):
            return None
        return S3CompatibleArtifactStorage(
            bucket=bucket,
            endpoint=endpoint,
            access_key_id=access_key,
            secret_access_key=secret_key,
            region=region,
        )
    raise ApiError(ErrorCode.INTERNAL_ERROR, 500)


def local_tarball_path(job_id: str) -> Path:
    """Resolve the GPU worker tarball path under the artifact root env."""

    from scooling_lab.gpu_worker import artifact_root  # noqa: PLC0415

    return artifact_root() / job_id / _OBJECT_NAME


def _s3_signed_headers(
    *,
    method: str,
    url: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
    payload_hash: str,
    content_type: str | None = None,
) -> dict[str, str]:
    """Return AWS SigV4 authorization headers for one S3-compatible request."""

    parsed = urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"
    amz_date = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = amz_date[:8]
    service = "s3"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        [
            method,
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = _derive_signing_key(secret_access_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers = {
        "Authorization": authorization,
        "Host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers


def _s3_presigned_get_url(
    *,
    url: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
    expires_seconds: int,
) -> str:
    """Return a presigned GET URL for S3-compatible object storage."""

    parsed = urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"
    amz_date = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = amz_date[:8]
    service = "s3"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    query_params: dict[str, str] = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key_id}/{credential_scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires_seconds),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_query = urlencode(sorted(query_params.items()))
    canonical_headers = f"host:{host}\n"
    canonical_request = "\n".join(
        [
            "GET",
            canonical_uri,
            canonical_query,
            canonical_headers,
            "host",
            "UNSIGNED-PAYLOAD",
        ]
    )
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = _derive_signing_key(secret_access_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{url}?{canonical_query}&X-Amz-Signature={signature}"


def _derive_signing_key(
    secret_access_key: str,
    date_stamp: str,
    region: str,
    service: str,
) -> bytes:
    """Derive the AWS SigV4 signing key."""

    key = ("AWS4" + secret_access_key).encode("utf-8")
    for chunk in (date_stamp, region, service, "aws4_request"):
        key = hmac.new(key, chunk.encode("utf-8"), hashlib.sha256).digest()
    return key
