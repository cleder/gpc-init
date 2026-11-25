# pc-init

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`gh` CLI) for `cleder/gpc-init`; external PRs are not treated as a triage surface.
See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`); `wontfix` exists, the other four need creating in GitHub.
See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at repo root, ADRs at `.claude/docs/adr/` (non-default location).
See `docs/agents/domain.md`.

## Engineering rules

- Behavior changes are test-first with `pytest`: write the test, watch it fail, then make it pass.
- Type errors block merge.
  Run both `ty` and `pyrefly` (both are pre-commit hooks; `ty` is skipped on pre-commit.ci, so run it locally), and give new public functions explicit signatures.
- Generation stays deterministic and offline: same Generation request and Catalog, same output (ADR 0003).
- New hooks follow "Adding hooks" below.

## Adding hooks

When a new hook is added to a preset, credit its author: add a `CHANGELOG.md` entry under `[Unreleased]` → `Enhancements` that names the hook and tags the upstream repository owner, e.g. ``Add `auto-walrus` (experimental) to the `py` preset, by @MarcoGorelli``, and repeat the credit in the commit message and the PR description.
Take the handle from the hook repository's GitHub owner, not from a guess.

<!-- code-map:begin -->
## Code map (generated)

Before crawling the source, read `docs/README.md` — a generated, always-current map of this repo: subsystems, module dependencies, docstring coverage.
Per-module API references (signatures, docstrings, callers and callees) live in `docs/architecture/`.
Those pages are regenerated automatically; never hand-edit them.
<!-- code-map:end -->
