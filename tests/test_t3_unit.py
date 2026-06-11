"""Unit tier tests — T3 dataset review and job queue state machine."""

from __future__ import annotations

import unittest

from scooling_lab_helpers import valid_payload

from scooling_lab.contracts import TrainingJobStatus
from scooling_lab.dataset_review import (
    DatasetStatus,
    DatasetStore,
    RejectionReasonCode,
    dataset_transition,
    default_dataset_shape,
    require_dataset_id,
    validate_review_request,
)
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


class T3UnitDatasetStateMachineTests(unittest.TestCase):
    """Unit tests for the dataset review state machine."""

    def test_unit_t3_registered_to_pending_review(self) -> None:
        """registered → pending_review is a valid transition."""

        self.assertEqual(
            dataset_transition(DatasetStatus.REGISTERED, DatasetStatus.PENDING_REVIEW),
            DatasetStatus.PENDING_REVIEW,
        )

    def test_unit_t3_pending_to_approved(self) -> None:
        """pending_review → approved is a valid transition."""

        self.assertEqual(
            dataset_transition(DatasetStatus.PENDING_REVIEW, DatasetStatus.APPROVED),
            DatasetStatus.APPROVED,
        )

    def test_unit_t3_pending_to_rejected(self) -> None:
        """pending_review → rejected is a valid transition."""

        self.assertEqual(
            dataset_transition(DatasetStatus.PENDING_REVIEW, DatasetStatus.REJECTED),
            DatasetStatus.REJECTED,
        )

    def test_unit_t3_approved_is_terminal(self) -> None:
        """approved cannot transition to any other state."""

        with self.assertRaises(ApiError) as raised:
            dataset_transition(DatasetStatus.APPROVED, DatasetStatus.REJECTED)
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_TRANSITION)

    def test_unit_t3_rejected_is_terminal(self) -> None:
        """rejected cannot transition to approved."""

        with self.assertRaises(ApiError) as raised:
            dataset_transition(DatasetStatus.REJECTED, DatasetStatus.APPROVED)
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_TRANSITION)

    def test_unit_t3_registered_cannot_skip_to_approved(self) -> None:
        """registered → approved must go through pending_review."""

        with self.assertRaises(ApiError) as raised:
            dataset_transition(DatasetStatus.REGISTERED, DatasetStatus.APPROVED)
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_TRANSITION)

    def test_unit_t3_idempotent_same_state_replay(self) -> None:
        """Same-state replay is allowed for every dataset status."""

        for status in DatasetStatus:
            with self.subTest(status=status):
                self.assertEqual(dataset_transition(status, status), status)


class T3UnitRejectionReasonCodeTests(unittest.TestCase):
    """Unit tests for the rejection reason code validation."""

    def test_unit_t3_all_reason_codes_are_accepted(self) -> None:
        """Every RejectionReasonCode value passes validation."""

        for code in RejectionReasonCode:
            with self.subTest(code=code):
                from scooling_lab.dataset_review import require_rejection_reason

                self.assertEqual(require_rejection_reason(code.value), code)

    def test_unit_t3_free_text_reason_rejected(self) -> None:
        """Arbitrary strings that are not enum members are rejected."""

        from scooling_lab.dataset_review import require_rejection_reason

        with self.assertRaises(ApiError):
            require_rejection_reason("because I said so")

    def test_unit_t3_url_shaped_reason_rejected(self) -> None:
        """URL-shaped strings are not accepted as reason codes."""

        from scooling_lab.dataset_review import require_rejection_reason

        with self.assertRaises(ApiError):
            require_rejection_reason("https://attacker.invalid/reason")


class T3UnitReviewRequestValidationTests(unittest.TestCase):
    """Unit tests for the review request payload validator."""

    def test_unit_t3_approve_action_accepted(self) -> None:
        """action=approve with no reasonCode is valid."""

        action, reason = validate_review_request({"action": "approve"})
        self.assertEqual(action, "approve")
        self.assertIsNone(reason)

    def test_unit_t3_reject_action_requires_reason_code(self) -> None:
        """action=reject without a reasonCode raises VALIDATION_ERROR."""

        with self.assertRaises(ApiError) as raised:
            validate_review_request({"action": "reject"})
        self.assertEqual(raised.exception.code, ErrorCode.VALIDATION_ERROR)

    def test_unit_t3_reject_with_valid_reason_accepted(self) -> None:
        """action=reject with a valid reasonCode returns both values."""

        action, reason = validate_review_request(
            {"action": "reject", "reasonCode": "POLICY_VIOLATION"}
        )
        self.assertEqual(action, "reject")
        self.assertEqual(reason, RejectionReasonCode.POLICY_VIOLATION)

    def test_unit_t3_unknown_action_rejected(self) -> None:
        """Unknown action values fail validation."""

        with self.assertRaises(ApiError):
            validate_review_request({"action": "delete"})

    def test_unit_t3_unknown_keys_rejected(self) -> None:
        """Extra keys in the review payload are rejected."""

        with self.assertRaises(ApiError):
            validate_review_request(
                {"action": "approve", "workerUrl": "http://attacker.invalid"}
            )

    def test_unit_t3_approve_with_reason_code_rejected(self) -> None:
        """approve action must not carry a reasonCode."""

        with self.assertRaises(ApiError):
            validate_review_request(
                {"action": "approve", "reasonCode": "FORMAT_INVALID"}
            )


class T3UnitDatasetIdValidationTests(unittest.TestCase):
    """Unit tests for dataset id format enforcement."""

    def test_unit_t3_safe_dataset_ids_accepted(self) -> None:
        """Well-formed dataset ids within length bounds are accepted."""

        safe_ids = (
            "fixture:synthetic-tiny-v1",
            "ds.001",
            "dataset-v2",
        )
        for dataset_id in safe_ids:
            with self.subTest(dataset_id=dataset_id):
                self.assertEqual(require_dataset_id(dataset_id), dataset_id)

    def test_unit_t3_path_traversal_and_url_ids_rejected(self) -> None:
        """Path-like and URL-like dataset ids are rejected."""

        bad_ids = (
            "../private/dataset",
            "https://attacker.invalid/ds",
            "ds;rm-rf",
            "d",  # too short
        )
        for bad in bad_ids:
            with self.subTest(bad=bad):
                with self.assertRaises(ApiError):
                    require_dataset_id(bad)


class T3UnitDatasetStoreTests(unittest.TestCase):
    """Unit tests for the DatasetStore lifecycle operations."""

    def test_unit_t3_fixture_dataset_pre_approved(self) -> None:
        """The synthetic fixture dataset is pre-approved in a fresh store."""

        store = DatasetStore()
        self.assertTrue(store.is_approved("fixture:synthetic-tiny-v1"))

    def test_unit_t3_register_new_dataset(self) -> None:
        """A new dataset starts in registered state."""

        store = DatasetStore()
        record = store.register("new-dataset-v1")
        self.assertEqual(record.status, DatasetStatus.REGISTERED)

    def test_unit_t3_register_already_approved_raises_conflict(self) -> None:
        """Re-registering an approved dataset raises CONFLICT."""

        store = DatasetStore()
        with self.assertRaises(ApiError) as raised:
            store.register("fixture:synthetic-tiny-v1")
        self.assertEqual(raised.exception.code, ErrorCode.CONFLICT)

    def test_unit_t3_full_approval_lifecycle(self) -> None:
        """Submit-time validation approves the default synthetic shape."""

        store = DatasetStore()
        store.register("lifecycle-ds-v1")
        submitted = store.submit_for_review("lifecycle-ds-v1")
        self.assertEqual(submitted.status, DatasetStatus.APPROVED)
        record = store.approve("lifecycle-ds-v1")
        self.assertEqual(record.status, DatasetStatus.APPROVED)
        self.assertTrue(store.is_approved("lifecycle-ds-v1"))

    def test_unit_t3_full_rejection_lifecycle(self) -> None:
        """Submit-time validation rejects invalid metadata with the reason code."""

        store = DatasetStore()
        store.register_shape(
            "reject-ds-v1",
            default_dataset_shape(RejectionReasonCode.FORMAT_INVALID),
        )
        store.submit_for_review("reject-ds-v1")
        record = store.reject("reject-ds-v1", RejectionReasonCode.FORMAT_INVALID)
        self.assertEqual(record.status, DatasetStatus.REJECTED)
        self.assertEqual(record.rejection_reason, RejectionReasonCode.FORMAT_INVALID)
        self.assertFalse(store.is_approved("reject-ds-v1"))

    def test_unit_t3_unknown_dataset_is_not_found(self) -> None:
        """Getting an unregistered dataset raises NOT_FOUND."""

        store = DatasetStore()
        with self.assertRaises(ApiError) as raised:
            store.get("totally-unknown-ds")
        self.assertEqual(raised.exception.code, ErrorCode.NOT_FOUND)

    def test_unit_t3_unapproved_dataset_blocks_job_creation(self) -> None:
        """Jobs against a registered-but-not-yet-approved dataset are refused."""

        store = DatasetStore()
        store.register("new-dataset-v1")
        service = TrainingApiService(TrainingJobStore(), dataset_store=store)

        bad_payload = {
            "idempotencyKey": "test-unapproved",
            "datasetId": "fixture:synthetic-tiny-v1",
            "modelId": "fixture-tiny-llm",
            "requestedBy": "unit-test",
        }
        with self.assertRaises(ApiError) as raised:
            service.create_training_job({**bad_payload, "datasetId": "new-dataset-v1"})
        self.assertEqual(raised.exception.code, ErrorCode.DATASET_NOT_APPROVED)

    def test_unit_t3_queue_state_fields_present(self) -> None:
        """get_queue_state returns all expected fields with correct types."""

        service = TrainingApiService(TrainingJobStore())
        state = service.get_queue_state()
        self.assertIn("queuedCount", state)
        self.assertIn("runningCount", state)
        self.assertIn("activeCount", state)
        self.assertIn("maxConcurrentRunning", state)
        self.assertIn("queueLimit", state)
        self.assertIsInstance(state["queuedCount"], int)
        self.assertIsInstance(state["runningCount"], int)


if __name__ == "__main__":
    unittest.main()
