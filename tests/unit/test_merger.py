"""Unit tests for gpc_init/merger.py."""

from typing import Any

from gpc_init.merger import (
    _deep_merge_top_level,
    _merge_hooks_list,
    _merge_repos,
    _repo_key,
    merge_presets,
)


def make_hook(hook_id: str, **kwargs: Any) -> dict[str, Any]:
    return {"id": hook_id, **kwargs}


def make_repo(
    url: str,
    rev: str,
    hooks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {"repo": url, "rev": rev, "hooks": hooks}


class TestRepoKey:
    def test_repo_key_missing_repo_defaults_to_empty_string(self) -> None:
        # When "repo" key is absent, the default should be "" not None.
        # Mutants 3, 5, 8 change the default to None or "XXXX".
        result = _repo_key({"rev": "v1"})
        assert result == ("", "v1")

    def test_repo_key_missing_rev_defaults_to_empty_string(self) -> None:
        # When "rev" key is absent, the default should be "" not None.
        # Mutants 11, 13, 16 change the default to None or "XXXX".
        entry = {"repo": "https://a.com"}
        key = _repo_key(entry)
        assert key == ("https://a.com", ""), (
            f"Expected rev component to be '' but got {key[1]!r}"
        )

    def test_repos_without_rev_share_same_key_and_merge(self) -> None:
        # Two entries for the same repo URL but neither has a 'rev' key.
        # _repo_key falls back to the default for "rev"; both entries must
        # produce an identical key so they are merged rather than appended.
        # Mutant 16 uses "XXXX" as default — both entries still get "XXXX",
        # so they still merge. This test verifies the actual key value is "".
        lower = [{"repo": "https://a.com", "hooks": [make_hook("ha")]}]
        higher = [{"repo": "https://a.com", "hooks": [make_hook("hb")]}]
        result = _merge_repos(lower, higher)
        assert len(result) == 1, (
            "repos with no 'rev' key must share the same identity key and be merged"
        )
        assert [h["id"] for h in result[0]["hooks"]] == ["ha", "hb"]
        # Also verify the key produced is exactly ("https://a.com", "")
        key = _repo_key({"repo": "https://a.com"})
        assert key == ("https://a.com", "")


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

    def test_hooks_without_id_are_merged_not_duplicated(self) -> None:
        # Both hooks lack an 'id' field; they should be treated as the same
        # hook (keyed by the empty-string default) so the higher entry merges
        # into the lower entry rather than being appended as a second hook.
        # Mutants 7, 12, 19, 24 change the default to None or "XXXX" in either
        # or both loops, causing a key mismatch and incorrect duplication.
        lower = [{"args": ["--old"]}]
        higher = [{"args": ["--new"]}]
        result = _merge_hooks_list(lower, higher)
        assert len(result) == 1
        assert result[0]["args"] == ["--new"]

    def test_hook_without_id_does_not_merge_with_hook_whose_id_is_string_none(
        self,
    ) -> None:
        # A lower hook with id="None" (the literal string) and a higher hook
        # with no "id" key must NOT be merged together.  The original code
        # resolves a missing id to "" so the two entries have different keys
        # ("None" vs "").  Mutant 9 resolves a missing id to None, which
        # str()-ifies to "None", making both keys collide.
        lower = [make_hook("None", args=["--lower"])]
        higher = [{"args": ["--higher"]}]  # no "id" key at all
        result = _merge_hooks_list(lower, higher)
        assert len(result) == 2, (
            "hook with id='None' and hook without id must remain separate entries"
        )
        assert result[0]["id"] == "None"
        assert result[0]["args"] == ["--lower"]
        assert result[1]["args"] == ["--higher"]

    def test_higher_hook_without_id_matches_lower_hook_with_empty_id(self) -> None:
        # A lower hook with an explicit empty-string id and a higher hook with
        # no "id" key must merge together (both resolve to "" via the default).
        # Mutant 21 changes the higher-loop default to None so str(None)=="None"
        # and the lookup misses, causing an extra entry instead of a merge.
        lower = [{"id": "", "args": ["--old"]}]
        higher = [{"args": ["--new"]}]  # no 'id' key — defaults to "" via get("id", "")
        result = _merge_hooks_list(lower, higher)
        assert len(result) == 1
        assert result[0]["args"] == ["--new"]


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

    def test_merge_repos_lower_repo_without_hooks_key(self) -> None:
        # When the lower repo entry has no "hooks" key at all, _merge_repos must
        # default to an empty list rather than None.  The mutant changes the
        # default to None, which causes list(None) to raise a TypeError.
        lower = [{"repo": "https://a.com", "rev": "v1"}]  # no "hooks" key
        higher = [make_repo("https://a.com", "v1", [make_hook("ha")])]
        result = _merge_repos(lower, higher)
        assert len(result) == 1
        assert [h["id"] for h in result[0]["hooks"]] == ["ha"]

    def test_merge_repos_lower_entry_without_hooks_key(self) -> None:
        # A lower repo entry that has no "hooks" key at all must not crash when a
        # higher entry with the same (repo, rev) key is merged into it.
        # The mutant removes the default `[]` from `result[idx].get("hooks", [])`,
        # causing `list(None)` to raise TypeError when the key is absent.
        lower = [{"repo": "https://a.com", "rev": "v1"}]  # no "hooks" key
        higher = [make_repo("https://a.com", "v1", [make_hook("ha")])]
        result = _merge_repos(lower, higher)
        assert len(result) == 1
        assert [h["id"] for h in result[0]["hooks"]] == ["ha"]

    def test_same_repo_rev_higher_missing_hooks_key(self) -> None:
        # When the higher repo entry shares the same (repo, rev) key as a lower
        # entry but has no "hooks" key, _merge_repos must not raise and must
        # preserve the lower hooks unchanged.
        # Mutant 26 changes the default from [] to None so list(None) raises TypeError.
        lower = [make_repo("https://a.com", "v1", [make_hook("ha")])]
        higher = [{"repo": "https://a.com", "rev": "v1"}]  # no "hooks" key
        result = _merge_repos(lower, higher)
        assert len(result) == 1
        assert [h["id"] for h in result[0]["hooks"]] == ["ha"]

    def test_higher_repo_without_hooks_key_merged_safely(self) -> None:
        # A higher-layer repo entry for the same (repo, rev) key that has no
        # "hooks" key at all must default to an empty list, not raise TypeError.
        # Mutant 28 removes the default from repo.get("hooks", []), so
        # list(None) would be raised instead of list([]).
        lower = [make_repo("https://a.com", "v1", [make_hook("ha")])]
        higher = [{"repo": "https://a.com", "rev": "v1"}]  # no "hooks" key
        result = _merge_repos(lower, higher)
        assert len(result) == 1
        assert [h["id"] for h in result[0]["hooks"]] == ["ha"]


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
        lang = {
            "repos": [make_repo("https://lang.com", "v1", [make_hook("lang-hook")])]
        }
        fw = {"repos": [make_repo("https://fw.com", "v1", [make_hook("fw-hook")])]}
        result = merge_presets({}, [lang], [fw])
        repos = result["repos"]
        assert repos[0]["repo"] == "https://lang.com"
        assert repos[1]["repo"] == "https://fw.com"

    def test_recommended_metadata_excluded_from_output(self) -> None:
        fw = {
            "recommended": {"lang": ["js"]},
            "repos": [make_repo("https://fw.com", "v1", [make_hook("fw-hook")])],
        }
        result = merge_presets({}, [], [fw])
        assert "recommended" not in result

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


class TestDeepMergeTopLevel:
    def test_new_key_in_higher_added_to_result(self) -> None:
        result = _deep_merge_top_level({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_scalar_in_higher_overwrites_scalar_in_lower(self) -> None:
        result = _deep_merge_top_level({"a": 1}, {"a": 99})
        assert result["a"] == 99

    def test_repos_key_skipped(self) -> None:
        result = _deep_merge_top_level({"a": 1}, {"repos": ["should be ignored"]})
        assert "repos" not in result

    def test_repos_key_skipped_other_keys_still_merged(self) -> None:
        # repos appears first in higher so a break (vs continue) would drop all
        # subsequent keys; verify they are still present in the result
        higher = {"repos": ["ignored"], "extra": "value"}
        result = _deep_merge_top_level({"a": 1}, higher)
        assert "repos" not in result
        assert result["extra"] == "value"

    def test_nested_dict_recursively_merged(self) -> None:
        lower = {"versions": {"python": "3.10"}}
        higher = {"versions": {"python": "3.12", "node": "18"}}
        result = _deep_merge_top_level(lower, higher)
        assert result["versions"]["python"] == "3.12"
        assert result["versions"]["node"] == "18"


class TestMergePresetsHigherHookReplaces:
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
