# Changelog

All notable changes to this project will be documented in this file.

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
