"""pc-init CLI: Generate .pre-commit-config.yaml from language and framework presets."""

import difflib
import importlib.metadata
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer

from gpc_init import fetcher
from gpc_init.exceptions import (
    PresetFetchError,
    PresetNotFoundError,
    PresetParseError,
    UnsupportedFrameworkError,
    UnsupportedLanguageError,
)
from gpc_init.loader import (
    load_common_preset,
    load_framework_preset,
    load_language_preset,
)
from gpc_init.merger import merge_presets
from gpc_init.renderer import render_yaml
from gpc_init.resolver import (
    deduplicate_preserving_order,
    get_primary_languages_info,
    get_supported_frameworks,
    get_supported_languages,
    normalize_framework,
    normalize_lang,
    validate_frameworks,
    validate_langs,
)


def _generate_content(
    langs: list[str],
    frameworks: list[str],
    base_dir: Path | None,
) -> tuple[str, list]:
    """Validate, load, merge, render. Returns (yaml_content, fw_presets)."""
    if base_dir is not None and not (base_dir / "lang").is_dir():
        typer.echo(f"Error: '{base_dir}' must contain a 'lang' subdirectory.", err=True)
        raise typer.Exit(code=1)

    try:
        validate_langs(langs, base_dir=base_dir)
        validate_frameworks(frameworks, base_dir=base_dir)

        common = load_common_preset(base_dir=base_dir)
        lang_presets = [
            load_language_preset(lang_id, base_dir=base_dir) for lang_id in langs
        ]
        fw_presets = [
            load_framework_preset(fw_id, base_dir=base_dir) for fw_id in frameworks
        ]

        merged = merge_presets(common, lang_presets, fw_presets)
        return render_yaml(merged), fw_presets

    except UnsupportedLanguageError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    except UnsupportedFrameworkError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    except PresetNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    except PresetParseError as exc:
        typer.echo(f"Error: failed to parse preset YAML: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _run(
    langs: list[str],
    frameworks: list[str],
    target: Path,
    base_dir: Path | None,
) -> None:
    """Generate and write the preset config to target."""
    content, fw_presets = _generate_content(langs, frameworks, base_dir)

    overwritten = target.exists()
    try:
        target.write_text(content, encoding="utf-8")
    except (PermissionError, OSError) as exc:
        typer.echo(f"Error: cannot write to '{target}': {exc}", err=True)
        raise typer.Exit(code=1) from exc

    info = get_primary_languages_info(frameworks, fw_presets, langs)
    if info:
        typer.echo(info)

    lang_str = ", ".join(langs)
    fw_str = (", ".join(frameworks)) if frameworks else "none"
    action = "Overwrote" if overwritten else "Generated"
    typer.echo(f"{action} {target} with languages: {lang_str} and frameworks: {fw_str}")


def _dispatch(
    langs: list[str],
    frameworks: list[str],
    target: Path,
    base_dir: Path | None,
    *,
    force: bool,
) -> None:
    """Route to diff display or write depending on whether target exists."""
    if target.exists() and not force:
        _handle_existing_file(langs, frameworks, target, base_dir)
    else:
        _run(langs, frameworks, target, base_dir)


def _handle_existing_file(
    langs: list[str],
    frameworks: list[str],
    target: Path,
    base_dir: Path | None,
) -> None:
    """Show unified diff vs existing file. Always raises typer.Exit."""
    content, _ = _generate_content(langs, frameworks, base_dir)
    existing = target.read_text(encoding="utf-8")
    diff_lines = list(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=str(target),
            tofile="<generated>",
        )
    )
    if diff_lines:
        typer.echo("".join(diff_lines))
        typer.echo(f"\nRun with --force to overwrite '{target}'.", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"No changes: '{target}' already matches the generated config.")
    raise typer.Exit(code=0)


def _version_callback(value: bool) -> None:
    if value:
        try:
            ver = importlib.metadata.version("pc-init")
        except importlib.metadata.PackageNotFoundError:  # pragma: no cover
            ver = "unknown"
        typer.echo(ver)
        raise typer.Exit


@contextmanager
def _resolved_preset_base(
    presets: str | None,
) -> Generator[Path | None]:
    """Resolve --presets to a local Path, yielding None for the bundled catalog."""
    if presets is None:
        yield None
    elif not fetcher.is_git_url(presets):
        local = Path(presets)
        if not local.is_dir():
            typer.echo(f"Error: presets directory '{local}' does not exist.", err=True)
            raise typer.Exit(code=1)
        yield local
    else:
        try:
            with fetcher.fetch_preset_repo(presets) as cloned:
                yield cloned
        except PresetFetchError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc


app = typer.Typer(
    name="pc-init",
    help="Generate a .pre-commit-config.yaml for your project.",
    add_completion=False,
)


def _expand_comma_separated(raw: list[str] | None) -> list[str]:
    """Split comma-delimited items, strip whitespace, and filter empty strings."""
    return [
        v for item in (raw or []) for v in (s.strip() for s in item.split(",")) if v
    ]


def _normalize_langs(raw_langs: list[str] | None) -> list[str]:
    """Lowercase, resolve aliases, and deduplicate language values."""
    return deduplicate_preserving_order(
        [normalize_lang(v) for v in _expand_comma_separated(raw_langs)]
    )


def _normalize_frameworks(raw_frameworks: list[str] | None) -> list[str]:
    """Lowercase and deduplicate framework values."""
    return deduplicate_preserving_order(
        [normalize_framework(v) for v in _expand_comma_separated(raw_frameworks)]
    )


_PRESETS_HELP = (
    "Preset catalog to use. Accepts a local directory path or a git "
    "repository URL (https://, git@, git://, ssh://). The directory / "
    "repo root must contain lang/ and framework/ subdirectories. "
    "Defaults to the bundled presets."
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    lang: Annotated[
        list[str] | None,
        typer.Option(
            "--lang",
            help=(
                "Language preset to include (repeatable, or comma-delimited: "
                "--lang=py,js). "
                "Run `pc-init list` to see supported values from the active catalog."
            ),
        ),
    ] = None,
    framework: Annotated[
        list[str] | None,
        typer.Option(
            "--framework",
            help=(
                "Framework preset to layer on top of language baselines "
                "(repeatable, or comma-delimited: --framework=react,django). "
                "Run `pc-init list` to see supported values from the active "
                "catalog."
            ),
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite existing .pre-commit-config.yaml without prompting.",
        ),
    ] = False,
    output: Annotated[
        str,
        typer.Option(
            "--output",
            help="Output file path. Defaults to .pre-commit-config.yaml.",
        ),
    ] = ".pre-commit-config.yaml",
    presets: Annotated[
        str | None,
        typer.Option("--presets", help=_PRESETS_HELP),
    ] = None,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """
    Generate a .pre-commit-config.yaml from language and optional framework presets.

    At least one --lang value is required. --framework values are optional.
    Use --force to overwrite an existing config file.
    Run `pc-init list` to see all available languages and frameworks.
    """
    if ctx.invoked_subcommand is not None:
        return

    if not lang:
        typer.echo(
            "No --lang specified. "
            "Run `pc-init list` to see available languages and frameworks.",
            err=True,
        )
        raise typer.Exit(code=1)

    langs = _normalize_langs(lang)
    frameworks = _normalize_frameworks(framework)

    target = Path(output)

    with _resolved_preset_base(presets) as base_dir:
        _dispatch(langs, frameworks, target, base_dir, force=force)


@app.command("list")
def list_presets(
    presets: Annotated[
        str | None,
        typer.Option("--presets", help=_PRESETS_HELP),
    ] = None,
) -> None:
    """List available language and framework presets in the active catalog."""
    with _resolved_preset_base(presets) as base_dir:
        langs = get_supported_languages(base_dir)
        frameworks = get_supported_frameworks(base_dir)

    typer.echo("Languages:")
    typer.echo("  " + ", ".join(langs))
    typer.echo("\nFrameworks:")
    typer.echo("  " + ", ".join(frameworks))


def entry_point() -> None:
    """Entry point for the pc-init command."""
    app()


if __name__ == "__main__":  # pragma: no cover
    app()
