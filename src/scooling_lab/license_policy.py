"""License and source-path policy for Scooling Lab dependency evidence."""

from __future__ import annotations

from dataclasses import dataclass


ALLOWED_LICENSES: frozenset[str] = frozenset(
    {
        "Apache-2.0",
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "PSF-2.0",
    }
)

BLOCKED_LICENSES: frozenset[str] = frozenset(
    {
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "GPL-2.0",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
    }
)

BLOCKED_PATH_SEGMENTS: frozenset[str] = frozenset({"studio", "unsloth_cli"})


class LicensePolicyError(ValueError):
    """Raised when a dependency or source path violates Scooling Lab policy."""


@dataclass(frozen=True)
class BomEntry:
    """Single dependency or project inventory row used by the BOM generator."""

    name: str
    version: str
    license: str
    source_path: str
    evidence: str


def normalize_source_path(source_path: str) -> str:
    """Normalize a source path for policy checks without touching the filesystem."""

    stripped = source_path.strip().replace("\\", "/")
    while "//" in stripped:
        stripped = stripped.replace("//", "/")
    return stripped.strip("/")


def validate_source_path(source_path: str) -> None:
    """Reject source paths that enter AGPL-covered Unsloth Studio or CLI code."""

    normalized = normalize_source_path(source_path)
    segments = {segment for segment in normalized.split("/") if segment}
    blocked = segments.intersection(BLOCKED_PATH_SEGMENTS)
    if blocked:
        blocked_list = ", ".join(sorted(blocked))
        raise LicensePolicyError(f"blocked source path segment: {blocked_list}")


def validate_license(license_id: str) -> None:
    """Reject non-allowlisted licenses before code can enter CI or the BOM."""

    normalized = license_id.strip()
    if normalized in BLOCKED_LICENSES:
        raise LicensePolicyError(f"blocked license: {normalized}")
    if normalized not in ALLOWED_LICENSES:
        raise LicensePolicyError(f"non-allowlisted license: {normalized}")


def validate_entry(entry: BomEntry) -> None:
    """Validate one BOM entry against license and source-path policy."""

    if not entry.name.strip():
        raise LicensePolicyError("BOM entry name is required")
    if not entry.version.strip():
        raise LicensePolicyError("BOM entry version is required")
    if not entry.evidence.strip():
        raise LicensePolicyError("BOM entry evidence is required")
    validate_license(entry.license)
    validate_source_path(entry.source_path)


def validate_entries(entries: list[BomEntry]) -> None:
    """Validate all BOM entries and fail closed when the BOM is empty."""

    if not entries:
        raise LicensePolicyError("BOM must contain at least one entry")
    for entry in entries:
        validate_entry(entry)
