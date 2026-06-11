"""Retention policy classes and expiry evaluation for fixture artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from scooling_lab.errors import ApiError, ErrorCode


class RetentionPolicyClass(str, Enum):
    """Supported artifact retention classes for synthetic fixture jobs."""

    EPHEMERAL = "ephemeral"
    STANDARD = "standard"
    EXTENDED = "extended"


@dataclass(frozen=True)
class RetentionBounds:
    """Default and allowed TTL range for one retention class."""

    default_ttl_seconds: int
    min_ttl_seconds: int
    max_ttl_seconds: int


@dataclass(frozen=True)
class RetentionPolicy:
    """Validated retention policy for one training job request."""

    policy_class: RetentionPolicyClass
    ttl_seconds: int

    def to_public_dict(self) -> dict[str, str | int]:
        """Serialize the policy without private paths, text, or credentials."""

        return {
            "policyClass": self.policy_class.value,
            "ttlSeconds": self.ttl_seconds,
        }


RETENTION_BOUNDS: MappingProxyType[RetentionPolicyClass, RetentionBounds] = MappingProxyType(
    {
        RetentionPolicyClass.EPHEMERAL: RetentionBounds(
            default_ttl_seconds=3_600,
            min_ttl_seconds=60,
            max_ttl_seconds=86_400,
        ),
        RetentionPolicyClass.STANDARD: RetentionBounds(
            default_ttl_seconds=2_592_000,
            min_ttl_seconds=3_600,
            max_ttl_seconds=7_776_000,
        ),
        RetentionPolicyClass.EXTENDED: RetentionBounds(
            default_ttl_seconds=31_536_000,
            min_ttl_seconds=86_400,
            max_ttl_seconds=63_072_000,
        ),
    }
)


def default_retention_policy() -> RetentionPolicy:
    """Return the default artifact retention policy for fixture jobs."""

    bounds = RETENTION_BOUNDS[RetentionPolicyClass.STANDARD]
    return RetentionPolicy(
        policy_class=RetentionPolicyClass.STANDARD,
        ttl_seconds=bounds.default_ttl_seconds,
    )


def retention_policy_from_mapping(value: object) -> RetentionPolicy:
    """Validate a request retention policy or return the default policy."""

    if value is None:
        return default_retention_policy()
    if not isinstance(value, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if set(value).difference({"policyClass", "ttlSeconds"}):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    policy_class_value = value.get("policyClass")
    if not isinstance(policy_class_value, str):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    try:
        policy_class = RetentionPolicyClass(policy_class_value)
    except ValueError as exc:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400) from exc

    bounds = RETENTION_BOUNDS[policy_class]
    ttl_value = value.get("ttlSeconds", bounds.default_ttl_seconds)
    if not isinstance(ttl_value, int) or isinstance(ttl_value, bool):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if not bounds.min_ttl_seconds <= ttl_value <= bounds.max_ttl_seconds:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    return RetentionPolicy(policy_class=policy_class, ttl_seconds=ttl_value)


def parse_utc_timestamp(value: str) -> datetime:
    """Parse a public UTC timestamp emitted by Scooling Lab."""

    if not value.endswith("Z"):
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00").astimezone(UTC)


def utc_timestamp(value: datetime) -> str:
    """Format a UTC datetime for public API metadata."""

    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def expires_at(created_at: str, policy: RetentionPolicy) -> str:
    """Return the expiry timestamp for an artifact under a retention policy."""

    expires = parse_utc_timestamp(created_at) + timedelta(seconds=policy.ttl_seconds)
    return utc_timestamp(expires)


def is_expired(created_at: str, policy: RetentionPolicy, now: datetime) -> bool:
    """Return whether an artifact is expired at the supplied UTC instant."""

    expiry = parse_utc_timestamp(expires_at(created_at, policy))
    return now.astimezone(UTC) >= expiry
