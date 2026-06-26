"""Unit tests for gpc_init/resolver.py."""

from pathlib import Path

import pytest

from gpc_init.exceptions import UnsupportedFrameworkError, UnsupportedLanguageError
from gpc_init.resolver import (
    deduplicate_preserving_order,
    expand_recommendations,
    get_recommendations_info,
    get_supported_frameworks,
    get_supported_languages,
    normalize_framework,
    normalize_lang,
    validate_frameworks,
    validate_langs,
)


class TestNormalizeLang:
    def test_lowercase(self) -> None:
        assert normalize_lang("PY") == "py"

    def test_alias_python(self) -> None:
        assert normalize_lang("python") == "py"

    def test_alias_javascript(self) -> None:
        assert normalize_lang("javascript") == "js"

    def test_alias_rust(self) -> None:
        assert normalize_lang("rust") == "ru"

    def test_alias_golang(self) -> None:
        assert normalize_lang("golang") == "go"

    def test_strips_whitespace(self) -> None:
        assert normalize_lang("  py  ") == "py"

    def test_unknown_lang_passthrough(self) -> None:
        assert normalize_lang("go") == "go"

    def test_mixed_case_alias(self) -> None:
        assert normalize_lang("Python") == "py"


class TestNormalizeFramework:
    def test_lowercase(self) -> None:
        assert normalize_framework("REACT") == "react"

    def test_strips_whitespace(self) -> None:
        assert normalize_framework("  django  ") == "django"


class TestDeduplicatePreservingOrder:
    def test_removes_duplicates(self) -> None:
        assert deduplicate_preserving_order(["py", "js", "py"]) == ["py", "js"]

    def test_preserves_first_occurrence(self) -> None:
        assert deduplicate_preserving_order(["js", "py", "js"]) == ["js", "py"]

    def test_empty_list(self) -> None:
        assert deduplicate_preserving_order([]) == []

    def test_no_duplicates(self) -> None:
        assert deduplicate_preserving_order(["py", "js"]) == ["py", "js"]


class TestGetSupportedLanguages:
    def test_returns_list_of_ids(self, tmp_preset_dir: Path) -> None:
        supported = get_supported_languages(base_dir=tmp_preset_dir)
        assert "py" in supported
        assert "js" in supported
        assert "common" not in supported

    def test_returns_sorted_list(self, tmp_preset_dir: Path) -> None:
        supported = get_supported_languages(base_dir=tmp_preset_dir)
        assert supported == sorted(supported)

    def test_empty_lang_dir(self, tmp_path: Path) -> None:
        # No lang dir at all
        supported = get_supported_languages(base_dir=tmp_path)
        assert supported == []


class TestGetSupportedFrameworks:
    def test_returns_list_of_ids(self, tmp_preset_dir: Path) -> None:
        supported = get_supported_frameworks(base_dir=tmp_preset_dir)
        assert "react" in supported

    def test_returns_sorted_list(self, tmp_preset_dir: Path) -> None:
        supported = get_supported_frameworks(base_dir=tmp_preset_dir)
        assert supported == sorted(supported)

    def test_empty_framework_dir(self, tmp_path: Path) -> None:
        supported = get_supported_frameworks(base_dir=tmp_path)
        assert supported == []

    def test_excludes_framework_dir_without_preset_yaml(
        self, tmp_preset_dir: Path
    ) -> None:
        # Create a framework directory that has no preset.yaml — it must not appear.
        (tmp_preset_dir / "framework" / "incomplete").mkdir()
        supported = get_supported_frameworks(base_dir=tmp_preset_dir)
        assert "incomplete" not in supported
        assert "react" in supported


class TestValidateLangs:
    def test_valid_lang_passes(self, tmp_preset_dir: Path) -> None:
        validate_langs(["py"], base_dir=tmp_preset_dir)  # no error

    def test_invalid_lang_raises(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            validate_langs(["cobol"], base_dir=tmp_preset_dir)
        assert "cobol" in str(exc_info.value)
        assert "Supported:" in str(exc_info.value)

    def test_error_lists_supported(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedLanguageError) as exc_info:
            validate_langs(["nope"], base_dir=tmp_preset_dir)
        assert len(exc_info.value.supported) > 0


class TestValidateFrameworks:
    def test_valid_framework_passes(self, tmp_preset_dir: Path) -> None:
        validate_frameworks(["react"], base_dir=tmp_preset_dir)  # no error

    def test_invalid_framework_raises(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedFrameworkError) as exc_info:
            validate_frameworks(["angular"], base_dir=tmp_preset_dir)
        assert "angular" in str(exc_info.value)
        assert "Supported:" in str(exc_info.value)

    def test_empty_frameworks_passes(self, tmp_preset_dir: Path) -> None:
        validate_frameworks([], base_dir=tmp_preset_dir)  # no error

    def test_base_dir_is_forwarded_to_discovery(self, tmp_path: Path) -> None:
        # Create a framework that cannot exist in the real package install.
        fw_dir = tmp_path / "framework" / "xtest-only-fw"
        fw_dir.mkdir(parents=True)
        (fw_dir / "preset.yaml").write_text("repos: []\n")

        # With the correct base_dir the synthetic framework is visible — no error.
        validate_frameworks(["xtest-only-fw"], base_dir=tmp_path)

        # If base_dir were ignored (mutant: None), the real install would be used
        # and "xtest-only-fw" would be absent, raising UnsupportedFrameworkError.


class TestGetRecommendationsInfo:
    def test_returns_message_when_recommended_lang_missing(self) -> None:
        result = get_recommendations_info(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
        )
        assert result is not None
        assert "react" in result
        assert "js" in result

    def test_returns_none_when_recommended_lang_already_selected(self) -> None:
        # react recommends js; user already has js — no note
        result = get_recommendations_info(
            langs=["js"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js"]}}],
        )
        assert result is None

    def test_returns_none_when_one_of_recommended_langs_selected(self) -> None:
        result = get_recommendations_info(
            langs=["js"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
        )
        # js is selected — ts is still missing, so note IS emitted
        assert result is not None
        assert "ts" in result
        assert "--lang=ts" in result

    def test_returns_none_when_no_recommended_section(self) -> None:
        result = get_recommendations_info(
            langs=["py"],
            frameworks=["django"],
            lang_presets=[{}],
            fw_presets=[{}],
        )
        assert result is None

    def test_message_contains_recommended_lang_names(self) -> None:
        result = get_recommendations_info(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
        )
        assert result is not None
        assert "js" in result
        assert "ts" in result
        assert "None" not in result

    def test_message_includes_actionable_suggestion(self) -> None:
        result = get_recommendations_info(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
        )
        assert result is not None
        # selected lang preserved; missing recommended langs appended
        assert "pc-init --lang=py,js,ts --framework=react" in result

    def test_multiple_presets_consolidated_into_one_suggestion(self) -> None:
        result = get_recommendations_info(
            langs=["go"],
            frameworks=["react", "django"],
            lang_presets=[{}],
            fw_presets=[
                {"recommended": {"lang": ["js", "ts"]}},
                {"recommended": {"lang": ["py"]}},
            ],
        )
        assert result is not None
        assert result.count("Try:") == 1
        assert "pc-init --lang=go,js,ts,py --framework=react,django" in result

    def test_framework_recommendation_reported(self) -> None:
        # A lang preset that recommends a framework
        result = get_recommendations_info(
            langs=["py"],
            frameworks=[],
            lang_presets=[{"recommended": {"framework": ["git"]}}],
            fw_presets=[],
        )
        assert result is not None
        assert "git" in result
        assert "--framework=git" in result

    def test_suggestion_includes_all_selected_frameworks(self) -> None:
        result = get_recommendations_info(
            langs=["py"],
            frameworks=["react", "django"],
            lang_presets=[{}],
            fw_presets=[
                {"recommended": {"lang": ["js", "ts"]}},
                {"recommended": {"lang": ["py"]}},
            ],
        )
        assert result is not None
        assert "--framework=react,django" in result

    def test_multiple_presets_multiple_notes(self) -> None:
        result = get_recommendations_info(
            langs=["go"],
            frameworks=["react", "django"],
            lang_presets=[{}],
            fw_presets=[
                {"recommended": {"lang": ["js"]}},
                {"recommended": {"lang": ["py"]}},
            ],
        )
        assert result is not None
        assert "react" in result
        assert "django" in result
        assert "js" in result
        assert "py" in result

    def test_raises_value_error_when_langs_and_lang_presets_length_mismatch(
        self,
    ) -> None:
        # langs has 2 entries but lang_presets has only 1 — strict=True must catch this.
        with pytest.raises(ValueError, match=r"zip\(\) argument.*shorter"):
            get_recommendations_info(
                langs=["py", "go"],
                frameworks=[],
                lang_presets=[{}],  # intentionally one element short
                fw_presets=[],
            )

    def test_raises_on_mismatched_langs_and_lang_presets(self) -> None:
        # langs has 2 entries but lang_presets has only 1 — strict=True must raise
        with pytest.raises(ValueError, match=r"zip\(\) argument.*shorter"):
            get_recommendations_info(
                langs=["py", "go"],
                frameworks=[],
                lang_presets=[{}],
                fw_presets=[],
            )

    def test_mismatched_frameworks_and_fw_presets_raises(self) -> None:
        # frameworks has 2 entries but fw_presets has only 1; strict=True must
        # raise ValueError — without strict the mismatch would be silently ignored.
        with pytest.raises(ValueError):  # noqa: PT011
            get_recommendations_info(
                langs=["py"],
                frameworks=["react", "django"],
                lang_presets=[{}],
                fw_presets=[{"recommended": {"lang": ["js"]}}],
            )

    def test_raises_when_frameworks_and_fw_presets_length_mismatch(self) -> None:
        # frameworks has 2 entries but fw_presets has only 1 — strict=True must raise
        with pytest.raises(ValueError, match=r"zip\(\) argument.*shorter"):
            get_recommendations_info(
                langs=["py"],
                frameworks=["react", "django"],
                lang_presets=[{}],
                fw_presets=[{"recommended": {"lang": ["js"]}}],
            )

    def test_note_lang_flag_uses_comma_separator_for_multiple_missing_langs(
        self,
    ) -> None:
        # react recommends js and ts; both are missing — the per-preset note must
        # show "--lang=js,ts" (comma-separated, no extra characters).
        result = get_recommendations_info(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
        )
        assert result is not None
        # The "recommends adding:" note line must contain the compact flag form.
        note_line = next(
            line for line in result.splitlines() if "recommends adding" in line
        )
        assert "--lang=js,ts" in note_line

    def test_note_uses_comma_separator_for_multiple_missing_frameworks(self) -> None:
        # A lang preset that recommends two frameworks, neither currently selected.
        # The per-preset note must use ',' (not 'XX,XX') to join the framework ids.
        result = get_recommendations_info(
            langs=["py"],
            frameworks=[],
            lang_presets=[{"recommended": {"framework": ["git", "docker"]}}],
            fw_presets=[],
        )
        assert result is not None
        assert "--framework=git,docker" in result

    def test_note_joins_lang_and_framework_parts_with_space(self) -> None:
        # A single preset recommends both a missing language and framework.
        # The two parts in the note must be separated by a plain space, not 'XX XX'.
        result = get_recommendations_info(
            langs=["py"],
            frameworks=[],
            lang_presets=[{"recommended": {"lang": ["js"], "framework": ["git"]}}],
            fw_presets=[],
        )
        assert result is not None
        assert "--lang=js --framework=git" in result

    def test_notes_and_suggestion_joined_by_newline(self) -> None:
        result = get_recommendations_info(
            langs=["py"],
            frameworks=["react"],
            lang_presets=[{}],
            fw_presets=[{"recommended": {"lang": ["js", "ts"]}}],
        )
        assert result is not None
        lines = result.split("\n")
        # Exactly two lines: one Note line and one Try line
        assert len(lines) == 2
        assert lines[0].startswith("Note:")
        assert lines[1].strip().startswith("Try:")


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
