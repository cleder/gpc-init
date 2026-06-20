"""Fetch preset catalogs from remote git repositories."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from gpc_init.exceptions import PresetFetchError

if TYPE_CHECKING:
    from collections.abc import Generator

_GIT_URL_PREFIXES = ("https://", "git@", "git://", "ssh://")


def is_git_url(value: str) -> bool:
    """Return True if value looks like a git repository URL rather than a local path."""
    return value.startswith(_GIT_URL_PREFIXES) or value.endswith(".git")


@contextmanager
def fetch_preset_repo(url: str) -> Generator[Path]:
    """
    Shallow-clone a git repository and yield the path to the clone root.

    The temporary directory is removed on exit regardless of success or failure.

    Args:
        url: Git repository URL (https://, git@, git://, or ssh://).

    Yields:
        Path to the root of the cloned repository.

    Raises:
        PresetFetchError: If git is not installed or the clone fails.

    """
    git = shutil.which("git")
    if git is None:
        msg = "git is not installed or not on PATH"
        raise PresetFetchError(url, msg)

    with tempfile.TemporaryDirectory(prefix="gpc-init-presets-") as tmp:
        try:
            subprocess.run(  # noqa: S603
                [git, "clone", "--depth=1", url, tmp],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "unknown error").strip()
            raise PresetFetchError(url, detail) from exc
        yield Path(tmp)
