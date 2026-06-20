"""Unit tests for gpc_init/profiles.py data classes."""

import pytest

from gpc_init.profiles import (
    GenerationRequest,
    GenerationResult,
    HookConfig,
    RepoConfig,
)


class TestHookConfig:
    def test_valid_hook(self) -> None:
        hook = HookConfig(id="ruff-check")
        assert hook.id == "ruff-check"

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="id must be non-empty"):
            HookConfig(id="")

    def test_hook_with_args(self) -> None:
        hook = HookConfig(id="mypy", args=("--strict",))
        assert hook.args == ("--strict",)

    def test_hook_immutable(self) -> None:
        hook = HookConfig(id="ruff-check")
        with pytest.raises(AttributeError):
            hook.id = "other"  # type: ignore[misc]


class TestRepoConfig:
    def test_valid_repo(self) -> None:
        hook = HookConfig(id="ruff-check")
        repo = RepoConfig(repo="https://example.com/repo", rev="v1.0.0", hooks=(hook,))
        assert repo.repo == "https://example.com/repo"

    def test_empty_repo_raises(self) -> None:
        hook = HookConfig(id="ruff-check")
        with pytest.raises(ValueError, match="repo must be non-empty"):
            RepoConfig(repo="", rev="v1.0.0", hooks=(hook,))

    def test_empty_hooks_raises(self) -> None:
        with pytest.raises(ValueError, match="hooks must contain at least one"):
            RepoConfig(repo="https://example.com", hooks=())


class TestGenerationRequest:
    def test_valid_request(self) -> None:
        req = GenerationRequest(langs=("py",))
        assert req.langs == ("py",)
        assert req.frameworks == ()
        assert req.force is False
        assert req.target_path == ".pre-commit-config.yaml"

    def test_empty_langs_raises(self) -> None:
        with pytest.raises(ValueError, match="langs must be non-empty"):
            GenerationRequest(langs=())

    def test_request_with_force(self) -> None:
        req = GenerationRequest(langs=("py",), force=True)
        assert req.force is True


class TestGenerationResult:
    def test_valid_result(self) -> None:
        result = GenerationResult(content="repos: []", path=".pre-commit-config.yaml")
        assert result.overwritten is False

    def test_overwritten_result(self) -> None:
        result = GenerationResult(
            content="repos: []", path=".pre-commit-config.yaml", overwritten=True
        )
        assert result.overwritten is True
