"""Render merged configuration dict to a YAML or TOML string."""

from enum import StrEnum
from typing import Any, override

import tomli_w
import yaml


class OutputFormat(StrEnum):
    """Supported config output formats."""

    YAML = "yaml"
    TOML = "toml"

    @property
    def default_filename(self) -> str:
        """Return the file name the format is discovered under by default."""
        return "prek.toml" if self is OutputFormat.TOML else ".pre-commit-config.yaml"


_REPO_KEY_ORDER = ["repo", "rev", "hooks"]
_HOOK_KEY_ORDER = [
    "id",
    "name",
    "description",
    "entry",
    "language",
    "types",
    "types_or",
    "files",
    "args",
    "additional_dependencies",
    "stages",
    "exclude",
]


def _ordered_keys(data: dict[str, Any]) -> list[str]:
    """Return the keys of data in semantic (repo/hook aware) order."""
    if "repo" in data:
        priority = _REPO_KEY_ORDER
    elif "id" in data:
        priority = _HOOK_KEY_ORDER
    else:
        priority: list[str] = []
    ordered = [k for k in priority if k in data]
    ordered += sorted(k for k in data if k not in ordered)
    return ordered


def _semantic_dict_representer(
    dumper: yaml.Dumper, data: dict[str, Any]
) -> yaml.MappingNode:
    return dumper.represent_mapping(
        "tag:yaml.org,2002:map", [(k, data[k]) for k in _ordered_keys(data)]
    )


def _semantic_order(value: Any) -> Any:  # noqa: ANN401
    """
    Recursively order dict keys semantically and drop null values.

    TOML has no null, and null means "unset" in pre-commit semantics, so None
    dict values and list items are omitted.
    """
    if isinstance(value, dict):
        return {
            k: _semantic_order(value[k])
            for k in _ordered_keys(value)
            if value[k] is not None
        }
    if isinstance(value, list):
        return [_semantic_order(item) for item in value if item is not None]
    return value


class _PrecommitDumper(yaml.Dumper):
    @override
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow=flow, indentless=False)


_PrecommitDumper.add_representer(dict, _semantic_dict_representer)


def render_yaml(merged_dict: dict[str, Any]) -> str:
    """
    Render a merged configuration dict to a YAML string matching pre-commit conventions.

    Output conforms to the format expected by pre-commit and prek:
    - Starts with a ``---`` document-start marker.
    - Keys within repo entries follow the order ``repo`` → ``rev`` → ``hooks``;
      ``id`` is always first within hook entries.
    - Sequence items are indented 2 spaces from their parent key.

    Args:
        merged_dict: Merged configuration dictionary to render.

    Returns:
        UTF-8 YAML string suitable for writing to .pre-commit-config.yaml.

    """
    return yaml.dump(
        merged_dict,
        Dumper=_PrecommitDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=4096,
        explicit_start=True,
    )


def render_toml(merged_dict: dict[str, Any]) -> str:
    """
    Render a merged configuration dict to a TOML string for prek.

    The data matches :func:`render_yaml` (null values are omitted) and keys follow
    the same semantic order, except that TOML always writes scalar fields before
    nested tables. Repos and hooks become ``[[repos]]`` / ``[[repos.hooks]]``
    array-of-tables.

    Args:
        merged_dict: Merged configuration dictionary to render.

    Returns:
        TOML string suitable for writing to prek.toml.

    """
    return tomli_w.dumps(_semantic_order(merged_dict))


def render(merged_dict: dict[str, Any], fmt: OutputFormat) -> str:
    """Render a merged configuration dict in the requested format."""
    if fmt is OutputFormat.TOML:
        return render_toml(merged_dict)
    return render_yaml(merged_dict)
