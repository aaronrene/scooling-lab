# Scooling Lab Overseer Handover

**Living relay for Scooling Lab.** Paste the **NEXT SESSION** block into a fresh chat.

**Regime:** muse+git-mirror (`.overseer/config.yaml` live)  
**Constellation:** `scooling-stack` (product order: `~/scooling`)  
**Product surfaces:** Scooling, Knowtation, YouTube train paths queue after T4–T6 in this repo.

---

<!-- overseer:next role=primary lane=product status=live -->
## NEXT SESSION — T6 Artifact Storage + Durable State (PRIMARY)

**Date:** 2026-08-26  
**Current position:** T5 Auto **DONE** — BV **`pass`**; 147 tests green  
**Model:** Auto

### Operator decision (2026-08-26)

CUDA `@gpu` live test and Railway GPU wiring remain deferred to **T8/T9** — not blocking T6 build.

### What just landed (T5)

| Slice | Deliverable |
| --- | --- |
| T5 | `POST /datasets/{id}/package` — server JWT auth envelope |
| T5 | Canonical `train.jsonl` write; `datasetHash` = SHA-256 of file bytes |
| T5 | `vaultScope` metadata; seven-tier `test_t5_package_ingest.py` |
| T5 | `TRAINING-API-CONTRACT.md` + LEGAL-CLOSURE L16 evidenced |

### THE ONE NEXT STEP — **Model: Auto**

| | |
| --- | --- |
| **ID** | **T6** |
| **Branch** | `feat/t6-artifact-storage` (from `feat/t5-vault-package-ingest` or `main` after merge) |
| **Repo** | **scooling-lab** |
| **Read first** | `docs/ROADMAP.md` T6; `docs/TRAINING-API-CONTRACT.md` retention/download gaps |

### Paste-ready prompt — T6

```
Phase T6 — Artifact object storage + durable job store (scooling-lab).

Model: Auto
Repo: ~/scooling-lab
Branch: feat/t6-artifact-storage
Step: T6
Authority: docs/ROADMAP.md T6

Deliverables:
1. Require SCOOLING_LAB_STATE_PATH in production
2. Upload adapter tarball to object storage (S3 / R2 / volume)
3. GET .../artifacts/{id}/download — signed URL, server auth only
4. Retention sweep deletes storage + metadata per policy
5. Seven-tier tests; update TRAINING-API-CONTRACT.md
6. Run /build-verification-review → pass before ROADMAP T6 → DONE
7. Feature-branch commit; push; draft PR (not to GitHub main)

Governance sync: update docs/ROADMAP.md + docs/OVERSEER-HANDOVER.md on completion.
```

---

### Paste-ready prompt (archived — T5 Auto)

```
Phase T5 — Vault dataset package ingest (scooling-lab).

Model: Auto
Status: DONE — BV pass (2026-08-26); 147 tests green; @gpu skip without CUDA.
Evidence: docs/reviews/2026-08-26-t5-package-ingest-bv-pass.md
```

---

## Build order (confirmed — no skips)

| Order | Phase | Repo |
| --- | --- | --- |
| 1 | T4 Real trainer | scooling-lab — **DONE** |
| 2 | T5 Vault package ingest | scooling-lab — **DONE** (Scooling export → T7) |
| 3 | T6 Artifacts + durable state | scooling-lab |
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
| Branch | `feat/t5-vault-package-ingest` |
| Overseer Kit | **live** — `initialized: true`, `kit_version: 0.1.0`, `footprint_self_integrity: ok` |
| Handover | `docs/OVERSEER-HANDOVER.md` |
| Roadmap | `docs/ROADMAP.md` |
| T5 BV | **`pass`** — `docs/reviews/2026-08-26-t5-package-ingest-bv-pass.md` |
| Tests | 147 passed, 1 skipped (`@gpu` — no CUDA in CI) |
| Package ingest | Server JWT + canonical JSONL + content `datasetHash` |
| GPU worker | T4b stub/real; provenance uses file hash after T5 |
| Pack credits | Muse Hub packs exist; **T-CREDIT not wired** |
| Legal | L2, L3, L5, L6, L9, L16 **DONE**; others open per `LEGAL-CLOSURE.md` |
| Products | Scooling / Knowtation / YouTube train paths **not wired** (T7+) |

### Governance gates checklist

- [x] **Overseer Kit installed** — 2026-08-26
- [x] **T4a freeze** — `docs/T4-TRAINER-SPEC.md` + `ok check-ok` **`pass`**
- [x] **T4b build** — `/build-verification-review` **`pass`** (2026-08-26)
- [x] **T5 build** — `/build-verification-review` **`pass`** (2026-08-26)
- [ ] **CUDA `@gpu`** — deferred to T8/T9 (operator 2026-08-26)

---

## Finish-line checklist (master)

- [x] **T4** Real Unsloth train → adapter files (build); CUDA verify before production
- [x] **T5** Vault package ingest + content hash (Lab); Scooling export → T7
- [ ] **T6** Durable state + object storage + download
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
| `feat/t5-vault-package-ingest` | T5 vault package ingest | draft PR → `main` (not feature→main per SD-14) |
| `feat/t4-unsloth-trainer` | T4b real trainer runtime | prior draft PR |

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
