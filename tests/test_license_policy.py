"""Unit tests for dependency license policy checks."""

from unittest import TestCase

from scooling_lab.license_policy import (
    DependencyEntry,
    audit_dependency_entries,
    is_allowed_source_path,
    is_approved_license,
)


class LicensePolicyTests(TestCase):
    """Validate the initial Apache-compatible dependency policy."""

    def test_permissive_license_ids_are_allowed(self) -> None:
        self.assertTrue(is_approved_license("Apache-2.0"))
        self.assertTrue(is_approved_license("MIT"))
        self.assertFalse(is_approved_license("AGPL-3.0"))

    def test_agpl_component_paths_are_blocked(self) -> None:
        self.assertTrue(is_allowed_source_path("unsloth/models/loader.py"))
        self.assertFalse(is_allowed_source_path("studio/app.py"))
        self.assertFalse(is_allowed_source_path("unsloth_cli/train.py"))

    def test_audit_splits_accepted_and_rejected_entries(self) -> None:
        accepted = DependencyEntry(
            name="candidate-core",
            license_id="Apache-2.0",
            source_path="unsloth/core.py",
        )
        rejected = DependencyEntry(
            name="candidate-studio",
            license_id="AGPL-3.0",
            source_path="studio/app.py",
        )

        result = audit_dependency_entries((accepted, rejected))

        self.assertFalse(result.ok)
        self.assertEqual(result.accepted, (accepted,))
        self.assertEqual(result.rejected, (rejected,))
