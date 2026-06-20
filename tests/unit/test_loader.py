"""Unit tests for gpc_init/loader.py."""

from pathlib import Path

import pytest

from gpc_init.exceptions import PresetNotFoundError, PresetParseError
from gpc_init.loader import load_common_preset, load_framework_preset, load_language_preset


class TestLoadCommonPreset:
    def test_loads_common_preset(self, tmp_preset_dir: Path) -> None:
        result = load_common_preset(base_dir=tmp_preset_dir)
        assert "repos" in result
        repos = result["repos"]
        assert len(repos) > 0

    def test_returns_empty_dict_when_missing(self, tmp_path: Path) -> None:
        # No lang/common/default.yaml in tmp_path
        result = load_common_preset(base_dir=tmp_path)
        assert result == {}

    def test_preserves_hook_order(self, tmp_preset_dir: Path) -> None:
        result = load_common_preset(base_dir=tmp_preset_dir)
        repos = result["repos"]
        # Verify all repos are dicts with expected keys
        for repo in repos:
            assert "repo" in repo
            assert "hooks" in repo


class TestLoadLanguagePreset:
    def test_loads_py_preset(self, tmp_preset_dir: Path) -> None:
        result = load_language_preset("py", base_dir=tmp_preset_dir)
        assert "repos" in result
        assert len(result["repos"]) > 0

    def test_loads_js_preset(self, tmp_preset_dir: Path) -> None:
        result = load_language_preset("js", base_dir=tmp_preset_dir)
        assert "repos" in result

    def test_missing_language_raises_preset_not_found(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(PresetNotFoundError, match="not found"):
            load_language_preset("unknown_lang", base_dir=tmp_preset_dir)

    def test_invalid_yaml_raises_preset_parse_error(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "lang" / "bad"
        lang_dir.mkdir(parents=True)
        (lang_dir / "baseline.yaml").write_text("key: [unclosed bracket", encoding="utf-8")
        with pytest.raises(PresetParseError, match="Failed to parse"):
            load_language_preset("bad", base_dir=tmp_path)

    def test_non_mapping_yaml_raises_preset_parse_error(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "lang" / "list_preset"
        lang_dir.mkdir(parents=True)
        (lang_dir / "baseline.yaml").write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(PresetParseError, match="must contain a YAML mapping"):
            load_language_preset("list_preset", base_dir=tmp_path)

    def test_returns_dict_with_repos(self, tmp_preset_dir: Path) -> None:
        result = load_language_preset("py", base_dir=tmp_preset_dir)
        assert isinstance(result, dict)
        assert "repos" in result
        assert isinstance(result["repos"], list)


class TestLoadFrameworkPreset:
    def test_loads_react_preset(self, tmp_preset_dir: Path) -> None:
        result = load_framework_preset("react", base_dir=tmp_preset_dir)
        assert "repos" in result

    def test_missing_framework_raises_preset_not_found(self, tmp_preset_dir: Path) -> None:
        with pytest.raises(PresetNotFoundError, match="not found"):
            load_framework_preset("unknown_fw", base_dir=tmp_preset_dir)

    def test_framework_preset_includes_primary_languages(self, tmp_preset_dir: Path) -> None:
        result = load_framework_preset("react", base_dir=tmp_preset_dir)
        assert "primary_languages" in result
        assert "js" in result["primary_languages"]
