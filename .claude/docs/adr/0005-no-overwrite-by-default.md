# 0005: Existing output is never overwritten without `--force`

## Status

Accepted

## Context

Running `pc-init` in a repository that already has a `.pre-commit-config.yaml` risks destroying hand-maintained configuration.
The tool is used both interactively and in scripts and CI.

## Decision

- If the output file exists, `pc-init` leaves it untouched unless `--force` is given.
- It does not prompt.
  Behaviour must be identical interactively and in automation.
- Without `--force`, it prints a unified diff between the existing file and the generated config, exits with code 1, and prints a ready-to-run command ending in `--force`.
- If the existing file already matches the generated config, it says so and exits 0.
- With `--force`, the file is overwritten.

## Alternatives considered

- **Interactive confirmation.**
  Friendlier at a terminal, but hangs or fails in CI.
- **Back up and overwrite by default.**
  Leaves surprise files behind and still replaces the user's config unasked.

## Consequences

- Re-running is safe by default, and the diff doubles as a preview of what would change.
- A recommendation hint reuses the same mechanism: its suggested command ends in `--force` because it rewrites the file the current run just wrote.
