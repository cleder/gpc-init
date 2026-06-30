# Contributing

Thank you for helping improve the bundled presets and tooling for `pc-init`.

## Development setup

```bash
git clone https://github.com/cleder/gpc-init.git
cd gpc-init
uv sync
uv tool install prek
prek install
```

## Repository layout

```text
lang/<id>/preset.yaml        # language presets  (--lang)
framework/<id>/preset.yaml   # framework presets (--framework)
gpc_init/                    # Python package source
tests/                       # pytest test suite
```

## Contributing a preset

### Adding or updating a hook

Each preset is a standalone `preset.yaml` file that follows the [pre-commit config format](https://pre-commit.com/#pre-commit-configyaml---top-level).
Every check (hooks id) should have a name and description.
A language preset looks like this:

```yaml
---
repos:
  - repo: https://github.com/example/hook
    rev: v1.2.3
    hooks:
      - id: hook-id
        name: Example hook
        description: What this hook does
```

Framework presets may additionally declare which languages and frameworks they recommend:

```yaml
---
recommended:
  lang:
    - py
  framework:
    - git
repos:
  - ...
```

### Scope rule

**One PR must touch exactly one language or framework preset.**
If you want to update both `lang/py/preset.yaml` and `framework/django/preset.yaml`, open two separate PRs.

### Validation steps

Run all four commands against the preset file before opening a PR.
CI enforces the same checks and will fail if they are skipped.

```bash
pre-commit validate-config lang/<id>/preset.yaml
pre-commit autoupdate -c lang/<id>/preset.yaml

prek validate-config lang/<id>/preset.yaml
prek autoupdate -c lang/<id>/preset.yaml
```

After running `autoupdate`, commit the file if any revisions changed.

To validate and update every preset at once:

```bash
find . -name "preset*.yaml" | xargs -I{} pre-commit validate-config {}
find . -name "preset*.yaml" | xargs -I{} pre-commit autoupdate -c {}

find . -name "preset*.yaml" | xargs -I{} prek validate-config {}
find . -name "preset*.yaml" | xargs -I{} prek autoupdate -c {}
```

### Just Runner

The repository includes a `.justfile` for using the [just](https://just.systems/man/en/) runner framework.
You can install `just` with `uv`.

```bash
uv tool install rust-just
```

Once you have this installed you can use `just` to see the available recipes.

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

### Hook quality bar

Only include hooks that are publicly available, actively maintained, and add clear value over hooks already in the preset.

## Running the CLI locally

After `uv sync`, run the CLI directly without installing:

```bash
uv run pc-init --help
uv run pc-init --lang=py --framework=django
```

Or install it into the project venv once:

```bash
uv pip install -e .
pc-init --help
```

## Contributing to the Python code

Run the test suite and static checks before opening a PR:

```bash
uv run pytest tests --cov=gpc_init
uv run ruff check gpc_init tests
uv run ruff format gpc_init tests
uv run pyrefly check gpc_init tests
uv run ty check gpc_init tests
uv run complexipy gpc_init
```

## Submitting a pull request

Fill in the PR description and complete every item in the pre-submission checklist before requesting review.
Incomplete checklists will not be merged.
