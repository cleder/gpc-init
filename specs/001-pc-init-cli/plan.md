# Implementation Plan: pc-init CLI Scaffold

**Branch**: `001-pc-init-cli` | **Date**: 2026-06-20 | **Spec**: `specs/001-pc-init-cli/spec.md`

**Input**: Feature specification from `/specs/001-pc-init-cli/spec.md`

## Summary

Build a deterministic Python CLI tool, `pc-init`, that generates `.pre-commit-config.yaml` from one or more `--lang` values and optional repeatable `--framework` values.
Frameworks are modeled independently from languages and may declare optional `primary_languages` for informational guidance.
The tool must enforce safe overwrite behavior (`--force` required), emit actionable errors, and satisfy TDD (`pytest`) plus strict typing (`pyrefly`) gates.
Baselines are loaded from filesystem presets: `lang/<language>/` for language profiles and `framework/<framework>/` for framework profiles.

## Technical Context

**Language/Version**: Python >= 3.14

**Primary Dependencies**: `typer` for CLI, `PyYAML` for preset parsing/rendering, standard library for file IO and path resolution

**Storage**: File output only (`.pre-commit-config.yaml`); no database

**Testing**: `pytest` (red-green-refactor), with focused unit and integration CLI tests

**Target Platform**: Cross-platform CLI (Linux/macOS/Windows), developed on Linux

**Project Type**: Single-project CLI utility

**Performance Goals**:

- Generate output for any supported profile in < 200 ms on a developer machine
- Keep runtime memory under 50 MB for generation path

**Constraints**:

- Deterministic output for identical inputs and version
- No network dependency at generation time
- Non-interactive overwrite policy (`--force`)
- Strict `pyrefly` must pass before merge
- Preset resolution must use local filesystem folders under `lang/` and `framework/`

**Scale/Scope**:

- Initial language profiles: Python, JavaScript, Go, Rust
- Initial framework profiles: React, Bevy
- Extensible profile catalogs for future additions

## Constitution Check

*GATE: Must pass before Phase 0 research.*
*Re-check after Phase 1 design.*

### Pre-Research Gate

- [x] Feature scope directly improves CLI-driven `.pre-commit-config.yaml` generation.
- [x] Configuration generation is deterministic for identical inputs.
- [x] TDD plan defined: tests are written first with `pytest` (red-green-refactor).
- [x] Strict type-safety plan defined: `pyrefly` (strictest settings) passes.
- [x] Proposed stack/profile additions are minimal and justified by quality value.

### Post-Design Re-Check

- [x] `research.md` selects deterministic filesystem presets and non-interactive overwrite behavior.
- [x] `data-model.md` captures language/framework independence with optional primary-language recommendations.
- [x] `contracts/cli-contract.md` defines actionable errors and deterministic guarantees.
- [x] `quickstart.md` includes `pytest` and strict `pyrefly` quality gates.

## Loader & Merge Design

### Preset Discovery

- Common preset source: `lang/common/default.yaml` (if present)
- Language preset source: `lang/<lang>/baseline.yaml`
- Framework preset source: `framework/<framework>/preset.yaml` (optional)

### Merge Order (lowest to highest precedence)

1. Common preset
2. Language presets in CLI input order
3. Framework presets in CLI input order

### Merge Semantics

- Top-level `repos` entries merge by `(repo, rev)` key.
- If a `(repo, rev)` pair exists in multiple layers, hooks are merged by hook `id`:
  - preserve first-seen order from lower-precedence layer
  - append new hook ids from higher-precedence layer
  - when same hook id appears again, higher-precedence definition replaces fields while retaining position
- Top-level mapping keys (for example `default_language_version`) are deep-merged with higher-precedence values overriding lower-precedence values on key conflicts.
- Unknown top-level keys are preserved and merged deterministically using the same precedence order.

### Validation Rules During Load

- At least one requested language must be provided.
- Each requested language must exist as `lang/<lang>/baseline.yaml`.
- Each requested framework (if provided) must exist as `framework/<framework>/preset.yaml`.
- Framework presets may optionally declare `primary_languages` for informational purposes only.
- Duplicate `--lang` and `--framework` values are normalized before merge.
- Each loaded preset must parse as valid YAML and contain either `repos` or recognized metadata fields.

### Determinism Requirements

- Files are loaded from explicit known paths only (no directory glob ordering).
- Repo and hook output ordering follows merge order rules above.
- Output YAML key order is stable across runs.
- Same inputs and same preset files produce semantically equivalent output.

## Project Structure

### Documentation (this feature)

```text
specs/001-pc-init-cli/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
main.py
pyproject.toml
README.md
lang/
└── <language>/
    └── preset YAML file(s)
framework/
└── <framework>/
    └── preset YAML file(s)
gpc_init/
├── __init__.py
├── cli.py
├── profiles.py
├── loader.py
├── merger.py
├── resolver.py
└── renderer.py

tests/
├── unit/
│   ├── test_profiles.py
│   └── test_renderer.py
└── integration/
    └── test_cli_generation.py
```

**Structure Decision**: Use a single Python CLI package (`gpc_init/`) with filesystem-backed preset catalogs from `lang/` and `framework/`, plus separated request resolution and rendering concerns to keep determinism and testability explicit.

## Complexity Tracking

No constitution violations identified.
