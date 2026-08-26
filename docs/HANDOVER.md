# Handover

## NEXT SESSION

**Model:** Thinking → Auto  
**Phase:** T4 — Real Trainer Runtime  
**Branch:** `cursor/t4-unsloth-trainer-ecd7` (create when starting T4b)

### THE ONE NEXT STEP

Run **T4a freeze**: base model + HF license path, Unsloth core lockfile, package/artifact layout.

---

## Paste-ready prompt (T4a — Thinking)

```
Model: Thinking
Repo: scooling-lab (main)
Phase: T4a — Real Trainer Runtime (freeze)

Read docs/ROADMAP.md (T4), docs/TRAINING-API-CONTRACT.md, docs/UNSLOTH-LICENSE-EVIDENCE.md.

Freeze WHAT/HOW for real Unsloth QLoRA training:

1. Base model id + HF license acceptance path (L5)
2. requirements.lock packages — Unsloth Apache core only; no studio/unsloth_cli (L4, L6)
3. SCOOLING_LAB_PACKAGE_ROOT layout for own:* JSONL packages
4. SCOOLING_LAB_ARTIFACT_ROOT layout for loadable adapters
5. Content-based datasetHash (replaces id-only hash at T5 boundary)
6. CI strategy without CUDA (@gpu skip markers)
7. Provenance fields that stay content-free on HTTP wire
8. Worker logging rules (L9, L16)

Output: docs/T4-TRAINER-SPEC.md (frozen). Pass freeze review before T4b Auto build.
```

---

## Paste-ready prompt (T4b — Auto)

```
Model: Auto
Repo: scooling-lab
Phase: T4b — Real Trainer Runtime (build)

Implement exactly docs/T4-TRAINER-SPEC.md. No redesign.

1. Lock runtime deps; regenerate DEPENDENCIES.md via python -m scooling_lab.bom
2. gpu_worker.py: real Unsloth QLoRA → adapter files on disk
3. Env-driven package/artifact roots; never accept paths from HTTP JSON
4. Seven-tier tests; @gpu integration skip without CUDA
5. Update LEGAL-CLOSURE L2, L3, L6, L9 when evidenced
6. Update ROADMAP GPU-S0 → DONE (stub cleared for worker); HANDOVER snapshot
7. Feature-branch commit; push; draft PR

Do not start T5 until T4 Definition of Done on a CUDA host.
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
| Branch | `cursor/finish-line-roadmap-handover-ecd7` → merge PR #6 |
| Tests | 127 passed (`PYTHONPATH=src python3 -m unittest discover -s tests`) |
| Runtime deps | Stdlib only; Unsloth not installed |
| GPU worker | **STUB** — provenance placeholder only |
| Pack credits | Muse Hub packs exist; **T-CREDIT not wired** |
| Legal | **LEGAL-CLOSURE.md** tracker open (L8, L10, L13 partial/done) |
| Products | Scooling / Knowtation / YouTube train paths **not wired** |

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
| `cursor/finish-line-roadmap-handover-ecd7` | Complete finish-line plan | [#6](https://github.com/aaronrene/scooling-lab/pull/6) |

---

## Change log

| Date | Change |
| --- | --- |
| 2026-08-26 | Finish-line roadmap; initial handover |
| 2026-08-26 (rev) | Reinstated T-CREDIT, T-LEGAL, T-POLICY, T-KNOW, T-YT; STUB inventory |
| 2026-08-26 (final) | LEGAL-CLOSURE tracker; build order; T4a/T4b prompts; confirmed no skips |
