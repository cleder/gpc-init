# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Enhancements

- Auto-detect the `behave` framework preset (added in 0.7.0) via a `features/steps/` directory or a `behave.ini`/`.behaverc` file at the repo root, and add it to the generated `AWESOME.md` list with a display name and emoji.

## [0.6.0]

Expanded the language catalog further and taught `--detect` to recognize the new languages.

### New Features

- Add `env` (`dotenv-linter`), `groovy` (`npm-groovy-lint`), and `lua` (`luacheck`) language presets.
- Auto-detect the new languages via `.env`/`.env.*` files, `.groovy`/`.gvy`/`.gradle` extensions and `Jenkinsfile`, and the `.lua` extension, respectively.

## [0.5.0]

Expanded the language/framework catalog, made every bundled hook self-documenting, and closed gaps found by cross-referencing MegaLinter's bundled linters.

### New Features

- Add `make` language preset (`checkmake`) for Makefile linting.
- Add `rb` (Ruby), `cpp` (C/C++), `proto` (Protocol Buffers), `swift`, `kt` (Kotlin), and `css` (CSS/SCSS/Sass) language presets.
- Add `ansible` framework preset (`ansible-lint`), detected via an `ansible.cfg` file at the repo root.

### Enhancements

- Cross-reference MegaLinter's bundled linters against every existing preset and add genuine gaps with verified, actively-maintained pre-commit hooks: `shfmt` (sh), `lintr` (R), `mypy` (Python), `stylelint` (react), `rstcheck`/`rstfmt` (Sphinx), Helm lint (k8s), and `jscpd`/`vale`/`lychee` (common).
- Refactor the `react` preset to recommend the new `css` language preset instead of hardcoding a duplicate `stylelint` hook.
- Backfill a `description:` field on every hook across all presets (~250 hooks), harvested from each hook's own upstream `.pre-commit-hooks.yaml` manifest (falling back to the hook's name, then the repo's GitHub description) via a new `scripts/harvest_hook_docs.py` maintainer script.
  Generated `.pre-commit-config.yaml` files are now self-documenting.
- Add roughly three dozen additional hook ids discovered from repos already in use, limited to genuinely distinct capabilities — skipping alternate install-method variants, upstream-deprecated ids, and hooks from "grab-bag" repos that are unrelated to the preset they'd land in.
- Add long-form names and emoji to `AWESOME.md`'s table of contents and section headings (e.g. "🦀 Rust (`ru`)"), with anchors generated to match GitHub's actual heading-slug algorithm.

### CI

- Enable the `vercheck` tag-name/version check on release tag pushes, verifying the git tag matches the version declared in `pyproject.toml`.

### Documentation

- Add an "Alternatives" section to the README pointing to MegaLinter for users who want a single all-in-one linter instead of curated pre-commit hooks.
- Add `CONTEXT.md` documenting the "hook capability" vs. "hook variant" distinction used when deciding which additional hook ids to include.
- Require every hook to declare a `description` in `CONTRIBUTING.md`'s hook quality bar, with a matching pull request checklist item.

### Build

- Add `ruamel.yaml` as a dev dependency, used by the new hook-description harvesting script to edit `preset.yaml` files without disturbing hand-written comments.

## [0.4.0]

Enhanced preset support with detection and recommendations, improved YAML rendering, and code quality improvements.

### New Features

- Add language and framework detection from repository structure: `--detect` flag automatically identifies programming languages and frameworks present in the repository.
- Implement `--recommended` flag to suggest and auto-apply recommended languages/frameworks from preset metadata.
- Support preset recommendations metadata: presets can now declare `recommended` field to suggest compatible language and framework combinations.

### Enhancements

- Improve YAML output rendering to strictly conform with pre-commit conventions and spacing requirements.
- Refactor preset loading and merging logic to support the new `recommended` metadata structure.
- Enhance resolver logic to provide actionable recommendations when user-selected languages or frameworks have suggestions.
- Improve test coverage for detection, recommendations, and YAML output validation.
- Update contributing guidelines with preset validation and installation commands.
- Refactor codebase for improved readability and maintainability with better separation of concerns.

### Tests

- Add comprehensive tests for language and framework detection from common file patterns.
- Add tests for recommendation resolution and suggestion generation.
- Add tests validating YAML output structure and pre-commit compliance.
- Enhance integration tests for CLI flows combining detection and recommendations.

## [0.3.1]

Preset updates and generate_awesome_list improvements.

### Enhancements

- Add `uv-audit` hook to the Python preset (runs on changes to `uv.lock` or
  `pyproject.toml`).
- Add `deptry` hook to the Python preset for detecting unused, missing, or
  transitive dependency issues.
- Add `primary_languages` (`docker`, `tf`) to the Kubernetes framework preset.
- Remove `checkov_diff` from the Kubernetes preset.
- Bump bundled hook revisions: `ruff` → v0.15.20, `ty` → v0.0.54,
  `rumdl` → v0.2.23, `django-upgrade` → 1.31.1.
- Filter `meta` repos from the generated AWESOME.md output.
- Remove the "Applied to every generated configuration" note from the Common
  section of AWESOME.md.
- Improve type annotations in `generate_awesome_list.py`.

## [0.3.0]

Expanded preset catalog, framework/language UX improvements, and CI refinements.

### New Features

- Add actionable language suggestion on framework mismatch: when none of the selected
  languages satisfy a framework's `primary_languages`, emit a consolidated `Try:` command
  that preserves existing `--lang` values so it is safe to re-run with `--force`.

### Enhancements

- Modernise `js` preset to complement `ts`: replace local prettier + typos with
  biome-check and mirrors-prettier scoped to JS/JSX/JSON/CSS/Markdown types.
- Add `ts` as a primary language for the `react` preset alongside `js`.
- Remove `biome-check` from the `react` preset — it is now inherited from the `js` preset.
- Consolidate `typos` hook into the `common` preset, removing redundant copies from
  individual language presets (`js`, `md`, `ru`).
- Add `codespell` hook to the `common` preset.
- Add R language preset with pre-commit hooks for the statistical programming language.
- Expand Python preset: add `numpydoc`, `nbstripout`, and `nbQA` hooks and autoupdate pins.
- Expand Jupyter Notebooks preset: add `nbqa` hooks for `check-ast` and `isort`.
- Expand Markdown preset: add `markdownlint-cli2` hook and autoupdate pins.
- Print unique repo count in `generate_awesome_list.py`.

### CI

- Restrict the "fail if hook revisions are outdated" step to tag pushes and the main
  branch, so it does not block work-in-progress feature branches.

## [0.2.0]

Enhanced CLI, richer preset catalog, and stronger validation and testing around preset loading, merging, and error handling.

### New Features

- Add a `pc-init list` subcommand and comma-delimited argument support for languages and frameworks.
- Introduce a version flag that prints the installed `pc-init` version and exits.
- Support custom preset catalogs from local directories or git URLs via a unified presets option and context-managed resolution.
- Implement diff-only behavior for existing config files, requiring `--force` to overwrite and providing unified diffs and guidance.

### Enhancements

- Refine CLI messages, exit codes, and stderr usage for unsupported languages/frameworks, missing presets, parse failures, and write errors.
- Extend preset discovery and alias resolution, standardizing on `preset.yaml` files and expanding language aliases.
- Add a common preset and expand bundled language and framework presets with curated hooks for Python, JS/TS, Go, Docker, Terraform, Markdown, SQL, notebooks, YAML, images, Git, Django, React, Sphinx, and Kubernetes.
- Introduce an AWESOME.md generator script based on the curated presets and document contribution guidelines for preset changes.
- Update README with detailed usage, preset lists, and examples, and refresh project metadata, licensing, and supported Python versions.
- Adopt `ryl` for YAML linting, configure `mutmut`, and adjust CI to validate and keep all preset hook revisions up to date.

### Build

- Adjust development dependencies to include tools for YAML linting, mutation testing, and broader Python version support, and remove now-unnecessary metadata files.

### CI

- Add a dedicated workflow to validate all preset YAML files and ensure hook revisions are current using `pre-commit` and `prek`, and switch existing workflow YAML linting to `ryl`.

### Documentation

- Rewrite and expand the README with motivation, installation, usage, preset tables, custom catalogs, and maintenance workflows.
- Add CONTRIBUTING guidelines, a pull request template, and YAML linting configuration documentation via `.ryl.toml`.

### Tests

- Greatly expand integration and unit tests to cover CLI flows, diff/force behavior, list/version commands, preset resolution, merging logic, YAML rendering, loader error paths, and exception messages.
- Add fixtures for language and framework presets to validate behavior with both bundled and custom catalogs.
