"""Unit tier tests for Scooling Lab T0/T2 contracts."""

from __future__ import annotations

import unittest

from scooling_lab_helpers import valid_payload

from scooling_lab.contracts import TrainingJobRequest, TrainingJobStatus
from scooling_lab.errors import ApiError, ErrorCode, error_payload
from scooling_lab.license_policy import BomEntry, LicensePolicyError, validate_entry
from scooling_lab.state_machine import transition


class ScoolingLabUnitTests(unittest.TestCase):
    """Unit tests for state transitions, schema, license policy, and errors."""

    def test_unit_state_transitions_are_explicit_and_idempotent(self) -> None:
        """queued -> running -> succeeded works and replay is a no-op."""

        self.assertEqual(
            transition(TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING),
            TrainingJobStatus.RUNNING,
        )
        self.assertEqual(
            transition(TrainingJobStatus.RUNNING, TrainingJobStatus.SUCCEEDED),
            TrainingJobStatus.SUCCEEDED,
        )
        self.assertEqual(
            transition(TrainingJobStatus.SUCCEEDED, TrainingJobStatus.SUCCEEDED),
            TrainingJobStatus.SUCCEEDED,
        )

    def test_unit_invalid_state_transition_raises_safe_error(self) -> None:
        """queued -> succeeded is not allowed by the transition table."""

        with self.assertRaises(ApiError) as raised:
            transition(TrainingJobStatus.QUEUED, TrainingJobStatus.SUCCEEDED)
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_TRANSITION)

    def test_unit_schema_rejects_unsafe_fields_and_unapproved_models(self) -> None:
        """Dangerous keys and unknown model ids fail in schema validation."""

        payload = valid_payload()
        payload["workerUrl"] = "https://attacker.invalid/worker"
        with self.assertRaises(ApiError):
            TrainingJobRequest.from_mapping(payload)

        model_payload = valid_payload()
        model_payload["modelId"] = "unapproved-model"
        with self.assertRaises(ApiError):
            TrainingJobRequest.from_mapping(model_payload)

    def test_unit_license_policy_blocks_agpl_and_blocked_paths(self) -> None:
        """The BOM policy rejects AGPL licenses and Unsloth Studio/CLI paths."""

        validate_entry(
            BomEntry(
                name="safe",
                version="1.0.0",
                license="MIT",
                source_path="third_party/safe",
                evidence="fixture",
            )
        )
        with self.assertRaises(LicensePolicyError):
            validate_entry(
                BomEntry(
                    name="blocked",
                    version="1.0.0",
                    license="AGPL-3.0",
                    source_path="third_party/blocked",
                    evidence="fixture",
                )
            )
        with self.assertRaises(LicensePolicyError):
            validate_entry(
                BomEntry(
                    name="blocked-path",
                    version="1.0.0",
                    license="Apache-2.0",
                    source_path="vendor/unsloth_cli/main.py",
                    evidence="fixture",
                )
            )

    def test_unit_error_model_does_not_echo_payload_or_paths(self) -> None:
        """Safe errors expose only code and stable public message."""

        payload = error_payload(ApiError(ErrorCode.VALIDATION_ERROR, 400))
        text = str(payload)
        self.assertIn("VALIDATION_ERROR", text)
        self.assertNotIn("/Users/", text)
        self.assertNotIn("attacker.invalid", text)
        self.assertNotIn("payload", text.lower())


if __name__ == "__main__":
    unittest.main()
