# T4 — Real Trainer Runtime (Unsloth QLoRA)

**Phase:** T4 (`T4a` Thinking freeze → `T4b` Auto)  
**Freeze status:** **CLEARED for T4b** — `ok check-ok --path` **`pass`** (stamp `sha256:34671c15…`)  
**Date:** 2026-08-26  
**Model (this artifact):** Thinking  
**Owner repo:** scooling-lab  
**Branch:** `feat/overseer-kit-governance`  
**Authority:** `docs/ROADMAP.md` T4; `docs/OVERSEER-HANDOVER.md` NEXT

Status: **Frozen Thinking spec.** No Unsloth install or GPU train in this artifact. T4b implements
exactly this contract after freeze-review **`pass`**.

```yaml
phase: T4a
outputs:
- id: t4-trainer-spec
  path: docs/T4-TRAINER-SPEC.md
  frozen: true
  notes: Real Unsloth QLoRA trainer in isolated gpu_worker subprocess; Apache core only; env-driven package/artifact roots; content-free HTTP wire.
frozen_inputs:
- id: training-api-contract
  path: docs/TRAINING-API-CONTRACT.md
  notes: GPU model id scooling-lab-gpu-personal-v1; dryRun false; own:* only; no browser paths
- id: unsloth-license-evidence
  path: docs/UNSLOTH-LICENSE-EVIDENCE.md
  notes: Apache core only; studio/ and unsloth_cli/ no-go
- id: legal-closure
  path: docs/LEGAL-CLOSURE.md
  notes: L2-L6, L9, L16 open until T4b evidences
- id: lab-gpu-train-freeze
  path: ../scooling/docs/LAB-GPU-TRAIN-FREEZE.md
  notes: Product GPU shape; scooling-lab-gpu-personal-v1; isolated worker
- id: gpu-worker-stub
  path: src/scooling_lab/gpu_worker.py
  notes: Subprocess isolation; placeholder provenance today
- id: license-policy
  path: src/scooling_lab/license_policy.py
  notes: AGPL path block; allowlist licenses
- id: contracts
  path: src/scooling_lab/contracts.py
  notes: GPU_PRODUCT_MODEL_ID; own:* regex
review_stamp:
  reviewed_at: '2026-08-26T20:25:00Z'
  verdict: pass
  reviewer_mode: agent
  reviewer_model: thinking-high
  reviewer_provider: local
  kit_version: 0.1.0
  artifact_digest: sha256:34671c15c95d537e44099f133814f28968dcc02f41c6db74824198026855cd1c
downstream:
- id: T4b
  model: Auto
  consumes_as_ground_truth: true
  notes: Implement T4-R1–R16; seven-tier; BV pass; CUDA @gpu skip in CI
tier3_gates:
- T1 Merge to Muse/GitHub main outside SD-21 land hygiene
- T2 HF_TOKEN or model weights committed to git
- T3 Import from unsloth studio/ or unsloth_cli/ paths
- T4 Browser-supplied package/artifact paths on HTTP API
- T5 Production deploy with stub worker after T4b claims DONE
```

## Review record

| Round | Reviewer | Verdict | Resolution |
| --- | --- | --- | --- |
| 0 | Thinking (this session) | draft | Freeze authored from ROADMAP T4 + existing contract |
| 1 | `ok check-ok --path` mechanical | **pass** | Stamp written 2026-08-26; digest `sha256:34671c15…` |

---

## 1. Goal

Replace the GPU worker **stub** (content-free provenance hashes only) with a **real Unsloth QLoRA**
fine-tune that writes **loadable adapter files** to an operator-controlled artifact root. The HTTP API
and subprocess isolation boundary **do not change** — only the worker subprocess gains training
runtime deps.

**Definition of Done (T4):** On a CUDA host, an approved `own:*` job with
`modelId: scooling-lab-gpu-personal-v1` and `dryRun: false` completes `succeeded` with adapter files
under `SCOOLING_LAB_ARTIFACT_ROOT/{jobId}/` and provenance `artifactHash` = SHA-256 of the output
tarball bytes (content-free on HTTP responses).

---

## 2. Base model and HF license (L5)

| Field | Value |
| --- | --- |
| **Product `modelId`** (wire) | `scooling-lab-gpu-personal-v1` (unchanged — `contracts.py`) |
| **HF base model** | `unsloth/Llama-3.2-3B-Instruct` |
| **License** | Llama 3.2 Community License — operator accepts on Hugging Face |
| **HF auth** | `HF_TOKEN` env on GPU host only — never in git, HTTP JSON, or logs |
| **Provenance `baseModelId`** | `scooling-lab-gpu-personal-v1` on wire; freeze pins HF id in worker-only config constant `T4_BASE_HF_MODEL_ID` |

T4b must add `NOTICE` row documenting HF model + acceptance URL. T-LEGAL L5 closes when evidenced.

---

## 3. Runtime dependencies (L2, L3, L4, L6)

### 3.1 Allowlisted packages (`requirements.lock`)

Pin exact versions with `# license=… source=… evidence=…` rows. Minimum set:

| Package | Role | License (expected) |
| --- | --- | --- |
| `unsloth` | QLoRA trainer (Apache core paths only) | Apache-2.0 |
| `torch` | GPU backend | BSD-3-Clause |
| `transformers` | Model loading | Apache-2.0 |
| `datasets` | JSONL ingest in worker | Apache-2.0 |
| `peft` | LoRA adapters | Apache-2.0 |
| `trl` | Training helpers (if imported by Unsloth path) | Apache-2.0 |
| `accelerate` | Device placement | Apache-2.0 |
| `bitsandbytes` | QLoRA quant (CUDA) | MIT |

T4b runs `python -m scooling_lab.bom` → `DEPENDENCIES.md`; CI `bom --check` must pass.

### 3.2 Hard blocks (unchanged)

- No import from `studio/*` or `unsloth_cli/*` (AGPL).
- `license_policy.validate_source_path` + security tests remain green.
- Post-install wheel audit log in T4b commit message / `LEGAL-CLOSURE` L6 evidence — no AGPL path
  segments in installed `unsloth` tree.

### 3.3 API container vs GPU worker

- **Dockerfile / Railway API image:** may stay stdlib-only; GPU train runs on **GPU host** (T8) with
  full `requirements.lock` install.
- T4b must not require Unsloth import at API import time — only `gpu_worker` subprocess imports
  training stack.

---

## 4. Package layout (`SCOOLING_LAB_PACKAGE_ROOT`)

Server env only — **never** accepted from HTTP JSON.

```
$SCOOLING_LAB_PACKAGE_ROOT/
  {datasetId}/                 # e.g. own:user123:v1
    manifest.json              # content-free metadata (ids, row count, scope flags)
    train.jsonl                # canonical training bytes (T4 reads this; T5 populates)
```

| Rule | Detail |
| --- | --- |
| **T4 minimum** | Worker reads `train.jsonl` if present; else **fail** job with `failed` (no synthetic train) |
| **`datasetHash` at T4** | Still id-derived stub (`package_dataset_hash`) until T5 — **documented boundary** |
| **T5 upgrade** | Replace with SHA-256 of canonical `train.jsonl` bytes; T4 tests must not assume content hash |
| **Permissions** | Worker process uid only; API never lists package bodies on HTTP |

For T4b local/CUDA dev, tests may seed packages via env root + fixture files in `tests/fixtures/packages/`
(gitignored or synthetic tiny JSONL committed as fixture).

---

## 5. Artifact layout (`SCOOLING_LAB_ARTIFACT_ROOT`)

```
$SCOOLING_LAB_ARTIFACT_ROOT/
  {jobId}/
    adapter/                   # loadable PEFT adapter (config.json, adapters.safetensors, …)
    manifest.json              # jobId, datasetId, modelId, createdAt — no note bodies
    artifact.tar.gz            # tarball hashed for provenance artifactHash
```

| Rule | Detail |
| --- | --- |
| **Write atomicity** | Write to `{jobId}.tmp/` then rename to `{jobId}/` on success |
| **`artifactHash`** | SHA-256 of `artifact.tar.gz` file bytes |
| **HTTP** | Responses carry hashes and ids only — never tarball bytes on list/get job |
| **Download** | Signed URL deferred to T6 — T4 only requires on-disk presence |

---

## 6. Worker behavior (`gpu_worker.py` T4b)

### 6.1 Subprocess boundary (unchanged)

- API spawns `python -m scooling_lab.gpu_worker` with JSON envelope on stdin.
- No in-process GPU fallback.
- Strip callback/webhook/worker_url env keys before spawn (existing).

### 6.2 Training steps (T4b)

1. Validate envelope (existing `execute_gpu_worker_envelope` gates).
2. Resolve package path from `SCOOLING_LAB_PACKAGE_ROOT` + `datasetId`.
3. Load `train.jsonl` — **fail closed** if missing or empty.
4. Run Unsloth QLoRA with bounded params:
   - `epochs`: 1–3 (clamp; default 1)
   - `learningRate`: 1e-5 – 5e-4 (clamp; default 2e-4)
   - `dryRun`: must be `false` (existing)
5. Write adapter to artifact root; build `artifact.tar.gz`.
6. Compute `datasetHash` (id stub at T4), `artifactHash` (tarball), `trainingConfigHash` (existing shape).
7. Emit JSON result on stdout — same keys as today.

### 6.3 Logging (L9, L16)

- Log job id, dataset id, phase, wall seconds, exit code only.
- **Never** log: JSONL lines, prompts, `HF_TOKEN`, filesystem paths from user input, stderr from HF
  containing note text.
- Redirect/transform Hugging Face / Unsloth verbose logs to OFF in worker.

### 6.4 Timeout

- T4 keeps 30s for stub; T4b introduces `SCOOLING_LAB_GPU_TIMEOUT_SECONDS` (default 3600) read only
  in API driver — T8 extends further from pack estimate.

---

## 7. HTTP / contract non-regression

| ID | Rule |
| --- | --- |
| T4-C1 | Wave A `fixture-tiny-llm` + `dryRun: true` unchanged |
| T4-C2 | GPU shape `scooling-lab-gpu-personal-v1` + `dryRun: false` + `own:*` unchanged |
| T4-C3 | No new HTTP fields for paths, URLs, shell, callbacks |
| T4-C4 | Provenance records remain content-free on `GET …/provenance` |
| T4-C5 | Fake worker path unchanged for practice fixture |

---

## 8. CI strategy (no CUDA in default CI)

| Tier | T4b expectation |
| --- | --- |
| unit | Envelope, path policy, param clamps, hash shapes — no torch |
| integration | Subprocess spawn with **stub train mode** env `SCOOLING_LAB_GPU_TRAIN_MODE=stub` for default CI |
| e2e | HTTP job lifecycle with stub train mode |
| stress | Concurrent GPU job submissions (stub mode) |
| data-integrity | Tarball hash stable; package manifest schema |
| performance | Stub mode completes under budget |
| security | No path injection; license policy; log redaction test |
| **@gpu** | Real Unsloth train — `unittest.skipUnless(torch.cuda.is_available())` |

`SCOOLING_LAB_GPU_TRAIN_MODE=real` only on CUDA dev host / T8 — never required in GitHub Actions default
matrix.

---

## 9. Test matrix (T4b deliverables)

| Test module | Change |
| --- | --- |
| `tests/test_gpu_worker.py` | Extend for artifact dir + tarball hash; `@gpu` real train case |
| `tests/test_unit.py` | BOM rows for new deps |
| `tests/test_security.py` | No new HTTP surface for paths |
| Existing T2/T3 suites | Non-regression green |

---

## 10. Legal closure hooks (T4b evidences)

| ID | Evidence |
| --- | --- |
| L2 | `DEPENDENCIES.md` + lockfile |
| L3 | BOM allowlist rows |
| L6 | Wheel path audit log |
| L9 | Worker log review test |
| L16 | Integration test: no JSONL in logs |

---

## 11. Explicit non-goals (T4)

- Vault package ingest (T5)
- Content-based `datasetHash` (T5)
- Artifact download URL (T6)
- Pack credit gate (T-CREDIT)
- Scooling / Knowtation UI (T7, T-KNOW)
- Production GPU deploy lane (T8)

---

## 12. Ground truth citations (file+line discipline)

Downstream T4b and build-verification must cite **file+line** anchors — not re-derive from memory.

| ID | Citation | Notes |
| --- | --- | --- |
| GT-1 | `src/scooling_lab/contracts.py:33` | `GPU_PRODUCT_MODEL_ID` |
| GT-2 | `src/scooling_lab/contracts.py:38` | `OWN_DATA_DATASET_ID_RE` |
| GT-3 | `src/scooling_lab/gpu_worker.py:37-38` | Stub placeholder + 30s timeout |
| GT-4 | `src/scooling_lab/gpu_worker.py:41-50` | Id-only `package_dataset_hash` (T5 replaces) |
| GT-5 | `src/scooling_lab/gpu_worker.py:215-240` | Subprocess isolation — preserve |
| GT-6 | `src/scooling_lab/license_policy.py:33` | `BLOCKED_PATH_SEGMENTS` studio/unsloth_cli |
| GT-7 | `src/scooling_lab/api.py:217` | `SCOOLING_LAB_HOST` env pattern |
| GT-8 | `docs/TRAINING-API-CONTRACT.md:42-49` | GPU model + dryRun false |
| GT-9 | `tests/test_gpu_worker.py:45-50` | GPU shape unit test |
| GT-10 | `tests/scooling_lab_helpers.py:24-28` | Default training params in tests |

---

## 13. Implementation checklist (T4b — do not start until freeze `pass`)

- [ ] T4-R1 Lock `requirements.lock` + regenerate BOM
- [ ] T4-R2 `T4_BASE_HF_MODEL_ID` constant + NOTICE
- [ ] T4-R3 Package root reader + fail-closed missing JSONL
- [ ] T4-R4 Unsloth QLoRA train + adapter write
- [ ] T4-R5 Artifact tarball + `artifactHash` from bytes
- [ ] T4-R6 `SCOOLING_LAB_GPU_TRAIN_MODE` stub/real switch
- [ ] T4-R7 `SCOOLING_LAB_GPU_TIMEOUT_SECONDS`
- [ ] T4-R8 Log redaction tests
- [ ] T4-R9 `@gpu` integration test
- [ ] T4-R10 Update `TRAINING-API-CONTRACT.md` + `LEGAL-CLOSURE` rows
- [ ] T4-R11 ROADMAP T4 → DONE only after BV `pass` on CUDA evidence or `@gpu` green locally
