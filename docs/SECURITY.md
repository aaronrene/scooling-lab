# Scooling Lab Security

## Simple Summary

Scooling Lab can run Wave A fixture / `own:*` dry-run jobs on the fake worker, and
product GPU-shaped jobs (`scooling-lab-gpu-personal-v1` + `dryRun: false`) on an
isolated Lab-owned worker subprocess for **approved** `own:*` package ids only.
It cannot receive private note bodies on the wire, browser credentials, worker URLs,
shell commands, callback URLs, local file paths, or Unsloth Studio/CLI components.

## Technical Controls

- The T2 API accepts only server-validated JSON fields for training jobs.
- The schema rejects unknown fields and dangerous key terms such as `url`, `path`, `file`, `shell`,
  `command`, `callback`, `webhook`, and `worker`.
- Approved model ids:
  - `fixture-tiny-llm` (Wave A / practice)
  - `scooling-lab-gpu-personal-v1` (product GPU; `own:*` only)
- Approved dataset ids are the practice fixture `fixture:synthetic-tiny-v1` **or**
  product ids matching `^own:[A-Za-z0-9._-]{3,64}$` (after DatasetStore approval).
- Wave A product `own:*` jobs require `trainingParameters.dryRun: true`.
- Product GPU jobs require `dryRun: false` and refuse the practice fixture dataset.
- The fake worker handles Wave A only. GPU jobs spawn
  `python -m scooling_lab.gpu_worker` (process isolation; no browser-supplied worker URL).
- GPU worker provenance is content-free; private note bodies are not loaded.
- API errors return stable codes and safe messages without internal paths or request payload echoes.
- Default HTTP logging is suppressed to avoid path and payload leakage.
- Tests must not perform network egress.
- Secret scanning runs in CI with gitleaks.
- The BOM audit fails on non-allowlisted licenses and blocked AGPL source-path segments.

## Blocked Until Later Review

- Private learner data bodies on the wire or in artifacts.
- Paid GPU billing inside Lab (payer policy lives in Scooling / Hub).
- Real weight training / Unsloth package install.
- Unsloth Studio or CLI use.
- External worker endpoints supplied by clients.
- Callback or webhook delivery.
- Local filesystem paths supplied by a browser or client.
- Shell command execution.

## Review Requirement

Before any private data bodies or Unsloth weight training, the legal checklist in
`docs/LEGAL-REVIEW-CHECKLIST.md` must be completed and accepted with matching seven-tier tests.
