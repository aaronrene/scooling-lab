# Cross-Repo Status

## Simple Summary

Scooling is not blocked as a whole.

The live MuseHub staging repository and the future MuseHub Knowtation-domain path are still blockers
for the final provenance/versioning lane, but product work can continue in three coordinated tracks:

- Scooling: user-facing flows, consent, review gates, billing/credit decisions, and adapter contracts.
- Knowtation: private memory, imports, hosted/self-hosted Hub, MCP/REST surfaces, vault permissions,
  and proposal/write-back authority.
- Scooling Lab: open-source training workspace, dependency policy, training API contract, worker
  skeleton, license evidence, and artifact boundary.

## Current Repo Roles

### Scooling

Scooling is the product surface. It should keep owning:

- login and user session flow
- workspace and classroom/product permissions
- consent and dataset review
- billing and training-credit reservation
- model lane selection and policy display
- proposal review before durable writes
- artifact registration metadata

Scooling should not become the memory system, parser, vault authority, training worker, or MuseHub
domain implementation.

### Knowtation

Knowtation is the source of truth for private memory and document authority. It should keep owning:

- vault isolation
- note search, note reads, and import pipelines
- section/source parsing policy
- proposals and write-back review
- hosted/self-hosted Hub behavior
- hosted MCP and REST parity where approved
- memory consolidation and deletion/export/retention controls

Scooling consumes Knowtation through reviewed adapters. It must not bypass Knowtation authorization
or expose private body/snippet content outside an approved context.

### Scooling Lab

Scooling Lab is the open-source training boundary. It should own:

- Apache-compatible dependency inventory
- training job request/status/cancel contracts
- isolated worker runtime
- content-free logs
- training artifact metadata
- license notices and dependency evidence
- tests proving AGPL Studio/CLI components are not bundled into the main product

Scooling Lab starts with no private data path and no trainer implementation.

## What Is Blocked

- Direct `muse push staging` for the main Scooling repo until `aaronrene/scooling` exists or
  permissions are repaired on MuseHub staging.
- Production dependence on MuseHub-backed Scooling provenance until that remote path is verified.
- Production dependence on a MuseHub Knowtation-domain target until the exact domain plugin behavior
  is smoke-tested and accepted.
- Real private-data training jobs until Scooling Lab completes license inventory, consent design,
  dataset review, billing/credit reservation, and artifact retention/deletion gates.

## What Can Continue Now

- Scooling UI and product contract work, merged through local Muse `main` and GitHub `muse-mirror`.
- Scooling setup, import, consent, review, billing, and model-runtime adapter surfaces as preview or
  gated flows.
- Knowtation hosted/self-hosted import, search, note, proposal, auth, and billing/gateway work.
- Scooling Lab T0/T1/T2 work: dependency policy, training consent design, dataset preview contract,
  and API boundary tests.
- Cross-repo fixtures that prove Scooling cannot bypass Knowtation permissions.

## Work That Must Be Tested Together

- Scooling login identity mapped to Knowtation vault scope.
- Scooling workspace policy mapped to Knowtation read/proposal rights.
- Import and dataset preview flows from Scooling into Knowtation-owned documents.
- Proposal/write-back review before durable Knowtation changes.
- Billing or training-credit reservation before Scooling Lab jobs.
- Artifact metadata registration after Scooling Lab jobs.
- Deletion/export/retention behavior across Knowtation, Scooling, and Scooling Lab.
- Model runtime routing with private-data consent and cloud/local policy.

## Recommended Next Build Order

1. Keep Scooling Lab public and small: finish Phase T0 dependency/license inventory.
2. Define Scooling Lab T1 consent and dataset preview contracts before any worker can train.
3. Continue Knowtation hosted/self-hosted parity and vault-permission hardening.
4. Add Scooling adapter contracts that call Scooling Lab only from the server side.
5. Add cross-repo integration fixtures with content-free sample datasets.
6. Defer live MuseHub staging/provenance reliance until remote repo and domain-plugin behavior are
   verified.

## Current Remote Policy

For Scooling, the active source-control flow remains:

```text
local Muse feature branch
  -> local Muse main
  -> Git muse-mirror branch
  -> GitHub PR to main
  -> deployment only after separate authorization
```

For Scooling Lab, create a public GitHub repository first, then mirror/push to MuseHub when the
target repository is available and authenticated.
