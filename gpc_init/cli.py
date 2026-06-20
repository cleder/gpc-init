"""pc-init CLI: Generate .pre-commit-config.yaml from language and framework presets."""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from gpc_init.exceptions import (
    PresetNotFoundError,
    PresetParseError,
    TargetFileExistsError,
    UnsupportedFrameworkError,
    UnsupportedLanguageError,
)
from gpc_init.loader import load_common_preset, load_framework_preset, load_language_preset
from gpc_init.merger import merge_presets
from gpc_init.renderer import render_yaml
from gpc_init.resolver import (
    deduplicate_preserving_order,
    get_primary_languages_info,
    normalize_framework,
    normalize_lang,
    validate_frameworks,
    validate_langs,
)

app = typer.Typer(
    name="pc-init",
    help="Generate a .pre-commit-config.yaml for your project.",
    add_completion=False,
)


def _normalize_langs(raw_langs: list[str]) -> list[str]:
    """Lowercase, resolve aliases, and deduplicate language values."""
    return deduplicate_preserving_order([normalize_lang(v) for v in raw_langs])


def _normalize_frameworks(raw_frameworks: list[str]) -> list[str]:
    """Lowercase and deduplicate framework values."""
    return deduplicate_preserving_order([normalize_framework(v) for v in raw_frameworks])


@app.command()
def main(
    lang: Annotated[
        list[str],
        typer.Option(
            "--lang",
            help="Language preset to include (repeatable). "
            "Supported: py, js, go, ru. Aliases: python, javascript, rust.",
        ),
    ],
    framework: Annotated[
        Optional[list[str]],
        typer.Option(
            "--framework",
            help="Framework preset to layer on top of language baselines (repeatable). "
            "Supported: react, bevy, django.",
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
) -> None:
    """Generate a .pre-commit-config.yaml from language and optional framework presets.

    At least one --lang value is required. --framework values are optional.
    Use --force to overwrite an existing config file.
    """
    raw_frameworks: list[str] = framework or []

    # Normalize and deduplicate
    langs = _normalize_langs(lang)
    frameworks = _normalize_frameworks(raw_frameworks)

    try:
        # Validate
        validate_langs(langs)
        validate_frameworks(frameworks)

        # Check existing file
        target = Path(output)
        if target.exists() and not force:
            raise TargetFileExistsError(str(target))

        # Load presets
        common = load_common_preset()
        lang_presets = [load_language_preset(lang_id) for lang_id in langs]
        fw_presets = [load_framework_preset(fw_id) for fw_id in frameworks]

        # Merge
        merged = merge_presets(common, lang_presets, fw_presets)

        # Render
        content = render_yaml(merged)

        # Write
        overwritten = target.exists()
        try:
            target.write_text(content, encoding="utf-8")
        except (PermissionError, OSError) as exc:
            typer.echo(
                f"Error: cannot write to '{target}': {exc}", err=True
            )
            raise typer.Exit(code=1) from exc

        # Report informational primary_languages notes
        info = get_primary_languages_info(frameworks, fw_presets, langs)
        if info:
            typer.echo(info)

        # Success message
        lang_str = ", ".join(langs)
        fw_str = (", ".join(frameworks)) if frameworks else "none"
        action = "Overwrote" if overwritten else "Generated"
        typer.echo(
            f"{action} {target} with languages: {lang_str} and frameworks: {fw_str}"
        )

    except TargetFileExistsError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

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


def entry_point() -> None:
    """Entry point for the pc-init command."""
    app()


if __name__ == "__main__":
    app()
