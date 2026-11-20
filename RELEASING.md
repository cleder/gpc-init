---
type: Playbook
title: Releasing pc-init
description: Maintainer runbook for cutting a pc-init release to PyPI.
tags: [release, maintainer, ci]
status: draft
generated:
  by: claude-code/claude-sonnet-5-5
  at: "2026-11-20T10:01:13Z"
sources:
  - id: workflow
    resource: .github/workflows/test-build-publish.yml
    title: test-build-publish workflow
  - id: justfile
    resource: .justfile
    title: just recipes for the release
  - id: release-script
    resource: scripts/release.py
    title: just release
  - id: ship-script
    resource: scripts/ship.py
    title: just ship
  - id: changelog-script
    resource: scripts/changelog_section.py
    title: changelog check, notes and promotion
---

## Releasing pc-init

Only the maintainer releases.
This is a runbook, not contributor documentation.

### The flow

```text
develop:  just release X.Y.Z  ->  review  ->  push develop + tag
CI (tag): vercheck, changelog, prerequisites, TestPyPI
          just ship X.Y.Z     ->  PR merge to main
CI (main): PyPI  ->  GitHub Release
```

- The tag goes on `develop` **first**, so a mistake is caught before anything reaches PyPI.
- Tags have no `v` prefix: `0.8.2`, not `v0.8.2`.
  The `test-release` environment only accepts tags that look like `X.Y.Z`.
- Merging to `main` uploads to PyPI straight away.
  The `release` environment only accepts the `main` branch and has no approval step.
- The PyPI package is called `pc-init`.

### 1. Prepare the release

Be on a clean `develop` with the changelog entries under `## [Unreleased]`.

```bash
just release X.Y.Z
```

The recipe refuses to run unless you are on `develop`, tracked files are clean, and `X.Y.Z` is higher than the latest tag.
Then it:

1. runs `just prepare-release` (upgrades `uv.lock`, runs `prek autoupdate` on the local config and every preset, runs the tests),
2. sets `version` in `pyproject.toml` and runs `uv lock`,
3. moves the `[Unreleased]` entries under `## [X.Y.Z]` and validates the changelog,
4. makes one `Release X.Y.Z` commit and an annotated tag `X.Y.Z`.

It never pushes.
Review what it did, including the hook and dependency bumps:

```bash
git show --stat
```

Check that every hook added since the last release credits its author (`by @owner`), as `CLAUDE.md` requires.

### 2. Push and wait for the tag run

```bash
git push origin develop X.Y.Z
gh run watch
```

The tag run checks that the tag matches `pyproject.toml` (`vercheck`), that the changelog has a non-empty `X.Y.Z` section and an empty `[Unreleased]`, and that everything is up to date (`just check-release-ready`).
Then it uploads to TestPyPI.

### 3. Ship it

```bash
just ship X.Y.Z
```

The recipe refuses to continue unless the tag exists locally and on `origin`, points at `origin/develop`, and its `test-build-publish` run succeeded.
It then opens (or reuses) the `develop` to `main` pull request with the changelog section as its description, asks you to type the version to confirm, and merges with `gh pr merge --merge`.
It checks that `main` has exactly the contents of the tag, then fast-forwards `develop` to `main`.

The push to `main` runs `publish` (PyPI), followed by `github-release`, which creates the GitHub Release from the changelog section.

```bash
gh run watch
```

### If something goes wrong

- **Tag run fails before the TestPyPI upload succeeded**: delete the tag, fix `develop`, tag again with the same version.

  ```bash
  git tag -d X.Y.Z && git push origin :refs/tags/X.Y.Z
  ```

- **Tag run fails after the TestPyPI upload succeeded**: TestPyPI refuses to re-upload a version, so do not reuse the number.
  Bump the patch version and start again with `just release`.

- **Once `main` has moved and PyPI has the version**: the tag is permanent.
  Fix forward with a new patch version, and yank the bad one in the PyPI project settings if needed.

- **`just ship` reports that `main` differs from the tag**: stop the `publish` run in GitHub Actions and investigate before anything else lands on `main`.

- **`validate-presets` fails on the release PR** because a hook revision went out of date after the tag: this is rare and costs a new patch version.

- **`validate-presets` reports an archived hook repo**: remove the hook from its preset (`just check-archived` runs the same check locally).

### Not covered

- There is no smoke test of the package uploaded to TestPyPI.
- There is no approval gate between the merge to `main` and the PyPI upload.
