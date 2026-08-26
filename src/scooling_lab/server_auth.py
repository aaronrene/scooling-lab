"""Server-to-server ingest auth (stdlib HS256 JWT envelope)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Mapping

from scooling_lab.contracts import is_own_data_dataset_id, require_safe_identifier
from scooling_lab.errors import ApiError, ErrorCode

_AUTH_SECRET_ENV = "SCOOLING_LAB_INGEST_AUTH_SECRET"
_AUTH_ISSUER_ENV = "SCOOLING_LAB_INGEST_AUTH_ISSUER"
_DEFAULT_ISSUER = "scooling"
_MAX_CLOCK_SKEW_SECONDS = 60
_REQUIRED_CLAIMS = frozenset({"iss", "datasetId", "exp", "sub"})


def ingest_auth_secret() -> str:
    """Return the configured ingest auth secret or fail closed."""

    raw = os.environ.get(_AUTH_SECRET_ENV, "").strip()
    if not raw:
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
    return raw


def ingest_auth_issuer() -> str:
    """Return the expected JWT issuer claim."""

    raw = os.environ.get(_AUTH_ISSUER_ENV, _DEFAULT_ISSUER).strip()
    return raw or _DEFAULT_ISSUER


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sign_ingest_jwt(
    dataset_id: str,
    subject: str,
    *,
    secret: str | None = None,
    issuer: str | None = None,
    ttl_seconds: int = 300,
) -> str:
    """Mint a test/dev HS256 JWT for package ingest (Scooling backend analogue)."""

    require_safe_identifier(dataset_id)
    require_safe_identifier(subject)
    if not is_own_data_dataset_id(dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    secret_value = secret if secret is not None else ingest_auth_secret()
    issuer_value = issuer if issuer is not None else ingest_auth_issuer()
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "iss": issuer_value,
        "sub": subject,
        "datasetId": dataset_id,
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


def _parse_bearer_token(authorization_header: str) -> str:
    """Extract a bearer token from the Authorization header."""

    header = authorization_header.strip()
    if not header.lower().startswith("bearer "):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    token = header[7:].strip()
    if not token or " " in token:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    return token


def _decode_hs256_jwt(token: str, secret: str) -> dict[str, object]:
    """Verify HS256 JWT signature and return claims."""

    parts = token.split(".")
    if len(parts) != 3:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    signing_input = f"{parts[0]}.{parts[1]}"
    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        signature = _b64url_decode(parts[2])
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401) from None
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    if not isinstance(claims, dict):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_sig):
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    return claims


def verify_ingest_auth(
    authorization_header: str,
    expected_dataset_id: str,
) -> dict[str, str]:
    """Validate server JWT; dataset id in path must match token claim."""

    require_safe_identifier(expected_dataset_id)
    if not is_own_data_dataset_id(expected_dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    token = _parse_bearer_token(authorization_header)
    claims = _decode_hs256_jwt(token, ingest_auth_secret())
    missing = _REQUIRED_CLAIMS.difference(claims)
    if missing:
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    iss = claims.get("iss")
    if not isinstance(iss, str) or iss != ingest_auth_issuer():
        raise ApiError(ErrorCode.UNAUTHORIZED, 401)
    dataset_id = claims.get("datasetId")
    sub = claims.get("sub")
    if not isinstance(dataset_id, str) or dataset_id != expected_dataset_id:
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
    return {"subject": sub, "datasetId": dataset_id}


def reject_forbidden_ingest_keys(payload: Mapping[str, object]) -> None:
    """Reject path/url/shell-shaped keys anywhere in an ingest payload."""

    for key, value in payload.items():
        lowered = key.lower()
        if any(
            term in lowered
            for term in (
                "url",
                "uri",
                "path",
                "file",
                "shell",
                "command",
                "callback",
                "webhook",
                "worker",
            )
        ):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        if isinstance(value, Mapping):
            reject_forbidden_ingest_keys(value)
