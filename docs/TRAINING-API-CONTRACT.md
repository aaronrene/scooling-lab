# Training API Contract

## Simple Summary

Scooling Lab exposes a small local training contract that only runs a synthetic fake-worker job. It
does not train a model, install Unsloth, use private data, call external workers, or create model
files.

## Routes

- `POST /training/jobs`: `createTrainingJob`.
- `GET /training/jobs/{job_id}`: `getTrainingJob`.
- `POST /training/jobs/{job_id}/cancel`: `cancelTrainingJob`.
- `GET /training/jobs/{job_id}/artifacts`: `listArtifacts`.
- `GET /training/jobs/{job_id}/provenance`: `getProvenance`.
- `DELETE /training/jobs/{job_id}/artifacts/{artifact_id}`: `deleteArtifact`.

## createTrainingJob Request

Allowed fields:

- `idempotencyKey`: safe identifier.
- `datasetId`: must be `fixture:synthetic-tiny-v1`.
- `modelId`: must be `fixture-tiny-llm`.
- `requestedBy`: non-secret caller label.
- `retentionPolicy`: optional bounded `policyClass` and `ttlSeconds`.
- `trainingParameters`: bounded `epochs`, `learningRate`, and `dryRun: true`.

Rejected at schema validation:

- Unknown fields.
- Worker URLs.
- Callback or webhook URLs.
- File paths or model paths.
- Shell strings or command fields.
- Unapproved model ids.
- Non-fixture dataset ids.

## State Machine

| Current | Allowed next states |
| --- | --- |
| `queued` | `running`, `failed`, `cancelled` |
| `running` | `succeeded`, `failed`, `cancelled` |
| `succeeded` | `deleted`; same-state replay is a no-op |
| `failed` | terminal; same-state replay is a no-op |
| `cancelled` | terminal; same-state replay is a no-op |
| `deleted` | terminal tombstone; same-state replay is a no-op |

Cancellation is accepted only from `queued` or `running`. Replaying the same state is idempotent.
Every other transition returns `INVALID_TRANSITION`.

## Provenance Records

Completed fixture jobs emit exactly one provenance record:

- `jobId`.
- `datasetHash`.
- `artifactHash`.
- `baseModelId`.
- `trainingConfigHash`.
- `createdAt`.
- `schemaVersion`.

The schema accepts only hashes, compact ids, and UTC timestamps. Unknown fields, path-like values,
URL-like values, whitespace-bearing free text, prompts, document text, local paths, and token-shaped
payloads are rejected by `scooling_lab.provenance.validate_provenance_record`. CI runs
`python -m scooling_lab.provenance --self-check`.

`listArtifacts` includes `provenanceRecordId`, `retentionPolicy`, and `expiresAt` for each visible
artifact. Deleted or expired artifacts are excluded.

## Retention And Deletion

Retention policy classes are `ephemeral`, `standard`, and `extended`. Each class has bounded TTLs,
and callers may only choose a TTL inside the class range. Expiry is evaluated on artifact, job, and
provenance reads, and can also be evaluated explicitly through the sweep function.

`deleteArtifact` is idempotent. The cascade removes the artifact placeholder, artifact metadata, and
provenance record. The job id remains as a `deleted` tombstone with no request, dataset, model,
training parameter, artifact hash, dataset hash, or provenance fields. Deletion verification checks
that the deleted artifact's hashes are absent from every public and persisted store serialization.

## Safe Error Codes

- `VALIDATION_ERROR`.
- `MALFORMED_JSON`.
- `NOT_FOUND`.
- `INVALID_TRANSITION`.
- `QUEUE_LIMIT_EXCEEDED`.
- `METHOD_NOT_ALLOWED`.
- `CONFLICT`.
- `INTERNAL_ERROR`.

Errors return a stable code and public message only. They do not echo payloads, local paths, stack
traces, worker addresses, or request bodies.

## Fixture Queue And Quota Policy

The fake-worker queue defaults to five queued or running jobs. Duplicate create requests with the
same validated request shape return the same deterministic job id. New jobs beyond the queue limit
return `QUEUE_LIMIT_EXCEEDED`.

## Audit Event Names

The T2 fake contract reserves these audit event names for later durable audit wiring:

- `training.job.create.accepted`.
- `training.job.create.rejected`.
- `training.job.state.transitioned`.
- `training.job.cancel.accepted`.
- `training.job.cancel.rejected`.
- `training.artifact.placeholder.registered`.
- `training.artifact.provenance.recorded`.
- `training.artifact.deleted`.
- `training.artifact.retention.swept`.
- `training.bom.audit.passed`.
- `training.bom.audit.failed`.

## T3: Dataset Review and Job Lifecycle (Slice 7)

### Dataset Registration and Review

Datasets move through a bounded state machine before any job may reference them:

```
registered → pending_review → approved | rejected
```

Only `approved` datasets are eligible for job submission.  Rejection uses a bounded
machine-readable `RejectionReasonCode` enum — no caller-supplied text is ever echoed.

| Route | Method | Handler |
|-------|--------|---------|
| `POST /datasets` | POST | `registerDataset` |
| `POST /datasets/{dataset_id}/submit` | POST | `submitDatasetForReview` |
| `POST /datasets/{dataset_id}/review` | POST | `reviewDataset` |
| `GET /datasets/{dataset_id}` | GET | `getDataset` |

#### `registerDataset` request

```json
{ "datasetId": "fixture:synthetic-tiny-v1" }
```

- `datasetId` must match the safe-identifier pattern `[A-Za-z0-9._:-]{3,96}`.
- Registering an already-approved or already-rejected dataset returns `CONFLICT` (409).

#### `reviewDataset` request

```json
{ "action": "approve" }
{ "action": "reject", "reasonCode": "POLICY_VIOLATION" }
```

- `action` must be `"approve"` or `"reject"`.
- `reasonCode` is required (and only allowed) when `action` is `"reject"`.
- Allowed `reasonCode` values: `SYNTHETIC_LIMIT`, `FORMAT_INVALID`, `POLICY_VIOLATION`,
  `SCHEMA_MISMATCH`, `DUPLICATE_SUBMISSION`.

#### Dataset status response

```json
{
  "datasetId": "fixture:synthetic-tiny-v1",
  "status": "approved",
  "registeredAt": "2026-06-11T00:00:00Z",
  "updatedAt": "2026-06-11T00:01:00Z"
}
```

Rejected datasets also carry `"rejectionReasonCode": "<enum value>"`.

### Job Queue State

`GET /training/queue` returns a content-free snapshot:

```json
{
  "activeCount": 2,
  "maxConcurrentRunning": 1,
  "queueLimit": 5,
  "queuedCount": 1,
  "runningCount": 1
}
```

`maxConcurrentRunning` is the FIFO concurrency bound (default 1).  Jobs beyond
the bound remain `queued` until a running slot is free.

### Dataset Approval Gate

`POST /training/jobs` now enforces:

1. **Schema validation** — `datasetId` must be a safe identifier (format).
2. **Approval check** — the dataset must be in `approved` state in the `DatasetStore`.
   Returns `DATASET_NOT_APPROVED` (HTTP 403) otherwise.

The synthetic fixture dataset `fixture:synthetic-tiny-v1` is pre-approved so all
existing job submission flows are unaffected.

### Retention Integration — Expiry Tombstone Provenance

After TTL expiry (sweep-triggered deletion):

- The job enters `deleted` tombstone state.
- Artifacts and request content are cleared.
- **Provenance is retained** and readable via `GET .../provenance`.
- `GET .../artifacts` returns an empty list.

After explicit `DELETE .../artifacts/{id}`:

- Provenance is wiped (existing Slice-5 behavior preserved).
- `GET .../provenance` returns 404.

### Provenance Failure Safety

If `validate_provenance_record` raises during job completion, the job is
marked `failed` instead of silently succeeding.  No partial or invalid
provenance record is ever stored.

### New Error Code

- `DATASET_NOT_APPROVED` — the dataset referenced in a job creation request has not
  completed the review lifecycle or has been rejected.  Returns HTTP 403.

### Slice 9 Fixture Shapes

The following shapes are stable contract fixtures for the Slice 9 submission UI:

**Dataset registration payload:**
```json
{ "datasetId": "fixture:synthetic-tiny-v1" }
```

**Review approval payload:**
```json
{ "action": "approve" }
```

**Review rejection payload:**
```json
{ "action": "reject", "reasonCode": "POLICY_VIOLATION" }
```

**Queue state response:** see above.

**Job creation with approved dataset:** existing `createTrainingJob` shape unchanged;
the approval gate is transparent when the dataset is pre-approved.

**Unapproved dataset error response:**
```json
{ "error": { "code": "DATASET_NOT_APPROVED", "message": "The dataset has not been approved for job submission." } }
```

**Expiry tombstone with retained provenance:**
```json
{
  "id": "job_...",
  "status": "deleted",
  "createdAt": "...",
  "updatedAt": "...",
  "deletedAt": "..."
}
```
After expiry, `GET .../provenance` returns the full content-free provenance record
(all seven keys: `jobId`, `datasetHash`, `artifactHash`, `baseModelId`,
`trainingConfigHash`, `createdAt`, `schemaVersion`).
