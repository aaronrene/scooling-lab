"""Security tier tests for Scooling Lab request and dependency boundaries."""

from __future__ import annotations

import unittest

from scooling_lab_helpers import PROJECT_ROOT, valid_payload

from scooling_lab.bom import audit_repository_paths
from scooling_lab.contracts import TrainingJobRequest
from scooling_lab.fake_worker import fixture_dataset_bytes
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.license_policy import BomEntry, LicensePolicyError, validate_entry
from scooling_lab.service import TrainingApiService
from scooling_lab.store import TrainingJobStore


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

    def test_security_provenance_excludes_synthetic_fixture_text_markers(self) -> None:
        """Provenance output never contains text from the fixture dataset."""

        marker = "synthetic learner practices"
        self.assertIn(marker, fixture_dataset_bytes().decode("utf-8"))
        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("marker-absence"))
        provenance_text = str(service.get_provenance(str(created["id"])))

        self.assertNotIn(marker, provenance_text)
        self.assertNotIn("study habits", provenance_text)
        self.assertNotIn("astronomy facts", provenance_text)

    def test_security_forged_artifact_id_cannot_delete_another_job(self) -> None:
        """A valid artifact id from one job cannot delete a different job."""

        service = TrainingApiService(TrainingJobStore())
        first = service.create_training_job(valid_payload("forged-a"))
        second = service.create_training_job(valid_payload("forged-b"))
        first_job_id = str(first["id"])
        second_job_id = str(second["id"])
        second_artifact_id = str(service.list_artifacts(second_job_id)["artifacts"][0]["id"])

        with self.assertRaises(ApiError):
            service.delete_artifact(first_job_id, second_artifact_id)

        self.assertEqual(service.get_training_job(first_job_id)["status"], "succeeded")
        self.assertEqual(service.get_training_job(second_job_id)["status"], "succeeded")

    def test_security_path_traversal_and_injection_ids_are_rejected(self) -> None:
        """Job and artifact ids reject path traversal and command characters."""

        service = TrainingApiService(TrainingJobStore())
        created = service.create_training_job(valid_payload("id-injection"))
        job_id = str(created["id"])
        artifact_id = str(service.list_artifacts(job_id)["artifacts"][0]["id"])

        attacks = (
            ("../private", artifact_id),
            (job_id, "../artifact"),
            (job_id, f"{artifact_id};rm-rf"),
            ("https://attacker.invalid/job", artifact_id),
        )
        for attack_job_id, attack_artifact_id in attacks:
            with self.subTest(job_id=attack_job_id, artifact_id=attack_artifact_id):
                with self.assertRaises(ApiError):
                    service.delete_artifact(attack_job_id, attack_artifact_id)
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

    def test_security_t4_dataset_shape_rejections_are_enum_only(self) -> None:
        """Unknown and forbidden dataset metadata reject without reflecting fields."""

        service = TrainingApiService(TrainingJobStore())
        unknown = service.register_dataset(
            {
                "datasetId": "security-unknown-shape",
                "rowCount": 3,
                "declaredSchema": {
                    "exampleId": "string",
                    "inputTokenCount": "integer",
                    "outputTokenCount": "integer",
                    "split": "string",
                },
                "extraField": "not-returned",
            }
        )
        forbidden = service.register_dataset(
            {
                "datasetId": "security-forbidden-shape",
                "rowCount": 3,
                "declaredSchema": {
                    "exampleId": "string",
                    "inputTokenCount": "integer",
                    "outputTokenCount": "integer",
                    "promptPayload": "string",
                    "split": "string",
                },
            }
        )

        unknown_decision = service.submit_dataset_for_review(str(unknown["datasetId"]))
        forbidden_decision = service.submit_dataset_for_review(str(forbidden["datasetId"]))
        combined = f"{unknown_decision} {forbidden_decision}"

        self.assertEqual(unknown_decision["status"], "rejected")
        self.assertEqual(unknown_decision["rejectionReasonCode"], "FORMAT_INVALID")
        self.assertEqual(forbidden_decision["status"], "rejected")
        self.assertEqual(forbidden_decision["rejectionReasonCode"], "POLICY_VIOLATION")
        self.assertNotIn("extraField", combined)
        self.assertNotIn("not-returned", combined)
        self.assertNotIn("promptPayload", combined)

    def test_security_t4_cancel_and_retry_reject_injection_shaped_ids(self) -> None:
        """Cancel and retry validate job ids before any store lookup."""

        service = TrainingApiService(TrainingJobStore(), auto_run_worker=False)
        created = service.create_training_job(valid_payload("security-t4-id"))
        cancelled = service.cancel_training_job(str(created["id"]))
        self.assertEqual(cancelled["status"], "cancelled")

        for unsafe_job_id in ("../job-id", "job_" + "a" * 24 + ";x"):
            with self.subTest(unsafe_job_id=unsafe_job_id):
                with self.assertRaises(ApiError) as cancel_error:
                    service.cancel_training_job(unsafe_job_id)
                self.assertEqual(cancel_error.exception.code, ErrorCode.VALIDATION_ERROR)
                with self.assertRaises(ApiError) as retry_error:
                    service.retry_training_job(unsafe_job_id)
                self.assertEqual(retry_error.exception.code, ErrorCode.VALIDATION_ERROR)


if __name__ == "__main__":
    unittest.main()
