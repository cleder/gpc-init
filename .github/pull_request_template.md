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

### Code contributions

The following checks apply only when `gpc_init/` or `tests/` are changed.

- [ ] `uv run pytest tests --cov=gpc_init` passes
- [ ] `uv run ruff check gpc_init tests` passes
- [ ] `uv run ruff format gpc_init tests` passes
- [ ] `uv run pyrefly check gpc_init tests` passes
- [ ] `uv run ty check gpc_init tests` passes
- [ ] `uv run complexipy gpc_init` passes
