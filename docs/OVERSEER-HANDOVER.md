# Scooling Lab Overseer Handover

**Living relay for Scooling Lab.** Paste the **NEXT SESSION** block into a fresh chat.

**Regime:** muse+git-mirror (`.overseer/config.yaml` live)  
**Constellation:** `scooling-stack` (product order: `~/scooling`)  
**Product surfaces:** Scooling, Knowtation, YouTube train paths queue after T6 in this repo.

---

<!-- overseer:next role=primary lane=product status=live -->
## NEXT SESSION — T-CREDIT Pack Credits (PRIMARY)

**Date:** 2026-08-26  
**Current position:** T6 Auto **DONE** — BV **`pass`**; 161 tests green  
**Model:** Auto

### Operator decision (2026-08-26)

CUDA `@gpu` live test and Railway GPU wiring remain deferred to **T8/T9** — not blocking T-CREDIT.

### What just landed (T6)

| Slice | Deliverable |
| --- | --- |
| T6 | `SCOOLING_LAB_STATE_PATH` required in production |
| T6 | Volume / S3 / R2 artifact upload after GPU train |
| T6 | `GET .../artifacts/{id}/download` — server JWT → signed URL |
| T6 | Retention sweep deletes object storage + metadata |
| T6 | Seven-tier `test_t6_artifact_storage.py`; BV **`pass`** |

### THE ONE NEXT STEP — **Model: Auto**

| | |
| --- | --- |
| **ID** | **T-CREDIT** |
| **Branch** | `feat/t-credit-pack-reserve` (from `main` after T6 merge) |
| **Repo** | **scooling** + Muse Hub (cross-repo) |
| **Read first** | `docs/ROADMAP.md` T-CREDIT; `~/scooling/docs/OVERSEER-HANDOVER.md` |

### Paste-ready prompt — T-CREDIT

```
Phase T-CREDIT — Muse Hub pack credit measure, reserve, debit, refund (scooling + Hub).

Model: Auto
Repo: ~/scooling (primary); scooling-lab accepts reservation envelope later
Branch: feat/t-credit-pack-reserve
Step: T-CREDIT
Authority: docs/ROADMAP.md T-CREDIT

Deliverables:
1. Training pack SKU + credit unit definition
2. Pre-flight estimate API (dataset rows + model + epochs → quote)
3. Reserve on createTrainingJob (idempotent with job idempotency key)
4. Capture debit on succeeded; release on failed/cancelled
5. Insufficient balance → refuse before GPU starts
6. Audit row (content-free): job id, pack id, credits reserved/captured
7. Seven-tier tests; governance sync
```

---

### Paste-ready prompt (archived — T6 Auto)

```
Phase T6 — Artifact object storage + durable job store (scooling-lab).

Model: Auto
Status: DONE — BV pass (2026-08-26); 161 tests green; @gpu skip without CUDA.
Evidence: docs/reviews/2026-08-26-t6-artifact-storage-bv-pass.md
```

---

## Build order (confirmed — no skips)

| Order | Phase | Repo |
| --- | --- | --- |
| 1 | T4 Real trainer | scooling-lab — **DONE** |
| 2 | T5 Vault package ingest | scooling-lab — **DONE** |
| 3 | T6 Artifacts + durable state | scooling-lab — **DONE** |
| 4 | T-CREDIT Pack measure / reserve / debit | scooling + Muse Hub |
| 5 | T7 Scooling train UI + backend | scooling |
| 6 | T-KNOW Knowtation train path | knowtation + scooling-lab |
| 7 | T-YT YouTube vault scope in export | scooling |
| 8 | T8 GPU deploy lane | scooling-lab infra |
| 9 | T-POLICY Consent + scope + auth envelope | scooling |
| 10 | T-LEGAL Close LEGAL-CLOSURE.md | scooling-lab + scooling |
| 11 | T9 E2E all surfaces; stub inventory zero | all |

---

## Verified snapshot (2026-08-26)

| Item | Value |
| --- | --- |
| Repo | `scooling-lab` |
| Branch | `feat/t6-artifact-storage` |
| Overseer Kit | **live** — `initialized: true`, `kit_version: 0.1.0`, `footprint_self_integrity: ok` |
| Handover | `docs/OVERSEER-HANDOVER.md` |
| Roadmap | `docs/ROADMAP.md` |
| T6 BV | **`pass`** — `docs/reviews/2026-08-26-t6-artifact-storage-bv-pass.md` |
| Tests | 161 passed, 1 skipped (`@gpu` — no CUDA in CI) |
| Artifact storage | Volume/S3/R2 upload; signed download; durable `SCOOLING_LAB_STATE_PATH` |
| Pack credits | Muse Hub packs exist; **T-CREDIT not wired** |
| Legal | L2, L3, L5, L6, L9, L16, L17 **DONE**; others open per `LEGAL-CLOSURE.md` |
| Products | Scooling / Knowtation / YouTube train paths **not wired** (T7+) |

### Governance gates checklist

- [x] **Overseer Kit installed** — 2026-08-26
- [x] **T4a freeze** — `docs/T4-TRAINER-SPEC.md` + `ok check-ok` **`pass`**
- [x] **T4b build** — `/build-verification-review` **`pass`** (2026-08-26)
- [x] **T5 build** — `/build-verification-review` **`pass`** (2026-08-26)
- [x] **T6 build** — `/build-verification-review` **`pass`** (2026-08-26)
- [ ] **CUDA `@gpu`** — deferred to T8/T9 (operator 2026-08-26)

---

## Finish-line checklist (master)

- [x] **T4** Real Unsloth train → adapter files (build); CUDA verify before production
- [x] **T5** Vault package ingest + content hash (Lab); Scooling export → T7
- [x] **T6** Durable state + object storage + download
- [ ] **T-CREDIT** Muse Hub pack measure / reserve / debit / refund
- [ ] **T7** Scooling UI + backend train flow
- [ ] **T-KNOW** Knowtation vault export + train
- [ ] **T-YT** YouTube vault items in training scope
- [ ] **T8** GPU deploy + long job timeouts
- [ ] **T-POLICY** Consent + scope + server auth envelope
- [ ] **T-LEGAL** Every `LEGAL-CLOSURE.md` row DONE with evidence
- [ ] **T9** E2E all surfaces; stub inventory zero

---

## VCS

| Branch | Purpose | PR |
| --- | --- | --- |
| `main` | Stable contract + tests | — |
| `feat/t6-artifact-storage` | T6 artifact storage + durable state | draft PR → `main` (not feature→main per SD-14) |
| `feat/t5-vault-package-ingest` | T5 vault package ingest | prior draft PR |

---

## Change log

| Date | Change |
| --- | --- |
| 2026-08-26 | Finish-line roadmap; initial handover |
| 2026-08-26 (rev) | Reinstated T-CREDIT, T-LEGAL, T-POLICY, T-KNOW, T-YT; STUB inventory |
| 2026-08-26 (final) | LEGAL-CLOSURE tracker; build order; T4a/T4b prompts; confirmed no skips |
| 2026-08-26 | Overseer Kit installed; T4-TRAINER-SPEC freeze authored |
| 2026-08-26 | **T4b DONE** — gpu_worker stub/real, lockfile, 134 tests, BV pass |
| 2026-08-26 | Operator: defer CUDA/Railway live test; continue T5+ then verify at T8/T9 |
| 2026-08-26 | **T5 DONE** — package ingest API, content datasetHash, 147 tests, BV pass |
| 2026-08-26 | **T6 DONE** — artifact storage, signed download, durable state, 161 tests, BV pass |
