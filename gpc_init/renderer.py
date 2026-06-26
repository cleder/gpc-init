"""Render merged configuration dict to YAML string."""

from typing import Any

import yaml

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


def _semantic_dict_representer(
    dumper: yaml.Dumper, data: dict[str, Any]
) -> yaml.MappingNode:
    if "repo" in data:
        priority = _REPO_KEY_ORDER
    elif "id" in data:
        priority = _HOOK_KEY_ORDER
    else:
        priority = []
    ordered = [k for k in priority if k in data]
    ordered += sorted(k for k in data if k not in ordered)
    return dumper.represent_mapping(
        "tag:yaml.org,2002:map", [(k, data[k]) for k in ordered]
    )


class _PrecommitDumper(yaml.Dumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:  # noqa: FBT001, FBT002, ARG002
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
