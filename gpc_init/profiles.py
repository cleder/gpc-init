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
        if not self.id:
            raise ValueError("HookConfig.id must be non-empty")


@dataclass(frozen=True)
class RepoConfig:
    """A pre-commit repository entry."""

    repo: str
    hooks: tuple[HookConfig, ...] = field(default_factory=tuple)
    rev: str = ""

    def __post_init__(self) -> None:
        if not self.repo:
            raise ValueError("RepoConfig.repo must be non-empty")
        if not self.hooks:
            raise ValueError("RepoConfig.hooks must contain at least one hook")


@dataclass(frozen=True)
class GenerationRequest:
    """User request parsed from CLI."""

    langs: tuple[str, ...] = field(default_factory=tuple)
    frameworks: tuple[str, ...] = field(default_factory=tuple)
    force: bool = False
    target_path: str = ".pre-commit-config.yaml"

    def __post_init__(self) -> None:
        if not self.langs:
            raise ValueError("GenerationRequest.langs must be non-empty")


@dataclass(frozen=True)
class GenerationResult:
    """Deterministic rendering and write outcome."""

    content: str
    path: str
    overwritten: bool = False
