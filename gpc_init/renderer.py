"""Render merged configuration dict to YAML string."""

from typing import Any

import yaml


def render_yaml(merged_dict: dict[str, Any]) -> str:
    """
    Render a merged configuration dict to a deterministic YAML string.

    Uses yaml.dump with stable key ordering and block style for readability.
    The output is compatible with pre-commit's expected .pre-commit-config.yaml format.

    Args:
        merged_dict: Merged configuration dictionary to render.

    Returns:
        UTF-8 YAML string suitable for writing to .pre-commit-config.yaml.

    """
    return yaml.dump(
        merged_dict,
        default_flow_style=False,
        sort_keys=True,
        allow_unicode=True,
        width=4096,
    )
