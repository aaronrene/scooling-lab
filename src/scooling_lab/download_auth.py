"""Server-to-server artifact download auth (HS256 JWT envelope)."""

from __future__ import annotations

import json
import os
import time

from scooling_lab.contracts import require_artifact_id, require_job_id, require_safe_identifier
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.server_auth import (
    _MAX_CLOCK_SKEW_SECONDS,
    _b64url_encode,
    _decode_hs256_jwt,
    _parse_bearer_token,
    ingest_auth_issuer,
    ingest_auth_secret,
)

_DOWNLOAD_SECRET_ENV = "SCOOLING_LAB_DOWNLOAD_AUTH_SECRET"
_DOWNLOAD_ISSUER_ENV = "SCOOLING_LAB_DOWNLOAD_AUTH_ISSUER"
_DEFAULT_DOWNLOAD_TTL_SECONDS = 300
_REQUIRED_CLAIMS = frozenset({"iss", "datasetId", "exp", "sub"})


def download_auth_secret() -> str:
    """Return the configured download auth secret or fall back to ingest secret."""

    raw = os.environ.get(_DOWNLOAD_SECRET_ENV, "").strip()
    if raw:
        return raw
    return ingest_auth_secret()


def download_auth_issuer() -> str:
    """Return the expected JWT issuer for download requests."""

    raw = os.environ.get(_DOWNLOAD_ISSUER_ENV, "").strip()
    if raw:
        return raw
    return ingest_auth_issuer()


def sign_download_jwt(
    job_id: str,
    artifact_id: str,
    subject: str,
    *,
    secret: str | None = None,
    issuer: str | None = None,
    ttl_seconds: int = _DEFAULT_DOWNLOAD_TTL_SECONDS,
) -> str:
    """Mint a test/dev HS256 JWT for artifact download URL issuance."""

    import hashlib
    import hmac

    require_job_id(job_id)
    require_artifact_id(artifact_id)
    require_safe_identifier(subject)
    secret_value = secret if secret is not None else download_auth_secret()
    issuer_value = issuer if issuer is not None else download_auth_issuer()
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    composite = f"{job_id}:{artifact_id}"
    claims = {
        "iss": issuer_value,
        "sub": subject,
        "datasetId": composite,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    header_segment = _b64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_segment = _b64url_encode(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        secret_value.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def verify_download_auth(
    authorization_header: str,
    expected_job_id: str,
    expected_artifact_id: str,
) -> dict[str, str]:
    """Validate server JWT; job and artifact ids must match token composite claim."""

    require_job_id(expected_job_id)
    require_artifact_id(expected_artifact_id)
    token = _parse_bearer_token(authorization_header)
    claims = _decode_hs256_jwt(token, download_auth_secret())
    missing = _REQUIRED_CLAIMS.difference(claims)
    if missing:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    iss = claims.get("iss")
    if not isinstance(iss, str) or iss != download_auth_issuer():
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    composite = claims.get("datasetId")
    sub = claims.get("sub")
    if not isinstance(composite, str):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    expected_composite = f"{expected_job_id}:{expected_artifact_id}"
    if composite != expected_composite:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    if not isinstance(sub, str):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    require_safe_identifier(sub)
    exp = claims.get("exp")
    if not isinstance(exp, int) or isinstance(exp, bool):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    now = int(time.time())
    if exp < now - _MAX_CLOCK_SKEW_SECONDS:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    iat = claims.get("iat")
    if isinstance(iat, int) and not isinstance(iat, bool) and iat > now + _MAX_CLOCK_SKEW_SECONDS:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    return {
        "subject": sub,
        "jobId": expected_job_id,
        "artifactId": expected_artifact_id,
    }
