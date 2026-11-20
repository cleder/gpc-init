"""pc-init CLI: Generate .pre-commit-config.yaml or prek.toml from presets."""

import difflib
import importlib.metadata
import shlex
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Annotated, NoReturn
from urllib.parse import urlsplit, urlunsplit

import typer

from gpc_init import fetcher
from gpc_init.catalog import Catalog
from gpc_init.detector import detect_frameworks, detect_languages
from gpc_init.exceptions import (
    MetadataConflictError,
    PresetFetchError,
    PresetNotFoundError,
    PresetParseError,
    UnsupportedFrameworkError,
    UnsupportedLanguageError,
    UnsupportedProfileError,
)
from gpc_init.generator import (
    GeneratedConfig,
    GenerationRequest,
    OutputFormat,
    generate,
)
from gpc_init.resolver import (
    SELECTABLE_PROFILES,
    normalize_framework,
    normalize_lang,
)
from gpc_init.util import deduplicate_preserving_order


def _generate_or_exit(request: GenerationRequest) -> GeneratedConfig:
    """Run generate, turning expected preset errors into a clean exit 1."""
    try:
        return generate(request)
    except (
        UnsupportedLanguageError,
        UnsupportedFrameworkError,
        UnsupportedProfileError,
        PresetNotFoundError,
    ) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except PresetParseError as exc:
        typer.echo(f"Error: failed to parse preset YAML: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _read_text(target: Path) -> str:
    """Read target as UTF-8, turning I/O errors into a clean exit 1."""
    try:
        return target.read_text(encoding="utf-8")
    except (PermissionError, OSError) as exc:
        typer.echo(f"Error: cannot read '{target}': {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _write_text(target: Path, content: str) -> None:
    """Write content to target as UTF-8, turning I/O errors into a clean exit 1."""
    try:
        target.write_text(content, encoding="utf-8")
    except (PermissionError, OSError) as exc:
        typer.echo(f"Error: cannot write to '{target}': {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _recommendation_advice(
    result: GeneratedConfig,
    request: GenerationRequest,
    *,
    output: str | None,
    presets: str | None,
) -> str | None:
    """
    Render the notes about missing recommendations plus a ``Try:`` command.

    The command repeats the whole run (profiles, format, output, presets, ...)
    with the missing languages and frameworks added, so running it yields the
    same config plus the recommended presets. It ends in ``--force`` because it
    overwrites the file this run just wrote. URL credentials in ``--presets`` are
    redacted, so a line tells the user to put them back.
    """
    recs = result.recommendations
    if recs is None:
        return None
    wider = replace(
        request,
        langs=(*request.langs, *recs.missing_langs),
        frameworks=(*request.frameworks, *recs.missing_frameworks),
    )
    command = _build_force_command(wider, output=output, presets=presets)
    lines = [*recs.notes, f"      Try: {command}"]
    if presets and _redact_url_credentials(presets) != presets:
        lines.append("      (the --presets credentials are hidden; add them back)")
    return "\n".join(lines)


def _write_config(
    target: Path,
    request: GenerationRequest,
    result: GeneratedConfig,
    advice: str | None,
) -> None:
    """Write the generated config to target and report what was done."""
    overwritten = target.exists()
    _write_text(target, result.content)

    if advice:
        typer.echo(advice)

    lang_str = ", ".join(result.langs)
    fw_str = (", ".join(result.frameworks)) if result.frameworks else "none"
    action = "Overwrote" if overwritten else "Generated"
    msg = f"{action} {target} with languages: {lang_str} and frameworks: {fw_str}"
    if request.profiles:
        msg += f" and profiles: {', '.join(request.profiles)}"
    typer.echo(msg)


def _redact_url_credentials(value: str) -> str:
    """
    Hide the credentials in a URL so they are not echoed into logs.

    An http(s) URL's user info is a token or password and is replaced by ``***``;
    so is any user info that carries a password. A bare ``git@`` user (scp-style
    or ssh://) is public and kept, and values that are not URLs are unchanged.
    """
    url = urlsplit(value)
    secret = url.password is not None or (
        url.scheme in ("http", "https") and url.username is not None
    )
    if not secret:
        return value
    host = url.netloc.rpartition("@")[2]
    return urlunsplit(url._replace(netloc=f"***@{host}"))


def _build_force_command(
    request: GenerationRequest, *, output: str | None, presets: str | None
) -> str:
    """
    Return a ready-to-run pc-init command that repeats the run, plus --force.

    output and presets are the raw option values: without them the command would
    write to the default file or use the bundled catalog instead. Every ``Try:``
    command is built here, so none can drop an option of the run.
    """
    parts = ["pc-init"]
    if request.langs:
        parts.append(f"--lang={','.join(request.langs)}")
    if request.frameworks:
        parts.append(f"--framework={','.join(request.frameworks)}")
    if request.profiles:
        parts.append(f"--profile={','.join(request.profiles)}")
    if request.fmt is not OutputFormat.YAML:
        parts.append(f"--format={request.fmt.value}")
    if request.recommended:
        parts.append("--recommended")
    if presets:
        parts.append(f"--presets={_redact_url_credentials(presets)}")
    if output:
        parts.append(f"--output={output}")
    parts.append("--force")
    return shlex.join(parts)


def _show_diff_and_exit(
    target: Path, result: GeneratedConfig, force_command: str
) -> NoReturn:
    """Show a unified diff of target vs the generated config. Always exits."""
    diff_lines = list(
        difflib.unified_diff(
            _read_text(target).splitlines(keepends=True),
            result.content.splitlines(keepends=True),
            fromfile=str(target),
            tofile="<generated>",
        )
    )
    if diff_lines:
        typer.echo("".join(diff_lines))
        typer.echo(
            f"\nRun with --force to overwrite '{target}'.\n  Try: {force_command}",
            err=True,
        )
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
def _preset_root(
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


@contextmanager
def _open_catalog(presets: str | None) -> Generator[Catalog]:
    """Resolve --presets and load the catalog rooted there, exiting 1 on errors."""
    with _preset_root(presets) as root:
        try:
            yield Catalog.load(root)
        except (PresetNotFoundError, MetadataConflictError, PresetParseError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc


app = typer.Typer(
    name="pc-init",
    help="Generate a .pre-commit-config.yaml for your project.",
    add_completion=False,
)


def _apply_detection(
    lang: list[str] | None,
    framework: list[str] | None,
    catalog: Catalog,
) -> tuple[list[str], list[str]]:
    """Run auto-detection, print results, and merge with explicit flags."""
    repo_dir = Path.cwd()
    detected_langs = detect_languages(repo_dir, catalog)
    detected_frameworks = detect_frameworks(repo_dir, catalog)
    if detected_langs:
        typer.echo(f"Detected languages: {', '.join(detected_langs)}")
    if detected_frameworks:
        typer.echo(f"Detected frameworks: {', '.join(detected_frameworks)}")
    return (
        [*detected_langs, *_expand_comma_separated(lang)],
        [*detected_frameworks, *_expand_comma_separated(framework)],
    )


def _require_lang_or_exit(
    lang: list[str] | None,
    framework: list[str] | None,
    *,
    recommended: bool,
    detect: bool,
) -> None:
    """Exit with an error when no language is available and none can be inferred."""
    if lang or (recommended and framework):
        return
    msg = (
        "No --lang specified and none detected. "
        "Run `pc-init list` to see available languages and frameworks."
    )
    if framework:
        msg += " Use --recommended to apply languages suggested by the frameworks."
    if not detect:
        msg += " Use --detect to auto-detect languages from the current directory."
    typer.echo(msg, err=True)
    raise typer.Exit(code=1)


def _expand_comma_separated(raw: list[str] | None) -> list[str]:
    """Split comma-delimited items, strip whitespace, and filter empty strings."""
    return [
        v for item in (raw or []) for v in (s.strip() for s in item.split(",")) if v
    ]


def _normalize_langs(raw_langs: list[str] | None, catalog: Catalog) -> list[str]:
    """Lowercase, resolve aliases, and deduplicate language values."""
    return deduplicate_preserving_order(
        [normalize_lang(v, catalog) for v in _expand_comma_separated(raw_langs)]
    )


def _normalize_frameworks(raw_frameworks: list[str] | None) -> list[str]:
    """Lowercase and deduplicate framework values."""
    return deduplicate_preserving_order(
        [normalize_framework(v) for v in _expand_comma_separated(raw_frameworks)]
    )


def _normalize_profiles(raw_profiles: list[str] | None) -> list[str]:
    """Lowercase and deduplicate profile (hook category) values."""
    return deduplicate_preserving_order(
        [v.strip().lower() for v in _expand_comma_separated(raw_profiles)]
    )


_FORMAT_EXTENSIONS: dict[str, OutputFormat] = {
    ".toml": OutputFormat.TOML,
    ".yaml": OutputFormat.YAML,
    ".yml": OutputFormat.YAML,
}


def _resolve_target(output: str | None, fmt: OutputFormat) -> Path:
    """Return the output path, defaulting by format and rejecting conflicts."""
    if output is None:
        return Path(fmt.default_filename)
    target = Path(output)
    implied = _FORMAT_EXTENSIONS.get(target.suffix.lower())
    if implied is not None and implied is not fmt:
        typer.echo(
            f"Error: --output '{output}' looks like {implied.value.upper()} "
            f"but --format is {fmt.value}.",
            err=True,
        )
        raise typer.Exit(code=1)
    return target


_PRESETS_HELP = (
    "Preset catalog to use. Accepts a local directory path or a git "
    "repository URL (https://, git@, git://, ssh://). The directory / "
    "repo root must contain lang/ and framework/ subdirectories. "
    "Defaults to the bundled presets."
)

_PROFILE_HELP = (
    "Hook profile to include on top of the default preset baseline "
    "(repeatable, or comma-delimited: --profile=legacy,experimental). "
    "preset hooks are always included. Supported: legacy, experimental."
)


_LangOption = Annotated[
    list[str] | None,
    typer.Option(
        "--lang",
        help=(
            "Language preset to include (repeatable, or comma-delimited: "
            "--lang=py,js). "
            "Run `pc-init list` to see supported values from the active catalog."
        ),
    ),
]
_FrameworkOption = Annotated[
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
]
_ForceOption = Annotated[
    bool,
    typer.Option(
        "--force", help="Overwrite an existing output file without prompting."
    ),
]
_OutputOption = Annotated[
    str | None,
    typer.Option(
        "--output",
        help=(
            "Output file path. Defaults to .pre-commit-config.yaml, or "
            "prek.toml with --format toml. A .toml/.yaml/.yml extension "
            "that contradicts --format is an error."
        ),
    ),
]
_FormatOption = Annotated[
    OutputFormat,
    typer.Option(
        "--format",
        help=(
            "Output format: yaml (.pre-commit-config.yaml) or toml "
            "(prek.toml). The toml format is read by prek only; plain "
            "pre-commit cannot read it."
        ),
    ),
]
_RecommendedOption = Annotated[
    bool,
    typer.Option(
        "--recommended",
        help=(
            "Automatically include all languages and frameworks recommended "
            "by the selected presets."
        ),
    ),
]
_DetectOption = Annotated[
    bool,
    typer.Option(
        "--detect",
        help=(
            "Auto-detect languages and frameworks from the current directory "
            "and merge them with any explicitly supplied --lang/--framework values."
        ),
    ),
]
_ProfileOption = Annotated[
    list[str] | None, typer.Option("--profile", help=_PROFILE_HELP)
]
_PresetsOption = Annotated[str | None, typer.Option("--presets", help=_PRESETS_HELP)]
_VersionOption = Annotated[
    bool | None,
    typer.Option(
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
]


@app.callback(invoke_without_command=True)
def main(  # noqa: PLR0917
    ctx: typer.Context,
    lang: _LangOption = None,
    framework: _FrameworkOption = None,
    force: _ForceOption = False,
    output: _OutputOption = None,
    fmt: _FormatOption = OutputFormat.YAML,
    recommended: _RecommendedOption = False,
    detect: _DetectOption = False,
    profile: _ProfileOption = None,
    presets: _PresetsOption = None,
    version: _VersionOption = None,
) -> None:
    """
    Generate a .pre-commit-config.yaml from language and optional framework presets.

    Use --format toml to write a prek.toml instead (prek only; pre-commit cannot
    read it).

    At least one --lang value is required (or use --detect).
    --framework values are optional. Use --force to overwrite an existing config file.
    Use --profile to include legacy or experimental hooks on top of the default
    preset baseline. Run `pc-init list` to see all available languages and frameworks.
    """
    if ctx.invoked_subcommand is not None:
        return

    with _open_catalog(presets) as catalog:
        if detect:
            lang, framework = _apply_detection(lang, framework, catalog)

        _require_lang_or_exit(lang, framework, recommended=recommended, detect=detect)

        request = GenerationRequest(
            langs=tuple(_normalize_langs(lang, catalog)),
            frameworks=tuple(_normalize_frameworks(framework)),
            catalog=catalog,
            profiles=tuple(_normalize_profiles(profile)),
            fmt=fmt,
            recommended=recommended,
        )
        target = _resolve_target(output, fmt)
        result = _generate_or_exit(request)
        if target.exists() and not force:
            force_command = _build_force_command(
                request, output=output, presets=presets
            )
            _show_diff_and_exit(target, result, force_command)
        advice = _recommendation_advice(result, request, output=output, presets=presets)
        _write_config(target, request, result, advice)


@app.command("list")
def list_presets(
    presets: Annotated[
        str | None,
        typer.Option("--presets", help=_PRESETS_HELP),
    ] = None,
) -> None:
    """List available language and framework presets in the active catalog."""
    with _open_catalog(presets) as catalog:
        langs = catalog.lang_ids
        frameworks = catalog.framework_ids

    typer.echo("Languages:")
    typer.echo("  " + ", ".join(langs))
    typer.echo("\nFrameworks:")
    typer.echo("  " + ", ".join(frameworks))
    typer.echo("\nProfiles (opt in with --profile; preset is always included):")
    typer.echo("  " + ", ".join(sorted(SELECTABLE_PROFILES)))


def entry_point() -> None:
    """Entry point for the pc-init command."""
    app()


if __name__ == "__main__":  # pragma: no cover
    app()
