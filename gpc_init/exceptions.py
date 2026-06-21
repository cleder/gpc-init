"""Custom exceptions for pc-init."""


class PresetNotFoundError(Exception):
    """Raised when a preset file is not found on the filesystem."""


class PresetParseError(Exception):
    """Raised when a preset file contains invalid YAML or unexpected structure."""


class UnsupportedLanguageError(Exception):
    """Raised when a requested language is not in the language catalog."""

    def __init__(self, lang: str, supported: list[str]) -> None:
        """Initialize with the unsupported language and supported language list."""
        self.lang = lang
        self.supported = supported
        supported_str = ", ".join(sorted(supported))
        super().__init__(f"Unsupported language '{lang}'. Supported: {supported_str}")


class UnsupportedFrameworkError(Exception):
    """Raised when a requested framework is not in the framework catalog."""

    def __init__(self, fw: str, supported: list[str]) -> None:
        """Initialize with the unsupported framework and supported framework list."""
        self.fw = fw
        self.supported = supported
        supported_str = ", ".join(sorted(supported))
        super().__init__(f"Unsupported framework '{fw}'. Supported: {supported_str}")


class TargetFileExistsError(Exception):
    """Raised when target file already exists and --force was not provided."""

    def __init__(self, path: str) -> None:
        """Initialize with the path that already exists."""
        self.path = path
        super().__init__(f"'{path}' already exists. Use --force to overwrite.")


class PresetFetchError(Exception):
    """Raised when a remote preset repository cannot be fetched."""

    def __init__(self, url: str, detail: str) -> None:
        """Initialize with the URL that failed and the reason."""
        self.url = url
        super().__init__(f"Failed to fetch presets from '{url}': {detail}")
