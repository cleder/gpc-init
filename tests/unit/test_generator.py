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

    def test_framework_preset_loaded_from_base_dir(self, tmp_preset_dir: Path) -> None:
        # The fixture react preset pins eslint-plugin-react@7.0.0, distinct from
        # the real default preset's version, so this fails if the framework
        # preset is loaded from the default base_dir instead of tmp_preset_dir.
        result = generate(["js"], ["react"], base_dir=tmp_preset_dir)
        assert "eslint-plugin-react@7.0.0" in result.yaml_content

    def test_common_preset_loaded_from_base_dir(self, tmp_preset_dir: Path) -> None:
        # The fixture common preset only has trailing-whitespace/end-of-file
        # hooks; the real default common preset also has 'gitleaks', so this
        # fails if the common preset is loaded from the default base_dir
        # instead of tmp_preset_dir.
        result = generate(["py"], [], base_dir=tmp_preset_dir)
        assert "gitleaks" not in result.yaml_content


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

    def test_expansion_checks_base_dir_catalog_not_default(
        self, tmp_preset_dir: Path
    ) -> None:
        # "zzlang" only exists in tmp_preset_dir's catalog, not in the real
        # default catalog. This fails if expand_recommendations is fed the
        # default catalog's supported langs instead of tmp_preset_dir's.
        zzlang_dir = tmp_preset_dir / "lang" / "zzlang"
        zzlang_dir.mkdir()
        (zzlang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")

        customfw_dir = tmp_preset_dir / "framework" / "customfw"
        customfw_dir.mkdir()
        (customfw_dir / "preset.yaml").write_text(
            "recommended:\n  lang:\n    - zzlang\nrepos: []\n", encoding="utf-8"
        )

        result = generate([], ["customfw"], base_dir=tmp_preset_dir, recommended=True)
        assert result.langs == ["zzlang"]

    def test_recommended_framework_uses_custom_base_dir(
        self, tmp_preset_dir: Path
    ) -> None:
        # "widget" only exists as a framework in tmp_preset_dir, not in the
        # real default catalog, so it is only recognized as "supported" (and
        # therefore included via recommendation expansion) if the supported
        # frameworks are discovered from base_dir instead of the default.
        widget_dir = tmp_preset_dir / "framework" / "widget"
        widget_dir.mkdir()
        (widget_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (tmp_preset_dir / "lang" / "py" / "preset.yaml").write_text(
            "recommended:\n"
            "  framework:\n"
            "    - widget\n"
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.15.20\n"
            "    hooks:\n"
            "      - id: ruff-check\n"
            "      - id: ruff-format\n",
            encoding="utf-8",
        )
        result = generate(["py"], [], base_dir=tmp_preset_dir, recommended=True)
        assert result.frameworks == ["widget"]

    def test_reloads_framework_preset_from_base_dir_when_recommended(
        self, tmp_preset_dir: Path
    ) -> None:
        # After recommendation expansion, presets are reloaded a second time;
        # the fixture react preset pins eslint-plugin-react@7.0.0, distinct
        # from the real default preset's version, so this fails if that
        # reload uses the default base_dir instead of tmp_preset_dir.
        result = generate([], ["react"], base_dir=tmp_preset_dir, recommended=True)
        assert "eslint-plugin-react@7.0.0" in result.yaml_content


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

    def test_validation_uses_base_dir_for_custom_framework(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "lang").mkdir()
        fw_dir = tmp_path / "framework" / "customfw"
        fw_dir.mkdir(parents=True)
        (fw_dir / "preset.yaml").write_text(
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: custom-hook\n"
            "        name: custom\n"
            "        entry: custom\n"
            "        language: system\n",
            encoding="utf-8",
        )
        result = generate([], ["customfw"], base_dir=tmp_path)
        assert result.frameworks == ["customfw"]

    def test_unsupported_framework_uses_supplied_base_dir(
        self, tmp_preset_dir: Path
    ) -> None:
        # "django" is supported in the real default preset catalog but not
        # in tmp_preset_dir's fixtures; this fails with PresetNotFoundError
        # instead of UnsupportedFrameworkError if validate_frameworks ignores
        # the supplied base_dir and falls back to the default one.
        with pytest.raises(UnsupportedFrameworkError):
            generate(["py"], ["django"], base_dir=tmp_preset_dir)


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
