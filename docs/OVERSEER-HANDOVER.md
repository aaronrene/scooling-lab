# Scooling Lab Overseer Handover

**Living relay for Scooling Lab.** Paste the **NEXT SESSION** block into a fresh chat.

**Regime:** muse+git-mirror (`.overseer/config.yaml` live)  
**Constellation:** `scooling-stack` (product order: `~/scooling`)  
**Product surfaces:** Scooling, Knowtation, YouTube train paths queue after T4–T6 in this repo.

---

<!-- overseer:next role=primary lane=product status=live -->
## NEXT SESSION — T5 Vault Package Ingest (PRIMARY)

**Date:** 2026-08-26  
**Current position:** T4b Auto **DONE** — BV **`pass`**; `@gpu` real train pending CUDA host before T5 start  
**Model:** Auto

### What just landed

| Slice | Deliverable |
| --- | --- |
| T4b | Real trainer runtime — `gpu_worker.py` stub/real modes, tarball provenance, locked deps |
| T4b | `requirements.lock` + `DEPENDENCIES.md`; LEGAL-CLOSURE L2, L3, L5, L6, L9 |
| T4b | 134 tests green (1 `@gpu` skip without CUDA) |

### THE ONE NEXT STEP — **Model: Auto** (blocked until CUDA `@gpu` green)

**Hard stop:** Run `test_gpu_real_unsloth_train_writes_adapter` on a CUDA host with
`SCOOLING_LAB_GPU_TRAIN_MODE=real` before starting T5.

| | |
| --- | --- |
| **ID** | **T5** |
| **Branch** | `feat/t5-vault-package-ingest` (create from `main` after T4 merge) |
| **Repo** | **scooling-lab** |
| **Read first** | `docs/ROADMAP.md` T5; `docs/T4-TRAINER-SPEC.md` §4 package layout |

### Paste-ready prompt — T5

```
Phase T5 — Vault dataset package ingest (scooling-lab).

Model: Auto
Repo: ~/scooling-lab
Step: T5
Authority: docs/ROADMAP.md T5; docs/T4-TRAINER-SPEC.md package layout

Prerequisite: CUDA host — @gpu real-train test green (T4 Definition of Done).

Read first: docs/ROADMAP.md T5; docs/TRAINING-API-CONTRACT.md.

Deliverables:
1. POST /datasets/{id}/package — server-to-server auth envelope
2. Write JSONL to SCOOLING_LAB_PACKAGE_ROOT; datasetHash = SHA-256 of canonical bytes
3. Seven-tier tests; no browser-supplied paths
4. Update TRAINING-API-CONTRACT.md + LEGAL-CLOSURE as evidenced
5. Run /build-verification-review → pass before ROADMAP T5 → DONE
6. Feature-branch commit; push; draft PR (not to GitHub main)

Governance sync: update docs/ROADMAP.md + docs/OVERSEER-HANDOVER.md on completion.
```

---

### Paste-ready prompt (archived — T4b Auto)

```
Phase T4b — Real Trainer Runtime build (scooling-lab).

Model: Auto
Repo: ~/scooling-lab
Branch: feat/t4-unsloth-trainer
Step: T4b
Authority: docs/T4-TRAINER-SPEC.md (frozen — no redesign)

Status: DONE — BV pass (2026-08-26); 134 tests green; @gpu skip without CUDA.
CUDA gate remains before T5.
```

---

## Build order (confirmed — no skips)

| Order | Phase | Repo |
| --- | --- | --- |
| 1 | T4 Real trainer | scooling-lab — **DONE** |
| 2 | T5 Vault package ingest | scooling-lab + scooling |
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
| Branch | `feat/t4-unsloth-trainer` (T4b build) |
| Overseer Kit | **live** — `initialized: true`, `kit_version: 0.1.0`, `footprint_self_integrity: ok` |
| Handover | `docs/OVERSEER-HANDOVER.md` |
| Roadmap | `docs/ROADMAP.md` |
| T4 freeze | `docs/T4-TRAINER-SPEC.md` — **`pass`** (`ok check-ok`, 2026-08-26) |
| T4b BV | **`pass`** (2026-08-26) |
| Tests | 134 passed, 1 skipped (`@gpu` — no CUDA in CI) |
| Runtime deps | Locked in `requirements.lock`; GPU host install only |
| GPU worker | **T4b** — stub/real Unsloth QLoRA; tarball `artifactHash` |
| Pack credits | Muse Hub packs exist; **T-CREDIT not wired** |
| Legal | L2, L3, L5, L6, L9 **DONE**; others open per `LEGAL-CLOSURE.md` |
| Products | Scooling / Knowtation / YouTube train paths **not wired** |

### Governance gates checklist

- [x] **Overseer Kit installed** — 2026-08-26
- [x] **T4a freeze** — `docs/T4-TRAINER-SPEC.md` + `ok check-ok` **`pass`**
- [x] **T4b build** — `/build-verification-review` **`pass`** (2026-08-26)
- [ ] **CUDA `@gpu`** — real train on GPU host before T5

---

## Finish-line checklist (master)

- [x] **T4** Real Unsloth train → adapter files (build); CUDA verify before T5
- [ ] **T5** Vault package ingest + content hash
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
| `feat/t4-unsloth-trainer` | T4b real trainer runtime | draft PR → `main` (not feature→main per SD-14) |

---

## Change log

| Date | Change |
| --- | --- |
| 2026-08-26 | Finish-line roadmap; initial handover |
| 2026-08-26 (rev) | Reinstated T-CREDIT, T-LEGAL, T-POLICY, T-KNOW, T-YT; STUB inventory |
| 2026-08-26 (final) | LEGAL-CLOSURE tracker; build order; T4a/T4b prompts; confirmed no skips |
| 2026-08-26 | Overseer Kit installed; T4-TRAINER-SPEC freeze authored |
| 2026-08-26 | **T4b DONE** — gpu_worker stub/real, lockfile, 134 tests, BV pass |
