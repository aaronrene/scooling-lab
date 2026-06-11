"""Scooling Lab training API contract and fake worker.

The package intentionally uses only the Python standard library during the
T0/T2 phases. Real training libraries, GPU work, private data, and model
artifacts remain blocked until later legal and security gates are accepted.
"""

from scooling_lab.contracts import TrainingJobRequest, TrainingJobStatus

__all__ = ["TrainingJobRequest", "TrainingJobStatus"]
