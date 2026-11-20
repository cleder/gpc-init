"""Merge language and framework presets into a single configuration dict."""

from collections.abc import Callable
from typing import Any

# Implicit category for hooks with no explicit `category:` field.
DEFAULT_CATEGORY = "preset"


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


def _merge_by_key(
    lower: list[dict[str, Any]],
    higher: list[dict[str, Any]],
    *,
    key_fn: Callable[[dict[str, Any]], Any],
    merge_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge two lists of dicts by an identity key.

    - Preserves first-seen order from the lower-precedence layer.
    - Appends new keys from the higher-precedence layer.
    - When the same key appears in both, entries are combined via merge_fn.
    """
    result: list[dict[str, Any]] = []
    lower_by_key: dict[Any, int] = {}
    for i, item in enumerate(lower):
        lower_by_key[key_fn(item)] = i
        result.append(dict(item))

    for item in higher:
        key = key_fn(item)
        if key in lower_by_key:
            idx = lower_by_key[key]
            result[idx] = merge_fn(result[idx], item)
        else:
            result.append(dict(item))

    return result


def _merge_repo_entries(
    lower: dict[str, Any], higher: dict[str, Any]
) -> dict[str, Any]:
    """
    Merge two repo entries.

    Higher-precedence fields replace lower fields, and hooks are merged by
    hook id rather than replaced wholesale.
    """
    merged = {**lower, **higher}
    merged["hooks"] = _merge_by_key(
        list(lower.get("hooks", [])),
        list(higher.get("hooks", [])),
        key_fn=lambda h: str(h.get("id", "")),
        merge_fn=_merge_hook,
    )
    return merged


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
    return _merge_by_key(
        lower, higher, key_fn=lambda h: str(h.get("id", "")), merge_fn=_merge_hook
    )


def _merge_repos(
    lower: list[dict[str, Any]], higher: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Merge two repos lists by (repo, rev) key.

    - Preserves first-seen order from the lower-precedence layer.
    - Appends new (repo, rev) pairs from the higher-precedence layer.
    - When the same (repo, rev) pair appears in both, higher-precedence fields
      replace lower fields and hooks are merged by hook id.
    """
    return _merge_by_key(lower, higher, key_fn=_repo_key, merge_fn=_merge_repo_entries)


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


def _filter_hooks(
    hooks: list[dict[str, Any]], active_categories: frozenset[str]
) -> list[dict[str, Any]]:
    """Return hooks whose category is active, with the 'category' key stripped."""
    return [
        {k: v for k, v in hook.items() if k != "category"}
        for hook in hooks
        if hook.get("category", DEFAULT_CATEGORY) in active_categories
    ]


def filter_by_category(
    merged: dict[str, Any], active_categories: frozenset[str]
) -> dict[str, Any]:
    """
    Drop hooks whose category isn't active, from an already-merged config dict.

    Each hook's `category` field (default: 'preset') is checked against
    active_categories. Surviving hooks have the 'category' key stripped
    (it isn't a pre-commit config field). A repo entry left with zero hooks
    after filtering is removed entirely from the result.

    Args:
        merged: Merged configuration dict, as returned by merge_presets().
        active_categories: Categories to keep (always includes 'preset').

    Returns:
        A new configuration dict with non-active-category hooks removed.

    """
    repos = merged.get("repos", [])
    if not repos:
        return dict(merged)

    filtered_repos: list[dict[str, Any]] = []
    for repo in repos:
        kept_hooks = _filter_hooks(repo.get("hooks", []), active_categories)
        if kept_hooks:
            filtered_repos.append({**repo, "hooks": kept_hooks})

    return {**merged, "repos": filtered_repos}
