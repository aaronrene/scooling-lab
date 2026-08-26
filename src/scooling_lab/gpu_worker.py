"""Isolated Lab-owned GPU worker for product GPU train jobs.

Process isolation: the API service never runs GPU job completion in-process.
It spawns ``python -m scooling_lab.gpu_worker`` with a content-free JSON envelope
on stdin and reads a content-free result on stdout. Worker addresses never appear
on the HTTP wire.

T4b: real Unsloth QLoRA (``SCOOLING_LAB_GPU_TRAIN_MODE=real`` on CUDA hosts) or
stub train (default CI) that writes loadable adapter layout + tarball without
importing torch at module load time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Mapping

import scooling_lab
from scooling_lab.contracts import (
    GPU_PRODUCT_MODEL_ID,
    is_own_data_dataset_id,
)
from scooling_lab.errors import ApiError, ErrorCode
from scooling_lab.license_policy import BLOCKED_PATH_SEGMENTS, validate_source_path

T4_BASE_HF_MODEL_ID = "unsloth/Llama-3.2-3B-Instruct"
DEFAULT_GPU_TIMEOUT_SECONDS = 3600
DEFAULT_EPOCHS = 1
DEFAULT_LEARNING_RATE = 2e-4
MIN_LEARNING_RATE = 1e-5
MAX_LEARNING_RATE = 5e-4
MIN_EPOCHS = 1
MAX_EPOCHS = 3

_PACKAGE_ROOT_ENV = "SCOOLING_LAB_PACKAGE_ROOT"
_ARTIFACT_ROOT_ENV = "SCOOLING_LAB_ARTIFACT_ROOT"
_TRAIN_MODE_ENV = "SCOOLING_LAB_GPU_TRAIN_MODE"
_TIMEOUT_ENV = "SCOOLING_LAB_GPU_TIMEOUT_SECONDS"

_logger = logging.getLogger("scooling_lab.gpu_worker")


def gpu_worker_timeout_seconds() -> int:
    """Return API-side subprocess timeout (env-only; not from HTTP JSON)."""

    raw = os.environ.get(_TIMEOUT_ENV, str(DEFAULT_GPU_TIMEOUT_SECONDS))
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_GPU_TIMEOUT_SECONDS
    return max(30, value)


def package_root() -> Path:
    """Resolve the operator-controlled package root from env."""

    raw = os.environ.get(_PACKAGE_ROOT_ENV, "").strip()
    if not raw:
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
    return Path(raw)


def artifact_root() -> Path:
    """Resolve the operator-controlled artifact root from env."""

    raw = os.environ.get(_ARTIFACT_ROOT_ENV, "").strip()
    if not raw:
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
    return Path(raw)


def gpu_train_mode() -> str:
    """Return ``stub`` (CI default) or ``real`` (CUDA host with training stack)."""

    return os.environ.get(_TRAIN_MODE_ENV, "stub").strip().lower()


def package_dataset_hash(dataset_id: str) -> str:
    """Return a content-free hash of an approved ``own:*`` package id.

    Private note bodies never enter this hash — only the package identifier.
    T5 replaces this with SHA-256 of canonical ``train.jsonl`` bytes.
    """

    if not is_own_data_dataset_id(dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    payload = f"scooling-lab-gpu-package:{dataset_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gpu_training_config_hash(
    model_id: str,
    retention_policy: Mapping[str, object],
    training_parameters: Mapping[str, int | float | bool],
) -> str:
    """Content-free training-config hash for GPU provenance."""

    payload = json.dumps(
        {
            "modelId": model_id,
            "retentionPolicy": dict(sorted(retention_policy.items())),
            "trainingParameters": dict(sorted(training_parameters.items())),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clamp_training_parameters(
    training_parameters: Mapping[str, int | float | bool],
) -> dict[str, int | float | bool]:
    """Clamp epochs and learning rate to T4 bounds."""

    epochs_raw = training_parameters.get("epochs", DEFAULT_EPOCHS)
    if not isinstance(epochs_raw, int) or isinstance(epochs_raw, bool):
        epochs_raw = DEFAULT_EPOCHS
    epochs = max(MIN_EPOCHS, min(MAX_EPOCHS, int(epochs_raw)))

    lr_raw = training_parameters.get("learningRate", DEFAULT_LEARNING_RATE)
    if not isinstance(lr_raw, (int, float)) or isinstance(lr_raw, bool):
        lr_raw = DEFAULT_LEARNING_RATE
    learning_rate = max(MIN_LEARNING_RATE, min(MAX_LEARNING_RATE, float(lr_raw)))

    return {"dryRun": False, "epochs": epochs, "learningRate": learning_rate}


def resolve_package_dir(dataset_id: str) -> Path:
    """Map dataset id to package directory under env package root."""

    if not is_own_data_dataset_id(dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    return package_root() / dataset_id


def load_train_jsonl(dataset_id: str) -> list[dict[str, object]]:
    """Load canonical training JSONL; fail closed when missing or empty."""

    train_path = resolve_package_dir(dataset_id) / "train.jsonl"
    if not train_path.is_file():
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
    rows: list[dict[str, object]] = []
    for line_number, raw_line in enumerate(
        train_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500) from None
        if not isinstance(parsed, dict):
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        rows.append(parsed)
    if not rows:
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
    return rows


def hash_file_bytes(path: Path) -> str:
    """Return SHA-256 hex digest of a file's bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stub_adapter_config() -> dict[str, object]:
    """Minimal PEFT adapter metadata for stub train mode."""

    return {
        "base_model_name_or_path": T4_BASE_HF_MODEL_ID,
        "peft_type": "LORA",
        "r": 8,
        "target_modules": ["q_proj", "v_proj"],
        "lora_alpha": 16,
        "lora_dropout": 0.0,
    }


def _write_stub_adapter(adapter_dir: Path) -> None:
    """Write a minimal loadable adapter layout without torch."""

    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "adapter_config.json").write_text(
        json.dumps(_stub_adapter_config(), indent=2),
        encoding="utf-8",
    )
    # Minimal safetensors header placeholder — not weights; stub mode only.
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"\x00" * 64)


def _run_real_unsloth_train(
    *,
    rows: list[dict[str, object]],
    adapter_dir: Path,
    epochs: int,
    learning_rate: float,
) -> None:
    """Run Unsloth QLoRA; imports deferred so API process stays stdlib-only."""

    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("UNSLOTH_DISABLE_STATISTICS", "1")

    from datasets import Dataset  # noqa: PLC0415
    from trl import SFTTrainer, SFTConfig  # noqa: PLC0415
    from unsloth import FastLanguageModel  # noqa: PLC0415

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=T4_BASE_HF_MODEL_ID,
        max_seq_length=512,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=8,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_alpha=16,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    def _format_example(row: dict[str, object]) -> dict[str, str]:
        instruction = str(row.get("instruction", row.get("text", "")))
        input_text = str(row.get("input", ""))
        output = str(row.get("output", row.get("response", "")))
        if input_text:
            prompt = f"### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n{output}"
        else:
            prompt = f"### Instruction:\n{instruction}\n\n### Response:\n{output}"
        return {"text": prompt}

    dataset = Dataset.from_list([_format_example(row) for row in rows])
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            warmup_steps=0,
            num_train_epochs=epochs,
            learning_rate=learning_rate,
            logging_steps=1,
            output_dir=str(adapter_dir.parent / "checkpoints"),
            logging_dir=None,
            report_to=[],
            max_steps=-1,
            dataset_text_field="text",
            max_seq_length=512,
        ),
    )
    trainer.train()
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))


def run_training(
    *,
    job_id: str,
    dataset_id: str,
    model_id: str,
    training_parameters: Mapping[str, int | float | bool],
    retention_policy: Mapping[str, object],
) -> dict[str, str]:
    """Execute train, write artifact bundle, return provenance fields."""

    started = time.perf_counter()
    _logger.info(
        "gpu_worker phase=start job_id=%s dataset_id=%s mode=%s",
        job_id,
        dataset_id,
        gpu_train_mode(),
    )

    params = clamp_training_parameters(training_parameters)
    rows = load_train_jsonl(dataset_id)
    root = artifact_root()
    root.mkdir(parents=True, exist_ok=True)
    tmp_dir = root / f"{job_id}.tmp"
    final_dir = root / job_id
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    if final_dir.exists():
        shutil.rmtree(final_dir)
    tmp_dir.mkdir(parents=True)

    adapter_dir = tmp_dir / "adapter"
    mode = gpu_train_mode()
    if mode == "real":
        _run_real_unsloth_train(
            rows=rows,
            adapter_dir=adapter_dir,
            epochs=int(params["epochs"]),
            learning_rate=float(params["learningRate"]),
        )
    elif mode == "stub":
        _write_stub_adapter(adapter_dir)
    else:
        raise ApiError(ErrorCode.INTERNAL_ERROR, 500)

    manifest = {
        "jobId": job_id,
        "datasetId": dataset_id,
        "modelId": model_id,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "trainMode": mode,
        "rowCount": len(rows),
    }
    (tmp_dir / "manifest.json").write_text(
        json.dumps(manifest, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )

    tarball_path = tmp_dir / "artifact.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as archive:
        archive.add(adapter_dir, arcname="adapter")
        archive.add(tmp_dir / "manifest.json", arcname="manifest.json")

    artifact_hash = hash_file_bytes(tarball_path)
    tmp_dir.rename(final_dir)

    dataset_hash = package_dataset_hash(dataset_id)
    config_hash = gpu_training_config_hash(model_id, retention_policy, params)
    elapsed = time.perf_counter() - started
    _logger.info(
        "gpu_worker phase=complete job_id=%s dataset_id=%s seconds=%.3f exit_code=0",
        job_id,
        dataset_id,
        elapsed,
    )
    return {
        "artifactHash": artifact_hash,
        "baseModelId": GPU_PRODUCT_MODEL_ID,
        "datasetHash": dataset_hash,
        "jobId": job_id,
        "trainingConfigHash": config_hash,
    }


def audit_installed_unsloth_paths() -> list[str]:
    """Return installed unsloth paths that violate AGPL segment policy."""

    try:
        import unsloth  # noqa: PLC0415
    except ImportError:
        return []

    package_dir = Path(unsloth.__file__).resolve().parent
    violations: list[str] = []
    for path in package_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(package_dir).as_posix()
        segments = set(relative.split("/"))
        if segments.intersection(BLOCKED_PATH_SEGMENTS):
            violations.append(relative)
        else:
            try:
                validate_source_path(relative)
            except Exception:
                violations.append(relative)
    return sorted(violations)


def execute_gpu_worker_envelope(envelope: Mapping[str, object]) -> dict[str, str]:
    """Validate a worker envelope and return content-free completion fields."""

    job_id = envelope.get("jobId")
    model_id = envelope.get("modelId")
    dataset_id = envelope.get("datasetId")
    training_parameters = envelope.get("trainingParameters")
    retention_policy = envelope.get("retentionPolicy")
    if not isinstance(job_id, str) or not isinstance(model_id, str):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if not isinstance(dataset_id, str) or not is_own_data_dataset_id(dataset_id):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if model_id != GPU_PRODUCT_MODEL_ID:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if not isinstance(training_parameters, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if training_parameters.get("dryRun") is not False:
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
    if not isinstance(retention_policy, Mapping):
        raise ApiError(ErrorCode.VALIDATION_ERROR, 400)

    params: dict[str, int | float | bool] = {}
    for key, value in training_parameters.items():
        if not isinstance(key, str) or not isinstance(value, (int, float, bool)):
            raise ApiError(ErrorCode.VALIDATION_ERROR, 400)
        params[key] = value
    retention: dict[str, object] = {
        str(key): value for key, value in retention_policy.items()
    }

    return run_training(
        job_id=job_id,
        dataset_id=dataset_id,
        model_id=model_id,
        training_parameters=params,
        retention_policy=retention,
    )


class IsolatedGpuWorker:
    """API-side driver that completes GPU jobs via an isolated subprocess."""

    def __init__(self, store) -> None:
        """Bind the worker driver to a server-owned job store."""

        self._store = store

    def run_job(self, job_id: str):
        """Move a queued GPU job through running to succeeded via subprocess."""

        from scooling_lab.contracts import TrainingJobStatus  # noqa: PLC0415
        from scooling_lab.provenance import (  # noqa: PLC0415
            ProvenanceRecord,
            validate_provenance_record,
        )
        from scooling_lab.store import ArtifactMetadata, utc_now_iso  # noqa: PLC0415

        job = self._store.get(job_id)
        if job.status in {
            TrainingJobStatus.SUCCEEDED,
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
            TrainingJobStatus.DELETED,
        }:
            return job
        self._store.update_status(job_id, TrainingJobStatus.RUNNING)
        running_job = self._store.get(job_id)
        if running_job.request is None:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        if running_job.request.model_id != GPU_PRODUCT_MODEL_ID:
            return self._store.update_status(job_id, TrainingJobStatus.FAILED)
        if running_job.request.training_parameters.get("dryRun") is not False:
            return self._store.update_status(job_id, TrainingJobStatus.FAILED)

        envelope = {
            "datasetId": running_job.request.dataset_id,
            "jobId": job_id,
            "modelId": running_job.request.model_id,
            "retentionPolicy": running_job.request.retention_policy.to_public_dict(),
            "trainingParameters": dict(running_job.request.training_parameters),
        }
        try:
            result = self._invoke_isolated_process(envelope)
        except (ApiError, OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError):
            return self._store.update_status(job_id, TrainingJobStatus.FAILED)

        created_at = utc_now_iso()
        artifact_hash = result["artifactHash"]
        artifact_id = f"artifact_{artifact_hash[:24]}"
        provenance = ProvenanceRecord(
            artifact_hash=artifact_hash,
            base_model_id=result["baseModelId"],
            created_at=created_at,
            dataset_hash=result["datasetHash"],
            job_id=job_id,
            training_config_hash=result["trainingConfigHash"],
        )
        try:
            validate_provenance_record(provenance)
        except ApiError:
            return self._store.update_status(job_id, TrainingJobStatus.FAILED)
        self._store.register_artifact(
            job_id,
            ArtifactMetadata(
                id=artifact_id,
                job_id=job_id,
                dataset_hash=result["datasetHash"],
                artifact_hash=artifact_hash,
                created_at=created_at,
                provenance_id=f"provenance_{job_id}",
                retention_policy=running_job.request.retention_policy,
            ),
            provenance,
        )
        return self._store.update_status(job_id, TrainingJobStatus.SUCCEEDED)

    def _invoke_isolated_process(self, envelope: dict[str, object]) -> dict[str, str]:
        """Spawn the GPU worker module in a separate process; no in-process fallback."""

        env = os.environ.copy()
        for key in list(env):
            lowered = key.lower()
            if any(term in lowered for term in ("callback", "webhook", "worker_url", "proxy")):
                env.pop(key, None)
        src_root = str(Path(scooling_lab.__file__).resolve().parent.parent)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            src_root if not existing else f"{src_root}{os.pathsep}{existing}"
        )
        if _TRAIN_MODE_ENV not in env:
            env[_TRAIN_MODE_ENV] = "stub"

        completed = subprocess.run(
            [sys.executable, "-m", "scooling_lab.gpu_worker"],
            input=json.dumps(envelope, separators=(",", ":"), sort_keys=True),
            capture_output=True,
            text=True,
            timeout=gpu_worker_timeout_seconds(),
            check=False,
            env=env,
            cwd=None,
        )
        if completed.returncode != 0:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict):
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        required = {
            "artifactHash",
            "baseModelId",
            "datasetHash",
            "jobId",
            "trainingConfigHash",
        }
        if set(payload) != required:
            raise ApiError(ErrorCode.INTERNAL_ERROR, 500)
        return {key: str(payload[key]) for key in required}


def main() -> int:
    """Subprocess entrypoint: read envelope on stdin, write result on stdout."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    for noisy in ("transformers", "datasets", "urllib3", "httpx", "unsloth"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    envelope: Mapping[str, object] | None = None
    try:
        raw = sys.stdin.read()
        envelope = json.loads(raw)
        if not isinstance(envelope, Mapping):
            return 1
        result = execute_gpu_worker_envelope(envelope)
        sys.stdout.write(json.dumps(result, separators=(",", ":"), sort_keys=True))
        sys.stdout.write("\n")
        return 0
    except (ApiError, json.JSONDecodeError, TypeError, ValueError):
        job_id = "unknown"
        dataset_id = "unknown"
        if isinstance(envelope, Mapping):
            if isinstance(envelope.get("jobId"), str):
                job_id = envelope["jobId"]
            if isinstance(envelope.get("datasetId"), str):
                dataset_id = envelope["datasetId"]
        _logger.info(
            "gpu_worker phase=failed job_id=%s dataset_id=%s exit_code=1",
            job_id,
            dataset_id,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
