"""Orchestrate validation, loading, merging, and rendering into a config file."""

from dataclasses import dataclass
from typing import Any

from gpc_init.catalog import Catalog
from gpc_init.merger import DEFAULT_CATEGORY, filter_by_category, merge_presets
from gpc_init.renderer import OutputFormat, render
from gpc_init.resolver import (
    expand_recommendations,
    get_recommendations_info,
    validate_frameworks,
    validate_langs,
    validate_profiles,
)

__all__ = ["GeneratedConfig", "GenerationRequest", "OutputFormat", "generate"]


@dataclass(frozen=True)
class GenerationRequest:
    """Everything that determines one generated config."""

    langs: tuple[str, ...]
    frameworks: tuple[str, ...]
    catalog: Catalog
    profiles: tuple[str, ...] = ()
    fmt: OutputFormat = OutputFormat.YAML
    recommended: bool = False


@dataclass(frozen=True)
class GeneratedConfig:
    """
    Rendered config plus the final (post-expansion) langs and frameworks.

    advice is the ready-to-print note about recommended languages/frameworks the
    selection is missing, or None (also None when recommendations were applied).
    """

    content: str
    langs: tuple[str, ...]
    frameworks: tuple[str, ...]
    advice: str | None = None

    @property
    def yaml_content(self) -> str:
        """Alias for ``content``, kept for backward compatibility."""
        return self.content


def _load_all(
    langs: list[str], frameworks: list[str], catalog: Catalog
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lang_presets = [catalog.lang_preset(lang_id) for lang_id in langs]
    fw_presets = [catalog.framework_preset(fw_id) for fw_id in frameworks]
    return lang_presets, fw_presets


def generate(request: GenerationRequest) -> GeneratedConfig:
    """
    Validate, load, merge, filter by profile, render.

    When request.recommended is set the lang/framework lists are expanded with
    every recommendation from the selected presets before merging.
    request.profiles selects additional hook categories (legacy/experimental)
    to include on top of the always-on 'preset' baseline; request.fmt selects
    the output format (YAML or prek TOML).

    Raises:
        PresetNotFoundError: If a requested preset file is missing.
        UnsupportedLanguageError: If a requested language isn't in the catalog.
        UnsupportedFrameworkError: If a requested framework isn't in the catalog.
        UnsupportedProfileError: If a requested profile isn't in the catalog.
        PresetParseError: If a preset file contains invalid YAML.

    """
    catalog = request.catalog
    langs, frameworks = list(request.langs), list(request.frameworks)
    validate_langs(langs, catalog)
    validate_frameworks(frameworks, catalog)
    validate_profiles(list(request.profiles))

    lang_presets, fw_presets = _load_all(langs, frameworks, catalog)

    if request.recommended:
        langs, frameworks = expand_recommendations(
            langs=langs,
            frameworks=frameworks,
            lang_presets=lang_presets,
            fw_presets=fw_presets,
            supported_langs=catalog.lang_ids,
            supported_frameworks=catalog.framework_ids,
        )
        lang_presets, fw_presets = _load_all(langs, frameworks, catalog)

    merged = merge_presets(catalog.common_preset(), lang_presets, fw_presets)
    categories = frozenset({DEFAULT_CATEGORY, *request.profiles})
    merged = filter_by_category(merged, categories)
    advice = (
        None
        if request.recommended
        else get_recommendations_info(langs, frameworks, lang_presets, fw_presets)
    )
    return GeneratedConfig(
        content=render(merged, request.fmt),
        langs=tuple(langs),
        frameworks=tuple(frameworks),
        advice=advice,
    )
