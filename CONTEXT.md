# gpc-init

`gpc-init` generates a `.pre-commit-config.yaml` from curated language and framework presets, so a repo gets the right linters, formatters, and quality tools wired up with one command.

## Language

**Preset**: A single `lang/<id>/preset.yaml` or `framework/<id>/preset.yaml` file — a standalone, curated bundle of pre-commit `repos:`/`hooks:` entries for one language or framework.
_Avoid_: Config, profile

**Hook**: One entry under a repo's `hooks:` list in a preset — a single check or action identified by its `id` (e.g. `ruff-check`, `checkmake`), sourced from that repo's own `.pre-commit-hooks.yaml` manifest.

**Hook capability**: A distinct check or action a repo's manifest offers (e.g. `pocc/pre-commit-hooks`' `clang-format` formatting vs. its `cppcheck` static analysis).
Capabilities from the same repo are additive — each is worth including on its own merits.

**Hook variant**: An alternate execution strategy for the _same_ hook capability, distinguished by an install-method suffix such as `-system`, `-docker`, or `-src` (e.g. `shfmt` vs. `shfmt-docker`), or occasionally a differently-named duplicate the repo itself marks deprecated in favor of another id.
Variants are mutually exclusive — only one belongs in a preset per capability.
_Avoid_: Alternate hook, duplicate hook

**Grab-bag repo**: A hook repo whose manifest bundles capabilities for several unrelated languages or domains (e.g. `gruntwork-io/pre-commit` mixes Go, Terraform, Packer, and Python tooling; `macisamuele/language-formatters-pre-commit-hooks` bundles formatters for many languages).
When pulling additional hook ids from a repo already in use, only the ids relevant to that specific preset's own language/framework belong — the rest are noise, not missing capabilities.

**Recommended language/framework**: A `recommended: {lang: [...], framework: [...]}` entry a preset declares for itself, surfaced to the user as a suggestion (not auto-applied) when their selection doesn't already include it — e.g. `framework/react` recommends `js`, `ts`, `css`.
_Avoid_: Dependency, requirement (recommendations are advisory, never enforced)
