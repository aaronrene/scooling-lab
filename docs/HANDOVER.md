# Handover

## NEXT SESSION

**Model:** Thinking → Auto  
**Phase:** T4 — Real Trainer Runtime  
**Branch:** `cursor/t4-unsloth-trainer-ecd7` (create when starting T4b)

### THE ONE NEXT STEP

Run **T4a freeze**: pick base model, lock Unsloth core in `requirements.lock`, and write the on-disk
package + artifact layout spec. Do not install trainers until the freeze review passes.

---

## Paste-ready prompt (T4a — Thinking)

```
Model: Thinking
Repo: scooling-lab (main)
Phase: T4a — Real Trainer Runtime (freeze)

Read docs/ROADMAP.md (T4 row) and docs/TRAINING-API-CONTRACT.md.

Freeze WHAT/HOW for replacing gpu_worker placeholder with real Unsloth QLoRA fine-tune:

1. Base model id and license posture
2. Exact packages for requirements.lock (Unsloth Apache core only; no studio/unsloth_cli)
3. Training package directory layout under SCOOLING_LAB_PACKAGE_ROOT
4. Artifact output layout under SCOOLING_LAB_ARTIFACT_ROOT
5. How datasetHash switches from id-only to content hash for own:* packages
6. CI strategy without CUDA (mock/skip markers)
7. Provenance fields that stay content-free on the HTTP wire

Output: frozen spec section appended to docs/TRAINING-API-CONTRACT.md or new docs/T4-TRAINER-SPEC.md.
Then run ok review --freeze or /freeze-review-loop → pass before any Auto build.
```

---

## Paste-ready prompt (T4b — Auto, after freeze pass)

```
Model: Auto
Repo: scooling-lab
Phase: T4b — Real Trainer Runtime (build)

Implement exactly the frozen T4 spec. No redesign.

1. Lock runtime deps; regenerate DEPENDENCIES.md via python -m scooling_lab.bom
2. gpu_worker.py: real Unsloth QLoRA train → write adapter files
3. Env-driven package/artifact roots; never accept paths from HTTP JSON
4. Seven-tier tests; GPU integration marked skip without CUDA
5. Update HANDOVER verified snapshot + ROADMAP T4 → DONE, T5 → NEXT
6. Feature-branch commit; push; draft PR

Do not start T5 dataset ingest until T4 Definition of Done is met on a CUDA host.
```

---

## Verified snapshot (2026-08-26)

| Item | Value |
| --- | --- |
| Repo | `scooling-lab` |
| Branch | `main` |
| Tests | 127 passed (`PYTHONPATH=src python3 -m unittest discover -s tests`) |
| Runtime deps | Python stdlib only |
| Unsloth | Evidence-only (`docs/UNSLOTH-LICENSE-EVIDENCE.md`); not installed |
| API | Job + dataset + queue HTTP contract live |
| GPU worker | Isolated subprocess; **placeholder** — no weights, no vault read |
| Deploy | Dockerfile + Railway shell; API binds `PORT` |
| Cross-repo | Scooling app vault export + UI **not wired** |

---

## VCS

| Branch | Purpose | PR |
| --- | --- | --- |
| `main` | Stable contract + tests | — |
| `cursor/finish-line-roadmap-handover-ecd7` | Roadmap + handover finish-line plan | draft |

---

## Finish-line checklist (all phases)

Use this as the master relay until T9 DONE.

- [ ] **T4** Unsloth QLoRA in `gpu_worker`; real adapter on disk
- [ ] **T5** Server-side package ingest; content `datasetHash`; Scooling vault export
- [ ] **T6** Object storage + signed download + durable state path in prod
- [ ] **T7** Scooling UI: vault scope → train → model in picker
- [ ] **T8** GPU host deployed with secrets and queue longevity
- [ ] **T9** E2E vault → train → inference smoke; `CROSS-REPO-STATUS` operational

---

## Change log

| Date | Change |
| --- | --- |
| 2026-08-26 | Added finish-line roadmap (T4–T9); solo-operator gates removed; handover NEXT = T4a freeze |
