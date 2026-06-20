"""Unit tests for gpc_init/exceptions.py."""

from gpc_init.exceptions import (
    PresetFetchError,
    TargetFileExistsError,
    UnsupportedFrameworkError,
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
