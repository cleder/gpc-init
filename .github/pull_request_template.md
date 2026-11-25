## Description

<!-- Describe what this PR adds or changes and why. -->

## Pre-submission checklist

### Preset contributions

- [ ] This PR touches exactly one language or framework preset

Run the following commands against the preset file and confirm each passes.

- [ ] `pre-commit validate-config <preset-file>` passes without errors
- [ ] `prek validate-config <preset-file>` passes without errors
- [ ] `pre-commit autoupdate -c <preset-file>` was run and hook revisions are up to date
- [ ] `prek autoupdate -c <preset-file>` was run and hook revisions are up to date
- [ ] All hooks listed in the preset are publicly available and actively maintained
- [ ] Every hook in this preset has a `description` field

### Code contributions

The following checks apply only when `pc_init/` or `tests/` are changed.

- [ ] `uv run pytest tests --cov=pc_init` passes
- [ ] `uv run ruff check pc_init tests` passes
- [ ] `uv run ruff format pc_init tests` passes
- [ ] `uv run pyrefly check pc_init tests` passes
- [ ] `uv run ty check pc_init tests` passes
- [ ] `uv run zuban check pc_init tests` passes
- [ ] `uv run complexipy pc_init` passes
