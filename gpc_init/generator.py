"""Orchestrate validation, loading, merging, and rendering into a config file."""

from typing import Any, NamedTuple

from gpc_init.catalog import Catalog
from gpc_init.merger import DEFAULT_CATEGORY, filter_by_category, merge_presets
from gpc_init.renderer import OutputFormat, render
from gpc_init.resolver import (
    expand_recommendations,
    validate_frameworks,
    validate_langs,
    validate_profiles,
)


class GeneratedConfig(NamedTuple):
    """Rendered config plus the final (post-expansion) langs/frameworks/presets."""

    content: str
    langs: list[str]
    frameworks: list[str]
    lang_presets: list[dict[str, Any]]
    fw_presets: list[dict[str, Any]]

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


def generate(  # noqa: PLR0913
    langs: list[str],
    frameworks: list[str],
    catalog: Catalog,
    *,
    recommended: bool = False,
    profiles: tuple[str, ...] = (),
    fmt: OutputFormat = OutputFormat.YAML,
) -> GeneratedConfig:
    """
    Validate, load, merge, filter by profile, render.

    When recommended=True the lang/framework lists are expanded with every
    recommendation from the selected presets before merging.
    profiles selects additional hook categories (legacy/experimental) to
    include on top of the always-on 'preset' baseline.
    fmt selects the output format (YAML or prek TOML).

    Raises:
        PresetNotFoundError: If a requested preset file is missing.
        UnsupportedLanguageError: If a requested language isn't in the catalog.
        UnsupportedFrameworkError: If a requested framework isn't in the catalog.
        UnsupportedProfileError: If a requested profile isn't in the catalog.
        PresetParseError: If a preset file contains invalid YAML.

    """
    validate_langs(langs, catalog)
    validate_frameworks(frameworks, catalog)
    validate_profiles(list(profiles))

    common = catalog.common_preset()
    lang_presets, fw_presets = _load_all(langs, frameworks, catalog)

    if recommended:
        langs, frameworks = expand_recommendations(
            langs=langs,
            frameworks=frameworks,
            lang_presets=lang_presets,
            fw_presets=fw_presets,
            supported_langs=catalog.lang_ids,
            supported_frameworks=catalog.framework_ids,
        )
        lang_presets, fw_presets = _load_all(langs, frameworks, catalog)

    merged = merge_presets(common, lang_presets, fw_presets)
    merged = filter_by_category(merged, frozenset({DEFAULT_CATEGORY, *profiles}))
    return GeneratedConfig(
        render(merged, fmt), langs, frameworks, lang_presets, fw_presets
    )
