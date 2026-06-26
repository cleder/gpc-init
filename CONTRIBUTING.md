# Contributing

Thank you for helping improve the bundled presets and tooling for `pc-init`.

## Development setup

```bash
git clone https://github.com/cleder/gpc-init.git
cd gpc-init
uv sync
pre-commit install
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
A language preset looks like this:

```yaml
---
repos:
  - repo: https://github.com/example/hook
    rev: v1.2.3
    hooks:
      - id: hook-id
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
prek validate-config lang/<id>/preset.yaml

pre-commit autoupdate -c lang/<id>/preset.yaml
prek autoupdate -c lang/<id>/preset.yaml
```

After running `autoupdate`, commit the file if any revisions changed.

To validate and update every preset at once:

```bash
find . -name "preset*.yaml" | xargs -I{} pre-commit validate-config {}
find . -name "preset*.yaml" | xargs -I{} prek validate-config {}
find . -name "preset*.yaml" | xargs -I{} pre-commit autoupdate -c {}
find . -name "preset*.yaml" | xargs -I{} prek autoupdate -c {}
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
```

## Submitting a pull request

Fill in the PR description and complete every item in the pre-submission checklist before requesting review.
Incomplete checklists will not be merged.
