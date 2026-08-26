# Scooling Lab Roadmap

**Scope of this board.** Scooling Lab owns the **training API, worker runtime, dependency BOM, and
license boundary** for personal model jobs. Product UI, vault export, pack credits, and consent live
in Scooling / Knowtation — wired in T7, T-KNOW, T-CREDIT, T-POLICY.

Cross-repo product order: `~/scooling/docs/OVERSEER-HANDOVER.md` + `~/scooling/docs/ROADMAP.md`.
Session relay: `docs/OVERSEER-HANDOVER.md`.

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

## Current status (2026-08-26)

| | |
| --- | --- |
| **Overseer Kit** | **Live** — `initialized: true`, `kit_version: 0.1.0`, `footprint_self_integrity: ok` |
| **Tests** | **127/127** green (stdlib runtime; no Unsloth installed) |
| **GPU worker** | **STUB** — isolated subprocess; provenance placeholder only (GPU-S0) |
| **THE ONE NEXT STEP** | **T4b Auto** — implement `docs/T4-TRAINER-SPEC.md` (freeze **`pass`**) |
| **Finish-line** | T4 → T9 + T-CREDIT + T-LEGAL + T-POLICY — no skips (see build queue) |

---

## Build Queue (master)

| Phase | Model | Status | Deliverable |
| --- | --- | --- | --- |
| T0 | Auto | **DONE** | License + dependency BOM (`DEPENDENCIES.md`, AGPL path block) |
| T2 | Auto | **DONE** | Training job API contract, provenance, retention, deletion |
| T3 | Auto | **DONE** | Dataset review lifecycle, queue, cancel/retry, persistence hook |
| GPU-S0 | Auto | **STUB** | Isolated GPU worker subprocess — **placeholder only** (no weights) |
| **T4** | **Thinking → Auto** | **NEXT** (T4a **DONE**; T4b Auto) | Real Unsloth fine-tune → loadable adapter weights |
| T5 | Auto | QUEUED | Vault dataset package ingest (content hash, server-side auth) |
| T6 | Auto | QUEUED | Artifact object storage + signed download + durable job store |
| **T-CREDIT** | Auto | QUEUED | Muse Hub **pack credit** measure, reserve, debit, refund on train jobs |
| T7 | Auto | QUEUED | Scooling app integration (export, UI, job polling, model registration) |
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
| GPU worker placeholder (hashes only, no train) | `gpu_worker.py` | T4 real Unsloth QLoRA |
| `package_dataset_hash` id-only (no file bytes) | `gpu_worker.py` | T5 content SHA-256 |
| Fake / Wave A worker in prod path | `fake_worker.py` | T9 dev-only (`SCOOLING_LAB_DEV_FIXTURES=1`) |
| Unsloth evidence-only (not installed) | `requirements.lock` | T4 lockfile + BOM row |
| In-memory / optional persistence default | `api.main()` | T6 `SCOOLING_LAB_STATE_PATH` required in prod |
| GPU subprocess 30s timeout | `gpu_worker.py` | T8 job-scoped timeout from pack-estimated duration |
| No pack credit gate on job create | — | T-CREDIT Hub integration |
| Billing “lives elsewhere” doc-only | `SECURITY.md`, README | T-CREDIT implemented end-to-end |
| Legal checklist unchecked | `LEGAL-REVIEW-CHECKLIST.md` | T-LEGAL all boxes + tests |
| Scooling / Knowtation / YouTube unwired | cross-repo | T7, T-KNOW, T-YT |

---

## DONE — T0 / T2 / T3

What exists today (127 tests green):

- HTTP API: jobs, artifacts, provenance, datasets, queue (`src/scooling_lab/api.py`)
- Dataset lifecycle: `registered → pending_review → approved | rejected`
- Workers: fake worker (synthetic fixture); GPU worker subprocess (**stub** — provenance only)
- Docker + Railway deploy shell (API only, stdlib runtime)
- Unsloth recorded as evidence-only; **not installed**

---

## NEXT — T4: Real Trainer Runtime

**Goal:** A completed GPU job produces a real fine-tuned adapter the app can load.

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

## QUEUED — T5: Vault Dataset Package Ingest

### Scooling Lab

1. `POST /datasets/{id}/package` — server-to-server auth (JWT from Scooling backend).
2. Stream/write JSONL to package root; `datasetHash` = SHA-256 of canonical bytes.
3. Scope metadata: `vaultScope` (`all`, `folder`, `tag`, `selection`, `youtube`) — ids only on wire.

### Scooling app

1. Vault export service → training JSONL for selected scope.
2. Redaction hook (implement pass-through minimum; full rules in T-POLICY).

**Definition of Done:** Real vault export lands as `own:{userId}:{version}`; provenance hash matches file.

---

## QUEUED — T6: Artifact Storage And Durable State

1. Require `SCOOLING_LAB_STATE_PATH` in production.
2. Upload adapter tarball to object storage (S3 / R2 / volume).
3. `GET .../artifacts/{id}/download` — signed URL, server auth only.
4. Retention sweep deletes storage + metadata per policy.

**Definition of Done:** Restart-survivable queue; succeeded artifact downloadable.

---

## QUEUED — T-CREDIT: Muse Hub Pack Credits

**Why this is not skipped:** Packs and a credit pool already exist in Muse Hub. Training must **measure
cost, reserve credits from the pool, debit on success, and refund on cancel/fail** — same as other
pack-gated features.

### Scooling / Muse Hub (cross-repo)

1. Define **training pack SKU** and credit unit (e.g. GPU-seconds, tokens trained, or flat per job tier).
2. **Pre-flight estimate** API: dataset row count + model + epochs → credit quote shown in UI.
3. **Reserve** credits on `createTrainingJob` (idempotent with job idempotency key).
4. **Capture** debit when job → `succeeded`; **release** reserve on `failed` / `cancelled`.
5. Insufficient pool balance → refuse job with stable error before GPU starts.
6. Audit row: job id, pack id, credits reserved/captured, timestamp (content-free).

### Scooling Lab

1. Accept `packReservationId` or equivalent in server-signed job envelope (not browser-forged).
2. Refuse `running` transition if reservation invalid or expired.
3. Report metered usage (wall seconds, optional token counts) back to Hub on completion.

**Definition of Done:** Train flow debits the correct pack; cancel refunds; zero balance blocks queue.

---

## QUEUED — T7: Scooling Product Integration

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
