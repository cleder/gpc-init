"""Unit tests for gpc_init/resolver.py."""

from pathlib import Path

import pytest

from gpc_init.exceptions import UnsupportedFrameworkError, UnsupportedLanguageError
from gpc_init.resolver import (
    deduplicate_preserving_order,
    get_primary_languages_info,
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


class TestGetPrimaryLanguagesInfo:
    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="shorter than"):
            get_primary_languages_info(
                frameworks=["react", "django"],
                framework_presets=[{"primary_languages": ["js"]}],
                selected_langs=["py"],
            )

    def test_returns_message_when_lang_not_in_primary_languages(self) -> None:
        result = get_primary_languages_info(
            frameworks=["react"],
            framework_presets=[{"primary_languages": ["js", "ts"]}],
            selected_langs=["py"],
        )
        assert result is not None
        assert "react" in result
        assert "js" in result

    def test_no_message_when_selected_lang_matches_primary(self) -> None:
        # Framework declares primary_languages=["js"]; user selects "js" — no mismatch.
        # Original: (primary=["js"]) and not any("js" in ["js"] ...)
        #           -> True and False -> False -> None
        # Mutant:   (primary=["js"]) or not any(...) -> True
        #           -> message appended -> not None
        result = get_primary_languages_info(
            frameworks=["react"],
            framework_presets=[{"primary_languages": ["js"]}],
            selected_langs=["js"],
        )
        assert result is None

    def test_returns_none_when_selected_lang_in_primary(self) -> None:
        frameworks = ["react"]
        framework_presets = [{"primary_languages": ["js", "ts"]}]
        selected_langs = ["js"]

        result = get_primary_languages_info(
            frameworks, framework_presets, selected_langs
        )

        assert result is None

    def test_returns_none_when_selected_lang_matches_primary(self) -> None:
        result = get_primary_languages_info(
            frameworks=["react"],
            framework_presets=[{"primary_languages": ["js", "ts"]}],
            selected_langs=["js"],
        )
        assert result is None

    def test_message_contains_primary_language_names(self) -> None:
        frameworks = ["react"]
        framework_presets = [{"primary_languages": ["js", "ts"]}]
        selected_langs = ["py"]  # not in primary_languages -> mismatch

        result = get_primary_languages_info(
            frameworks, framework_presets, selected_langs
        )

        assert result is not None
        assert "js" in result
        assert "ts" in result
        assert "None" not in result

    def test_primary_languages_info_separator(self) -> None:
        # Framework has two primary languages; selected lang does not match either
        result = get_primary_languages_info(
            frameworks=["myfw"],
            framework_presets=[{"primary_languages": ["py", "ts"]}],
            selected_langs=["go"],
        )
        assert result is not None
        # The two primary langs must be separated by ", " not "XX, XX"
        assert "py, ts" in result

    def test_multiple_framework_mismatches_joined_by_newline(self) -> None:
        frameworks = ["react", "django"]
        framework_presets = [
            {"primary_languages": ["js"]},
            {"primary_languages": ["py"]},
        ]
        selected_langs = ["go"]  # matches neither framework's primary languages

        result = get_primary_languages_info(
            frameworks, framework_presets, selected_langs
        )

        assert result is not None
        lines = result.split("\n")
        assert len(lines) == 2
        assert all(not line.startswith("XX") for line in lines)
