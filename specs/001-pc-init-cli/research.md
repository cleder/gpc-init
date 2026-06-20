# Research: pc-init CLI Scaffold

## Decision 1: CLI Framework

- Decision: Use `typer` for command definition and argument parsing.
- Rationale: `typer` is already a project dependency and provides typed options, strong help output, and straightforward testability.
- Alternatives considered:
  - `argparse`: standard library but more boilerplate for polished UX.
  - `click`: mature, but `typer` provides better type-driven ergonomics for this codebase.

## Decision 2: Output Generation Model

- Decision: Render `.pre-commit-config.yaml` from deterministic filesystem presets (`lang/<language>/` + optional `framework/<framework>/`), then write with stable ordering.
- Rationale: Uses user-maintained preset folders as the single source of truth while still satisfying deterministic output and minimal extensible profiles.
- Alternatives considered:
  - Hardcoded in-memory profiles: simple bootstrapping but drifts from user-owned preset files.
  - Dynamic remote metadata fetch: flexible but introduces nondeterminism and network dependency.

## Decision 3: Framework Modeling

- Decision: Model frameworks independently from languages; framework primary_languages are informational recommendations and are not validation gates.
- Rationale: Matches clarified behavior where frameworks can be combined with any selected languages while still documenting intended pairings.
- Alternatives considered:
  - Nest frameworks under language profiles: simpler lookup but cannot express cross-language frameworks cleanly.

## Decision 4: Overwrite Behavior

- Decision: Default to no-overwrite; overwrite only when `--force` is present.
- Rationale: Prevents accidental data loss and keeps non-interactive automation predictable.
- Alternatives considered:
  - Interactive prompt: less CI-friendly.
  - Backup and overwrite by default: surprising side effects in existing repos.

## Decision 5: Validation and Quality Gates

- Decision: Enforce TDD workflow with `pytest` and strict static checks with `pyrefly` before merge.
- Rationale: Required by constitution and reduces regressions in profile composition logic.
- Alternatives considered:
  - Relaxed type checking: lower initial friction but weaker correctness guarantees.
