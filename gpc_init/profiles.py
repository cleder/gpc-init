"""Data classes for pc-init profiles and generation entities."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HookConfig:
    """Individual pre-commit hook item."""

    id: str
    args: tuple[str, ...] = field(default_factory=tuple)
    additional_dependencies: tuple[str, ...] = field(default_factory=tuple)
    stages: tuple[str, ...] = field(default_factory=tuple)
    extra_fields: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate hook fields."""
        if not self.id:
            msg = "HookConfig.id must be non-empty"
            raise ValueError(msg)


@dataclass(frozen=True)
class RepoConfig:
    """A pre-commit repository entry."""

    repo: str
    hooks: tuple[HookConfig, ...] = field(default_factory=tuple)
    rev: str = ""

    def __post_init__(self) -> None:
        """Validate repo fields."""
        if not self.repo:
            msg = "RepoConfig.repo must be non-empty"
            raise ValueError(msg)
        if not self.hooks:
            msg = "RepoConfig.hooks must contain at least one hook"
            raise ValueError(msg)


@dataclass(frozen=True)
class GenerationRequest:
    """User request parsed from CLI."""

    langs: tuple[str, ...] = field(default_factory=tuple)
    frameworks: tuple[str, ...] = field(default_factory=tuple)
    force: bool = False
    target_path: str = ".pre-commit-config.yaml"

    def __post_init__(self) -> None:
        """Validate generation request fields."""
        if not self.langs:
            msg = "GenerationRequest.langs must be non-empty"
            raise ValueError(msg)


@dataclass(frozen=True)
class GenerationResult:
    """Deterministic rendering and write outcome."""

    content: str
    path: str
    overwritten: bool = False
