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
**Every hook (by `id`) MUST have a `description`** explaining what it does — a `name` is encouraged too, but `description` is what makes generated `.pre-commit-config.yaml` files self-documenting and is not optional.
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

A hook may optionally declare a `category` to mark it as `legacy` or `experimental` instead of the default `preset` category:

```yaml
      - id: mypy
        category: legacy
        description: "Mirror of mypy for pre-commit"
```

Omit `category` for hooks that belong in the curated default (`preset`) — most hooks.
Use `category: legacy` when the hook is superseded by a newer hook already in the same preset but is still usable (e.g. `mypy`, superseded by `ty`).
Use `category: experimental` for a brand-new, not-yet-proven hook.
Users opt into `legacy`/`experimental` hooks with `--profile` (e.g. `pc-init --lang py --profile legacy`); `preset` hooks are always included.

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

### Adding a new language or framework

A new `lang/<id>/` or `framework/<id>/` directory needs **two** files, not just a preset:

```text
lang/<id>/preset.yaml       # the hooks (see "Adding or updating a hook" above)
lang/<id>/metadata.yaml     # fullname, icon, and detection data (required)
```

`metadata.yaml` is what makes the language/framework discoverable — it drives `pc-init list`, `--detect`, CLI alias normalization (e.g. `--lang=python`), and the generated `AWESOME.md` display label.
Without it, CI's `scripts/validate_metadata.py` check fails.

For a **language**:

```yaml
---
fullname: Python
icon: "🐍"
extensions:
  - .py
  - .pyi
filenames: []        # case-insensitive file stems with no fixed extension, e.g. dockerfile
aliases:
  - python            # extra --lang values that normalize to this id
```

For a **framework**, `metadata.yaml` declares how `--detect` recognizes it instead of `extensions`/`filenames`/`aliases`:

```yaml
---
fullname: Django
icon: "🎸"
detect:
  - file_exists: manage.py
```

Supported declarative rules (each list entry is OR'd — any match detects the framework):

- `file_exists: <path>` — a file exists at that path relative to the repo root
- `dir_exists: <path>` — a directory exists at that path
- `glob: "<pattern>"` — any file in the repo tree matches the filename pattern (e.g. `"*.nika.yaml"`)
- `package_json_dep: <name>` — `package.json` lists `<name>` as a dependency or devDependency

If detection genuinely needs to read file *content* or apply logic that doesn't reduce to one of the rules above (see `sphinx`/`k8s`/`git` for examples), add a Python function to `gpc_init/detector.py` and register it in `_DETECTOR_REGISTRY`, then reference it as `detect: "python:<function_name>"`.
This escape hatch is intentionally a fixed allowlist, not an arbitrary import path — a custom `--presets` catalog must not be able to smuggle in code.

**Extensions, filenames, and aliases must be globally unique** across every language — the catalog loader hard-fails at load time if two languages claim the same one.
Run this before opening a PR:

```bash
uv run scripts/validate_metadata.py
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
You can [install `just`](https://just.systems/man/en/packages.html) with `uv`.

```bash
uv tool install rust-just
```

Once you have this installed you can use `just` to see the available recipes.

``` bash
❱ just
just --list
Available recipes:
    awesome
    default
    test
    update target="all" type="lang"
    validate target="all" type="lang"
```

`validate` and `update` both take an optional `target` (a language or framework alias, defaulting to `all`) and `type` (`lang` or `framework`, defaulting to `lang`).
This lets you validate and/or update a given preset in a concise manner: just provide the alias, and, for framework presets, the type.

``` bash
❱ just validate py
Validating py ...
success: All configs are valid
success: All configs are valid
```

``` bash
❱ just update py
Autoupdating py...
[https://github.com/MarcoGorelli/absolufy-imports] already up to date!
[https://github.com/astral-sh/ruff-pre-commit] updating v0.15.19 -> v0.15.20
[https://github.com/abravalheri/validate-pyproject] already up to date!
...
```

For a framework preset, pass `framework` as the second argument, e.g. `just validate django framework`.

To validate or update every preset at once, omit the target (or pass `all`):

``` bash
just validate
just update
```

### Hook quality bar

Only include hooks that are publicly available, actively maintained, and add clear value over hooks already in the preset.
Every hook MUST have a `description`, harvested from its own `.pre-commit-hooks.yaml` where possible.

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
just test
```

which will run:

```bash
uv run pytest tests --cov=gpc_init tests
uv run complexipy --failed gpc_init
uv run ruff check gpc_init tests
uv run ruff format gpc_init tests
uv run pyrefly check gpc_init tests
uv run ty check gpc_init tests
```

## Submitting a pull request

Fill in the PR description and complete every item in the pre-submission checklist before requesting review.
Incomplete checklists will not be merged.
