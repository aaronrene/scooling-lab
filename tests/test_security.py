"""Security tier tests for Scooling Lab request and dependency boundaries."""

from __future__ import annotations

import unittest

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.bom import audit_repository_paths
from scooling_lab.contracts import TrainingJobRequest
from scooling_lab.errors import ApiError
from scooling_lab.license_policy import BomEntry, LicensePolicyError, validate_entry


class ScoolingLabSecurityTests(unittest.TestCase):
    """Security tests for injection rejection and AGPL boundary enforcement."""

    def test_security_rejects_path_traversal_command_and_url_injection(self) -> None:
        """Untrusted paths, commands, URLs, callbacks, and worker fields fail closed."""

        attacks: list[dict[str, object]] = []
        path_payload = valid_payload("path")
        path_payload["datasetId"] = "../private"
        attacks.append(path_payload)

        command_payload = valid_payload("command")
        command_payload["trainingParameters"] = {"epochs": 1, "command": "rm -rf /"}
        attacks.append(command_payload)

        callback_payload = valid_payload("callback")
        callback_payload["callbackUrl"] = "https://attacker.invalid/callback"
        attacks.append(callback_payload)

        worker_payload = valid_payload("worker")
        worker_payload["workerUrl"] = "http://127.0.0.1:9999"
        attacks.append(worker_payload)

        for payload in attacks:
            with self.subTest(payload=payload):
                with self.assertRaises(ApiError):
                    TrainingJobRequest.from_mapping(payload)

    def test_security_secret_scan_and_bom_audit_are_wired(self) -> None:
        """CI contains gitleaks and the repository path audit passes locally."""

        workflow = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("gitleaks detect", workflow)
        self.assertIn("python -m scooling_lab.bom", workflow)
        audit_repository_paths(PROJECT_ROOT)

    def test_security_agpl_package_and_blocked_paths_are_rejected(self) -> None:
        """AGPL license ids and Studio/CLI paths cannot enter the BOM."""

        with self.assertRaises(LicensePolicyError):
            validate_entry(
                BomEntry(
                    name="studio",
                    version="1.0.0",
                    license="AGPL-3.0-only",
                    source_path="studio/backend/run.py",
                    evidence="fixture",
                )
            )
        with self.assertRaises(LicensePolicyError):
            validate_entry(
                BomEntry(
                    name="unsloth-cli",
                    version="1.0.0",
                    license="Apache-2.0",
                    source_path="vendor/unsloth_cli/app.py",
                    evidence="fixture",
                )
            )


if __name__ == "__main__":
    unittest.main()
