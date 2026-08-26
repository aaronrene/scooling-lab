# Legal Closure Tracker

Track completion of every row in `LEGAL-REVIEW-CHECKLIST.md`. Update this file during **T-LEGAL**;
do not mark a row complete without evidence (PR link, test name, or doc section).

| ID | Checklist item | Status | Evidence | Closed |
| --- | --- | --- | --- | --- |
| L1 | Repository license and distribution model | OPEN | `LICENSE`, `NOTICE`, README | — |
| L2 | Every runtime dependency in `DEPENDENCIES.md` | DONE | `requirements.lock`, `DEPENDENCIES.md`, `bom --check` | 2026-08-26 |
| L3 | Every runtime license allowlisted or approved | DONE | BOM rows for torch/transformers/unsloth/peft/trl/accelerate/bitsandbytes | 2026-08-26 |
| L4 | No AGPL Studio/CLI imported or bundled | OPEN | `license_policy.py`, CI security tests | — |
| L5 | Base model license (HF terms) | DONE | `NOTICE` HF model row; operator HF acceptance | 2026-08-26 |
| L6 | Unsloth core wheel path audit (no AGPL segments) | DONE | `gpu_worker.audit_installed_unsloth_paths`, security test | 2026-08-26 |
| L7 | Dataset consent, scope, retention, export, deletion | OPEN | T-POLICY UI + server gate | — |
| L8 | API rejects browser paths, URLs, shell, callbacks | DONE | `contracts.py`, security tests | 2026-06 |
| L9 | Logs exclude prompts, notes, secrets, paths | DONE | `test_security_worker_logs_exclude_jsonl_and_secrets` | 2026-08-26 |
| L10 | Artifact retention and deletion tested | DONE | T2/T3 tests, retention module | 2026-06 |
| L11 | Payer-visible cost policy and spending caps | OPEN | T-CREDIT quote + receipt UI | — |
| L12 | Quota and replay controls | PARTIAL | Job idempotency done; pack quota T-CREDIT | — |
| L13 | Cancellation and cleanup before/at start | DONE | cancel/retry API + tests | 2026-06 |
| L14 | GPU credentials env-scoped | OPEN | T8 deploy doc | — |
| L15 | Network egress allowlisted | OPEN | T8 network policy | — |
| L16 | Private data excluded from fixtures/logs/telemetry | DONE | T5 server-auth ingest + `test_t5_package_ingest` security tier | 2026-08-26 |
| L17 | Artifact provenance, retention, deletion, export | PARTIAL | Provenance API done; export T6 | — |
| L18 | Exact package versions and deployment lane approved | OPEN | T4 lockfile + T8 deploy record | — |
| L19 | Incident response ownership | OPEN | Operator runbook in `SECURITY.md` | — |

**T-LEGAL Definition of Done:** every row `DONE` with evidence and date; CI green.
