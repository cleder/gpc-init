"""Unit tests for gpc_init/fetcher.py."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gpc_init.exceptions import PresetFetchError
from gpc_init.fetcher import fetch_preset_repo, is_git_url


class TestIsGitUrl:
    def test_https_prefix(self) -> None:
        assert is_git_url("https://github.com/user/repo") is True

    def test_git_at_prefix(self) -> None:
        assert is_git_url("git@github.com:user/repo.git") is True

    def test_ssh_prefix(self) -> None:
        assert is_git_url("ssh://git@example.com/repo") is True

    def test_git_protocol_prefix(self) -> None:
        assert is_git_url("git://example.com/repo") is True

    def test_dot_git_suffix_only(self) -> None:
        assert is_git_url("../local/bare-repo.git") is True

    def test_local_absolute_path(self) -> None:
        assert is_git_url("/path/to/presets") is False

    def test_local_relative_path(self) -> None:
        assert is_git_url("./my-presets") is False

    def test_plain_name(self) -> None:
        assert is_git_url("my-presets") is False


class TestFetchPresetRepo:
    def test_git_not_installed_raises(self) -> None:
        with (
            patch("gpc_init.fetcher.shutil.which", return_value=None),
            pytest.raises(PresetFetchError, match="git is not installed"),
            fetch_preset_repo("https://example.com/repo"),
        ):
            pass

    def test_clone_failure_raises(self) -> None:
        with (
            patch("gpc_init.fetcher.shutil.which", return_value="/usr/bin/git"),
            patch(
                "gpc_init.fetcher.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    1, "git", stderr="repository not found"
                ),
            ),
            pytest.raises(PresetFetchError, match="repository not found"),
            fetch_preset_repo("https://example.com/repo"),
        ):
            pass

    def test_clone_failure_uses_stdout_when_stderr_empty(self) -> None:
        with (
            patch("gpc_init.fetcher.shutil.which", return_value="/usr/bin/git"),
            patch(
                "gpc_init.fetcher.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    1, "git", output="fatal: something", stderr=""
                ),
            ),
            pytest.raises(PresetFetchError, match="fatal: something"),
            fetch_preset_repo("https://example.com/repo"),
        ):
            pass

    def test_successful_clone_yields_path(self) -> None:
        with (
            patch("gpc_init.fetcher.shutil.which", return_value="/usr/bin/git"),
            patch(
                "gpc_init.fetcher.subprocess.run",
                return_value=MagicMock(returncode=0),
            ),
            fetch_preset_repo("https://example.com/repo") as path,
        ):
            assert isinstance(path, Path)
            assert path.exists()

    def test_temp_dir_cleaned_up_after_context(self) -> None:
        captured: list[Path] = []
        with (
            patch("gpc_init.fetcher.shutil.which", return_value="/usr/bin/git"),
            patch(
                "gpc_init.fetcher.subprocess.run",
                return_value=MagicMock(returncode=0),
            ),
            fetch_preset_repo("https://example.com/repo") as path,
        ):
            captured.append(path)
        assert not captured[0].exists()
