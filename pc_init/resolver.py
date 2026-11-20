"""Resolve and validate generation requests against the preset catalog."""

from dataclasses import dataclass
from typing import Any

from pc_init.catalog import Catalog
from pc_init.exceptions import (
    UnsupportedFrameworkError,
    UnsupportedLanguageError,
    UnsupportedProfileError,
)

# Selectable hook profiles (categories) on top of the always-on "preset" baseline.
SELECTABLE_PROFILES = frozenset({"legacy", "experimental"})


@dataclass(frozen=True)
class Recommendations:
    """Recommended languages/frameworks the selection is missing."""

    notes: tuple[str, ...]
    missing_langs: tuple[str, ...]
    missing_frameworks: tuple[str, ...]


def _validate(
    supported: list[str], values: list[str], error_cls: type[Exception]
) -> None:
    for value in values:
        if value not in supported:
            raise error_cls(value, supported)


def normalize_lang(lang: str, catalog: Catalog) -> str:
    """
    Normalize a language value: lowercase and resolve aliases to canonical id.

    Aliases are catalog-specific, since a custom --presets catalog can declare
    its own languages and aliases.
    """
    normalized = lang.strip().lower()
    return catalog.alias_to_lang.get(normalized, normalized)


def normalize_framework(fw: str) -> str:
    """Normalize a framework value: lowercase and strip whitespace."""
    return fw.strip().lower()


def validate_langs(langs: list[str], catalog: Catalog) -> None:
    """
    Validate that all requested language ids are supported.

    Args:
        langs: Normalized language ids to validate.
        catalog: The catalog whose languages are supported.

    Raises:
        UnsupportedLanguageError: If any language is not in the catalog.

    """
    _validate(catalog.lang_ids, langs, UnsupportedLanguageError)


def validate_frameworks(frameworks: list[str], catalog: Catalog) -> None:
    """
    Validate that all requested framework ids are supported.

    Args:
        frameworks: Normalized framework ids to validate.
        catalog: The catalog whose frameworks are supported.

    Raises:
        UnsupportedFrameworkError: If any framework is not in the catalog.

    """
    _validate(catalog.framework_ids, frameworks, UnsupportedFrameworkError)


def validate_profiles(profiles: list[str]) -> None:
    """
    Validate that all requested profile/category values are supported.

    Args:
        profiles: Normalized profile values to validate (e.g. ["legacy"]).

    Raises:
        UnsupportedProfileError: If any profile is not legacy/experimental.

    """
    _validate(sorted(SELECTABLE_PROFILES), profiles, UnsupportedProfileError)


def _normalize_rec(preset: dict[str, Any]) -> dict[str, Any]:
    rec: dict[str, Any] | list[Any] = (
        preset.get("recommended") or preset.get("primary_languages") or {}
    )
    if isinstance(rec, list):
        return {"lang": rec}
    return rec


def expand_recommendations(  # noqa: PLR0913
    *,
    langs: list[str],
    frameworks: list[str],
    lang_presets: list[dict[str, Any]],
    fw_presets: list[dict[str, Any]],
    supported_langs: list[str],
    supported_frameworks: list[str],
) -> tuple[list[str], list[str]]:
    """
    Return (expanded_langs, expanded_frameworks) with preset recommendations applied.

    Reads the ``recommended`` section from every selected preset and appends any
    missing langs/frameworks that exist in the catalog. Single-pass — recommendations
    of newly-added presets are not recursively expanded.

    Args:
        langs: Currently selected language ids.
        frameworks: Currently selected framework ids.
        lang_presets: Loaded lang preset dicts (same order as langs).
        fw_presets: Loaded framework preset dicts (same order as frameworks).
        supported_langs: Full list of available language ids in the catalog.
        supported_frameworks: Full list of available framework ids in the catalog.

    """
    extra_langs: list[str] = []
    extra_fws: list[str] = []
    for preset in [*lang_presets, *fw_presets]:
        rec = _normalize_rec(preset)
        for lang in rec.get("lang") or []:
            if (
                lang not in langs
                and lang not in extra_langs
                and lang in supported_langs
            ):
                extra_langs.append(lang)
        for fw in rec.get("framework") or []:
            if (
                fw not in frameworks
                and fw not in extra_fws
                and fw in supported_frameworks
            ):
                extra_fws.append(fw)
    return [*langs, *extra_langs], [*frameworks, *extra_fws]


def _missing_recommendations(
    preset: dict[str, Any],
    langs: list[str],
    frameworks: list[str],
) -> tuple[list[str], list[str]]:
    rec = _normalize_rec(preset)
    missing_langs = [lang for lang in (rec.get("lang") or []) if lang not in langs]
    missing_fws = [fw for fw in (rec.get("framework") or []) if fw not in frameworks]
    return missing_langs, missing_fws


def _extend_unique(target: list[str], items: list[str]) -> None:
    for item in items:
        if item not in target:
            target.append(item)


def get_recommendations(
    langs: list[str],
    frameworks: list[str],
    lang_presets: list[dict[str, Any]],
    fw_presets: list[dict[str, Any]],
) -> Recommendations | None:
    """
    Return the unmet recommendations of the selected presets, or None.

    Each preset (lang or framework) may declare a ``recommended`` section listing
    languages and frameworks it is typically used with. When any recommended item
    is absent from the current selection, the result carries one note per preset
    and the consolidated, de-duplicated missing languages and frameworks.

    It does not build a command: only the caller knows the whole invocation
    (--profile, --format, --output, --presets, ...) a suggestion has to repeat.

    Args:
        langs: Normalized selected language ids.
        frameworks: Normalized selected framework ids.
        lang_presets: Loaded language preset dicts (same order as langs).
        fw_presets: Loaded framework preset dicts (same order as frameworks).

    """
    notes: list[str] = []
    extra_langs: list[str] = []
    extra_fws: list[str] = []

    for preset_id, preset in [
        *zip(langs, lang_presets, strict=True),
        *zip(frameworks, fw_presets, strict=True),
    ]:
        missing_langs, missing_fws = _missing_recommendations(preset, langs, frameworks)
        if not missing_langs and not missing_fws:
            continue

        parts: list[str] = []
        if missing_langs:
            parts.append(f"--lang={','.join(missing_langs)}")
        if missing_fws:
            parts.append(f"--framework={','.join(missing_fws)}")
        notes.append(f"Note: preset '{preset_id}' recommends adding: {' '.join(parts)}")

        _extend_unique(extra_langs, missing_langs)
        _extend_unique(extra_fws, missing_fws)

    if not notes:
        return None
    return Recommendations(
        notes=tuple(notes),
        missing_langs=tuple(extra_langs),
        missing_frameworks=tuple(extra_fws),
    )
