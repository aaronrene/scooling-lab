# Scooling Lab

Scooling Lab is the open-source training workspace for Scooling.

It provides the public, inspectable boundary for turning reviewed learning material into private
custom model jobs. The main Scooling app remains the product, consent, billing, permission,
Knowtation, and artifact-registration authority. Scooling Lab owns only the training API, worker
contract, worker runtime, fixtures, tests, dependency inventory, and license notices.

## Current Phase

Phase T0: license and dependency inventory.

This repository starts with no trainer implementation and no private data path. The first goal is to
prove that the worker boundary, dependency policy, and license evidence can be audited before any
training job runs.

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
