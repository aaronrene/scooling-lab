# Scooling Lab Security

## Simple Summary

Scooling Lab can run only synthetic fixture jobs in this phase. It cannot receive private learner data,
browser credentials, worker URLs, shell commands, callback URLs, local file paths, model artifacts, or
GPU billing instructions.

## Technical Controls

- The T2 API accepts only server-validated JSON fields for fixture jobs.
- The schema rejects unknown fields and dangerous key terms such as `url`, `path`, `file`, `shell`,
  `command`, `callback`, `webhook`, and `worker`.
- The only approved model id is `fixture-tiny-llm`.
- The only approved dataset id is `fixture:synthetic-tiny-v1`.
- The fake worker reads only the committed synthetic fixture dataset.
- API errors return stable codes and safe messages without internal paths or request payload echoes.
- Default HTTP logging is suppressed to avoid path and payload leakage.
- Tests must not perform network egress.
- Secret scanning runs in CI with gitleaks.
- The BOM audit fails on non-allowlisted licenses and blocked AGPL source-path segments.

## Blocked Until Later Review

- Private learner data.
- Paid GPU work.
- Real model training.
- Unsloth installation.
- Unsloth Studio or CLI use.
- External worker endpoints.
- Callback or webhook delivery.
- Local filesystem paths supplied by a browser or client.
- Shell command execution.

## Review Requirement

Before any private data or paid GPU work, the legal checklist in
`docs/LEGAL-REVIEW-CHECKLIST.md` must be completed and accepted with matching seven-tier tests.
