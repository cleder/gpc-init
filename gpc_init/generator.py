"""Orchestrate validation, loading, merging, and rendering into config YAML."""

from pathlib import Path
from typing import Any, NamedTuple

from gpc_init.exceptions import PresetNotFoundError
from gpc_init.loader import (
    load_common_preset,
    load_framework_preset,
    load_language_preset,
)
from gpc_init.merger import DEFAULT_CATEGORY, filter_by_category, merge_presets
from gpc_init.renderer import render_yaml
from gpc_init.resolver import (
    expand_recommendations,
    get_supported_frameworks,
    get_supported_languages,
    validate_frameworks,
    validate_langs,
    validate_profiles,
)


class GeneratedConfig(NamedTuple):
    """Rendered config plus the final (post-expansion) langs/frameworks/presets."""

    yaml_content: str
    langs: list[str]
    frameworks: list[str]
    lang_presets: list[dict[str, Any]]
    fw_presets: list[dict[str, Any]]


def _load_all(
    langs: list[str], frameworks: list[str], base_dir: Path | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lang_presets = [
        load_language_preset(lang_id, base_dir=base_dir) for lang_id in langs
    ]
    fw_presets = [
        load_framework_preset(fw_id, base_dir=base_dir) for fw_id in frameworks
    ]
    return lang_presets, fw_presets


def generate(
    langs: list[str],
    frameworks: list[str],
    base_dir: Path | None,
    *,
    recommended: bool = False,
    profiles: tuple[str, ...] = (),
) -> GeneratedConfig:
    """
    Validate, load, merge, filter by profile, render.

    When recommended=True the lang/framework lists are expanded with every
    recommendation from the selected presets before merging.
    profiles selects additional hook categories (legacy/experimental) to
    include on top of the always-on 'preset' baseline.

    Raises:
        PresetNotFoundError: If base_dir doesn't contain a 'lang' subdirectory,
            or a requested preset file is missing.
        UnsupportedLanguageError: If a requested language isn't in the catalog.
        UnsupportedFrameworkError: If a requested framework isn't in the catalog.
        UnsupportedProfileError: If a requested profile isn't in the catalog.
        PresetParseError: If a preset file contains invalid YAML.

    """
    if base_dir is not None and not (base_dir / "lang").is_dir():
        msg = f"'{base_dir}' must contain a 'lang' subdirectory."
        raise PresetNotFoundError(msg)

    validate_langs(langs, base_dir=base_dir)
    validate_frameworks(frameworks, base_dir=base_dir)
    validate_profiles(list(profiles))

    common = load_common_preset(base_dir=base_dir)
    lang_presets, fw_presets = _load_all(langs, frameworks, base_dir)

    if recommended:
        langs, frameworks = expand_recommendations(
            langs=langs,
            frameworks=frameworks,
            lang_presets=lang_presets,
            fw_presets=fw_presets,
            supported_langs=get_supported_languages(base_dir),
            supported_frameworks=get_supported_frameworks(base_dir),
        )
        lang_presets, fw_presets = _load_all(langs, frameworks, base_dir)

    merged = merge_presets(common, lang_presets, fw_presets)
    merged = filter_by_category(merged, frozenset({DEFAULT_CATEGORY, *profiles}))
    return GeneratedConfig(
        render_yaml(merged), langs, frameworks, lang_presets, fw_presets
    )
