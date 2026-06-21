"""Resolve and validate generation requests against the preset catalog."""

from pathlib import Path
from typing import Any

from gpc_init.exceptions import UnsupportedFrameworkError, UnsupportedLanguageError

# Language name aliases -> canonical id
_LANG_ALIASES: dict[str, str] = {
    "python": "py",
    "javascript": "js",
    "rust": "ru",
    "golang": "go",
}

# Default base directory for preset discovery.
# In development the symlinks gpc_init/lang -> ../lang resolve here; when installed
# from a wheel the real copies are present at the same location.
_DEFAULT_PRESETS_BASE = Path(__file__).parent


def _resolve_base(base_dir: Path | None) -> Path:
    return base_dir if base_dir is not None else _DEFAULT_PRESETS_BASE


def _discover_languages(base_dir: Path) -> list[str]:
    """Scan lang/<lang>/preset.yaml and return sorted list of language ids."""
    lang_dir = base_dir / "lang"
    if not lang_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in lang_dir.iterdir()
        if d.is_dir() and d.name != "common" and (d / "preset.yaml").exists()
    )


def _discover_frameworks(base_dir: Path) -> list[str]:
    """Scan framework/<fw>/preset.yaml and return sorted list of framework ids."""
    fw_dir = base_dir / "framework"
    if not fw_dir.is_dir():
        return []
    return sorted(
        d.name for d in fw_dir.iterdir() if d.is_dir() and (d / "preset.yaml").exists()
    )


def normalize_lang(lang: str) -> str:
    """Normalize a language value: lowercase and resolve aliases to canonical id."""
    normalized = lang.strip().lower()
    return _LANG_ALIASES.get(normalized, normalized)


def normalize_framework(fw: str) -> str:
    """Normalize a framework value: lowercase and strip whitespace."""
    return fw.strip().lower()


def deduplicate_preserving_order(values: list[str]) -> list[str]:
    """Remove duplicate values from a list, preserving first-occurrence order."""
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


def get_supported_languages(base_dir: Path | None = None) -> list[str]:
    """
    Return sorted list of supported language ids discovered from the filesystem.

    Args:
        base_dir: Override base directory for preset discovery (used in tests).

    """
    return _discover_languages(_resolve_base(base_dir))


def get_supported_frameworks(base_dir: Path | None = None) -> list[str]:
    """
    Return sorted list of supported framework ids discovered from the filesystem.

    Args:
        base_dir: Override base directory for preset discovery (used in tests).

    """
    return _discover_frameworks(_resolve_base(base_dir))


def validate_langs(langs: list[str], base_dir: Path | None = None) -> None:
    """
    Validate that all requested language ids are supported.

    Args:
        langs: Normalized language ids to validate.
        base_dir: Override base directory for preset discovery (used in tests).

    Raises:
        UnsupportedLanguageError: If any language is not in the catalog.

    """
    supported = get_supported_languages(base_dir)
    for lang in langs:
        if lang not in supported:
            raise UnsupportedLanguageError(lang, supported)


def validate_frameworks(frameworks: list[str], base_dir: Path | None = None) -> None:
    """
    Validate that all requested framework ids are supported.

    Args:
        frameworks: Normalized framework ids to validate.
        base_dir: Override base directory for preset discovery (used in tests).

    Raises:
        UnsupportedFrameworkError: If any framework is not in the catalog.

    """
    supported = get_supported_frameworks(base_dir)
    for fw in frameworks:
        if fw not in supported:
            raise UnsupportedFrameworkError(fw, supported)


def get_primary_languages_info(
    frameworks: list[str],
    framework_presets: list[dict[str, Any]],
    selected_langs: list[str],
) -> str | None:
    """
    Return a message if selected langs don't match a framework's primary_languages.

    This is purely informational and non-blocking.

    Args:
        frameworks: Normalized framework ids.
        framework_presets: Loaded framework preset dicts.
        selected_langs: Normalized selected language ids.

    Returns:
        Informational message string, or None if no mismatch.

    """
    messages: list[str] = []
    for fw_id, fw_preset in zip(frameworks, framework_presets, strict=True):
        primary = fw_preset.get("primary_languages", [])
        if primary and not any(lang in primary for lang in selected_langs):
            primary_str = ", ".join(primary)
            messages.append(
                f"Note: framework '{fw_id}' is typically used with: {primary_str}"
            )
    return "\n".join(messages) if messages else None
