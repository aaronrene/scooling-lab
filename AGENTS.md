# Scooling Lab — agent instructions

Apache-2.0 training workspace for Scooling. Read [`docs/OVERSEER-HANDOVER.md`](docs/OVERSEER-HANDOVER.md) and
[`docs/ROADMAP.md`](docs/ROADMAP.md) first.

## Version control

**Muse is canonical.** GitHub is a mirror only (`muse-mirror` → `main` PR — SD-14).

| Action | Authority |
| --- | --- |
| Muse commit on feature branch | Tier 1 — do it |
| `git push` to feature branch | Tier 1 — backup/share |
| Run tests before commit | Always |
| Update `docs/ROADMAP.md` + `docs/OVERSEER-HANDOVER.md` together | SD-17 — session end |
| Merge to Muse/`main` or GitHub `main` | Tier 3 — stop |

```bash
muse -C ~/scooling-lab status
muse -C ~/scooling-lab code add … && muse -C ~/scooling-lab commit -m "…"
```

Never `git push origin main`. Only `muse-mirror` → `main` after Muse `main` merge.

## Overseer Kit

Phased work runs through the kit — not a parallel hand-rolled protocol.

```bash
~/OVERSEER_KIT/overseer-kit/cli/ok -C ~/scooling-lab status
~/OVERSEER_KIT/overseer-kit/cli/ok -C ~/scooling-lab next
```

Before claiming Overseer is hooked up, `ok status --json` must show `initialized: true`, non-null
`lock.kit_version`, and `footprint_self_integrity.state: ok`.

## Boundaries

- No private Scooling app code, Knowtation vault bodies, or billing internals in this repo.
- No AGPL Unsloth Studio/CLI paths (`studio/`, `unsloth_cli/`).
- No secrets, weights, or browser-supplied paths on the training API.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Seven-tier tests for new slices. GPU integration uses `@gpu` skip without CUDA.
