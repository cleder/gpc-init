# 0001: Hook categories and the `--profile` flag

## Status

Accepted

## Context

[Issue #4](https://github.com/cleder/gpc-init/issues/4) asked for a way to pull in more hooks than the curated default: an "exhaustive" category with every known hook, and an "experimental" category for brand-new, not-yet-proven hooks.
Discussion on the issue added a third category, "legacy", for hooks superseded by a newer hook already in the same preset (e.g. `ruff` replacing `black`/`isort`, `ty` replacing `mypy`), and proposed that categories be able to include other categories (e.g. "experimental" includes "preset", "exhaustive" includes everything and carries no hooks of its own).

The maintainer's final proposal in the thread settled on three named profiles: `preset` ⭐ (default), `legacy` 🕰️, `experimental` ⚗️ — dropping the separate `exhaustive` category.

Before this change, `gpc-init` had no notion of hook categories at all: every hook in a `lang/<id>/preset.yaml` or `framework/<id>/preset.yaml` was included unconditionally once its language/framework was selected.

## Decision

- Implement exactly three categories: `preset`, `legacy`, `experimental`.
  No `exhaustive` category — since `preset` is always included, selecting all non-default categories has the same effect.
- `preset` is an unconditional baseline: `pc-init` with no `--profile` flag behaves exactly as before. `legacy` and `experimental` are flat, independent opt-ins layered on top via `--profile` — there is no recursive include-graph to resolve.
- Each hook in a `preset.yaml` may carry an optional `category: legacy|experimental` field.
  Absent ⇒ implicit `preset`.
  Verified this is safe: `pre_commit`'s own `cfgv`-based config schema (`CONFIG_HOOK_DICT` in `pre_commit/clientlib.py`) has no "no additional keys" check at the hook level, so this custom field doesn't break `pre-commit validate-config`/`prek validate-config`.
- The CLI flag is `--profile` (matching the issue title and the maintainer's own wording), repeatable/comma-delimited exactly like `--lang`/`--framework`.
  It is typed as a plain string list (not a Typer/Click `Enum`) so comma-delimited parsing keeps working the same way it does for `--lang`/`--framework`; validation of the parsed values happens via a dedicated `validate_profiles`/`UnsupportedProfileError` pair, mirroring the existing `validate_langs`/`UnsupportedLanguageError` pattern.
- Filtering by category happens **after** `merge_presets()`, on the fully merged `repos`/`hooks` structure, immediately before `render_yaml()` (`gpc_init/merger.py:filter_by_category`).
  This mirrors how `recommended`/`primary_languages` preset-metadata keys are already stripped post-merge, and correctly reflects whichever preset layer's `category` field wins after cross-preset field overrides.
  A repo entry left with zero hooks after filtering is removed entirely, not rendered as `hooks: []`.
- `CONTEXT.md`'s "Preset" glossary entry previously listed "profile" as a term to avoid (to prevent it becoming a confusing synonym for "preset").
  That avoidance is removed and a new "Hook category / profile" glossary term is added, since `--profile` now has its own, distinct meaning.
- The existing, unused `gpc_init/profiles.py` dataclass module (unrelated `HookConfig`/`RepoConfig`/`GenerationRequest`/`GenerationResult`, dead code) is left untouched — different concept, same word, low real collision risk since it isn't wired into the CLI.
- `mypy` in `lang/py/preset.yaml` is reclassified as `category: legacy`, since `ty` (already present in the same preset) supersedes it — the concrete example raised in the issue thread.
- `AWESOME.md`'s generator (`scripts/generate_awesome_list.py`) annotates legacy/experimental hooks with their category emoji, so the categorization is discoverable in the docs, not just via `--help`.

## Consequences

- Behavior change for existing Python users: `pc-init --lang py` (and any preset built on it) no longer includes `mypy` by default.
  Users who want it back run `pc-init --lang py --profile legacy`.
- Adding a new legacy/experimental hook to any preset going forward requires only a `category:` field — no changes to the CLI, merger, or filtering logic.
- Because filtering is a flat category check (not a graph), a future request to reintroduce something like `exhaustive` would need either a new dedicated CLI value that expands to `{legacy, experimental}` at the CLI layer, or a real hierarchical resolver — not needed today.
