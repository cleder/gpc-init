# pc-init

[![Tests](https://github.com/cleder/gpc-init/actions/workflows/test-build-publish.yml/badge.svg?branch=main)](https://github.com/cleder/gpc-init/actions/workflows/test-build-publish.yml) [![codecov](https://codecov.io/gh/cleder/gpc-init/graph/badge.svg?token=3enkN1Q8JM)](https://codecov.io/gh/cleder/gpc-init) [![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![pyrefly](https://img.shields.io/badge/type_checker-pyrefly-blue)](https://github.com/facebook/pyrefly) [![ty](https://img.shields.io/badge/type_checker-ty-blue)](https://github.com/astral-sh/ty) [![GPLv3 License](https://img.shields.io/pypi/l/pc-init)](https://opensource.org/license/gpl-3-0/) [![Python Version](https://img.shields.io/pypi/pyversions/pc-init)](https://www.python.org/) [![PyPI - Version](https://img.shields.io/pypi/v/pc-init)](https://pypi.org/project/pc-init/) [![Status](https://img.shields.io/pypi/status/pc-init)](https://pypi.org/project/pc-init/)

Generate a [pre-commit](https://pre-commit.com/) or [prek](https://github.com/j178/prek/) `.pre-commit-config.yaml` for your project from curated language and framework presets — so you get the right linters, formatters, and quality tools wired up with a single command instead of copying configs between repos.
Works with [prek](https://github.com/j178/prek/) and [pre-commit](https://pre-commit.com/)

## Motivation

Every new repository needs a `.pre-commit-config.yaml`.
Each language and framework has its own recommended linters, formatters, and quality tools, each with its own hook URL and revision.
`pc-init` encodes those choices in version-controlled presets so you run one command instead of copying configs and looking up hook URLs.
The bundled presets pin specific hook revisions — run `pre-commit autoupdate` or `prek autoupdate` after generation to pull in the latest versions.

## Awesome Pre-commit Hooks

The curated hooks bundled with `pc-init` are also published as a standalone reference at [awesome-pre-commit-hooks](https://github.com/cleder/awesome-pre-commit-hooks) — a browsable list of every hook organised by language and framework.

## Installation

```bash
uv tool install pc-init
```

## Usage

```text
Usage: pc-init [OPTIONS]

  Generate a .pre-commit-config.yaml from language and optional framework presets.

  At least one --lang value is required. --framework values are optional.
  Use --force to overwrite an existing config file.

Options:
  --lang       TEXT  Language preset to include (repeatable). Run without
                     --lang to see supported values from the active catalog.
                     [required]
  --framework  TEXT  Framework preset to layer on top of language baselines
                     (repeatable). Run without --framework to see supported
                     values from the active catalog.
  --force            Overwrite existing .pre-commit-config.yaml without
                     prompting.
  --output     TEXT  Output file path.  [default: .pre-commit-config.yaml]
  --presets    TEXT  Preset catalog to use. Accepts a local directory path or
                     a git repository URL (https://, git@, git://, ssh://).
                     The directory / repo root must contain lang/ and
                     framework/ subdirectories. Defaults to the bundled
                     presets.
  --help             Show this message and exit.
```

## Supported presets

**Languages** — pass as `--lang`:

| ID | Language |
|----|----------|
| `py` | Python |
| `js` | JavaScript |
| `go` | Go |
| `ru` | Rust |
| `md` | Markdown |
| `toml` | TOML |
| `yaml` | YAML |

Language aliases `python`, `javascript`, `rust`, and `golang` are also accepted.

**Frameworks** — pass as `--framework`:

| ID | Framework |
|----|-----------|
| `react` | React |
| `django` | Django |
| `bevy` | Bevy (Rust game engine) |

## Examples

Python project:

```bash
pc-init --lang py
```

JavaScript project with React:

```bash
pc-init --lang js --framework react
```

Python + Django, overwriting an existing config:

```bash
pc-init --lang py --framework django --force
```

Rust project with the Bevy game engine:

```bash
pc-init --lang ru --framework bevy
```

Multiple languages:

```bash
pc-init --lang py --lang js
```

## Custom presets

Point `--presets` at a local directory or a git repository that contains `lang/` and `framework/` subdirectories in the same layout as the bundled presets.

Local directory:

```bash
pc-init --lang py --presets /path/to/my-presets
```

Git repository:

```bash
pc-init --lang py --presets https://github.com/org/my-presets
```

## Updating bundled presets

To pull the latest hook revisions into all bundled preset files:

```bash
find . -name "preset*.yaml" | xargs -I{} prek auto-update -c {}
```
