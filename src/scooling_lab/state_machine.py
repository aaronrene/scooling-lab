"""Deterministic T2 training job state machine."""

from __future__ import annotations

from types import MappingProxyType

from scooling_lab.contracts import TrainingJobStatus
from scooling_lab.errors import ApiError, ErrorCode


TRANSITION_TABLE: MappingProxyType[TrainingJobStatus, frozenset[TrainingJobStatus]] = (
    MappingProxyType(
        {
            TrainingJobStatus.QUEUED: frozenset(
                {
                    TrainingJobStatus.RUNNING,
                    TrainingJobStatus.FAILED,
                    TrainingJobStatus.CANCELLED,
                }
            ),
            TrainingJobStatus.RUNNING: frozenset(
                {
                    TrainingJobStatus.SUCCEEDED,
                    TrainingJobStatus.FAILED,
                    TrainingJobStatus.CANCELLED,
                }
            ),
            TrainingJobStatus.SUCCEEDED: frozenset({TrainingJobStatus.DELETED}),
            TrainingJobStatus.DELETED: frozenset(),
            TrainingJobStatus.FAILED: frozenset(),
            TrainingJobStatus.CANCELLED: frozenset(),
        }
    )
)


def transition(
    current: TrainingJobStatus, target: TrainingJobStatus
) -> TrainingJobStatus:
    """Return the next state or raise for invalid non-idempotent transitions."""

    if current == target:
        return current
    if target in TRANSITION_TABLE[current]:
        return target
    raise ApiError(ErrorCode.INVALID_TRANSITION, 409)


def cancel(current: TrainingJobStatus) -> TrainingJobStatus:
    """Cancel a queued or running job; terminal replay is idempotent."""

    if current == TrainingJobStatus.CANCELLED:
        return current
    return transition(current, TrainingJobStatus.CANCELLED)
