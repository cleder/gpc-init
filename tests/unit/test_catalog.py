"""Unit tests for pc_init/catalog.py."""

import os
from collections import Counter
from pathlib import Path
from typing import IO, Any

import pytest

from pc_init.catalog import Catalog
from pc_init.exceptions import (
    MetadataConflictError,
    PresetNotFoundError,
    PresetParseError,
)


class TestCatalogIds:
    def test_lists_sorted_ids_excluding_common(self, tmp_preset_dir: Path) -> None:
        catalog = Catalog.load(tmp_preset_dir)
        assert catalog.lang_ids == sorted(catalog.lang_ids)
        assert "py" in catalog.lang_ids
        assert "common" not in catalog.lang_ids
        assert "react" in catalog.framework_ids

    def test_only_directories_with_a_preset_are_listed(self, tmp_path: Path) -> None:
        (tmp_path / "lang" / "has").mkdir(parents=True)
        (tmp_path / "lang" / "has" / "preset.yaml").write_text("repos: []\n")
        (tmp_path / "lang" / "empty").mkdir()
        (tmp_path / "framework").mkdir()
        catalog = Catalog.load(tmp_path)
        assert catalog.lang_ids == ["has"]
        assert catalog.framework_ids == []


class TestCatalogRoot:
    def test_defaults_to_the_bundled_presets(self) -> None:
        catalog = Catalog.load()
        assert "py" in catalog.lang_ids
        assert "django" in catalog.framework_ids

    def test_root_without_lang_directory_is_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "framework").mkdir()
        with pytest.raises(PresetNotFoundError, match="lang"):
            Catalog.load(tmp_path)


def _write_preset(root: Path, kind: str, name: str, text: str) -> None:
    preset_dir = root / kind / name
    preset_dir.mkdir(parents=True)
    (preset_dir / "preset.yaml").write_text(text, encoding="utf-8")


class TestCatalogPresets:
    def test_loads_language_framework_and_common_presets(
        self, tmp_preset_dir: Path
    ) -> None:
        catalog = Catalog.load(tmp_preset_dir)
        assert isinstance(catalog.lang_preset("py")["repos"], list)
        assert "repos" in catalog.framework_preset("react")
        assert "js" in catalog.framework_preset("react")["recommended"]["lang"]
        assert len(catalog.common_preset()["repos"]) > 0

    def test_missing_common_preset_is_empty(self, tmp_path: Path) -> None:
        (tmp_path / "lang").mkdir()
        assert Catalog.load(tmp_path).common_preset() == {}

    @pytest.mark.parametrize("kind", ["lang", "framework"])
    def test_unknown_preset_raises_not_found(
        self, tmp_preset_dir: Path, kind: str
    ) -> None:
        catalog = Catalog.load(tmp_preset_dir)
        load = catalog.lang_preset if kind == "lang" else catalog.framework_preset
        with pytest.raises(PresetNotFoundError, match="not found"):
            load("nope")

    def test_invalid_yaml_raises_parse_error(self, tmp_path: Path) -> None:
        _write_preset(tmp_path, "lang", "bad", "key: [unclosed bracket")
        with pytest.raises(PresetParseError, match="Failed to parse preset YAML"):
            Catalog.load(tmp_path).lang_preset("bad")

    @pytest.mark.parametrize(
        ("text", "type_name"), [("- a\n- b\n", "list"), ("just a string\n", "str")]
    )
    def test_non_mapping_names_the_actual_type(
        self, tmp_path: Path, text: str, type_name: str
    ) -> None:
        _write_preset(tmp_path, "lang", "odd", text)
        with pytest.raises(
            PresetParseError, match=f"must contain a YAML mapping.*{type_name}"
        ):
            Catalog.load(tmp_path).lang_preset("odd")

    def test_empty_preset_is_an_empty_mapping(self, tmp_path: Path) -> None:
        _write_preset(tmp_path, "lang", "empty", "")
        assert Catalog.load(tmp_path).lang_preset("empty") == {}


class TestCatalogFileReads:
    @staticmethod
    def _opened(monkeypatch: pytest.MonkeyPatch) -> Counter[tuple[str, str | None]]:
        opened: Counter[tuple[str, str | None]] = Counter()
        original = Path.open

        def spy(self: Path, *args: Any, **kwargs: Any) -> Any:
            opened[(self.name, kwargs.get("encoding"))] += 1
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", spy)
        return opened

    def test_load_reads_only_metadata_and_each_file_once(
        self, tmp_preset_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened = self._opened(monkeypatch)
        Catalog.load(tmp_preset_dir)
        assert opened
        assert {name for name, _ in opened} == {"metadata.yaml"}
        assert max(opened.values()) == 1

    def test_presets_are_read_on_demand_as_utf8(
        self, tmp_preset_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        catalog = Catalog.load(tmp_preset_dir)
        opened = self._opened(monkeypatch)
        catalog.lang_preset("py")
        assert list(opened) == [("preset.yaml", "utf-8")]
        assert opened[("preset.yaml", "utf-8")] == 1


class TestUnreadableFiles:
    def test_invalid_utf8_metadata_is_a_parse_error(self, tmp_path: Path) -> None:
        _write_preset(tmp_path, "lang", "a", "repos: []\n")
        (tmp_path / "lang" / "a" / "metadata.yaml").write_bytes(b"\xff\xfe\x00bad")
        with pytest.raises(PresetParseError, match="Failed to read metadata file"):
            Catalog.load(tmp_path)

    def test_invalid_utf8_preset_is_a_parse_error(self, tmp_path: Path) -> None:
        _write_preset(tmp_path, "lang", "a", "repos: []\n")
        (tmp_path / "lang" / "a" / "preset.yaml").write_bytes(b"\xff\xfe\x00bad")
        with pytest.raises(PresetParseError, match="Failed to read preset file"):
            Catalog.load(tmp_path).lang_preset("a")

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
    def test_permission_denied_is_a_parse_error(self, tmp_path: Path) -> None:
        _write_preset(tmp_path, "lang", "a", "repos: []\n")
        preset = tmp_path / "lang" / "a" / "preset.yaml"
        preset.chmod(0)
        try:
            with pytest.raises(PresetParseError, match="Failed to read preset file"):
                Catalog.load(tmp_path).lang_preset("a")
        finally:
            preset.chmod(0o644)


class TestBundledCatalog:
    def test_py_metadata_loaded(self) -> None:
        catalog = Catalog.load()
        assert catalog.langs["py"].fullname == "Python"
        assert catalog.langs["py"].icon == "🐍"
        assert ".py" in catalog.langs["py"].extensions

    def test_extension_to_lang_maps_py(self) -> None:
        catalog = Catalog.load()
        assert catalog.extension_to_lang[".py"] == "py"

    def test_filename_to_lang_maps_dockerfile(self) -> None:
        catalog = Catalog.load()
        assert catalog.filename_to_lang["dockerfile"] == "docker"

    def test_alias_to_lang_maps_python(self) -> None:
        catalog = Catalog.load()
        assert catalog.alias_to_lang["python"] == "py"

    def test_framework_metadata_loaded(self) -> None:
        catalog = Catalog.load()
        assert catalog.frameworks["django"].fullname == "Django"
        assert catalog.frameworks["django"].icon == "🎸"
        assert catalog.frameworks["django"].detect == ({"file_exists": "manage.py"},)

    def test_escape_hatch_detect_rule_is_a_python_string(self) -> None:
        catalog = Catalog.load()
        assert catalog.frameworks["sphinx"].detect == ("python:_has_sphinx_conf",)

    def test_common_lang_dir_is_excluded_from_langs(self) -> None:
        # lang/common has a preset.yaml but is a shared base, not a selectable lang.
        catalog = Catalog.load()
        assert "common" not in catalog.langs

    def test_common_lang_dir_is_excluded_despite_having_preset(self) -> None:
        # pc_init/lang/common has a preset.yaml but is passed via exclude=
        # in load_catalog, so it must never surface as a language.
        catalog = Catalog.load()
        assert "common" not in catalog.langs

    def test_framework_icon_loaded(self) -> None:
        catalog = Catalog.load()
        assert catalog.frameworks["django"].icon == "🎸"


class TestFallbackForMissingMetadata:
    def test_lang_without_metadata_falls_back_to_id(self, tmp_preset_dir: Path) -> None:
        # tests/fixtures/lang/js has preset.yaml but no metadata.yaml.
        catalog = Catalog.load(tmp_preset_dir)
        assert catalog.langs["js"].fullname == "js"
        assert catalog.langs["js"].icon == ""
        assert catalog.langs["js"].extensions == ()

    def test_lang_with_metadata_is_used(self, tmp_preset_dir: Path) -> None:
        # tests/fixtures/lang/py has both preset.yaml and metadata.yaml.
        catalog = Catalog.load(tmp_preset_dir)
        assert catalog.langs["py"].fullname == "Python"
        assert catalog.extension_to_lang[".py"] == "py"

    def test_framework_without_metadata_falls_back_to_id(
        self, tmp_preset_dir: Path
    ) -> None:
        # tests/fixtures/framework/react has preset.yaml but no metadata.yaml.
        catalog = Catalog.load(tmp_preset_dir)
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
            Catalog.load(tmp_path)
        assert "alpha" in str(exc_info.value)
        assert "beta" in str(exc_info.value)
        assert ".foo" in str(exc_info.value)

    def test_duplicate_extension_message_states_uniqueness_rule(
        self, tmp_path: Path
    ) -> None:
        self._make_lang(tmp_path, "alpha", ".foo")
        self._make_lang(tmp_path, "beta", ".foo")
        with pytest.raises(MetadataConflictError) as exc_info:
            Catalog.load(tmp_path)
        assert str(exc_info.value).endswith(
            "each extension/filename/alias must belong to exactly one language."
        )

    def test_duplicate_extension_message_capitalizes_kind(self, tmp_path: Path) -> None:
        self._make_lang(tmp_path, "alpha", ".foo")
        self._make_lang(tmp_path, "beta", ".foo")
        with pytest.raises(MetadataConflictError) as exc_info:
            Catalog.load(tmp_path)
        assert str(exc_info.value).startswith("Extension '.foo'")

    def test_duplicate_extension_message_explains_the_rule(
        self, tmp_path: Path
    ) -> None:
        self._make_lang(tmp_path, "alpha", ".foo")
        self._make_lang(tmp_path, "beta", ".foo")
        with pytest.raises(MetadataConflictError) as exc_info:
            Catalog.load(tmp_path)
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
            Catalog.load(tmp_path)
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
            Catalog.load(tmp_path)
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
            Catalog.load(tmp_path)
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
        catalog = Catalog.load(tmp_path)
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
            Catalog.load(tmp_path)

    def test_non_mapping_metadata_error_message_contains_actual_type_name(
        self, tmp_path: Path
    ) -> None:
        # A YAML list is not a mapping; error must report "list", not "NoneType".
        lang_dir = tmp_path / "lang" / "broken2"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (lang_dir / "metadata.yaml").write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(PresetParseError, match="got list"):
            Catalog.load(tmp_path)

    def test_metadata_non_mapping_raises_descriptive_error(
        self, tmp_path: Path
    ) -> None:
        lang_dir = tmp_path / "lang" / "alpha"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        (lang_dir / "metadata.yaml").write_text("- one\n- two\n", encoding="utf-8")
        with pytest.raises(PresetParseError) as exc_info:
            Catalog.load(tmp_path)
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
        Catalog.load(tmp_path)

        assert captured_encodings == ["utf-8"]
