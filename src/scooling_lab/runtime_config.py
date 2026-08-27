"""Production runtime configuration for durable state and artifact storage."""

from __future__ import annotations

import os
from pathlib import Path

_STATE_PATH_ENV = "SCOOLING_LAB_STATE_PATH"
_DEV_FIXTURES_ENV = "SCOOLING_LAB_DEV_FIXTURES"
_PRODUCTION_ENV = "SCOOLING_LAB_ENV"
_NODE_ENV = "NODE_ENV"
_RAILWAY_ENV = "RAILWAY_ENVIRONMENT"


def dev_fixtures_enabled() -> bool:
    """Return whether in-memory defaults are allowed (CI / local dev only)."""

    return os.environ.get(_DEV_FIXTURES_ENV, "").strip() == "1"


def is_production_runtime() -> bool:
    """Return whether the API is running in a production-like deploy context."""

    if dev_fixtures_enabled():
        return False
    explicit = os.environ.get(_PRODUCTION_ENV, "").strip().lower()
    if explicit in {"production", "prod"}:
        return True
    if os.environ.get(_NODE_ENV, "").strip().lower() == "production":
        return True
    if os.environ.get(_RAILWAY_ENV, "").strip():
        return True
    return False


def resolve_state_path() -> Path | None:
    """Return the durable job-store path, or None when dev fixtures are enabled.

    In production-like runtimes ``SCOOLING_LAB_STATE_PATH`` is required.
    """

    raw = os.environ.get(_STATE_PATH_ENV, "").strip()
    if raw:
        return Path(raw)
    if is_production_runtime():
        raise SystemExit(
            f"{_STATE_PATH_ENV} is required in production "
            f"(set {_DEV_FIXTURES_ENV}=1 only for local dev / CI)."
        )
    return None
