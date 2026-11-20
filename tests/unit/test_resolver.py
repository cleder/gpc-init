"""Unit tests for pc_init/resolver.py."""

from pathlib import Path
from typing import Any

import pytest

from pc_init.catalog import Catalog
from pc_init.exceptions import (
    UnsupportedFrameworkError,
    UnsupportedLanguageError,
    UnsupportedProfileError,
)
from pc_init.resolver import (
    Recommendations,
    expand_recommendations,
    get_recommendations,
    normalize_framework,
    normalize_lang,
    validate_frameworks,
    validate_langs,
    validate_profiles,
)


class TestNormalizeLang:
    def test_lowercase(self) -> None:
        assert normalize_lang("PY", Catalog.load()) == "py"

    def test_alias_python(self) -> None:
        assert normalize_lang("python", Catalog.load()) == "py"

    def test_alias_javascript(self) -> None:
        assert normalize_lang("javascript", Catalog.load()) == "js"

    @pytest.mark.parametrize("alias", ["ts", "typescript"])
    def test_typescript_aliases_resolve_to_js(self, alias: str) -> None:
        assert normalize_lang(alias, Catalog.load()) == "js"

    def test_alias_rust(self) -> None:
        assert normalize_lang("rust", Catalog.load()) == "rs"

    def test_alias_ruby(self) -> None:
        assert normalize_lang("ruby", Catalog.load()) == "rb"

    def test_alias_cplusplus(self) -> None:
        assert normalize_lang("c++", Catalog.load()) == "cpp"

    def test_alias_c(self) -> None:
        assert normalize_lang("c", Catalog.load()) == "cpp"

    def test_alias_kotlin(self) -> None:
        assert normalize_lang("kotlin", Catalog.load()) == "kt"

    def test_alias_golang(self) -> None:
        assert normalize_lang("golang", Catalog.load()) == "go"

    def test_alias_makefile(self) -> None:
        assert normalize_lang("makefile", Catalog.load()) == "make"

    def test_strips_whitespace(self) -> None:
        assert normalize_lang("  py  ", Catalog.load()) == "py"

    def test_unknown_lang_passthrough(self) -> None:
        assert normalize_lang("go", Catalog.load()) == "go"

    def test_mixed_case_alias(self) -> None:
        assert normalize_lang("Python", Catalog.load()) == "py"

    def test_aliases_come_from_the_given_catalog(self, tmp_path: Path) -> None:
        # Create a custom lang with an alias that only exists in this catalog.
        lang_dir = tmp_path / "lang" / "xtest"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n")
        (lang_dir / "metadata.yaml").write_text("aliases:\n  - xalias\n")

        assert normalize_lang("xalias", Catalog.load(tmp_path)) == "xtest"


class TestNormalizeFramework:
    def test_lowercase(self) -> None:
        assert normalize_framework("REACT") == "react"

    def test_strips_whitespace(self) -> None:
        assert normalize_framework("  django  ") == "django"


class TestValidateLangs:
    def test_valid_lang_passes(self, tmp_preset_dir: Path) -> None:
        validate_langs(["py"], Catalog.load(tmp_preset_dir))  # no error

    def test_invalid_lang_raises(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            validate_langs(["cobol"], Catalog.load(tmp_preset_dir))
        assert "cobol" in str(exc_info.value)
        assert "Supported:" in str(exc_info.value)

    def test_error_lists_supported(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            validate_langs(["nope"], Catalog.load(tmp_preset_dir))
        assert len(exc_info.value.supported) > 0


class TestValidateFrameworks:
    def test_valid_framework_passes(self, tmp_preset_dir: Path) -> None:
        validate_frameworks(["react"], Catalog.load(tmp_preset_dir))  # no error

    def test_invalid_framework_raises(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedFrameworkError) as exc_info:
            validate_frameworks(["angular"], Catalog.load(tmp_preset_dir))
        assert "angular" in str(exc_info.value)
        assert "Supported:" in str(exc_info.value)

    def test_empty_frameworks_passes(self, tmp_preset_dir: Path) -> None:
        validate_frameworks([], Catalog.load(tmp_preset_dir))  # no error


class TestValidateProfiles:
    def test_legacy_passes(self) -> None:
        validate_profiles(["legacy"])  # no error

    def test_experimental_passes(self) -> None:
        validate_profiles(["experimental"])  # no error

    def test_both_pass(self) -> None:
        validate_profiles(["legacy", "experimental"])  # no error

    def test_empty_passes(self) -> None:
        validate_profiles([])  # no error

    def test_preset_is_not_selectable(self) -> None:
        # 'preset' is the always-on baseline, not a user-facing --profile value.
        with pytest.raises(UnsupportedProfileError) as exc_info:
            validate_profiles(["preset"])
        assert "preset" in str(exc_info.value)

    def test_invalid_profile_raises(self) -> None:
        with pytest.raises(UnsupportedProfileError) as exc_info:
            validate_profiles(["bogus"])
        assert "bogus" in str(exc_info.value)
        assert "Supported:" in str(exc_info.value)

    def test_error_lists_supported(self) -> None:
        with pytest.raises(UnsupportedProfileError) as exc_info:
            validate_profiles(["bogus"])
        assert exc_info.value.supported == ["experimental", "legacy"]


def _recs(
    *,
    langs: list[str],
    frameworks: list[str],
    lang_presets: list[dict[str, Any]] | None = None,
    fw_presets: list[dict[str, Any]] | None = None,
) -> Recommendations | None:
    return get_recommendations(
        langs=langs,
        frameworks=frameworks,
        lang_presets=lang_presets if lang_presets is not None else [{}] * len(langs),
        fw_presets=fw_presets if fw_presets is not None else [{}] * len(frameworks),
    )


class TestGetRecommendations:
    """The resolver reports what is missing; it does not build a command."""

    def test_reports_missing_recommended_langs(self) -> None:
        result = _recs(
            langs=["py"],
            frameworks=["react"],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
        )
        assert result is not None
        assert result.missing_langs == ("js", "ts")
        assert result.missing_frameworks == ()

    def test_reports_missing_recommended_frameworks(self) -> None:
        result = _recs(
            langs=["py"],
            frameworks=[],
            lang_presets=[{"recommended": {"framework": ["git", "docker"]}}],
        )
        assert result is not None
        assert result.missing_langs == ()
        assert result.missing_frameworks == ("git", "docker")

    def test_framework_preset_can_recommend_a_framework(self) -> None:
        result = _recs(
            langs=[],
            frameworks=["react"],
            fw_presets=[{"recommended": {"framework": ["docker"]}}],
        )
        assert result is not None
        assert result.missing_frameworks == ("docker",)

    def test_none_when_everything_recommended_is_selected(self) -> None:
        assert (
            _recs(
                langs=["js"],
                frameworks=["react"],
                fw_presets=[{"recommended": {"lang": ["js"]}}],
            )
            is None
        )

    def test_none_without_a_recommended_section(self) -> None:
        assert _recs(langs=["py"], frameworks=["django"]) is None

    def test_only_the_unselected_part_is_reported(self) -> None:
        result = _recs(
            langs=["js"],
            frameworks=["react"],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
        )
        assert result is not None
        assert result.missing_langs == ("ts",)

    def test_one_note_per_preset_naming_what_to_add(self) -> None:
        result = _recs(
            langs=["go"],
            frameworks=["react", "django"],
            fw_presets=[
                {"recommended": {"lang": ["js"]}},
                {"recommended": {"lang": ["py"]}},
            ],
        )
        assert result is not None
        assert result.notes == (
            "Note: preset 'react' recommends adding: --lang=js",
            "Note: preset 'django' recommends adding: --lang=py",
        )

    def test_note_lists_langs_and_frameworks_of_one_preset(self) -> None:
        result = _recs(
            langs=["py"],
            frameworks=[],
            lang_presets=[
                {"recommended": {"lang": ["js", "ts"], "framework": ["git", "docker"]}}
            ],
        )
        assert result is not None
        assert result.notes == (
            "Note: preset 'py' recommends adding: --lang=js,ts --framework=git,docker",
        )

    def test_missing_items_are_consolidated_without_duplicates(self) -> None:
        result = _recs(
            langs=["go"],
            frameworks=["react", "vue"],
            fw_presets=[
                {"recommended": {"lang": ["js", "ts"]}},
                {"recommended": {"lang": ["js", "css"]}},
            ],
        )
        assert result is not None
        assert result.missing_langs == ("js", "ts", "css")

    def test_primary_languages_is_treated_as_a_recommendation(self) -> None:
        result = _recs(
            langs=["py"],
            frameworks=["react"],
            fw_presets=[{"primary_languages": ["js", "ts"]}],
        )
        assert result is not None
        assert result.missing_langs == ("js", "ts")

    @pytest.mark.parametrize(
        ("langs", "frameworks", "lang_presets", "fw_presets"),
        [
            (["py", "go"], [], [{}], []),
            (["py"], ["react", "django"], [{}], [{"recommended": {"lang": ["js"]}}]),
        ],
    )
    def test_presets_must_match_the_selection(
        self,
        langs: list[str],
        frameworks: list[str],
        lang_presets: list[dict[str, Any]],
        fw_presets: list[dict[str, Any]],
    ) -> None:
        with pytest.raises(ValueError, match=r"zip\(\) argument.*shorter"):
            get_recommendations(langs, frameworks, lang_presets, fw_presets)


class TestExpandRecommendations:
    def test_adds_recommended_lang(self) -> None:
        langs, _fws = expand_recommendations(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
            supported_langs=["py", "js", "ts", "go"],
            supported_frameworks=["react", "django"],
        )
        assert "js" in langs
        assert "ts" in langs
        assert langs[0] == "py"  # original first

    def test_adds_recommended_framework(self) -> None:
        _langs, fws = expand_recommendations(
            langs=["py"],
            frameworks=["django"],
            lang_presets=[{"recommended": {"framework": ["git"]}}],
            fw_presets=[{}],
            supported_langs=["py"],
            supported_frameworks=["django", "git"],
        )
        assert "git" in fws

    def test_does_not_add_already_selected(self) -> None:
        langs, _fws = expand_recommendations(
            langs=["py", "js"],
            frameworks=["react"],
            lang_presets=[{}, {}],
            fw_presets=[{"recommended": {"lang": ["js"]}}],
            supported_langs=["py", "js"],
            supported_frameworks=["react"],
        )
        assert langs.count("js") == 1

    def test_does_not_add_unsupported(self) -> None:
        langs, _fws = expand_recommendations(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["cobol"]}}],
            supported_langs=["py", "js"],
            supported_frameworks=["react"],
        )
        assert "cobol" not in langs

    def test_preserves_original_order(self) -> None:
        langs, _ = expand_recommendations(
            langs=["go", "py"],
            frameworks=["react"],
            lang_presets=[{}, {}],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
            supported_langs=["go", "py", "js", "ts"],
            supported_frameworks=["react"],
        )
        assert langs[:2] == ["go", "py"]
        assert langs[2:] == ["js", "ts"]

    def test_single_pass_no_recursion(self) -> None:
        # react recommends js; js preset recommends ts — ts should NOT be added
        langs, _fws = expand_recommendations(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js"]}}],
            supported_langs=["py", "js", "ts"],
            supported_frameworks=["react"],
        )
        assert "js" in langs
        assert "ts" not in langs

    def test_does_not_add_already_selected_framework_mutmut_28(self) -> None:
        # 'django' is already in frameworks and in supported_frameworks.
        # A preset recommending it must not cause a duplicate entry.
        _langs, fws = expand_recommendations(
            langs=["py"],
            frameworks=["django"],
            lang_presets=[{"recommended": {"framework": ["django"]}}],
            fw_presets=[{}],
            supported_langs=["py"],
            supported_frameworks=["django", "git"],
        )
        assert fws.count("django") == 1

    def test_does_not_add_already_selected_framework_mutmut_29(self) -> None:
        _langs, fws = expand_recommendations(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{"recommended": {"framework": ["react"]}}],
            fw_presets=[{}],
            supported_langs=["py"],
            supported_frameworks=["react", "django"],
        )
        assert fws.count("react") == 1

    def test_list_valued_recommended_is_treated_as_lang_list(self) -> None:
        # When a preset's "recommended" value is a plain list (not a dict), it must
        # be interpreted as a list of language ids — i.e. normalised to {"lang": rec}.
        # The mutant changes the normalisation key to "LANG", which causes the list
        # to be silently ignored so no extra langs are appended.
        langs, _fws = expand_recommendations(
            langs=["py"],
            frameworks=[],
            lang_presets=[{"recommended": ["js", "ts"]}],
            fw_presets=[],
            supported_langs=["py", "js", "ts"],
            supported_frameworks=[],
        )
        assert "js" in langs
        assert "ts" in langs
