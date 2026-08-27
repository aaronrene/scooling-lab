# Scooling Lab

Scooling Lab is the open-source training workspace for Scooling.

It provides the public, inspectable boundary for turning reviewed learning material into private
custom model jobs. The main Scooling app remains the product, consent, billing, permission,
Knowtation, and artifact-registration authority. Scooling Lab owns only the training API, worker
contract, worker runtime, fixtures, tests, dependency inventory, and license notices.

## Current Phase

**NEXT:** T4 — real Unsloth trainer runtime (see [`docs/ROADMAP.md`](docs/ROADMAP.md)).

T0–T3 contract work is done (127 tests). GPU worker is a **stub** until T4. Finish-line plan includes
Muse Hub pack credits (T-CREDIT), legal closure (T-LEGAL), and Scooling / Knowtation / YouTube
integration — no deferred phases.

Session relay: [`docs/OVERSEER-HANDOVER.md`](docs/OVERSEER-HANDOVER.md) (Overseer handover). Cross-repo status:
[`docs/CROSS-REPO-STATUS.md`](docs/CROSS-REPO-STATUS.md).

## Overseer Kit

Governance via [Overseer Kit](https://github.com/aaronrene/overseer-kit) (`ok` CLI). Config:
`.overseer/config.yaml`.

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
