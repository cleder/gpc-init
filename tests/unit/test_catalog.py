"""Unit tests for gpc_init/catalog.py."""

from pathlib import Path

import pytest

from gpc_init.catalog import load_catalog
from gpc_init.exceptions import MetadataConflictError


class TestBundledCatalog:
    def test_py_metadata_loaded(self) -> None:
        catalog = load_catalog()
        assert catalog.langs["py"].fullname == "Python"
        assert catalog.langs["py"].icon == "🐍"
        assert ".py" in catalog.langs["py"].extensions

    def test_extension_to_lang_maps_py(self) -> None:
        catalog = load_catalog()
        assert catalog.extension_to_lang[".py"] == "py"

    def test_filename_to_lang_maps_dockerfile(self) -> None:
        catalog = load_catalog()
        assert catalog.filename_to_lang["dockerfile"] == "docker"

    def test_alias_to_lang_maps_python(self) -> None:
        catalog = load_catalog()
        assert catalog.alias_to_lang["python"] == "py"

    def test_framework_metadata_loaded(self) -> None:
        catalog = load_catalog()
        assert catalog.frameworks["django"].fullname == "Django"
        assert catalog.frameworks["django"].detect == ({"file_exists": "manage.py"},)

    def test_escape_hatch_detect_rule_is_a_python_string(self) -> None:
        catalog = load_catalog()
        assert catalog.frameworks["sphinx"].detect == ("python:_has_sphinx_conf",)


class TestFallbackForMissingMetadata:
    def test_lang_without_metadata_falls_back_to_id(self, tmp_preset_dir: Path) -> None:
        # tests/fixtures/lang/js has preset.yaml but no metadata.yaml.
        catalog = load_catalog(tmp_preset_dir)
        assert catalog.langs["js"].fullname == "js"
        assert catalog.langs["js"].icon == ""
        assert catalog.langs["js"].extensions == ()

    def test_lang_with_metadata_is_used(self, tmp_preset_dir: Path) -> None:
        # tests/fixtures/lang/py has both preset.yaml and metadata.yaml.
        catalog = load_catalog(tmp_preset_dir)
        assert catalog.langs["py"].fullname == "Python"
        assert catalog.extension_to_lang[".py"] == "py"

    def test_framework_without_metadata_falls_back_to_id(
        self, tmp_preset_dir: Path
    ) -> None:
        # tests/fixtures/framework/react has preset.yaml but no metadata.yaml.
        catalog = load_catalog(tmp_preset_dir)
        assert catalog.frameworks["react"].fullname == "react"
        assert catalog.frameworks["react"].icon == ""
        assert catalog.frameworks["react"].detect == ()


class TestConflictDetection:
    def _make_lang(self, base: Path, lang_id: str, extension: str) -> None:
        lang_dir = base / "lang" / lang_id
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (lang_dir / "metadata.yaml").write_text(
            f"fullname: {lang_id}\nextensions: [{extension}]\n", encoding="utf-8"
        )

    def test_duplicate_extension_raises(self, tmp_path: Path) -> None:
        self._make_lang(tmp_path, "alpha", ".foo")
        self._make_lang(tmp_path, "beta", ".foo")
        with pytest.raises(MetadataConflictError) as exc_info:
            load_catalog(tmp_path)
        assert "alpha" in str(exc_info.value)
        assert "beta" in str(exc_info.value)
        assert ".foo" in str(exc_info.value)

    def test_same_extension_twice_in_one_lang_is_not_a_conflict(
        self, tmp_path: Path
    ) -> None:
        lang_dir = tmp_path / "lang" / "alpha"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (lang_dir / "metadata.yaml").write_text(
            "fullname: alpha\nextensions: [.foo, .foo]\n", encoding="utf-8"
        )
        catalog = load_catalog(tmp_path)
        assert catalog.extension_to_lang[".foo"] == "alpha"
