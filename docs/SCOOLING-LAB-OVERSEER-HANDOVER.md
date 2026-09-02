# Scooling Lab Overseer Handover — `scooling-lab`

**Living relay for Scooling Lab (the training engine).** Paste the **NEXT SESSION** block into a
fresh chat.

**This file governs `~/scooling-lab` only.** The Scooling app (`~/scooling`) keeps its own separate
`docs/OVERSEER-HANDOVER.md`. Renamed from `docs/OVERSEER-HANDOVER.md` on 2026-08-27 so the two can
never be mistaken for each other again. The final name is the Overseer Kit convention
(`<REPO-SLUG>-OVERSEER-HANDOVER.md`), which is why `ok` and the multi-repo workspace board resolve
it without extra configuration.

**Regime:** muse+git-mirror (Muse canonical; Muse `main` `@aa4b5c2e`)  
**Overseer Kit:** **INSTALLED and verified here (2026-08-27).** `ok -C ~/scooling-lab status --json` returns `initialized: true`, `lock.kit_version: "0.1.0"`, `footprint_self_integrity.state: "ok"`, `vcs.regime: "muse+git-mirror"`, `drift.status: "current"`. Installed with `ok init --migrate` so the two living docs below were **preserved**, not scaffolded over (SHA-256 verified identical across the install). One open warning: `governance_freshness: drifted` — see open items.  
**Constellation:** `scooling-stack` (product order: `~/scooling`)  
**Product surfaces:** Scooling, Knowtation, YouTube train paths queue after T6 in this repo.

## Repo boundary — read before touching anything

| Track | Repo that owns it | Governance docs to update |
| --- | --- | --- |
| **T4 / T5 / T6 / T8** Lab trainer, package ingest API, artifact storage, GPU lane | **`~/scooling-lab`** (this repo) | these docs |
| **T7 SCOOLING-TRAIN-UI** — vault picker, Hub export, ingest call, credit quote, job poll, download | **`~/scooling`** | `~/scooling/docs/{ROADMAP,OVERSEER-HANDOVER}.md` |
| **RHF RETAIL-HELPER-FINISH** — Codex helper on Home Start + My Work Send | **`~/scooling` only** | `~/scooling` docs only |

**RHF is not a Lab phase.** It shares the `~/scooling` repo (and therefore that repo's two
governance docs) with T7, which is why the Scooling roadmap now shows T7 **PARKED** behind RHF.
Nothing about RHF touches `~/scooling-lab`: verified 2026-08-27, zero RHF/Codex references in this
repo's own sources or docs. The training track is **T4→T5→T6→T-CREDIT→T7**; that is the work this
handover governs.

### Cross-repo work — label it every time

Any phase whose work happens outside this repo **must** say so in three places: the NEXT SESSION
heading, the step table's **Repo** row, and the paste-ready prompt's `Repo:` line. T7 below is the
worked example. A session that cannot tell which repo it is in should stop and re-read this table.

---

## Mandatory gates — no work starts or closes without them

**Operator standing instruction (2026-08-27): no build work without a freeze review, and no phase
marked DONE without a build verification.** Both gates, every phase, no exceptions in this repo.

| Gate | When | Command | Hard rule |
| --- | --- | --- | --- |
| **1. Freeze review** | **Before** any Auto build starts | `/freeze-review-loop` (thinking-high) on the `frozen: true` spec | **Do not start Auto** until the verdict is **`pass`** |
| **2. Build verification** | **After** Auto claims done, **before** DONE | `/build-verification-review` (thinking-high, independent verifier) | **Do not mark DONE** until the verdict is **`pass`** |

Rules that have already been broken once and must not be again:

- **Green tests are not DONE.** T7b had 17 passing tests and still failed BV round 1.
- **"Green" means the whole repo.** Name the command and the scope. A passing subset is not a
  passing suite — T7b's `pnpm test` failed 6 tests and `pnpm typecheck` failed while being reported
  as green.
- **Never claim a runtime fact you did not just verify.** This file once claimed the Overseer Kit
  was installed here on 2026-08-26 when `.overseer/config.yaml` did not exist — the install only
  actually happened on 2026-08-27. Quote the command and its decisive output fields, or write
  *unverified*.
- **A `findings` verdict means a fix round**, not a re-review. Fix the cited `path:line` items only,
  re-run the gate.
- **Both governance docs move together** in the closing commit: `docs/SCOOLING-LAB-ROADMAP.md` +
  `docs/SCOOLING-LAB-OVERSEER-HANDOVER.md`.

**Gap closed 2026-08-27:** the mechanical `ok` gates (`ok review --freeze`, `ok check-ok`,
`ok status`, `ok governance-sync`) now run **in this repo** — the kit was previously missing here and
both gates depended on skills invoked from `~/scooling`. *(An earlier version of this note said
`ok status` reports `governance_gates.active_phases: ["T7b fix round 1"]`. That phase is closed —
T7 landed 2026-09-02 — and the NEXT block below no longer declares it.)*

---

<!-- overseer:next role=primary lane=product status=live -->
## NEXT SESSION — Lab after T7 consumer land (PRIMARY in **`~/scooling-lab`**)

**Date:** 2026-09-02  
**Current position:** Scooling **T7 LANDED** (row 28 / GitHub [#354](https://github.com/aaronrene/scooling/pull/354)).
Lab API **T4–T6 DONE**; **T-CREDIT built but BV not recorded** (row corrected 2026-09-02 — it is not
DONE without a build-verification `pass`). This repo's stale "T7b fix round" PRIMARY is **SUPERSEDED**.
Tests re-run this session: **160 passed + 1 `@gpu` skip**, exit 0.
**Model:** **Thinking** (T6 prod durability — option A below)

**Why durability first:** T6 shipped correct artifact-storage code onto storage that does not
survive a restart. There is no Railway Volume at `/data` and no S3/R2, so a redeploy wipes stored
artifacts. Everything downstream (T8 GPU, theBRAIN **E4** Export to Edge) inherits that gap.

### THE ONE NEXT STEP — **Model: Operator** (choose Lab next)

| Option | What | Model |
| --- | --- | --- |
| **A (recommended)** | **T6 prod durability** — Railway Volume `/data` or S3/R2 so redeploy does not wipe artifacts | Thinking → Auto |
| **B** | **T8 GPU deployment lane** — long-running worker queue (CUDA `@gpu` before claiming prod GPU) | Thinking → Auto |
| **C** | **T-YT / T-KNOW** — only after Operator orders finish-line export surfaces | Thinking → Auto |

**Not blocked on Gabriel msign.** Lab can advance while MuseHub social identity is pending.

### Paste-ready prompt — T6 durability Thinking (default)

```text
Scooling Lab — T6 prod durability Thinking freeze

Repo: ~/scooling-lab · Model: Thinking
Branch: feat/t6-prod-durability-a (create at start)

Prior: T6 code DONE; T7 consumer LANDED on Scooling. Redeploy still wipes disk without
Volume/S3. Do not claim T8 CUDA prod.

Do:
  1. Freeze WHAT/HOW for durable artifact + job store (Volume vs S3/R2; fail-closed)
  2. /freeze-review-loop → pass
  3. Update SCOOLING-LAB-ROADMAP + SCOOLING-LAB-OVERSEER-HANDOVER; Muse commit on feature branch

Do not: invent T7 work in this repo · Netlify Scooling env flip · feature→GitHub-main

Model: Thinking
Authority: SCOOLING-LAB-ROADMAP T6 durability
```

### Archived — T7b fix round (SUPERSEDED 2026-09-02)

T7 fixed + Muse-landed in `~/scooling`. Do **not** paste the old BV findings fix prompt.

---

### Operator update (2026-08-27) — T7 status sync

| Phase | Status |
| --- | --- |
| T7a Thinking freeze | **DONE** — `~/scooling/docs/T7-SCOOLING-TRAIN-UI-FREEZE.md`, freeze-review **`pass`** |
| T-CREDIT (Scooling) | **On branch** — landed in `feat/t7-scooling-train-ui` (`aadcc5d1`). Note: this commit caused BV3. |
| T7b Auto (Scooling UI + export→ingest→job) | **IMPLEMENTED, BV r1 `findings`** — commit `5f1bc255`; fix round required |
| T7 (this repo) | Lab T5/T6 contract consumed; **product train path is NOT live** — do not claim it |

**Archived below:** T7a Thinking paste (do not use).

### Paste-ready prompt — T7a (ARCHIVED — do not use)

```
Phase T7a — Scooling train UI + backend freeze (vault export, package ingest, job polling).

Model: Thinking
Repo: ~/scooling (primary); scooling-lab API contract
Authority: ~/scooling/docs/ROADMAP.md T7

Deliverables: freeze spec for vault scope picker, server-side export→package→job flow, credit quote UI, artifact download.
```

---

## ARCHIVED — T-CREDIT Pack Credits (DONE pending BV)

**Date:** 2026-08-26  
**Model:** Auto

### Paste-ready prompt — T-CREDIT (archived)

```
Phase T-CREDIT — Muse Hub pack credit measure, reserve, debit, refund (scooling + Hub).
Model: Auto — DONE 2026-08-26 on feat/t-credit-pack-reserve. BV pending.
```

### Straight talk — T6 production durability (operator, not optional at finish-line)

T6 **code** is shipped and `curl https://lab.scool.ing/training/queue` is healthy.

**What is not finish-line yet:** Railway has **no persistent volume** attached. Job state
(`SCOOLING_LAB_STATE_PATH`), training packages, and artifact files are written to the
container filesystem under `/data/...`. When Railway **redeploys or replaces the container**
(new deploy, crash recovery, plan change), that filesystem is **wiped**.

| If Railway redeploys | What you lose |
| --- | --- |
| Job queue + statuses | Yes — in-memory of “who was training” resets |
| Completed job metadata on disk | Yes |
| Adapter tarballs on volume storage | Yes |
| Provenance in API after wipe | Depends — gone if only on local disk |

That is **not** “restart-survivable,” which is T6’s production definition of done. The API
working today does **not** mean durable storage is done. Close this before claiming T6
production-complete:

1. **Preferred:** Railway **Volume** mounted at `/data` (upgrade plan if UI has no Volumes), **or**
2. **Equivalent:** `SCOOLING_LAB_ARTIFACT_STORAGE_BACKEND=s3` or `r2` + durable state path on
   attached volume or object store.

Until then: Lab is **operational for smoke/tests**; **not** finish-line for production durability.
Track as **T6 operator closeout** (can run parallel to T-CREDIT; does not block starting T-CREDIT).

### Operator notes (2026-08-26 evening)

- T6 merged to GitHub `main` via PR #10 (`muse-mirror`); PR #9 closed.
- Railway crash was **service-level env vars** missing (project shared vars ≠ injected).
- Fix: vars on **scooling-lab → Variables**; deploy successful; queue endpoint green.
- `SCOOLING_LAB_GPU_TRAIN_MODE=stub` on Railway — real CUDA weights are **T8** (RunPod recommended).

### What just landed (T6 code)

| Slice | Deliverable |
| --- | --- |
| T6 | `SCOOLING_LAB_STATE_PATH` required in production |
| T6 | Volume / S3 / R2 artifact upload after GPU train |
| T6 | `GET .../artifacts/{id}/download` — server JWT → signed URL |
| T6 | Retention sweep deletes object storage + metadata |
| T6 | Seven-tier `test_t6_artifact_storage.py`; BV **`pass`** |

---

### Paste-ready prompt (archived — T6 Auto)

```
Phase T6 — Artifact object storage + durable job store (scooling-lab).

Model: Auto
Status: DONE (code + BV pass 2026-08-26); Lab live at lab.scool.ing.
Operator open: persistent volume or S3/R2 for restart-survivable prod (see handover).
Evidence: docs/reviews/2026-08-26-t6-artifact-storage-bv-pass.md
```

---

## Build order (confirmed — no skips)

| Order | Phase | Repo |
| --- | --- | --- |
| 1 | T4 Real trainer | scooling-lab — **DONE** |
| 2 | T5 Vault package ingest | scooling-lab — **DONE** |
| 3 | T6 Artifacts + durable state (code) | scooling-lab — **DONE** |
| 3b | T6 prod durability (volume/S3) | scooling-lab infra — **OPEN** |
| 4 | **T-CREDIT** Pack measure / reserve / debit | **scooling + Muse Hub — DONE (BV pending)** |
| 5 | **T7** Scooling train UI + backend | **scooling — b IMPLEMENTED; BV r1 `findings`; fix round open** |
| 6 | T-KNOW Knowtation train path | knowtation + scooling-lab |
| 7 | T-YT YouTube vault scope in export | scooling |
| 8 | T8 GPU deploy lane (real CUDA, RunPod) | scooling-lab infra |
| 9 | T-POLICY Consent + scope + auth envelope | scooling |
| 10 | T-LEGAL Close LEGAL-CLOSURE.md | scooling-lab + scooling |
| 11 | T9 E2E all surfaces; stub inventory zero | all |

---

## Verified snapshot (2026-09-02)

| Item | Value |
| --- | --- |
| Repo | `scooling-lab` |
| Muse branch | `feat/docs-t7-landed-sync` — **5 commits ahead of Muse `main`** (`aa4b5c2e`), not merged |
| Git branch | **`muse-mirror`** @ `c4eace1` — see the branch-hygiene warning below |
| GitHub `main` | `ecf22e1` (PR #10 merged) — **1 commit ahead of the git checkout** |
| Lab URL | `https://lab.scool.ing/` — queue endpoint green per operator 2026-08-26. **Not re-verified 2026-09-02** |
| Overseer Kit | **Installed and live** — re-verified 2026-09-02: `initialized: true`, `lock.kit_version: "0.1.0"`, `footprint_self_integrity.state: "ok"`. *(The old "NOT installed" line here predated the 2026-08-27 `ok init --migrate` and was stale.)* |
| T6 BV | **`pass`** — `docs/reviews/2026-08-26-t6-artifact-storage-bv-pass.md` |
| T4b BV | **`pass` claimed but no artifact on disk** — only T5 and T6 files exist under `docs/reviews/`. Either file the T4b artifact or restate the row |
| Tests | **160 passed + 1 `@gpu` skip = 161**, exit 0 — **re-run 2026-09-02** (~28s) |
| T6 prod durability | **OPEN** — no Railway Volume, no S3/R2; redeploy wipes `/data` state |
| GPU train mode (Railway) | `stub` — real weights **T8** |
| Pack credits | **T-CREDIT built 2026-08-26; BV not recorded** — the roadmap row previously read DONE and has been corrected |
| Products | Scooling **T7 LANDED** 2026-09-02 ([#354](https://github.com/aaronrene/scooling/pull/354), BV r2+r3 pass). The "T7b BV r1 findings / fix round open" text elsewhere in this file is **superseded** |
| Constellation | Scooling PRIMARY = row **42 SC-BRAIN-LIVE-1a** (theBRAIN auth seam). Lab is not blocked by Gabriel/MuseHub and does not block that chapter. theBRAIN **E4** depends on Lab GGUF export, downstream of **T8** |

### Branch hygiene warning (2026-09-02)

Two things are out of shape and should be settled before the next Auto row:

1. **Git is checked out on `muse-mirror`**, which is the *export* branch. Per SD-14 and
   `.overseer/config.yaml`, work belongs on a Muse feature branch; `muse-mirror` exists only to
   carry Muse → GitHub. Working there risks an inverted land.
2. **The doc rename never left Muse.** `docs/SCOOLING-LAB-ROADMAP.md` and
   `docs/SCOOLING-LAB-OVERSEER-HANDOVER.md` — the kit-configured living docs — are **untracked in
   git**, while git HEAD still tracks the old `docs/ROADMAP.md` / `docs/OVERSEER-HANDOVER.md` as
   deleted. The rename was committed in **Muse** on `feat/docs-t7-landed-sync` (`f9871af9`,
   2026-08-27) and never merged to Muse `main` or mirrored. Until it lands, GitHub shows the old
   names and this file does not exist there.

Neither is data loss — the content is on disk and in Muse history. Both need an operator-authorized
Muse `main` merge (Tier 3) followed by the normal bridge to `muse-mirror`.

### Governance gates checklist

- [x] **Overseer Kit installed** — **2026-08-27** (the earlier "2026-08-26" entry here was false;
      `.overseer/config.yaml` did not exist until the 2026-08-27 `ok init --migrate`)
- [x] **T4a freeze** — `docs/T4-TRAINER-SPEC.md` + `ok check-ok` **`pass`**
- [x] **T4b build** — `/build-verification-review` **`pass`** (2026-08-26)
- [x] **T5 build** — `/build-verification-review` **`pass`** (2026-08-26)
- [x] **T6 build** — `/build-verification-review` **`pass`** (2026-08-26)
- [ ] **T6 prod durability** — Railway Volume `/data` or S3/R2 (operator)
- [ ] **CUDA `@gpu`** — T8 (RunPod or equivalent)
- [x] **Install Overseer Kit in this repo** — done 2026-08-27; mechanical gates
      (`ok review --freeze`, `ok check-ok`, `ok status`, `ok governance-sync`) now run here
- [ ] **`ok governance-sync`** — `ok status` reports `governance_freshness: drifted` (D1/D2). The
      dry-run plan also wants to realign 10 commits, so an operator should review the plan before
      applying it. Command: `ok governance-sync --dry-run`, then apply only if the plan is correct.

---

## Finish-line checklist (master)

- [x] **T4** Real Unsloth train → adapter files (build); CUDA verify before production
- [x] **T5** Vault package ingest + content hash (Lab); Scooling export → T7
- [x] **T6** Code: object storage + download + state path contract
- [ ] **T6** Prod: restart-survivable storage (volume or S3/R2 on Railway)
- [ ] **T-CREDIT** Muse Hub pack measure / reserve / debit / refund — **built 2026-08-26; BV not recorded** (unchecked: a row without a BV `pass` is not DONE)
- [x] **T7** Scooling UI + backend train flow — **LANDED 2026-09-02** ([#354](https://github.com/aaronrene/scooling/pull/354); BV r2+r3 `pass`). No T7 production smoke claimed
- [ ] **T-KNOW** Knowtation vault export + train
- [ ] **T-YT** YouTube vault items in training scope
- [ ] **T8** GPU deploy + real train (`SCOOLING_LAB_GPU_TRAIN_MODE=real`)
- [ ] **T-POLICY** Consent + scope + server auth envelope
- [ ] **T-LEGAL** Every `LEGAL-CLOSURE.md` row DONE with evidence
- [ ] **T9** E2E all surfaces; stub inventory zero

---

## VCS

| Branch | Purpose | PR |
| --- | --- | --- |
| `main` | Stable contract + tests; Muse canonical | PR #10 merged |
| `feat/t6-artifact-storage` | T6 feature lineage | PR #9 closed (superseded) |

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
| 2026-08-26 | **T6 DONE** — artifact storage code, 161 tests, BV pass; PR #10 merged |
| 2026-08-26 | **Lab live** — Railway service vars fixed; queue green; T6 prod volume **OPEN** |
| 2026-08-26 | **NEXT** — T-CREDIT (scooling + Hub); then T7; T8 real GPU after T7 |
| 2026-08-27 | **T7b BV round 1 `findings`** — recorded honestly; corrected the prior "seven-tier green / typecheck green" claim; NEXT is a fix round in `~/scooling`, not a re-review |
| 2026-08-27 | **Repo boundary section added** — RHF (Codex retail helper) is `~/scooling`-only and never entered this repo (verified); T7 UI is `~/scooling`, Lab API is here |
| 2026-08-27 | **Corrected false kit claim** — `.overseer/config.yaml` is missing in this repo; kit is live in `~/scooling` only |
| 2026-08-27 | **Renamed** `docs/OVERSEER-HANDOVER.md` → `docs/SCOOLING-LAB-OVERSEER-HANDOVER.md` and `docs/ROADMAP.md` → `docs/SCOOLING-LAB-ROADMAP.md` (kit `<REPO-SLUG>-` convention, so `ok` and the workspace board resolve them); all in-repo references updated; `docs/HANDOVER.md` retired to a pointer stub. One repo, one relay, unambiguous name. |
| 2026-08-27 | **Overseer Kit installed here** — `ok init --migrate --regime muse+git-mirror` (v0.1.0). Living docs preserved (SHA-256 identical). Verified: `initialized: true`, `lock.kit_version: 0.1.0`, `footprint_self_integrity.state: ok`. Seeded `.cursor/rules`, `.cursor/skills`, `.claude/skills`, `.overseer/policy`, `docs/CROSS-REPO-COORDINATION.md`. Open: `governance_freshness: drifted`. |
| 2026-08-27 | **Mandatory gates section added** (operator instruction): no Auto build without freeze-review `pass`; no DONE without build-verification `pass`. Kit install logged as the open item that restores the mechanical gates. |
