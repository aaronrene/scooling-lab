# Build verification — T6 artifact storage (round 1 pass)

**Date:** 2026-08-26  
**Phase:** T6 Auto — artifact object storage + durable job store  
**Frozen authority:** `docs/ROADMAP.md` T6  
**Verdict:** **`pass`**

## Deliverable checklist

| # | Deliverable | Evidence |
| --- | --- | --- |
| D1 | Require `SCOOLING_LAB_STATE_PATH` in production | `runtime_config.py`; `api.main()` |
| D2 | Upload adapter tarball to object storage (volume / S3 / R2) | `artifact_storage.py`; `service._upload_artifacts_for_job` |
| D3 | `GET .../artifacts/{id}/download` — signed URL, server auth only | `api.py` download route; `download_auth.py` |
| D4 | Retention sweep deletes storage + metadata | `store.sweep_expired` + `on_storage_delete` callback |
| D5 | Seven-tier tests; `TRAINING-API-CONTRACT.md` updated | `tests/test_t6_artifact_storage.py`; docs diff |
| D6 | Durable state reload | `test_integration_job_store_survives_restart` |

## Verification checklist

| # | Check | Result |
| --- | --- | --- |
| V1 | Frozen deliverables exist | pass |
| V2 | APIs match spec (auth, signed URL, fail-closed) | pass |
| V3 | Tests cover upload, download, sweep, production gate | pass |
| V4 | No scope creep beyond T6 | pass |
| V5 | No frozen requirements deleted | pass |
| V6 | Governance docs updated with T6 DONE | pass |
| V7 | No secrets in diff; storage paths not on public wire | pass |

## Evidence

| type | sha256 | ref | notes |
| --- | --- | --- | --- |
| test_output | `e9d0cd2184fd59250b8708d994106bd29e5800c9a4cb821f2c56363b365b4569` | `PYTHONPATH=src python3 -m unittest discover -s tests` | 161 tests OK, 1 `@gpu` skip |

## Findings

None.
