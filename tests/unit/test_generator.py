"""Unit tests for gpc_init/generator.py."""

from pathlib import Path

import pytest

from gpc_init.exceptions import (
    PresetNotFoundError,
    PresetParseError,
    UnsupportedFrameworkError,
    UnsupportedLanguageError,
    UnsupportedProfileError,
)
from gpc_init.generator import generate


class TestGenerateHappyPath:
    def test_merges_common_and_language(self, tmp_preset_dir: Path) -> None:
        result = generate(["py"], [], base_dir=tmp_preset_dir)
        assert result.langs == ["py"]
        assert result.frameworks == []
        assert "ruff-check" in result.yaml_content
        assert "trailing-whitespace" in result.yaml_content

    def test_merges_language_and_framework(self, tmp_preset_dir: Path) -> None:
        result = generate(["js"], ["react"], base_dir=tmp_preset_dir)
        assert "prettier" in result.yaml_content
        assert "eslint-react" in result.yaml_content


class TestGenerateRecommended:
    def test_expands_recommended_language(self, tmp_preset_dir: Path) -> None:
        # framework/react/preset.yaml recommends lang: [js]
        result = generate([], ["react"], base_dir=tmp_preset_dir, recommended=True)
        assert result.langs == ["js"]
        assert "prettier" in result.yaml_content

    def test_no_expansion_when_not_recommended(self, tmp_preset_dir: Path) -> None:
        result = generate([], ["react"], base_dir=tmp_preset_dir, recommended=False)
        assert result.langs == []

    def test_recommended_defaults_to_false(self, tmp_preset_dir: Path) -> None:
        result = generate(["py"], ["react"], base_dir=tmp_preset_dir)
        assert result.langs == ["py"]


class TestGenerateValidationErrors:
    def test_unsupported_language_raises(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedLanguageError):
            generate(["cobol"], [], base_dir=tmp_preset_dir)

    def test_unsupported_framework_raises(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedFrameworkError):
            generate(["py"], ["angular"], base_dir=tmp_preset_dir)

    def test_unsupported_profile_raises(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(UnsupportedProfileError):
            generate(["py"], [], base_dir=tmp_preset_dir, profiles=("bogus",))


class TestGeneratePresetErrors:
    def test_missing_lang_subdir_raises_preset_not_found(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(PresetNotFoundError, match="lang' subdirectory"):
            generate(["py"], [], base_dir=empty_dir)

    def test_malformed_preset_yaml_raises_parse_error(
        self, tmp_preset_dir: Path
    ) -> None:
        bad_lang_dir = tmp_preset_dir / "lang" / "bad"
        bad_lang_dir.mkdir()
        (bad_lang_dir / "preset.yaml").write_text(": bad: [", encoding="utf-8")
        with pytest.raises(PresetParseError):
            generate(["bad"], [], base_dir=tmp_preset_dir)
