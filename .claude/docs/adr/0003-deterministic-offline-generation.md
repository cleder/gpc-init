# 0003: Deterministic generation, no network lookups

## Status

Accepted

## Context

A generated `.pre-commit-config.yaml` is committed and reviewed.
If the same command can yield different files on different days or machines, diffs become noise and CI becomes unreliable.

## Decision

The generated output is a pure function of the **Generation request** and the **Catalog contents**.
`pc-init` itself adds no randomness, no clock-dependent behaviour, and no network lookups.

Concretely:

- Presets are read from explicit known paths; there is no directory-glob ordering.
- Repo, hook and key ordering follow the merge rules in ADR 0002, and rendered YAML key order is stable.
- Hook revisions are whatever the Preset pins.
  The tool never resolves "latest tag" or fetches hook metadata at generation time.
- Default categories, hook ordering and revisions are encoded in Presets and covered by tests.

### Scope: the bundled Catalog versus `--presets <git-url>`

For the bundled Catalog the guarantee is complete: no network is involved and output is fully reproducible for a given `pc-init` version.

`--presets` pointing at a git URL (`pc_init/fetcher.py`) shallow-clones the repository at its default-branch HEAD.
That is network access, and it is **opt-in**.
The guarantee still holds relative to the Catalog contents, but the contents are whatever HEAD is at that moment, so output can change between runs.
Reproducibility is the caller's responsibility, for example by pointing at a local directory or a mirror they control.

Known limitation: the clone cannot be pinned to a ref.
Adding a ref option would close the gap but is a feature change and is not decided here.

## Alternatives considered

- **Fetch hook metadata or latest revisions at runtime.**
  Fresher, but nondeterministic and dependent on the network.
  Rejected; revision bumps are handled by `pre-commit autoupdate` and by editing Presets.
- **Hardcode profiles in Python.**
  Deterministic, but drifts from the user-editable Preset files, which are the source of truth.

## Consequences

- Tests can assert exact output for a given request and Catalog.
- Any future feature that reads external state at generation time needs a new ADR that supersedes this one.
