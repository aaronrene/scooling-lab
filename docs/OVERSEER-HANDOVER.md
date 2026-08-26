# Scooling Lab Overseer Handover

**Living relay for Scooling Lab.** Paste the **NEXT SESSION** block into a fresh chat.

**Regime:** muse+git-mirror (`.overseer/config.yaml` live)  
**Constellation:** `scooling-stack` (product order: `~/scooling`)  
**Product surfaces:** Scooling, Knowtation, YouTube train paths queue after T4–T6 in this repo.

---

<!-- overseer:next role=primary lane=product status=live -->
## NEXT SESSION — T4b Real Trainer Runtime (PRIMARY)

**Date:** 2026-08-26  
**Current position:** T4a freeze **`pass`** on `docs/T4-TRAINER-SPEC.md`; ready for T4b Auto build  
**Model:** Auto

### What just landed

| Slice | Deliverable |
| --- | --- |
| OK-INSTALL | Overseer Kit (`ok init --migrate`); skills, rules, `version.lock` |
| GOV-RENAME | `docs/OVERSEER-HANDOVER.md` + kit-aligned `docs/ROADMAP.md` |
| T4a | `docs/T4-TRAINER-SPEC.md` freeze-review **`pass`** (`ok check-ok`) |

### THE ONE NEXT STEP — **Model: Auto**

Implement **T4b** exactly per `docs/T4-TRAINER-SPEC.md` on branch `feat/t4-unsloth-trainer`.

| | |
| --- | --- |
| **ID** | **T4b** |
| **Branch** | `feat/t4-unsloth-trainer` |
| **Repo** | **scooling-lab** |
| **Read first** | `docs/T4-TRAINER-SPEC.md`; `docs/TRAINING-API-CONTRACT.md` |
| **Hard stops** | No redesign · no merge to `main` without Tier 3 · BV `pass` before ROADMAP T4 DONE |

### Paste-ready prompt — T4b

```
Phase T4b — Real Trainer Runtime build (scooling-lab).

Model: Auto
Repo: ~/scooling-lab
Branch: feat/t4-unsloth-trainer
Step: T4b
Authority: docs/T4-TRAINER-SPEC.md (frozen — no redesign)

Read first: docs/T4-TRAINER-SPEC.md; docs/TRAINING-API-CONTRACT.md.

Deliverables:
1. Lock runtime deps; regenerate DEPENDENCIES.md via python -m scooling_lab.bom
2. gpu_worker.py: real Unsloth QLoRA → adapter files on disk (stub/real train mode per spec)
3. Env-driven package/artifact roots; never accept paths from HTTP JSON
4. Seven-tier tests; @gpu integration skip without CUDA
5. Update LEGAL-CLOSURE L2, L3, L6, L9 when evidenced
6. Run /build-verification-review → pass before ROADMAP T4 → DONE
7. Feature-branch commit; push; draft PR (not to GitHub main)

Hard stops: Do not start T5 until T4 Definition of Done on a CUDA host.

Governance sync: update docs/ROADMAP.md + docs/OVERSEER-HANDOVER.md on completion.

Governance gates (mandatory — remind only; silence is not pass):
- Freeze review: /freeze-review-loop before Thinking freeze → DONE; ok review --freeze when CLI green
- Build verification: /build-verification-review after every Auto {step}b before ROADMAP DONE
- Workspace: ok workspace check-next before claiming multi-repo SD-17 complete
```

---

### Paste-ready prompt (archived — T4a Thinking)

```
Phase T4a — Real Trainer Runtime freeze (scooling-lab).

Model: Thinking
Repo: ~/scooling-lab
Step: T4a
Authority: docs/T4-TRAINER-SPEC.md

Status: DONE — ok check-ok --path docs/T4-TRAINER-SPEC.md → pass (2026-08-26).
Proceed to T4b Auto.
```

---

## Build order (confirmed — no skips)

| Order | Phase | Repo |
| --- | --- | --- |
| 1 | T4 Real trainer | scooling-lab |
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
| Branch | `main` @ `a730545` (finish-line plan merged PR #6) |
| Overseer Kit | **live** — `initialized: true`, `kit_version: 0.1.0`, `footprint_self_integrity: ok` |
| Handover | `docs/OVERSEER-HANDOVER.md` |
| Roadmap | `docs/ROADMAP.md` |
| T4 freeze | `docs/T4-TRAINER-SPEC.md` — **`pass`** (`ok check-ok`, 2026-08-26) |
| Tests | 127 passed (`PYTHONPATH=src python3 -m unittest discover -s tests`) |
| Runtime deps | Stdlib only; Unsloth not installed |
| GPU worker | **STUB** — provenance placeholder only |
| Pack credits | Muse Hub packs exist; **T-CREDIT not wired** |
| Legal | **LEGAL-CLOSURE.md** tracker open (L8, L10, L13 partial/done) |
| Products | Scooling / Knowtation / YouTube train paths **not wired** |

### Governance gates checklist

- [x] **Overseer Kit installed** — 2026-08-26, `initialized: true`, `kit_version: 0.1.0`, `footprint_self_integrity: ok`
- [x] **T4a freeze** — `docs/T4-TRAINER-SPEC.md` + `ok check-ok` **`pass`** (2026-08-26)
- [ ] **T4b build** — `/build-verification-review` **`pass`** before ROADMAP T4 → DONE

---

## Finish-line checklist (master)

- [ ] **T4** Real Unsloth train → adapter files
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
| `feat/overseer-kit-governance` | Kit install + governance rename + T4a freeze | (this session) |

---

## Change log

| Date | Change |
| --- | --- |
| 2026-08-26 | Finish-line roadmap; initial handover |
| 2026-08-26 (rev) | Reinstated T-CREDIT, T-LEGAL, T-POLICY, T-KNOW, T-YT; STUB inventory |
| 2026-08-26 (final) | LEGAL-CLOSURE tracker; build order; T4a/T4b prompts; confirmed no skips |
| 2026-08-26 | Overseer Kit installed; `HANDOVER.md` → `OVERSEER-HANDOVER.md`; T4-TRAINER-SPEC freeze authored |
