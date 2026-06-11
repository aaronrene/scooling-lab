"""Shared unittest helpers for Scooling Lab tests."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def valid_payload(
    suffix: str = "alpha", retention_policy: dict[str, object] | None = None
) -> dict[str, object]:
    """Return a valid fixture createTrainingJob payload."""

    payload: dict[str, object] = {
        "idempotencyKey": f"fixture-{suffix}-0001",
        "datasetId": "fixture:synthetic-tiny-v1",
        "modelId": "fixture-tiny-llm",
        "requestedBy": "unit-test",
        "trainingParameters": {
            "epochs": 1,
            "learningRate": 0.1,
            "dryRun": True,
        },
    }
    if retention_policy is not None:
        payload["retentionPolicy"] = retention_policy
    return payload
