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
Usage: pc-init [OPTIONS] COMMAND [ARGS]...

  Generate a .pre-commit-config.yaml for your project.

Options:
  --lang       TEXT  Language preset to include (repeatable, or
                     comma-delimited: --lang=py,js). Run `pc-init list` to
                     see supported values from the active catalog.
  --framework  TEXT  Framework preset to layer on top of language baselines
                     (repeatable, or comma-delimited: --framework=react,django).
                     Run `pc-init list` to see supported values from the
                     active catalog.
  --force            Overwrite existing .pre-commit-config.yaml without
                     prompting.
  --output     TEXT  Output file path.  [default: .pre-commit-config.yaml]
  --presets    TEXT  Preset catalog to use. Accepts a local directory path or
                     a git repository URL (https://, git@, git://, ssh://).
                     The directory / repo root must contain lang/ and
                     framework/ subdirectories. Defaults to the bundled
                     presets.
  --version          Show version and exit.
  --help             Show this message and exit.

Commands:
  list  List available language and framework presets in the active catalog.
```

### List available presets

Run `pc-init list` to discover all supported languages and frameworks in the active catalog (bundled or custom):

```bash
pc-init list
```

```text
Languages:
  docker, go, img, js, md, nb, py, ru, sh, sql, tf, toml, ts, yaml

Frameworks:
  django, git, k8s, react, sphinx
```

Use `--presets` to list what a custom catalog provides:

```bash
pc-init list --presets /path/to/my-presets
pc-init list --presets https://github.com/org/my-presets
```

## Supported presets

**Languages** — pass as `--lang`:

| ID | Language |
|----|----------|
| `py` | Python |
| `js` | JavaScript |
| `go` | Go |
| `ru` | Rust |
| `sh` | Shell / Bash |
| `ts` | TypeScript |
| `nb` | Jupyter Notebooks |
| `md` | Markdown |
| `img` | Images |
| `docker` | Docker |
| `sql` | SQL |
| `tf` | Terraform |
| `toml` | TOML |
| `yaml` | YAML |

Language aliases `python`, `javascript`, `typescript`, `rust`, `golang`, `shell`, `bash`, `image`, `notebook`, `jupyter`, `dockerfile`, and `terraform` are also accepted.

**Frameworks** — pass as `--framework`:

| ID | Framework |
|----|-----------|
| `react` | React |
| `django` | Django |
| `sphinx` | Sphinx documentation |
| `git` | Commit message linting |
| `k8s` | Kubernetes |

## Language suggestions for frameworks

Some framework presets declare the languages they are typically used with.
If none of your `--lang` selections match, `pc-init` prints an informational note and a ready-to-run command that adds the missing languages:

```text
Note: framework 'react' is typically used with: js, ts
      Try: pc-init --lang=py,js,ts --framework=react
```

The suggested command preserves your existing `--lang` values so it is safe to run with `--force` — no hooks you already selected will be removed.

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

Multiple languages (two equivalent forms):

```bash
pc-init --lang py --lang js
pc-init --lang=py,js
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

## Check the config files

To check the config files with `pre-commit` and `prek` for a specific language or framework:

```bash
pre-commit validate-config lang/py/preset.yaml
prek validate-config lang/py/preset.yaml
```

## Update bundled presets

Update a config file with the command:

```bash
pre-commit autoupdate lang/py/preset.yaml
prek autoupdate lang/py/preset.yaml
```

## Check and update all presets

To pull the latest hook revisions into all bundled preset files:

```bash
find . -name "preset*.yaml" | xargs -I{} prek validate-config {}
find . -name "preset*.yaml" | xargs -I{} prek autoupdate -c {}
find . -name "preset*.yaml" | xargs -I{} pre-commit validate-config {}
find . -name "preset*.yaml" | xargs -I{} pre-commit autoupdate -c {}
```

### Just Runner

The repository includes a `.justfile` for using the [just](https://just.systems/man/en/) runner framework.
If you have this installed you can use `just` to see the available recipes.

``` bash
❱ just
just --list
Available recipes:
    autoupdate target
    default
    validate target
    validate_update target
    validate_update_all
```

These allow you to validate and/or update a given language preset in a slightly more concise manner as the provided language name is inserted into the target path automatically, all you have to do is provide the language alias as the example below shows.

``` bash
❱ just validate_update py
Validating py...
pre-commit validate-config lang/py/preset.yaml
prek validate-config lang/py/preset.yaml
success: All configs are valid
Autoupdating py...
pre-commit autoupdate -c lang/py/preset.yaml
[https://github.com/MarcoGorelli/absolufy-imports] already up to date!
[https://github.com/astral-sh/ruff-pre-commit] updating v0.15.19 -> v0.15.20
[https://github.com/abravalheri/validate-pyproject] already up to date!
[https://github.com/kieran-ryan/pyprojectsort] already up to date!
[https://github.com/adamchainz/blacken-docs] already up to date!
[https://github.com/facebook/pyrefly-pre-commit] already up to date!
[https://github.com/astral-sh/ty-pre-commit] updating v0.0.53 -> v0.0.54
[https://github.com/rohaquinlop/complexipy-pre-commit] already up to date!
[https://github.com/asmeurer/removestar] already up to date!
[https://github.com/PyCQA/bandit] already up to date!
[https://github.com/PyCQA/docformatter] already up to date!
[https://github.com/econchick/interrogate] already up to date!
[https://github.com/asottile/pyupgrade] already up to date!
[https://github.com/astral-sh/uv-pre-commit] already up to date!
[https://github.com/numpy/numpydoc] already up to date!
prek autoupdate -c lang/py/preset.yaml
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, preset guidelines, and the pull request checklist.
