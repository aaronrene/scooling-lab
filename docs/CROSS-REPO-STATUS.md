# Cross-Repo Status

## Simple Summary

The Scooling Lab T0/T2 training contract lives in this `scooling-lab` repository. It does not touch
main Scooling runtime flows, private code, Knowtation vault data, MuseHub internals, or model
artifacts.

## Technical Status

- Main Scooling app runtime: unchanged by the T0/T2 Scooling Lab package.
- Scooling Lab package: `src/scooling_lab`.
- Synthetic fixture data: `src/scooling_lab/fixtures/synthetic_training_dataset.jsonl`.
- Training API surface: local HTTP contract only.
- Worker surface: in-process fake worker only.
- Dependency status: no runtime dependencies beyond the Python standard library.
- Unsloth status: evidence-only pinned candidate; no install, no imports, no package lock row.
- GitHub target: feature branch `feat/t0-dependency-inventory` to `main` PR.
- Muse target: staging push for the same feature branch after local and GitHub CI verification.

## Untouched Boundaries

- No private Scooling app code is copied into Scooling Lab.
- No Knowtation vault content is read or committed.
- No billing internals are added.
- No model weights or generated artifacts are committed.
- No AGPL Unsloth Studio or CLI code is copied, imported, bundled, or exposed.

## Incident Record: T0/T2 Relocation (2026-06)

- **What happened:** The Scooling Lab T0/T2 training contract (Apache-2.0 `LICENSE`,
  `pyproject.toml`, `requirements.lock`, `src/scooling_lab/`, the seven-tier Python test suite, and
  CI workflows) was initially committed into the proprietary `scooling` repository and merged there as
  pull request #25, bypassing the `muse-mirror` review flow.
- **Where the work now lives:** This `scooling-lab` repository on `main`. The relocated files are the
  authoritative T0/T2 deliverable; the earlier bootstrap stub versions of `contracts.py` and
  `license_policy.py` were superseded by the fuller implementations.
- **Remediation in `scooling`:** Pull request #25 was reverted with a normal GitHub pull request so the
  `scooling` `main` tree matches the Muse `main` tree. No history was rewritten and no force pushes
  were used. The `scooling` repository is private, so the Apache `LICENSE` was never publicly
  distributed — this was boundary cleanup, not a license revocation.
- **Boundary confirmation:** Only the files that the original mistaken commit added or modified for the
  Lab were transferred. No private Scooling application code, Knowtation vault data, billing internals,
  secrets, model artifacts, or AGPL Studio/CLI paths were copied.
