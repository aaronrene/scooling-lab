"""Security tier tests — T3 dataset approval boundary and injection defenses."""

from __future__ import annotations

import unittest

from scooling_lab_helpers import valid_payload

from scooling_lab.dataset_review import (
    DatasetStore,
    RejectionReasonCode,
    require_dataset_id,
    validate_review_request,
)
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class T3SecurityDatasetBoundaryTests(unittest.TestCase):
    """Security tests for dataset approval boundaries and injection rejection."""

    def test_security_t3_unknown_dataset_id_refused_at_job_creation(self) -> None:
        """A dataset id that was never registered is refused with DATASET_NOT_APPROVED."""

        ds_store = DatasetStore()
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        with self.assertRaises(ApiError) as raised:
            service.create_training_job(
                {
                    "idempotencyKey": "sec-unknown-ds",
                    "datasetId": "totally-unknown-ds-id",
                    "modelId": "fixture-tiny-llm",
                    "requestedBy": "security-test",
                }
            )
        self.assertEqual(raised.exception.code, ErrorCode.DATASET_NOT_APPROVED)

    def test_security_t3_rejected_dataset_id_refused_at_job_creation(self) -> None:
        """A rejected dataset cannot slip into job creation."""

        ds_store = DatasetStore()
        ds_store.register("sec-rejected-ds")
        ds_store.submit_for_review("sec-rejected-ds")
        ds_store.reject("sec-rejected-ds", RejectionReasonCode.POLICY_VIOLATION)
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        with self.assertRaises(ApiError) as raised:
            service.create_training_job(
                {
                    "idempotencyKey": "sec-rejected",
                    "datasetId": "sec-rejected-ds",
                    "modelId": "fixture-tiny-llm",
                    "requestedBy": "security-test",
                }
            )
        self.assertEqual(raised.exception.code, ErrorCode.DATASET_NOT_APPROVED)

    def test_security_t3_injection_shaped_dataset_ids_rejected(self) -> None:
        """Injection-shaped dataset ids are refused by the validator."""

        injection_ids = (
            "../private/dataset",
            "https://attacker.invalid/ds",
            "ds;rm${IFS}-rf",
            "`whoami`",
            "<script>x</script>",
            "d",  # too short
            "a" * 97,  # too long
        )
        for bad in injection_ids:
            with self.subTest(bad=bad):
                with self.assertRaises(ApiError):
                    require_dataset_id(bad)

    def test_security_t3_injection_shaped_reason_strings_rejected(self) -> None:
        """Injection-shaped strings are not accepted as rejection reason codes."""

        injection_reasons = (
            "https://attacker.invalid/reason",
            "../etc/passwd",
            "POLICY_VIOLATION; rm -rf /",
            "because I said so",
            "",
        )
        from scooling_lab.dataset_review import require_rejection_reason

        for bad in injection_reasons:
            with self.subTest(bad=bad):
                with self.assertRaises(ApiError):
                    require_rejection_reason(bad)

    def test_security_t3_no_free_text_reflected_in_dataset_rejection(self) -> None:
        """Rejection records never echo caller-supplied text."""

        ds_store = DatasetStore()
        ds_store.register("sec-reflect-check")
        ds_store.submit_for_review("sec-reflect-check")
        ds_store.reject("sec-reflect-check", RejectionReasonCode.SCHEMA_MISMATCH)
        public_str = str(ds_store.get("sec-reflect-check").to_public_dict())
        self.assertNotIn("caller supplied reason text", public_str)
        self.assertNotIn("free-text", public_str)

    def test_security_t3_review_request_rejects_unknown_keys(self) -> None:
        """Unknown keys in a review payload are rejected, including injections."""

        injection_payloads = (
            {"action": "approve", "workerUrl": "http://attacker.invalid"},
            {"action": "reject", "reasonCode": "POLICY_VIOLATION", "callbackUrl": "x"},
            {"action": "approve", "reasonCode": "POLICY_VIOLATION"},
        )
        for payload in injection_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ApiError):
                    validate_review_request(payload)

    def test_security_t3_dataset_not_approved_error_does_not_echo_id(self) -> None:
        """The DATASET_NOT_APPROVED error message does not echo the dataset id."""

        ds_store = DatasetStore()
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        try:
            service.create_training_job(
                {
                    "idempotencyKey": "sec-no-echo",
                    "datasetId": "fixture:synthetic-tiny-v1",
                    "modelId": "fixture-tiny-llm",
                    "requestedBy": "security-test",
                }
            )
        except ApiError as exc:
            # Override store to simulate unapproved state; verify message is generic.
            msg = exc.message
            self.assertNotIn("fixture:synthetic-tiny-v1", msg)
            self.assertNotIn("attacker", msg)

        # Force an unapproved scenario with a clearly synthetic id.
        ds_store2 = DatasetStore()
        service2 = TrainingApiService(TrainingJobStore(), dataset_store=ds_store2)
        ds_store2.register("echo-test-ds")
        with self.assertRaises(ApiError) as raised:
            service2.create_training_job(
                {
                    "idempotencyKey": "sec-no-echo2",
                    "datasetId": "echo-test-ds",
                    "modelId": "fixture-tiny-llm",
                    "requestedBy": "security-test",
                }
            )
        # Error message must not echo the dataset id.
        self.assertNotIn("echo-test-ds", raised.exception.message)
        self.assertEqual(raised.exception.code, ErrorCode.DATASET_NOT_APPROVED)

    def test_security_t3_pending_review_dataset_id_refused(self) -> None:
        """A dataset in pending_review state (not yet decided) blocks job creation."""

        ds_store = DatasetStore()
        ds_store.register("pending-review-ds")
        ds_store.submit_for_review("pending-review-ds")
        service = TrainingApiService(TrainingJobStore(), dataset_store=ds_store)
        with self.assertRaises(ApiError) as raised:
            service.create_training_job(
                {
                    "idempotencyKey": "sec-pending",
                    "datasetId": "pending-review-ds",
                    "modelId": "fixture-tiny-llm",
                    "requestedBy": "security-test",
                }
            )
        self.assertEqual(raised.exception.code, ErrorCode.DATASET_NOT_APPROVED)


if __name__ == "__main__":
    unittest.main()
