# Roadmap

## Phase T0: License And Dependency Inventory

- Keep the repository Apache-2.0.
- Maintain a dependency allowlist.
- Block AGPL Studio and CLI components.
- Run tests and secret scans before any remote push.
- Publish the bootstrap repository to GitHub before adding worker dependencies.

## Phase T1: Product And Consent Design

- Define training consent.
- Define dataset preview contracts.
- Define redaction and exclusion rules.
- Define artifact retention and deletion policy.
- Define the server-side Scooling-to-Scooling-Lab authorization envelope.

## Phase T2: Training Job API Contract

- Add job create, status, cancel, and artifact metadata contracts.
- Keep validation server-side.
- Preserve audit metadata without learner-content logs.
- Add content-free fixtures that can be shared with Scooling and Knowtation tests.
- Add content-free provenance records, bounded retention policies, idempotent deletion, and deletion
  verification before private data or real artifacts are allowed.

## Phase T3: Worker Skeleton

- Add an isolated worker process.
- Run only approved dependencies.
- Store artifacts outside the main app database.
- Keep real learner data and private model artifacts out of repository history.
- Keep the fixture worker path dependency-free until the isolation step is accepted.

## Slice 5: Fixture Provenance, Retention, And Deletion

- Emit validated provenance for completed fixture jobs.
- Evaluate retention on access and through explicit sweeps.
- Delete artifact placeholders, metadata, provenance, and job content fields as one cascade.
- Verify deleted artifact hashes are absent from store outputs before private data is allowed.