# Cross-Repo Status

## Simple Summary

Scooling Lab owns the training API and worker runtime. Scooling, Knowtation, Muse Hub, and YouTube
vault content connect through **queued finish phases** in `docs/ROADMAP.md` — nothing parked.

**Status:** contract built (T0–T3); **not operational** until T9 (real train + packs + all surfaces).

## Technical Status

| Component | Repo | Status |
| --- | --- | --- |
| Training API + state machine | scooling-lab | DONE (T2/T3) |
| GPU worker subprocess | scooling-lab | **STUB** — placeholder provenance (GPU-S0) |
| Real Unsloth training | scooling-lab | **NEXT** (T4) |
| Vault package ingest | scooling-lab | **DONE** (T5); Scooling export → T7 |
| Artifact storage + download | scooling-lab | **DONE** (T6) |
| Pack credit measure/debit | scooling + Muse Hub | QUEUED (T-CREDIT) |
| Scooling train UI + export | scooling | QUEUED (T7) |
| Knowtation train path | knowtation + scooling | QUEUED (T-KNOW) |
| YouTube vault in training scope | scooling | QUEUED (T-YT) |
| GPU deploy lane | scooling-lab infra | QUEUED (T8) |
| Consent + policy | scooling | QUEUED (T-POLICY) |
| Legal closure | scooling-lab | QUEUED (T-LEGAL) — tracker: `LEGAL-CLOSURE.md` |
| E2E finish verification | all | QUEUED (T9) |

## Boundary Rules (unchanged)

- No private Scooling application code copied into scooling-lab.
- No Knowtation vault bodies committed to scooling-lab.
- No billing **internals** in scooling-lab — pack integration via server API (T-CREDIT).
- No model weights in git.
- No AGPL Unsloth Studio or CLI.

## Finish-Line Target

One user flow works end-to-end on **each surface**:

1. **Scooling** — pick vault scope → see pack credit quote → consent → train → model in chat.
2. **Knowtation** — same flow on Knowtation vault (`own:know:*` ids).
3. **YouTube** — include or exclude YouTube-ingested vault items in scope.

See `docs/ROADMAP.md` build queue and STUB inventory for the complete plan.
