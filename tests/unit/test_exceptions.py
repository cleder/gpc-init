"""Unit tests for gpc_init/exceptions.py."""

from gpc_init.exceptions import (
    PresetFetchError,
    TargetFileExistsError,
    UnsupportedFrameworkError,
    UnsupportedLanguageError,
)


class TestUnsupportedFrameworkError:
    def test_fw_attribute(self) -> None:
        exc = UnsupportedFrameworkError("angular", ["react", "django"])
        assert exc.fw == "angular"

    def test_supported_attribute(self) -> None:
        supported = ["react", "django"]
        exc = UnsupportedFrameworkError("angular", supported)
        assert exc.supported == supported

    def test_message_includes_framework(self) -> None:
        assert "angular" in str(UnsupportedFrameworkError("angular", ["react"]))

    def test_message_lists_supported(self) -> None:
        assert "Supported:" in str(UnsupportedFrameworkError("x", ["a", "b"]))

    def test_message_contains_supported_frameworks(self) -> None:
        exc = UnsupportedFrameworkError("angular", ["react", "django"])
        assert "react" in str(exc)
        assert "django" in str(exc)

    def test_message_formats_supported_with_comma_separator(self) -> None:
        exc = UnsupportedFrameworkError("angular", ["react", "django"])
        assert "django, react" in str(exc)


class TestUnsupportedLanguageError:
    def test_lang_attribute(self) -> None:
        exc = UnsupportedLanguageError("cobol", ["python", "go"])
        assert exc.lang == "cobol"

    def test_supported_attribute(self) -> None:
        supported = ["python", "go"]
        exc = UnsupportedLanguageError("cobol", supported)
        assert exc.supported == supported

    def test_message_includes_language(self) -> None:
        assert "cobol" in str(UnsupportedLanguageError("cobol", ["python"]))

    def test_message_lists_supported_sorted(self) -> None:
        exc = UnsupportedLanguageError("cobol", ["python", "go"])
        msg = str(exc)
        assert "go" in msg
        assert "python" in msg
        assert msg.index("go") < msg.index("python")  # sorted order

    def test_message_lists_supported_with_separator(self) -> None:
        exc = UnsupportedLanguageError("cobol", ["python", "javascript"])
        msg = str(exc)
        assert "javascript, python" in msg or "python, javascript" in msg


class TestTargetFileExistsError:
    def test_path_attribute(self) -> None:
        exc = TargetFileExistsError(".pre-commit-config.yaml")
        assert exc.path == ".pre-commit-config.yaml"

    def test_message_includes_path(self) -> None:
        exc = TargetFileExistsError(".pre-commit-config.yaml")
        assert ".pre-commit-config.yaml" in str(exc)

    def test_message_mentions_force(self) -> None:
        assert "--force" in str(TargetFileExistsError("out.yaml"))


class TestPresetFetchError:
    def test_url_attribute(self) -> None:
        exc = PresetFetchError("https://example.com", "refused")
        assert exc.url == "https://example.com"

    def test_message_includes_url(self) -> None:
        exc = PresetFetchError("https://example.com", "err")
        assert "https://example.com" in str(exc)

    def test_message_includes_detail(self) -> None:
        exc = PresetFetchError("https://x", "connection refused")
        assert "connection refused" in str(exc)
