"""Unit tests for gpc_init/catalog.py."""

from pathlib import Path
from typing import IO, Any

import pytest

from gpc_init.catalog import load_catalog
from gpc_init.exceptions import MetadataConflictError, PresetParseError


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
        assert catalog.frameworks["django"].icon == "🎸"
        assert catalog.frameworks["django"].detect == ({"file_exists": "manage.py"},)

    def test_escape_hatch_detect_rule_is_a_python_string(self) -> None:
        catalog = load_catalog()
        assert catalog.frameworks["sphinx"].detect == ("python:_has_sphinx_conf",)

    def test_common_lang_dir_is_excluded_from_langs(self) -> None:
        # lang/common has a preset.yaml but is a shared base, not a selectable lang.
        catalog = load_catalog()
        assert "common" not in catalog.langs

    def test_common_lang_dir_is_excluded_despite_having_preset(self) -> None:
        # gpc_init/lang/common has a preset.yaml but is passed via exclude=
        # in load_catalog, so it must never surface as a language.
        catalog = load_catalog()
        assert "common" not in catalog.langs

    def test_framework_icon_loaded(self) -> None:
        catalog = load_catalog()
        assert catalog.frameworks["django"].icon == "🎸"


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

    def test_duplicate_extension_message_states_uniqueness_rule(
        self, tmp_path: Path
    ) -> None:
        self._make_lang(tmp_path, "alpha", ".foo")
        self._make_lang(tmp_path, "beta", ".foo")
        with pytest.raises(MetadataConflictError) as exc_info:
            load_catalog(tmp_path)
        assert str(exc_info.value).endswith(
            "each extension/filename/alias must belong to exactly one language."
        )

    def test_duplicate_extension_message_capitalizes_kind(self, tmp_path: Path) -> None:
        self._make_lang(tmp_path, "alpha", ".foo")
        self._make_lang(tmp_path, "beta", ".foo")
        with pytest.raises(MetadataConflictError) as exc_info:
            load_catalog(tmp_path)
        assert str(exc_info.value).startswith("Extension '.foo'")

    def test_duplicate_extension_message_explains_the_rule(
        self, tmp_path: Path
    ) -> None:
        self._make_lang(tmp_path, "alpha", ".foo")
        self._make_lang(tmp_path, "beta", ".foo")
        with pytest.raises(MetadataConflictError) as exc_info:
            load_catalog(tmp_path)
        assert (
            "each extension/filename/alias must belong to exactly one language."
            in str(exc_info.value)
        )

    def test_duplicate_extension_message_names_the_kind_as_extension(
        self, tmp_path: Path
    ) -> None:
        self._make_lang(tmp_path, "alpha", ".foo")
        self._make_lang(tmp_path, "beta", ".foo")
        with pytest.raises(MetadataConflictError) as exc_info:
            load_catalog(tmp_path)
        assert str(exc_info.value).startswith("Extension '.foo'")

    def test_duplicate_filename_message_capitalizes_kind(self, tmp_path: Path) -> None:
        for lang_id in ("alpha", "beta"):
            lang_dir = tmp_path / "lang" / lang_id
            lang_dir.mkdir(parents=True)
            (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
            (lang_dir / "metadata.yaml").write_text(
                f"fullname: {lang_id}\nfilenames: [Foo.txt]\n", encoding="utf-8"
            )
        with pytest.raises(MetadataConflictError) as exc_info:
            load_catalog(tmp_path)
        assert str(exc_info.value).startswith("Filename 'foo.txt'")

    def test_duplicate_alias_message_capitalizes_kind(self, tmp_path: Path) -> None:
        for lang_id in ("alpha", "beta"):
            lang_dir = tmp_path / "lang" / lang_id
            lang_dir.mkdir(parents=True)
            (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
            (lang_dir / "metadata.yaml").write_text(
                f"fullname: {lang_id}\naliases: [Foo]\n", encoding="utf-8"
            )
        with pytest.raises(MetadataConflictError) as exc_info:
            load_catalog(tmp_path)
        assert str(exc_info.value).startswith("Alias 'foo'")

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


class TestMalformedMetadata:
    def test_invalid_metadata_yaml_raises_preset_parse_error_with_message(
        self, tmp_path: Path
    ) -> None:
        lang_dir = tmp_path / "lang" / "broken"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (lang_dir / "metadata.yaml").write_text(
            "key: [unclosed bracket", encoding="utf-8"
        )
        with pytest.raises(PresetParseError, match="Failed to parse metadata YAML"):
            load_catalog(tmp_path)

    def test_non_mapping_metadata_error_message_contains_actual_type_name(
        self, tmp_path: Path
    ) -> None:
        # A YAML list is not a mapping; error must report "list", not "NoneType".
        lang_dir = tmp_path / "lang" / "broken2"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (lang_dir / "metadata.yaml").write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(PresetParseError, match="got list"):
            load_catalog(tmp_path)

    def test_metadata_non_mapping_raises_descriptive_error(
        self, tmp_path: Path
    ) -> None:
        lang_dir = tmp_path / "lang" / "alpha"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (lang_dir / "metadata.yaml").write_text("- one\n- two\n", encoding="utf-8")
        with pytest.raises(PresetParseError) as exc_info:
            load_catalog(tmp_path)
        assert "must contain a YAML mapping" in str(exc_info.value)
        assert "list" in str(exc_info.value)


class TestMetadataFileEncoding:
    def test_metadata_file_is_opened_with_utf8_encoding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lang_dir = tmp_path / "lang" / "alpha"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (lang_dir / "metadata.yaml").write_text("fullname: alpha\n", encoding="utf-8")

        captured_encodings: list[str | None] = []
        original_open = Path.open

        def spy_open(
            self: Path,
            mode: str = "r",
            *,
            buffering: int = -1,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
        ) -> IO[Any]:
            if self.name == "metadata.yaml":
                captured_encodings.append(encoding)
            return original_open(
                self,
                mode,
                buffering=buffering,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )

        monkeypatch.setattr(Path, "open", spy_open)
        load_catalog(tmp_path)

        assert captured_encodings == ["utf-8"]
