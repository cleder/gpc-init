"""Unit tests for gpc_init/merger.py."""

from typing import Any

import pytest

from gpc_init.merger import _merge_hooks_list, _merge_repos, merge_presets


def make_hook(id: str, **kwargs: Any) -> dict[str, Any]:
    return {"id": id, **kwargs}


def make_repo(
    url: str,
    rev: str,
    hooks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {"repo": url, "rev": rev, "hooks": hooks}


class TestMergeHooksList:
    def test_no_overlap(self) -> None:
        lower = [make_hook("hook-a")]
        higher = [make_hook("hook-b")]
        result = _merge_hooks_list(lower, higher)
        assert [h["id"] for h in result] == ["hook-a", "hook-b"]

    def test_higher_replaces_fields(self) -> None:
        lower = [make_hook("hook-a", args=["--foo"])]
        higher = [make_hook("hook-a", args=["--bar"])]
        result = _merge_hooks_list(lower, higher)
        assert len(result) == 1
        assert result[0]["args"] == ["--bar"]

    def test_preserves_lower_position_on_replacement(self) -> None:
        lower = [make_hook("a"), make_hook("b")]
        higher = [make_hook("b", args=["--new"]), make_hook("c")]
        result = _merge_hooks_list(lower, higher)
        assert [h["id"] for h in result] == ["a", "b", "c"]
        assert result[1]["args"] == ["--new"]

    def test_empty_lower(self) -> None:
        higher = [make_hook("hook-a")]
        result = _merge_hooks_list([], higher)
        assert result == [{"id": "hook-a"}]

    def test_empty_higher(self) -> None:
        lower = [make_hook("hook-a")]
        result = _merge_hooks_list(lower, [])
        assert result == [{"id": "hook-a"}]


class TestMergeRepos:
    def test_no_overlap_appends_in_order(self) -> None:
        lower = [make_repo("https://a.com", "v1", [make_hook("ha")])]
        higher = [make_repo("https://b.com", "v2", [make_hook("hb")])]
        result = _merge_repos(lower, higher)
        assert len(result) == 2
        assert result[0]["repo"] == "https://a.com"
        assert result[1]["repo"] == "https://b.com"

    def test_same_repo_rev_merges_hooks(self) -> None:
        lower = [make_repo("https://a.com", "v1", [make_hook("ha")])]
        higher = [make_repo("https://a.com", "v1", [make_hook("hb")])]
        result = _merge_repos(lower, higher)
        assert len(result) == 1
        assert [h["id"] for h in result[0]["hooks"]] == ["ha", "hb"]

    def test_same_repo_different_rev_appends(self) -> None:
        lower = [make_repo("https://a.com", "v1", [make_hook("ha")])]
        higher = [make_repo("https://a.com", "v2", [make_hook("hb")])]
        result = _merge_repos(lower, higher)
        assert len(result) == 2


class TestMergePresets:
    def test_merges_common_and_single_lang(self) -> None:
        common = {
            "repos": [make_repo("https://common.com", "v1", [make_hook("common-hook")])]
        }
        lang = {
            "repos": [make_repo("https://lang.com", "v1", [make_hook("lang-hook")])]
        }
        result = merge_presets(common, [lang], [])
        repos = result["repos"]
        assert len(repos) == 2
        assert repos[0]["repo"] == "https://common.com"
        assert repos[1]["repo"] == "https://lang.com"

    def test_merges_multiple_langs_in_order(self) -> None:
        lang1 = {"repos": [make_repo("https://a.com", "v1", [make_hook("ha")])]}
        lang2 = {"repos": [make_repo("https://b.com", "v1", [make_hook("hb")])]}
        result = merge_presets({}, [lang1, lang2], [])
        repos = result["repos"]
        assert repos[0]["repo"] == "https://a.com"
        assert repos[1]["repo"] == "https://b.com"

    def test_framework_appended_after_langs(self) -> None:
        lang = {"repos": [make_repo("https://lang.com", "v1", [make_hook("lang-hook")])]}
        fw = {"repos": [make_repo("https://fw.com", "v1", [make_hook("fw-hook")])]}
        result = merge_presets({}, [lang], [fw])
        repos = result["repos"]
        assert repos[0]["repo"] == "https://lang.com"
        assert repos[1]["repo"] == "https://fw.com"

    def test_framework_primary_languages_excluded_from_output(self) -> None:
        fw = {
            "primary_languages": ["js"],
            "repos": [make_repo("https://fw.com", "v1", [make_hook("fw-hook")])],
        }
        result = merge_presets({}, [], [fw])
        assert "primary_languages" not in result

    def test_duplicate_repo_rev_merges_hooks_across_layers(self) -> None:
        lang1 = {"repos": [make_repo("https://shared.com", "v1", [make_hook("ha")])]}
        lang2 = {"repos": [make_repo("https://shared.com", "v1", [make_hook("hb")])]}
        result = merge_presets({}, [lang1, lang2], [])
        repos = result["repos"]
        assert len(repos) == 1
        assert [h["id"] for h in repos[0]["hooks"]] == ["ha", "hb"]

    def test_top_level_keys_deep_merged(self) -> None:
        common = {"default_language_version": {"python": "python3.10"}}
        lang = {"default_language_version": {"python": "python3.12", "node": "18"}}
        result = merge_presets(common, [lang], [])
        assert result["default_language_version"]["python"] == "python3.12"
        assert result["default_language_version"]["node"] == "18"

    def test_deterministic_order_same_inputs(self) -> None:
        lang1 = {"repos": [make_repo("https://a.com", "v1", [make_hook("ha")])]}
        lang2 = {"repos": [make_repo("https://b.com", "v1", [make_hook("hb")])]}
        result1 = merge_presets({}, [lang1, lang2], [])
        result2 = merge_presets({}, [lang1, lang2], [])
        assert result1 == result2

    def test_empty_layers_produces_empty_result(self) -> None:
        result = merge_presets({}, [], [])
        assert result == {}

    def test_higher_layer_hook_replaces_lower_fields(self) -> None:
        lang1 = {
            "repos": [
                make_repo(
                    "https://shared.com",
                    "v1",
                    [make_hook("ha", args=["--old"])],
                )
            ]
        }
        lang2 = {
            "repos": [
                make_repo(
                    "https://shared.com",
                    "v1",
                    [make_hook("ha", args=["--new"])],
                )
            ]
        }
        result = merge_presets({}, [lang1, lang2], [])
        hook = result["repos"][0]["hooks"][0]
        assert hook["args"] == ["--new"]
