# Roadmap

## Phase Model Key

| Label | Meaning |
| --- | --- |
| **DONE** | Delivered on `main`; seven-tier tests green |
| **NEXT** | The one active build target |
| **QUEUED** | Ordered; start only after the row above is DONE |

Solo-operator mode: no user traffic, no paid-GPU pilot gates, no “pre-private-data” hold points.
Keep AGPL boundaries and secret hygiene; skip ceremony that exists only for scale we do not have yet.

---

## Build Queue

| Phase | Model | Status | Deliverable |
| --- | --- | --- | --- |
| T0 | Auto | **DONE** | License + dependency BOM (`DEPENDENCIES.md`, AGPL path block) |
| T2 | Auto | **DONE** | Training job API contract, provenance, retention, deletion |
| T3 | Auto | **DONE** | Dataset review lifecycle, queue, cancel/retry, persistence hook |
| GPU-S0 | Auto | **DONE** | Isolated GPU worker subprocess + content-free placeholder completion |
| **T4** | **Thinking → Auto** | **NEXT** | Real Unsloth fine-tune in `gpu_worker` → adapter weights on disk |
| T5 | Auto | QUEUED | Server-side dataset package ingest (vault export → hashed JSONL) |
| T6 | Auto | QUEUED | Artifact object storage + signed download + durable job store |
| T7 | Auto | QUEUED | Scooling app integration (export, UI, job polling, model registration) |
| T8 | Auto | QUEUED | GPU deployment lane (Railway GPU or equivalent) + env secrets |
| T9 | Auto | QUEUED | End-to-end vault → train → use model in Scooling; fake worker dev-only |

---

## DONE — T0 / T2 / T3 / GPU-S0

What exists today (127 tests green):

- HTTP API: jobs, artifacts, provenance, datasets, queue (`src/scooling_lab/api.py`)
- Dataset lifecycle: `registered → pending_review → approved | rejected`
- Workers:
  - Wave A fake worker — synthetic fixture, no real training
  - GPU worker — isolated subprocess, **provenance only**, no weights, no vault bodies
- Docker + Railway deploy shell (API only, stdlib runtime)
- Unsloth recorded as evidence-only; **not installed**

---

## NEXT — T4: Real Trainer Runtime

**Goal:** A completed GPU job produces a real fine-tuned adapter the app can load.

### T4a — Thinking (freeze spec)

1. Pick base model id (e.g. `meta-llama/Llama-3.2-3B-Instruct` or smaller QLoRA target).
2. Lock **Unsloth core only** (`unsloth` Apache paths) in `requirements.lock`; update BOM.
3. Define training package on-disk layout the worker reads (path from env / server envelope, never browser).
4. Define artifact output layout (adapter dir, `config.json`, tokenizer files).
5. Extend provenance: `artifactHash` = hash of output tarball; keep response content-free.

### T4b — Auto (build)

1. Add runtime deps: `unsloth`, `torch`, `transformers`, `datasets`, `peft` (allowlisted licenses only).
2. Replace placeholder logic in `gpu_worker.py` with Unsloth QLoRA fine-tune loop.
3. Read training JSONL from `SCOOLING_LAB_PACKAGE_ROOT/{datasetId}/train.jsonl` (or envelope field set server-side only).
4. Write artifacts to `SCOOLING_LAB_ARTIFACT_ROOT/{jobId}/`.
5. Fail job → `failed` with safe error code; never log row text.
6. Seven-tier tests: mock GPU path for CI; optional `@gpu` integration test marked skip without CUDA.
7. Update `TRAINING-API-CONTRACT.md` + `DEPENDENCIES.md`.

**Definition of Done:** Local CUDA run (or documented GPU box) completes `own:*` + `scooling-lab-gpu-personal-v1` + `dryRun: false` and leaves loadable adapter files on disk.

---

## QUEUED — T5: Vault Dataset Package Ingest

**Goal:** User vault content reaches the worker as an approved, hashed training package.

### Scooling Lab (`scooling-lab`)

1. `POST /datasets/{id}/package` — **server-to-server auth only** (shared secret or JWT from Scooling backend).
2. Accept bounded JSONL upload or streaming write to package root; reject browser-origin calls.
3. `datasetHash` = SHA-256 of canonical JSONL bytes (replace id-only hash for real packages).
4. Auto-approve owner packages on successful ingest (solo mode); keep review enum for later policy.
5. Scope metadata in registration: `vaultScope` enum (`all`, `folder`, `tag`, `selection`) — ids only, no echo of note titles in API.

### Scooling app (`scooling` repo — cross-repo)

1. Vault export service: serialize selected notes → training JSONL (`instruction` / `input` / `output` or chat turns).
2. Redaction hook (empty pass-through OK for v1 solo).
3. Call Lab package ingest after user confirms scope in UI.

**Definition of Done:** Export from a test vault in Scooling lands as `own:{userId}:{packageVersion}` on disk; hash in provenance matches file bytes.

---

## QUEUED — T6: Artifact Storage And Durable State

**Goal:** Survive restarts; deliver model files back to Scooling.

1. Wire `TrainingJobStore(persistence_path=...)` in production (`SCOOLING_LAB_STATE_PATH`).
2. Upload completed adapter tarball to object storage (S3 / R2 / Railway volume).
3. `GET /training/jobs/{id}/artifacts/{artifactId}/download` — short-lived signed URL, server auth only.
4. Retention sweep deletes object storage + provenance per existing policy.
5. Replace in-memory-only assumptions in deploy docs.

**Definition of Done:** Kill API process mid-queue; restart; job state intact; succeeded job artifact downloadable once.

---

## QUEUED — T7: Scooling Product Integration

**Goal:** A Scooling user can choose vault scope and start training from the app.

### Scooling app UI + backend

1. **Train** entry: scope picker (all vault / folders / tags / hand-picked notes).
2. Consent copy + single toggle (solo v1 — no multi-tenant billing gate).
3. Create dataset registration + package upload + `createTrainingJob` server-side.
4. Job status screen: poll Lab `getTrainingJob`, cancel, retry.
5. On success: register artifact in Scooling model registry for chat/inference routing.
6. Knowtation: reuse same export adapter if vault API differs only by source.

**Definition of Done:** Click train in Scooling → job runs on GPU host → new model appears in model picker.

---

## QUEUED — T8: GPU Deployment Lane

**Goal:** Always-on training capacity, not laptop-only.

1. GPU-enabled host (Railway GPU service, RunPod, Modal, or dedicated box).
2. Env: `HF_TOKEN`, `SCOOLING_LAB_PACKAGE_ROOT`, `SCOOLING_LAB_ARTIFACT_ROOT`, `SCOOLING_LAB_STATE_PATH`, storage creds, Scooling auth secret.
3. Separate **worker queue process** or long-timeout subprocess (training > 30s).
4. Health: `GET /health` + queue depth from existing `/training/queue`.
5. Network: Scooling backend → Lab API allowlist only.

**Definition of Done:** Deploy from `main`; submit job from Scooling staging; completes without manual SSH.

---

## QUEUED — T9: Finish Line Verification

**Goal:** Declare Scooling Lab operational for vault-based personal models.

1. E2E script: seed vault → export → train → download adapter → load in inference smoke test.
2. Demote fake worker to `SCOOLING_LAB_DEV_FIXTURES=1` only.
3. Update `CROSS-REPO-STATUS.md` to **operational**.
4. Archive fixture-only docs footnotes; keep synthetic dataset for CI.

**Definition of Done:** `/build-verification-review` pass + operator sign-off on one real vault train.

---

## Explicitly Skipped (solo / no users)

| Former gate | Why skipped now |
| --- | --- |
| Separate legal review phase | Operator is sole developer; AGPL path block stays in code |
| Wave A `dryRun: true` product path | Jump straight to GPU real train |
| Paid-GPU billing caps | No payers |
| Multi-tenant quota tiers | No tenants |
| Incident-response committee | Operator owns incidents |
| Private-data pilot cohort | No external users |

Re-enable any row above when Scooling has paying users or external vault data at scale.

---

## Hard Stops (unchanged)

- No AGPL `studio/` or `unsloth_cli/` imports.
- No secrets, vault bodies, or model weights in git.
- No browser-supplied paths, URLs, or shell commands on the API.
- Merge to `main` = operator Tier 3.
