"""Load language and framework presets from the filesystem."""

from pathlib import Path
from typing import Any

import yaml

from gpc_init.exceptions import PresetNotFoundError, PresetParseError
from gpc_init.merger import merge_presets
from gpc_init.resolver import resolve_profile_file_names

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


def _load_optional_yaml_file(path: Path) -> dict[str, Any] | None:
    """Load a YAML file if it exists, returning None when absent."""
    if not path.exists():
        return None
    return _load_yaml_file(path)


def load_common_preset(base_dir: Path | None = None) -> dict[str, Any]:
    """
    Load the common baseline preset (lang/common/preset.yaml).

    Returns an empty dict if the file does not exist.
    """
    path = _resolve_base(base_dir) / "lang" / "common" / "preset.yaml"
    if not path.exists():
        return {}
    return _load_yaml_file(path)


def load_language_preset(lang_id: str, base_dir: Path | None = None) -> dict[str, Any]:
    """
    Load the preset for a language (lang/<lang_id>/preset.yaml).

    Args:
        lang_id: Canonical language identifier (e.g. 'py', 'js', 'go', 'rs').
        base_dir: Override base directory for presets (used in tests).

    Returns:
        Parsed preset as a dictionary.

    Raises:
        PresetNotFoundError: If the preset file does not exist.
        PresetParseError: If the YAML is invalid or not a mapping.

    """
    return _load_yaml_file(_resolve_base(base_dir) / "lang" / lang_id / "preset.yaml")


def load_language_preset_for_profile(
    lang_id: str,
    profile_id: str,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Load and merge all profile files for a language.

    For each file name produced by :func:`resolve_profile_file_names`, the
    corresponding ``lang/<lang_id>/<file>`` is loaded if it exists.  The
    ``preset.yaml`` file is always required; profile-specific files are
    optional and silently skipped when absent.

    The loaded presets are merged in inclusion order (lower-precedence first)
    using the standard :func:`merge_presets` semantics.

    Args:
        lang_id: Canonical language identifier (e.g. 'py').
        profile_id: Profile identifier (e.g. 'preset', 'experimental').
        base_dir: Override base directory for presets (used in tests).

    Returns:
        Merged preset dict for the requested profile.

    Raises:
        PresetNotFoundError: If ``preset.yaml`` for the language does not exist.
        PresetParseError: If any loaded YAML file is invalid.

    """
    base = _resolve_base(base_dir)
    lang_dir = base / "lang" / lang_id
    file_names = resolve_profile_file_names(profile_id)

    presets: list[dict[str, Any]] = []
    for fname in file_names:
        path = lang_dir / fname
        if fname == "preset.yaml":
            # preset.yaml is required; raises PresetNotFoundError when missing
            presets.append(_load_yaml_file(path))
        else:
            loaded = _load_optional_yaml_file(path)
            if loaded is not None:
                presets.append(loaded)

    if not presets:
        return {}
    if len(presets) == 1:
        return presets[0]
    return merge_presets({}, presets, [])


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


def load_framework_preset_for_profile(
    framework_id: str,
    profile_id: str,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Load and merge all profile files for a framework.

    Follows the same semantics as :func:`load_language_preset_for_profile` but
    for framework presets stored under ``framework/<framework_id>/``.

    Args:
        framework_id: Canonical framework identifier (e.g. 'react').
        profile_id: Profile identifier (e.g. 'preset', 'experimental').
        base_dir: Override base directory for presets (used in tests).

    Returns:
        Merged preset dict for the requested profile.

    Raises:
        PresetNotFoundError: If ``preset.yaml`` for the framework does not exist.
        PresetParseError: If any loaded YAML file is invalid.

    """
    base = _resolve_base(base_dir)
    fw_dir = base / "framework" / framework_id
    file_names = resolve_profile_file_names(profile_id)

    presets: list[dict[str, Any]] = []
    for fname in file_names:
        path = fw_dir / fname
        if fname == "preset.yaml":
            presets.append(_load_yaml_file(path))
        else:
            loaded = _load_optional_yaml_file(path)
            if loaded is not None:
                presets.append(loaded)

    if not presets:
        return {}
    if len(presets) == 1:
        return presets[0]
    return merge_presets({}, presets, [])
