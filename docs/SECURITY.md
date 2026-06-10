# Security

Scooling Lab is a training boundary, not the authority for private learner data.

## Rules

- Accept only server-side jobs from the main Scooling app or an approved local test harness.
- Never accept browser session tokens.
- Never write directly to Knowtation.
- Never store private vault data in this repository.
- Never commit checkpoints, adapters, model exports, private datasets, logs with learner content, or
  credentials.
- Keep worker logs content-free by default.
- Treat dependency and license scans as release gates.

## Reporting

Do not file public issues containing private learner data, credentials, model artifacts, or
deployment details. Use the private Scooling security channel until a public reporting address is
published.
