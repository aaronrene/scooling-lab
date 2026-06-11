# Unsloth License Evidence

## Simple Summary

Unsloth is not installed in this session. The current candidate is recorded only so legal and security
review can decide later whether the Apache-2.0 core package is acceptable.

## Candidate

- Package: `unsloth`.
- Candidate version: `2026.6.1`.
- Evidence date: 2026-06-10.
- Evidence source: PyPI page for `unsloth` and the public `unslothai/unsloth` repository license
  notice.
- Install status: not installed.
- Lockfile status: not present in `requirements.lock`.
- Import status: no `unsloth` import in Scooling Lab.

## Preserved License Notice

The public Unsloth repository license notice states:

```text
Files under unsloth/*, tests/*, scripts/* are Apache 2.0 licensed.
Files under studio/*, unsloth_cli/* which is optional to install are AGPLv3 licensed.
```

PyPI and the public repository also describe a dual-license model where the core package remains
Apache-2.0 and optional Studio UI components are AGPL-3.0.

## Approved For Later Evaluation Only

- `unsloth/*` core package paths, after an exact package-content audit.
- `tests/*` and `scripts/*` upstream paths only as license evidence, not copied runtime code.

## No-Go List

- `studio/*`.
- `unsloth_cli/*`.
- Unsloth Studio UI.
- Studio backend routes or handlers.
- Studio generated frontend bundles.
- Shell install scripts that install Studio or CLI behavior.
- CLI command wrappers such as training, inference, export, or studio launch commands.
- Any AGPL-covered file, asset, or generated artifact.

## Byte-For-Byte CI Preservation

The data-integrity test reads this document and verifies the candidate version and preserved license
notice text exactly. Any future change to this evidence must update the test in the same review.
