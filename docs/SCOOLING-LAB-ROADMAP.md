# Scooling Lab Roadmap

**Scope of this board.** Scooling Lab owns the **training API, worker runtime, dependency BOM, and
license boundary** for personal model jobs. Product UI, vault export, pack credits, and consent live
in Scooling / Knowtation — wired in T7, T-KNOW, T-CREDIT, T-POLICY.

Session relay for **this repo**: `docs/SCOOLING-LAB-OVERSEER-HANDOVER.md`.
Governance process (tiers, handover protocol, Standing Decisions): `docs/CROSS-REPO-COORDINATION.md`.
Product wiring status across surfaces: `docs/CROSS-REPO-STATUS.md`.
Cross-repo product order (**different repo, different docs**): `~/scooling/docs/OVERSEER-HANDOVER.md`
+ `~/scooling/docs/ROADMAP.md`.

## Phase Model Key

| Label | Meaning |
| --- | --- |
| **DONE** | Delivered on `main`; seven-tier tests green |
| **NEXT** | The one active build target |
| **QUEUED** | Ordered; start only after the row above is DONE |
| **STUB** | Exists today but must be replaced — not a finish-line deliverable |

**Finish-line policy:** 100% operational. No parked phases, no “skip because no users,” no placeholder
workers in production. Muse Hub pack credits, legal closure, and every product surface (Scooling,
Knowtation, YouTube) are **in scope and queued** — not deferred.

---

## Current status (2026-09-02)

| | |
| --- | --- |
| **Scope of this roadmap** | **Lab API only** (T4/T5/T6/T8). T7 train **UI** is `~/scooling`. **RHF** (Codex retail helper) is `~/scooling`-only and is **not** a Lab phase. |
| **Overseer Kit** | **INSTALLED here 2026-08-27** (v0.1.0). Re-verified **2026-09-02**: `initialized: true`, `lock.kit_version: "0.1.0"`, `footprint_self_integrity.state: "ok"`, `drift.status: "current"`. Open warning: `governance_freshness: drifted` (this land addresses D1/D2). |
| **Tests** | **161** — 160 passed + 1 `@gpu` skip (no CUDA), exit 0. **Re-run and confirmed 2026-09-02** (~28s). |
| **GPU worker** | **T4b** — stub/real train modes; **T5** content `datasetHash` |
| **Artifact storage** | **T6 code DONE** — signed download; Lab live at `lab.scool.ing` *(live health doc-sourced; not re-curled 2026-09-02)* |
| **T6 prod durability** | **OPEN — this is the real next step.** No Railway Volume at `/data` and no S3/R2, so **a redeploy wipes stored artifacts**. T6 shipped correct code onto storage that does not survive restart. |
| **THE ONE NEXT STEP** | **T6 prod durability** (**Thinking**) — pick Railway Volume vs S3/R2, freeze it, then Auto. T7 consumer **LANDED** on Scooling 2026-09-02. |
| **Gates (both mandatory)** | **Freeze-review `pass` before any Auto build; build-verification `pass` before any row → DONE.** Green tests alone are never DONE. See `docs/SCOOLING-LAB-OVERSEER-HANDOVER.md` → "Mandatory gates". |
| **Finish-line** | T6 durability → T8 → T-KNOW + T-YT + T-POLICY + T-LEGAL → T9 — no skips (see build queue) |
| **Constellation position** | Scooling PRIMARY is row **42 SC-BRAIN-LIVE-1a** (theBRAIN auth seam) — unrelated to Lab. Lab is **not** blocked by Gabriel/MuseHub, and Lab does not block the seam chapter. theBRAIN **E4** (Export to Edge) does depend on Lab GGUF export, which is downstream of T8. |

### Honest note on T7 (resolves a contradiction in this file)

The build queue below records **T7 = DONE / LANDED**, and that is correct as of 2026-09-02
(Scooling [#354](https://github.com/aaronrene/scooling/pull/354), BV r2+r3 pass). Sections further
down this document still describe **T7b BV round 1 `findings`** and "product path not live" — those
are **superseded**, left in place as history. The fix round happened and landed. **No T7 production
smoke has been claimed**, and that remains true.

---

## Build Queue (master)

| Phase | Model | Status | Deliverable |
| --- | --- | --- | --- |
| T0 | Auto | **DONE** | License + dependency BOM (`DEPENDENCIES.md`, AGPL path block) |
| T2 | Auto | **DONE** | Training job API contract, provenance, retention, deletion |
| T3 | Auto | **DONE** | Dataset review lifecycle, queue, cancel/retry, persistence hook |
| GPU-S0 | Auto | **DONE** | Isolated GPU worker subprocess — replaced by T4b |
| **T4** | **Thinking → Auto** | **DONE** (T4a freeze + T4b BV **`pass`**; `@gpu` on CUDA before production) | Real Unsloth fine-tune → loadable adapter weights |
| **T5** | Auto | **DONE** (BV **`pass`** 2026-08-26; CUDA `@gpu` deferred to T8/T9) | Vault dataset package ingest (content hash, server-side auth) |
| **T6** | Auto | **DONE** (BV **`pass`** 2026-08-26) | Artifact object storage + signed download + durable job store |
| T-CREDIT | Auto | **BUILT 2026-08-26 — BV NOT RECORDED** (was marked DONE; corrected 2026-09-02) | Muse Hub **pack credit** measure, reserve, debit, refund on train jobs. Per the Definition of Done, a row without a build-verification `pass` is **not DONE**. Run `/build-verification-review` and file the artifact under `docs/reviews/`, or restate the row honestly. |
| T7 | Auto | **DONE / LANDED in `~/scooling`** 2026-09-02 — BV r2+r3 pass; Muse main + GitHub [#354](https://github.com/aaronrene/scooling/pull/354) | Scooling app integration (export, UI, job polling, model registration) |
| T-KNOW | Auto | QUEUED | Knowtation vault export → same training pipeline |
| T-YT | Auto | QUEUED | YouTube-sourced vault content → training export (where user opted in) |
| T8 | Auto | QUEUED | GPU deployment lane + long-running worker queue |
| **T-LEGAL** | Operator + Auto | QUEUED | Close every item in `LEGAL-REVIEW-CHECKLIST.md` with evidence |
| **T-POLICY** | Thinking → Auto | QUEUED | Consent, scope, redaction, retention/export — wired in product |
| T9 | Auto | QUEUED | E2E all surfaces; remove production stubs; `CROSS-REPO-STATUS` operational |

---

## STUB inventory (must hit zero at T9)

| Stub | Location | Replaced by |
| --- | --- | --- |
| GPU worker placeholder (hashes only, no train) | `gpu_worker.py` | **T4b** — stub/real train + tarball |
| Fake / Wave A worker in prod path | `fake_worker.py` | T9 dev-only (`SCOOLING_LAB_DEV_FIXTURES=1`) |
| Unsloth evidence-only (not installed) | `requirements.lock` | **T4b** lockfile + BOM row |
| In-memory / optional persistence default | `api.main()` | **T6 DONE** — `SCOOLING_LAB_STATE_PATH` required in prod |
| GPU subprocess 30s timeout | `gpu_worker.py` | **T4b** `SCOOLING_LAB_GPU_TIMEOUT_SECONDS` (default 3600) |
| No pack credit gate on job create | — | **T-CREDIT DONE** — Hub `/api/v1/billing/training/*` + Scooling coordinator |
| Billing “lives elsewhere” doc-only | `SECURITY.md`, README | **T-CREDIT DONE** — end-to-end reserve/capture/release (wire: `SCOOLING_TRAINING_CREDIT_HUB=enabled`) |
| Legal checklist unchecked | `LEGAL-REVIEW-CHECKLIST.md` | T-LEGAL all boxes + tests |
| Scooling / Knowtation / YouTube unwired | cross-repo | T7, T-KNOW, T-YT |

---

## DONE — T0 / T2 / T3

What exists today (134 tests green; 1 `@gpu` skip without CUDA):

- HTTP API: jobs, artifacts, provenance, datasets, queue (`src/scooling_lab/api.py`)
- Dataset lifecycle: `registered → pending_review → approved | rejected`
- Workers: fake worker (synthetic fixture); GPU worker subprocess (**T4b** — stub/real Unsloth QLoRA)
- Docker + Railway deploy shell (API only, stdlib runtime)
- GPU training stack locked in `requirements.lock`; installed on GPU host only

---

## DONE — T5: Vault Dataset Package Ingest

- `POST /datasets/{id}/package` — HS256 Bearer JWT (`SCOOLING_LAB_INGEST_AUTH_SECRET`)
- Canonical `train.jsonl` under `SCOOLING_LAB_PACKAGE_ROOT/{datasetId}/`
- `datasetHash` = SHA-256 of canonical file bytes (GPU provenance)
- `vaultScope` metadata: `all` / `folder` / `tag` / `selection` / `youtube` (ids only)
- Seven-tier tests in `tests/test_t5_package_ingest.py`
- BV: `docs/reviews/2026-08-26-t5-package-ingest-bv-pass.md` **`pass`**

**Operator note:** CUDA `@gpu` live test still deferred to T8/T9 before production GPU train.

---

## DONE — T6: Artifact Storage And Durable State

- `SCOOLING_LAB_STATE_PATH` required in production (`runtime_config.py`)
- Volume / S3 / R2 object storage upload after GPU train (`artifact_storage.py`)
- `GET .../artifacts/{id}/download` — server JWT → signed URL
- Retention sweep deletes storage bytes + metadata
- Seven-tier tests in `tests/test_t6_artifact_storage.py`
- BV: `docs/reviews/2026-08-26-t6-artifact-storage-bv-pass.md` **`pass`**

**Operator closeout (finish-line, not code):** attach Railway Volume at `/data` **or** wire
S3/R2 backends so job state and artifacts survive container replacement. Until then Lab is
**operational** but not **restart-survivable** in production.

---

## IN PROGRESS — T7: Scooling Product Integration (owned by `~/scooling`)

T7b is implemented on `~/scooling` `feat/t7-scooling-train-ui` (`5f1bc255`) but **build
verification round 1 returned `findings`** on 2026-08-27 — see
`~/scooling/docs/reviews/2026-08-27-t7b-scooling-train-ui-bv-round1-findings.md`. The product
train path is **not live** and must not be described as shipped.

Blocking items live entirely in `~/scooling`: the Start form drops `labIds` so only
`scopeKind: "all"` works, `pnpm typecheck` fails, four pre-existing product e2e suites are red,
and four of the seven test tiers assert tautologies rather than the real catalog/export/ingest
path. **Nothing in this Lab repo is blocked by that** — the T5 ingest and T6 download contracts
are consumed as-is and unchanged.

## DONE — T-CREDIT: Muse Hub Pack Credits (2026-08-26)

Cross-repo Auto on `feat/t-credit-pack-reserve`:

| Deliverable | Location |
| --- | --- |
| Training pack SKU `unified_pool` + credit unit | Knowtation `training-credit-policy.mjs`; Scooling `trainingCreditPolicy.ts` |
| Pre-flight estimate API | `POST /api/v1/billing/training/estimate` |
| Reserve on createTrainingJob (idempotent) | `POST /api/v1/billing/training/reserve` + Scooling `submitJob` hub path |
| Capture on succeeded / release on failed | `POST /api/v1/billing/training/capture` / `release` + `loadView` settlement |
| Insufficient balance refuse | Hub `402 INSUFFICIENT_BALANCE` before Lab job |
| Content-free audit rows | `training_audit` in billing DB |
| Seven-tier tests | `knowtation/test/billing-training.test.mjs`; Scooling `test/*/training-credit-policy.test.ts` |

**Wire gate:** Scooling hosted product sets `SCOOLING_TRAINING_CREDIT_HUB=enabled` (compile-time authorized). Loopback practice keeps mock adapter.

**BV:** pending `/build-verification-review`. **Lab envelope** (`packReservationId`) deferred to later scooling-lab slice.

---

## RETIRED — T-CREDIT queue detail (was NEXT)

See **DONE — T-CREDIT** above for shipped deliverables. Original queue spec retained in git history.

---

## DONE — T4: Real Trainer Runtime

T4a freeze: `docs/T4-TRAINER-SPEC.md` (`ok check-ok` **`pass`**). T4b Auto delivered:

- Locked `requirements.lock` + `DEPENDENCIES.md` (`python -m scooling_lab.bom`)
- `gpu_worker.py`: env-driven package/artifact roots; stub/real train; tarball `artifactHash`
- `SCOOLING_LAB_GPU_TIMEOUT_SECONDS` (default 3600); subprocess isolation preserved
- Seven-tier tests + `@gpu` skip without CUDA
- LEGAL-CLOSURE L2, L3, L5, L6, L9 evidenced

**CUDA gate (before T5):** run `test_gpu_real_unsloth_train_writes_adapter` on a CUDA host.

---

## RETIRED — T4 build queue (was NEXT)

### T4a — Thinking (freeze spec)

1. Pick base model id and confirm **HF / model license** acceptance path (see Legal blocks below).
2. Lock **Unsloth core only** (`unsloth` Apache paths) in `requirements.lock`; update BOM.
3. Define training package on-disk layout (`SCOOLING_LAB_PACKAGE_ROOT/{datasetId}/`).
4. Define artifact output layout (`SCOOLING_LAB_ARTIFACT_ROOT/{jobId}/`).
5. Provenance: `artifactHash` = hash of output tarball; HTTP responses stay content-free.

### T4b — Auto (build)

1. Add runtime deps: `unsloth`, `torch`, `transformers`, `datasets`, `peft` (allowlisted only).
2. Replace placeholder logic in `gpu_worker.py` with Unsloth QLoRA fine-tune.
3. Read training JSONL from env-driven package root — never from browser JSON.
4. Write loadable adapter files; fail → `failed` with safe error code.
5. Seven-tier tests; GPU integration `@gpu` skip without CUDA.
6. Update `TRAINING-API-CONTRACT.md` + `DEPENDENCIES.md`.

**Definition of Done:** CUDA host completes `own:*` + `scooling-lab-gpu-personal-v1` + `dryRun: false`
with loadable adapter on disk.

---

## RETIRED — T5 queue detail (Lab **DONE** 2026-08-26; Scooling export → **T7**)

Lab deliverables shipped in **DONE — T5** above. Remaining Scooling-app vault export wiring is **T7**.

---

## RETIRED — T-CREDIT queue detail (superseded by DONE — T-CREDIT 2026-08-26)

Original Scooling / Muse Hub queue rows moved to **DONE — T-CREDIT** section above.

---

## QUEUED — T7: Scooling Product Integration (detail)

1. **Train** UI: vault scope picker (all / folders / tags / notes).
2. Consent toggle + pack credit quote (T-POLICY copy).
3. Server-side: register dataset → upload package → reserve credits → create job.
4. Job status, cancel, retry; model registry on success.

**Definition of Done:** Scooling user trains on chosen vault scope; model in picker.

---

## QUEUED — T-KNOW: Knowtation

1. Knowtation vault export adapter (same JSONL contract as Scooling).
2. Shared `own:know:{userId}:{version}` dataset id namespace.
3. UI entry in Knowtation for “train personal model” with pack credits.

**Definition of Done:** Knowtation vault → train → model usable in Knowtation chat.

---

## QUEUED — T-YT: YouTube

1. Include YouTube-ingested notes/transcripts in vault export when user selects them.
2. Scope flag `youtube` in registration metadata.
3. Policy: only user-owned / user-imported YouTube content in their vault (T-POLICY).

**Definition of Done:** User with YouTube vault items can include or exclude them in training scope.

---

## QUEUED — T8: GPU Deployment Lane

1. GPU host (Railway GPU, RunPod, Modal, or dedicated box).
2. Env: `HF_TOKEN`, package/artifact/state roots, storage creds, Hub auth.
3. Worker queue process; timeout from estimated job duration (not 30s stub).
4. `GET /health` + `/training/queue`.

**Definition of Done:** Deploy from `main`; job from staging completes without SSH.

---

## QUEUED — T-LEGAL: Legal And License Closure

**These are finish work, not launch blockers to bypass.** Each row maps to
`docs/LEGAL-REVIEW-CHECKLIST.md`.

| # | Item | Action | Blocks training? |
| --- | --- | --- | --- |
| L1 | Repo license (Apache-2.0 Lab) | Confirm distribution model documented | No |
| L2 | Runtime deps in BOM | T4 lockfile + `bom --check` | Yes until T4 |
| L3 | Per-dep license allowlist | Audit torch/transformers/Unsloth/peft rows | Yes until T4 |
| L4 | No AGPL Studio/CLI | Keep `studio/` / `unsloth_cli/` block in CI | **Hard stop if violated** |
| L5 | Base **model** license | Accept HF Llama/etc. terms; document in NOTICE | Yes for Llama weights |
| L6 | Unsloth core Apache audit | Byte audit installed wheel paths (no AGPL segments) | Yes until T4 |
| L7 | Dataset consent policy | T-POLICY product copy + server gate | Yes for user vault |
| L8 | Retention / export / deletion | Already coded; T-POLICY + T6 prod wiring | No for solo test |
| L9 | API injection controls | Already coded; regression tests | No |
| L10 | Logs exclude private bodies | Verify in T4 worker logging | Yes |
| L11 | Payer-visible cost policy | **T-CREDIT** UI quote + receipt | Yes at launch |
| L12 | Quota / replay / idempotency | Job idempotency done; pack quota in T-CREDIT | Partial |
| L13 | GPU creds env-scoped | T8 deploy review | Yes |
| L14 | Egress allowlist | T8 network policy doc | Yes |
| L15 | Artifact provenance on export | T6 download + provenance endpoint | No |
| L16 | Incident response owner | Solo: operator runbook in `SECURITY.md` | No |

**Definition of Done:** Checklist copied into `docs/LEGAL-CLOSURE.md` with checkbox, evidence link, and
date for every row; CI still blocks AGPL paths.

### Legal blocks explained (specific)

1. **Unsloth AGPL optional paths** — `studio/*` and `unsloth_cli/*` are AGPL-3.0. We **may** use the
   Apache-2.0 PyPI core; we **may not** import, copy, or bundle Studio/CLI. This is implemented in
   `license_policy.py` + CI. **Not a reason to skip training** — use core only.

2. **GPL/AGPL dependency family** — Blocked unless distribution model changes. All torch/transformers/
   peft/Unsloth-core must pass allowlist at lock time.

3. **Base model weights license** — Models like Llama require Hugging Face license acceptance and
   `HF_TOKEN`. User/operator accepts terms; document in NOTICE. **Build step**, not skip.

4. **User data consent** — Training on vault content requires explicit consent UI (T-POLICY). Required
   for launch even for solo operator testing on real vault.

5. **Paid GPU / pack disclosure** — Credit quote before train, receipt after (T-CREDIT). Required
   because packs exist.

---

## QUEUED — T-POLICY: Consent, Scope, Redaction

1. Training consent text + toggle (what data is used, retention, deletion).
2. Scope rules: all vault, folders, tags, selections, YouTube-in-vault.
3. Redaction/exclusion rules (PII, excluded notes) — minimum viable + extension points.
4. Scooling → Lab authorization envelope (server JWT claims: userId, packId, datasetId).

**Definition of Done:** No job starts without consent + valid server auth + approved dataset.

---

## QUEUED — T9: Finish Line Verification

1. E2E: Scooling vault → pack reserve → train → debit → model in inference.
2. E2E: Knowtation vault path.
3. E2E: YouTube-inclusive scope path.
4. Fake worker **dev-only**; prod refuses `fixture-tiny-llm` unless env set.
5. `CROSS-REPO-STATUS.md` → **operational**; stub inventory → zero.

**Definition of Done:** All seven-tier tests green; operator sign-off; no STUB rows remain.

---

## Retired: “Explicitly Skipped” list

The following were **incorrectly** marked skipped in the 2026-08-26 draft. They are **reinstated**
above:

| Former “skip” | Correct treatment |
| --- | --- |
| Separate legal review phase | **T-LEGAL** — complete checklist with evidence |
| Paid-GPU billing caps | **T-CREDIT** — Muse Hub pack measure/allot/debit |
| Multi-tenant quota tiers | **T-CREDIT** — per-user pack balance from pool |
| Wave A dryRun product path | Demote to dev fixtures at T9; prod uses GPU real train |
| Incident-response committee | Operator runbook in T-LEGAL L16 |
| Private-data pilot cohort | Real vault training in T5/T7 — no fake cohort gate |

---

## Hard Stops (unchanged — not skippable)

- No AGPL `studio/` or `unsloth_cli/` imports.
- No secrets, vault bodies, or model weights in git.
- No browser-supplied paths, URLs, or shell commands on the API.
- Merge to `main` = operator Tier 3.
