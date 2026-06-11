# Dependency Policy

## Simple Summary

Scooling Lab does not install training libraries until their licenses and source paths are reviewed.

The current T0/T2 package uses only the Python standard library. Unsloth is recorded as candidate
evidence only and is not installed, imported, or locked.

## Technical Policy

- Allowed licenses for Scooling Lab dependencies are `Apache-2.0`, `MIT`, `BSD-2-Clause`,
  `BSD-3-Clause`, `ISC`, and `PSF-2.0`.
- AGPL and GPL-family licenses are blocked unless a later legal review explicitly changes the
  repository distribution model.
- Source paths named `studio/` and `unsloth_cli/` are blocked because Unsloth's public license notice
  identifies those optional paths as AGPL-3.0.
- Every dependency must appear in `requirements.lock` with version, license, source path, and evidence
  metadata before it can enter runtime use.
- `DEPENDENCIES.md` is generated from the BOM tool and must stay committed.

## Current State

- Runtime dependencies: none.
- Lockfile: `requirements.lock`, comment-only until the first real runtime dependency lands.
- BOM command: `PYTHONPATH=src python -m scooling_lab.bom --check --output DEPENDENCIES.md`.
- Unsloth status: pinned candidate evidence only; no package install and no import path.

## No-Go List

- No private Scooling code.
- No Knowtation vault data.
- No secrets, API keys, or local environment files.
- No model artifacts, weights, or training outputs.
- No copied Unsloth Studio UI, generated bundles, routes, handlers, or assets.
- No `unsloth_cli/` code, commands, wrappers, or shell install scripts.
- No browser-supplied worker URL, callback URL, shell command, file path, or model path accepted by
  the API contract.
