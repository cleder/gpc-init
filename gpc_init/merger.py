"""Merge language and framework presets into a single configuration dict."""

from typing import Any


def _repo_key(repo_entry: dict[str, Any]) -> tuple[str, str]:
    """Return a (repo, rev) identity key for a repo entry."""
    return (str(repo_entry.get("repo", "")), str(repo_entry.get("rev", "")))


def _merge_hook(lower: dict[str, Any], higher: dict[str, Any]) -> dict[str, Any]:
    """
    Merge two hook dicts: higher-precedence fields replace lower-precedence fields.

    The hook id and position come from the lower layer; all other fields from
    the higher layer override the lower layer.
    """
    return {**lower, **higher}


def _merge_hooks_list(
    lower: list[dict[str, Any]], higher: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Merge two hook lists by hook id.

    - Preserves first-seen order from the lower-precedence layer.
    - Appends new hook ids from the higher-precedence layer.
    - When the same hook id appears in both, higher-precedence fields
      replace lower fields.
    """
    result: list[dict[str, Any]] = []
    lower_by_id: dict[str, int] = {}
    for i, hook in enumerate(lower):
        hook_id = str(hook.get("id", ""))
        lower_by_id[hook_id] = i
        result.append(dict(hook))

    for hook in higher:
        hook_id = str(hook.get("id", ""))
        if hook_id in lower_by_id:
            idx = lower_by_id[hook_id]
            result[idx] = _merge_hook(result[idx], hook)
        else:
            result.append(dict(hook))

    return result


def _merge_repos(
    lower: list[dict[str, Any]], higher: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Merge two repos lists by (repo, rev) key.

    - Preserves first-seen order from the lower-precedence layer.
    - Appends new (repo, rev) pairs from the higher-precedence layer.
    - When the same (repo, rev) pair appears in both, hooks are merged by hook id.
    """
    result: list[dict[str, Any]] = []
    lower_by_key: dict[tuple[str, str], int] = {}
    for i, repo in enumerate(lower):
        key = _repo_key(repo)
        lower_by_key[key] = i
        result.append(dict(repo))

    for repo in higher:
        key = _repo_key(repo)
        if key in lower_by_key:
            idx = lower_by_key[key]
            merged_repo = dict(result[idx])
            lower_hooks = list(result[idx].get("hooks", []))
            higher_hooks = list(repo.get("hooks", []))
            merged_repo["hooks"] = _merge_hooks_list(lower_hooks, higher_hooks)
            result[idx] = merged_repo
        else:
            result.append(dict(repo))

    return result


def _deep_merge_top_level(
    lower: dict[str, Any], higher: dict[str, Any]
) -> dict[str, Any]:
    """
    Deep-merge two top-level dicts (excluding 'repos').

    Higher-precedence values override lower-precedence values on key conflicts.
    Nested dicts are recursively merged; other types are replaced by higher value.
    """
    merged: dict[str, Any] = dict(lower)
    for key, value in higher.items():
        if key == "repos":
            continue
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge_top_level(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_presets(
    common: dict[str, Any],
    langs: list[dict[str, Any]],
    frameworks: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Merge preset dicts in deterministic order.

    Merge order (lowest to highest precedence):
    1. Common preset
    2. Language presets in CLI input order
    3. Framework presets in CLI input order

    For top-level 'repos' key: entries are merged by (repo, rev) key.
    For other top-level keys: higher-precedence values override lower.
    Preset metadata keys (e.g. 'recommended') are excluded from output.

    Args:
        common: Common baseline preset dict.
        langs: Ordered list of language preset dicts.
        frameworks: Ordered list of framework preset dicts.

    Returns:
        Merged configuration dict ready for YAML rendering.

    """
    layers: list[dict[str, Any]] = [common, *langs, *frameworks]
    result: dict[str, Any] = {}
    merged_repos: list[dict[str, Any]] = []

    for layer in layers:
        if not layer:
            continue
        # Merge repos
        layer_repos: list[dict[str, Any]] = list(layer.get("repos", []))
        if layer_repos:
            merged_repos = _merge_repos(merged_repos, layer_repos)
        # Merge other top-level keys (skip repos and framework metadata)
        non_repo = {
            k: v
            for k, v in layer.items()
            if k not in {"repos", "recommended", "primary_languages"}
        }
        result = _deep_merge_top_level(result, non_repo)

    if merged_repos:
        result["repos"] = merged_repos

    return result
