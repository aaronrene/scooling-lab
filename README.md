# Scooling Lab

Scooling Lab is the open-source training workspace for Scooling.

It provides the public, inspectable boundary for turning reviewed learning material into private
custom model jobs. The main Scooling app remains the product, consent, billing, permission,
Knowtation, and artifact-registration authority. Scooling Lab owns only the training API, worker
contract, worker runtime, fixtures, tests, dependency inventory, and license notices.

## Current Phase

**NEXT:** nothing builds in this repo right now — T7b's fix round happens in `~/scooling`. Next Lab
phase is **T8** (GPU deploy + real train). See
[`docs/SCOOLING-LAB-ROADMAP.md`](docs/SCOOLING-LAB-ROADMAP.md).

T0–T6 are built (161 tests: 160 run + 1 `@gpu` skip without CUDA). Real GPU train mode is a **stub**
until T8, and T6 production durability is still open. Finish-line plan includes Muse Hub pack credits
(T-CREDIT), legal closure (T-LEGAL), and Scooling / Knowtation / YouTube integration — no deferred
phases.

Session relay: [`docs/SCOOLING-LAB-OVERSEER-HANDOVER.md`](docs/SCOOLING-LAB-OVERSEER-HANDOVER.md)
(Scooling Lab Overseer handover — this repo only; the Scooling app has its own). Cross-repo status:
[`docs/CROSS-REPO-STATUS.md`](docs/CROSS-REPO-STATUS.md).

## Overseer Kit

Governance via [Overseer Kit](https://github.com/aaronrene/overseer-kit) (`ok` CLI), installed here
2026-08-27 (v0.1.0). Config: `.overseer/config.yaml`.

```bash
~/OVERSEER_KIT/overseer-kit/cli/ok -C ~/scooling-lab status
~/OVERSEER_KIT/overseer-kit/cli/ok -C ~/scooling-lab next
```

## Boundary Rules

- No private Scooling application code.
- No Knowtation private vault data.
- No billing internals.
- No browser session tokens.
- No AGPL-covered Studio or CLI code.
- No secrets, API keys, local credentials, private datasets, or model artifacts.

## Local Checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## License

Apache-2.0. See `LICENSE` and `NOTICE`.
