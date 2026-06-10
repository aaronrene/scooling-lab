# Dependency Policy

Scooling Lab starts with an Apache-compatible worker boundary.

Allowed licenses for Phase T0:

- Apache-2.0
- MIT
- BSD-2-Clause
- BSD-3-Clause

Blocked components:

- AGPL-covered Studio code
- AGPL-covered CLI code
- copied vendor UI assets
- private Scooling application code
- private datasets, model artifacts, credentials, and local vault data

Every training dependency must have a recorded version, source URL, license identifier, and evidence
path before it can be used by a worker image.
