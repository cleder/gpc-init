# Quickstart: Validate pc-init CLI Scaffold

## Prerequisites
- Python >= 3.14
- Project dependencies installed
- Clean test workspace directory

## Setup

### 1. Install dependencies
Using `uv`:

```bash
uv sync --all-groups
```

### 2. Confirm test and typecheck tools are available
```bash
uv run pytest --version
uv run pyrefly --help
```

## Validation Scenarios

### Scenario A: Generate baseline config (MVP)
```bash
uv run pc-init --lang=py
```
Expected outcome:
- `.pre-commit-config.yaml` exists in current directory.
- Exit code is `0`.
- Output indicates language `py` and generated path.

### Scenario B: Generate framework-augmented config
```bash
uv run pc-init --lang=js --framework=react
```
Expected outcome:
- Output contains JavaScript baseline plus React-specific additions.
- Exit code is `0`.

### Scenario B2: Generate polyglot config with multiple frameworks
```bash
uv run pc-init --lang=py --lang=js --framework=django --framework=react
```
Expected outcome:
- Output contains merged common baseline, Python and JavaScript baselines, then Django and React framework additions.
- Merge order is deterministic and follows CLI input order.
- Exit code is `0`.

### Scenario C: Generate framework-augmented polyglot config
```bash
uv run pc-init --lang=go --framework=react
```
Expected outcome:
- Command succeeds with exit code `0`.
- Output contains Go baseline hooks plus React-specific additions (frameworks work with any language).
- Demonstrates framework language recommendations are informational, not enforced.

### Scenario D: Existing file without overwrite intent
```bash
uv run pc-init --lang=py
uv run pc-init --lang=py
```
Expected outcome:
- Second run fails with non-zero exit.
- Existing file remains unchanged.
- Error message tells user to use `--force`.

### Scenario E: Overwrite with force
```bash
uv run pc-init --lang=py --force
```
Expected outcome:
- Existing `.pre-commit-config.yaml` is overwritten.
- Exit code is `0`.

## Quality Gates

### Run tests (TDD evidence)
```bash
uv run pytest -q
```
Expected outcome:
- All tests pass.

### Run strict typing check
```bash
uv run pyrefly
```
Expected outcome:
- No type errors.

## References
- Specification: `specs/001-pc-init-cli/spec.md`
- Plan: `specs/001-pc-init-cli/plan.md`
- Data model: `specs/001-pc-init-cli/data-model.md`
- CLI contract: `specs/001-pc-init-cli/contracts/cli-contract.md`
