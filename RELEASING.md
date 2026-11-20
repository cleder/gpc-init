---
title: Releasing gpc-init
description: Maintainer runbook for cutting a gpc-init release to PyPI.
type: runbook
audience: maintainer
status: draft
---

## Releasing gpc-init

Only the maintainer releases.
This is a runbook, not contributor documentation.

### How publishing works

- Pushing to `main` runs the `publish` job in `.github/workflows/test-build-publish.yml`, which uploads to **PyPI** (environment `release`, OIDC trusted publishing).
- Pushing a tag runs the `vercheck` tag-versus-`pyproject.toml` check and the `test-publish` job, which uploads to **TestPyPI** (environment `test-release`).
- PyPI refuses to re-upload an existing version, so the version in `pyproject.toml` must be right **before** the merge to `main`.
- Tags have no `v` prefix: `0.8.1`, not `v0.8.1`.
- The workflow creates no GitHub Release.

### Steps

#### 1. Start from a clean, green `develop`

```bash
git switch develop && git pull
git status          # nothing unexpected
gh run list -b develop -L 3
```

#### 2. Bring everything to the latest versions

```bash
just prepare-release
```

This upgrades `uv.lock`, runs `prek autoupdate` on the local `.pre-commit-config.yaml` and on every preset, then runs the tests.
Review the diff.
A bumped hook can change behaviour, so read what moved before committing.
Commit the result on its own.

```bash
just check-release-ready    # must exit 0
```

#### 3. Bump the version and the changelog

- Set `version` in `pyproject.toml`, then run `uv lock`.
- In `CHANGELOG.md`, rename `## [Unreleased]` to the new version and add a fresh empty `## [Unreleased]` above it.
- Check that every hook added since the last release has its author credited (`by @owner`), as `CLAUDE.md` requires.

#### 4. Open the release PR (`develop` to `main`)

- Summarise the changes from the changelog.
- Repeat the author credits for new hooks in the PR description.
- Wait for CI.
  The PR-to-`main` run includes the check that the lockfile, local config and presets are current, and `validate-presets` fails on outdated hook revisions.
  If upstream released something in the meantime, re-run `just prepare-release`, commit and push.

#### 5. Merge, then verify PyPI

Merging runs `publish` (it may wait for approval on the `release` environment).
Confirm the new version at <https://pypi.org/project/pc-init/> and try it:

```bash
uvx --refresh --from pc-init==<version> pc-init --help
```

#### 6. Tag the release

```bash
git switch main && git pull
git tag <version>
git push origin <version>
```

This runs `vercheck` and the TestPyPI upload.
The tag comes after the PyPI publish, so a tag that mismatches `pyproject.toml` is only caught after the fact.
Double-check the version before step 5.

#### 7. Finish up

- Create the GitHub Release from the tag, using the changelog section as the notes (`gh release create <version> --notes-file ...`).
- Merge `main` back into `develop` so the merge commit is not lost.

### If something goes wrong

- **Wrong version published to PyPI**: it cannot be replaced.
  Fix forward with a new version, and yank the bad one in the PyPI project settings if needed.
- **`check-release-ready` or CI fails on outdated versions**: upstream released since step 2.
  Re-run `just prepare-release`.
- **`validate-presets` reports an archived hook repo**: remove the hook from its preset (`just check-archived` runs the same check locally).

### Open points

- Whether the `release` and `test-release` environments require manual approval has not been checked.
- Tagging before the merge to `main` would let `vercheck` run before the PyPI upload; that would need a workflow change.
