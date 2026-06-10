"""License policy helpers for Scooling Lab dependency inventory checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable


APPROVED_LICENSES = frozenset({"apache-2.0", "mit", "bsd-2-clause", "bsd-3-clause"})
DISALLOWED_PATH_PREFIXES = ("studio", "unsloth_cli")


@dataclass(frozen=True, slots=True)
class DependencyEntry:
    """Single dependency or source path observed by an inventory scan."""

    name: str
    license_id: str
    source_path: str


@dataclass(frozen=True, slots=True)
class LicenseAuditResult:
    """Deterministic result for a dependency policy audit."""

    accepted: tuple[DependencyEntry, ...]
    rejected: tuple[DependencyEntry, ...]

    @property
    def ok(self) -> bool:
        """Return true when every scanned dependency passed policy."""

        return len(self.rejected) == 0


def normalize_license_id(license_id: str) -> str:
    """Normalize SPDX-like license names for allowlist matching."""

    return license_id.strip().lower()


def is_approved_license(license_id: str) -> bool:
    """Return true when a license is allowed for the initial worker lane."""

    return normalize_license_id(license_id) in APPROVED_LICENSES


def is_allowed_source_path(source_path: str) -> bool:
    """Return false for known AGPL-covered or product-prohibited path prefixes."""

    path = PurePosixPath(source_path.strip())
    first_part = path.parts[0] if path.parts else ""

    return first_part not in DISALLOWED_PATH_PREFIXES


def audit_dependency_entries(entries: Iterable[DependencyEntry]) -> LicenseAuditResult:
    """Split dependency entries into accepted and rejected policy buckets."""

    accepted: list[DependencyEntry] = []
    rejected: list[DependencyEntry] = []

    for entry in entries:
        if is_approved_license(entry.license_id) and is_allowed_source_path(entry.source_path):
            accepted.append(entry)
        else:
            rejected.append(entry)

    return LicenseAuditResult(accepted=tuple(accepted), rejected=tuple(rejected))
