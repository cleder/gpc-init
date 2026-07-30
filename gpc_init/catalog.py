"""Load lang/framework metadata: display info, extensions, aliases, detection rules."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from gpc_init.exceptions import MetadataConflictError, PresetParseError

# Base directory containing lang/ and framework/ preset folders.
# In development the symlinks gpc_init/lang -> ../lang resolve here; when installed
# from a wheel the real copies are present at the same location.
_DEFAULT_PRESETS_BASE = Path(__file__).parent


def _resolve_base(base_dir: Path | None) -> Path:
    return base_dir if base_dir is not None else _DEFAULT_PRESETS_BASE


@dataclass(frozen=True)
class LangMetadata:
    """Display info and detection data for a single language."""

    id: str
    fullname: str
    icon: str = ""
    extensions: tuple[str, ...] = field(default_factory=tuple)
    filenames: tuple[str, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FrameworkMetadata:
    """Display info and detection rules for a single framework."""

    id: str
    fullname: str
    icon: str = ""
    detect: tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Catalog:
    """Resolved lang/framework metadata plus derived detection lookup tables."""

    langs: dict[str, LangMetadata]
    frameworks: dict[str, FrameworkMetadata]
    extension_to_lang: dict[str, str]
    filename_to_lang: dict[str, str]
    alias_to_lang: dict[str, str]


def _load_metadata_file(path: Path) -> dict[str, Any]:
    """Load and parse a metadata.yaml file, returning {} when it doesn't exist."""
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        msg = f"Failed to parse metadata YAML '{path}': {exc}"
        raise PresetParseError(msg) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = (
            f"Metadata file '{path}' must contain a YAML mapping,"
            f" got {type(data).__name__}"
        )
        raise PresetParseError(msg)
    return data


def _discover_ids(
    kind_dir: Path, *, exclude: frozenset[str] = frozenset()
) -> list[str]:
    """Return sorted names of subdirectories that contain a preset.yaml."""
    if not kind_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in kind_dir.iterdir()
        if d.is_dir() and d.name not in exclude and (d / "preset.yaml").exists()
    )


def _load_lang_metadata(lang_dir: Path, lang_id: str) -> LangMetadata:
    data = _load_metadata_file(lang_dir / "metadata.yaml")
    return LangMetadata(
        id=lang_id,
        fullname=str(data.get("fullname") or lang_id),
        icon=str(data.get("icon") or ""),
        extensions=tuple(data.get("extensions") or ()),
        filenames=tuple(data.get("filenames") or ()),
        aliases=tuple(data.get("aliases") or ()),
    )


def _load_framework_metadata(fw_dir: Path, fw_id: str) -> FrameworkMetadata:
    data = _load_metadata_file(fw_dir / "metadata.yaml")
    detect = data.get("detect") or ()
    if isinstance(detect, str | dict):
        detect = (detect,)
    return FrameworkMetadata(
        id=fw_id,
        fullname=str(data.get("fullname") or fw_id),
        icon=str(data.get("icon") or ""),
        detect=tuple(detect),
    )


def _claim_unique(
    mapping: dict[str, str], key: str, owner_id: str, *, kind: str
) -> None:
    """Register key -> owner_id in mapping, raising if another id already owns it."""
    existing = mapping.get(key)
    if existing is not None and existing != owner_id:
        msg = (
            f"{kind} '{key}' is claimed by both '{existing}' and '{owner_id}' — "
            "each extension/filename/alias must belong to exactly one language."
        )
        raise MetadataConflictError(msg)
    mapping[key] = owner_id


def load_catalog(base_dir: Path | None = None) -> Catalog:
    """
    Load and validate the full lang/framework metadata catalog.

    A missing metadata.yaml is tolerated (fullname falls back to the id, no icon,
    no extensions/filenames/aliases/detect rules) so a hand-authored --presets
    catalog that predates this convention keeps working for explicit --lang/
    --framework selection, even without auto-detection or display metadata.

    Args:
        base_dir: Override base directory for preset discovery (used in tests).

    Raises:
        MetadataConflictError: two langs claim the same extension, filename, or
            alias.
        PresetParseError: a metadata.yaml file is malformed.

    """
    base = _resolve_base(base_dir)
    lang_dir = base / "lang"
    fw_dir = base / "framework"

    langs: dict[str, LangMetadata] = {}
    extension_to_lang: dict[str, str] = {}
    filename_to_lang: dict[str, str] = {}
    alias_to_lang: dict[str, str] = {}

    for lang_id in _discover_ids(lang_dir, exclude=frozenset({"common"})):
        meta = _load_lang_metadata(lang_dir / lang_id, lang_id)
        langs[lang_id] = meta
        for ext in meta.extensions:
            _claim_unique(extension_to_lang, ext.lower(), lang_id, kind="Extension")
        for name in meta.filenames:
            _claim_unique(filename_to_lang, name.lower(), lang_id, kind="Filename")
        for alias in meta.aliases:
            _claim_unique(alias_to_lang, alias.lower(), lang_id, kind="Alias")

    frameworks: dict[str, FrameworkMetadata] = {
        fw_id: _load_framework_metadata(fw_dir / fw_id, fw_id)
        for fw_id in _discover_ids(fw_dir)
    }

    return Catalog(
        langs=langs,
        frameworks=frameworks,
        extension_to_lang=extension_to_lang,
        filename_to_lang=filename_to_lang,
        alias_to_lang=alias_to_lang,
    )
