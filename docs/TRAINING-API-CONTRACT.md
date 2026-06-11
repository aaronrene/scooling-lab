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

## createTrainingJob Request

Allowed fields:

- `idempotencyKey`: safe identifier.
- `datasetId`: must be `fixture:synthetic-tiny-v1`.
- `modelId`: must be `fixture-tiny-llm`.
- `requestedBy`: non-secret caller label.
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
| `succeeded` | terminal; same-state replay is a no-op |
| `failed` | terminal; same-state replay is a no-op |
| `cancelled` | terminal; same-state replay is a no-op |

Cancellation is accepted only from `queued` or `running`. Replaying the same state is idempotent.
Every other transition returns `INVALID_TRANSITION`.

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
- `training.bom.audit.passed`.
- `training.bom.audit.failed`.
