"""Load language and framework presets from the filesystem."""

from pathlib import Path
from typing import Any

import yaml

from gpc_init.exceptions import PresetNotFoundError, PresetParseError

# Base directory containing lang/ and framework/ preset folders.
# In development the symlinks gpc_init/lang -> ../lang resolve here; when installed
# from a wheel the real copies are present at the same location.
_DEFAULT_PRESETS_BASE = Path(__file__).parent


def _resolve_base(base_dir: Path | None) -> Path:
    return base_dir if base_dir is not None else _DEFAULT_PRESETS_BASE


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file, raising structured errors on failure."""
    if not path.exists():
        msg = f"Preset file not found: {path}"
        raise PresetNotFoundError(msg)
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        msg = f"Failed to parse preset YAML '{path}': {exc}"
        raise PresetParseError(msg) from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        msg = (
            f"Preset file '{path}' must contain a YAML mapping,"
            f" got {type(data).__name__}"
        )
        raise PresetParseError(msg)
    return data


def load_common_preset(base_dir: Path | None = None) -> dict[str, Any]:
    """
    Load the common baseline preset (lang/common/default.yaml).

    Returns an empty dict if the file does not exist.
    """
    path = _resolve_base(base_dir) / "lang" / "common" / "default.yaml"
    if not path.exists():
        return {}
    return _load_yaml_file(path)


def load_language_preset(lang_id: str, base_dir: Path | None = None) -> dict[str, Any]:
    """
    Load the baseline preset for a language (lang/<lang_id>/baseline.yaml).

    Args:
        lang_id: Canonical language identifier (e.g. 'py', 'js', 'go', 'ru').
        base_dir: Override base directory for presets (used in tests).

    Returns:
        Parsed preset as a dictionary.

    Raises:
        PresetNotFoundError: If the preset file does not exist.
        PresetParseError: If the YAML is invalid or not a mapping.

    """
    return _load_yaml_file(_resolve_base(base_dir) / "lang" / lang_id / "baseline.yaml")


def load_framework_preset(
    framework_id: str, base_dir: Path | None = None
) -> dict[str, Any]:
    """
    Load the preset for a framework (framework/<framework_id>/preset.yaml).

    Args:
        framework_id: Canonical framework identifier (e.g. 'react', 'bevy').
        base_dir: Override base directory for presets (used in tests).

    Returns:
        Parsed preset as a dictionary.

    Raises:
        PresetNotFoundError: If the preset file does not exist.
        PresetParseError: If the YAML is invalid or not a mapping.

    """
    return _load_yaml_file(
        _resolve_base(base_dir) / "framework" / framework_id / "preset.yaml"
    )
