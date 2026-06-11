# Legal Review Checklist

## Simple Summary

No private learner data or paid GPU work can enter Scooling Lab until legal, security, dependency, and
data controls are reviewed and accepted.

## Pre-Private-Data Checklist

- Confirm the repository license and distribution model for Scooling Lab.
- Confirm every runtime dependency is listed in `DEPENDENCIES.md`.
- Confirm every runtime dependency license is allowlisted or separately approved.
- Confirm no AGPL-covered Studio or CLI path is imported, copied, bundled, or exposed.
- Confirm dataset consent, scope, retention, export, and deletion policies are approved.
- Confirm the API rejects browser-supplied worker URLs, callback URLs, shell commands, file paths, and
  unapproved model ids.
- Confirm logs exclude prompt bodies, private notes, secrets, tokens, local paths, and raw payloads.
- Confirm artifact retention and deletion rules are written and tested.
- Confirm incident response ownership before any private-data pilot.

## Pre-Paid-GPU Checklist

- Confirm payer-visible cost policy and spending caps.
- Confirm quota and replay controls for duplicate jobs.
- Confirm cancellation and cleanup behavior before work starts.
- Confirm GPU credentials are environment-scoped and not shared with the browser.
- Confirm network egress rules are allowlisted.
- Confirm no private data reaches test fixtures, logs, telemetry, or artifacts.
- Confirm generated model artifacts have provenance, retention, deletion, and export records.
- Confirm legal approval covers the exact package versions, model licenses, data sources, and
  deployment lane.

## Required Seven-Tier Evidence

- Unit tests for schema, state, license, and error decisions.
- Integration tests for API-to-worker and BOM generation.
- End-to-end tests for fixture job completion and artifact listing.
- Stress tests for deterministic duplicate creation and queue limits.
- Data-integrity tests for stable ids, stable hashes, restart persistence, and Unsloth evidence.
- Performance tests for bounded status/list endpoints and BOM runtime.
- Security tests for path traversal, command injection, URL injection, secret scanning, and AGPL path
  blocking.
