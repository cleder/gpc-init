#!/usr/bin/env python3
"""
Prepare a release on ``develop``: ``just release X.Y.Z``.

Refuses to run unless you are on ``develop`` with a clean tree and X.Y.Z is
higher than the latest tag. Then it upgrades dependencies and hook revisions
(``just prepare-release``), bumps ``pyproject.toml`` and ``uv.lock``, promotes
the changelog, makes one ``Release X.Y.Z`` commit and tags it.

It never pushes. Review ``git show``, then push ``develop`` and the tag; the
tag run in CI checks the release and uploads to TestPyPI. Afterwards
``just ship X.Y.Z`` merges to ``main``.
"""

import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PROJECT_VERSION = re.compile(r'^version = "[^"]+"$', re.MULTILINE)


class ReleaseError(Exception):
    """A release precondition is not met."""


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse ``X.Y.Z`` (no ``v`` prefix) into a comparable tuple."""
    match = VERSION.match(version)
    if match is None:
        msg = f"'{version}' is not a version of the form X.Y.Z (no 'v' prefix)"
        raise ReleaseError(msg)
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def latest_version(tags: Iterable[str]) -> tuple[int, int, int] | None:
    """Return the highest ``X.Y.Z`` tag, ignoring tags of any other form."""
    versions = [parse_version(tag) for tag in tags if VERSION.match(tag)]
    return max(versions, default=None)


def bump_pyproject(text: str, version: str) -> str:
    """Set the project version in the text of ``pyproject.toml``."""
    bumped, count = PROJECT_VERSION.subn(f'version = "{version}"', text, count=1)
    if count == 0:
        msg = "no 'version = \"...\"' line found in pyproject.toml"
        raise ReleaseError(msg)
    return bumped


def git(*args: str) -> str:
    """Run git in the repository root and return its output."""
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def run(*args: str) -> None:
    """Run a command in the repository root, showing its output."""
    subprocess.run(args, cwd=ROOT, check=True)  # noqa: S603


def check_preconditions(version: str) -> None:
    """Raise ReleaseError unless a release of ``version`` can be started."""
    wanted = parse_version(version)
    if git("branch", "--show-current") != "develop":
        msg = "release from the 'develop' branch"
        raise ReleaseError(msg)
    if git("status", "--porcelain", "--untracked-files=no"):
        msg = "the working tree has uncommitted changes to tracked files"
        raise ReleaseError(msg)
    unreleased = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "changelog_section.py"), "unreleased"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if unreleased.returncode:
        raise ReleaseError(unreleased.stderr.strip() or "the changelog is not ready")
    latest = latest_version(git("tag", "--list").splitlines())
    if latest is not None and wanted <= latest:
        msg = (
            f"{version} is not higher than the latest tag {'.'.join(map(str, latest))}"
        )
        raise ReleaseError(msg)


def main(argv: list[str]) -> int:
    """Prepare the release commit and tag."""
    if len(argv) != 1:
        sys.stderr.write("usage: release.py X.Y.Z\n")
        return 2
    version = argv[0]
    changelog = ROOT / "scripts" / "changelog_section.py"
    pyproject = ROOT / "pyproject.toml"
    try:
        check_preconditions(version)
        run("just", "prepare-release")
        pyproject.write_text(
            bump_pyproject(pyproject.read_text(encoding="utf-8"), version),
            encoding="utf-8",
        )
        run("uv", "lock")
        run(sys.executable, str(changelog), "promote", version)
        run(sys.executable, str(changelog), "check", version)
        run("git", "add", "-u")
        run("git", "commit", "-m", f"Release {version}")
        run("git", "tag", "-a", version, "-m", f"Release {version}")
    except ReleaseError as error:
        sys.stderr.write(f"release: {error}\n")
        return 1
    sys.stdout.write(
        f"\nTagged {version}. Review with `git show --stat`, then:\n"
        f"  git push origin develop {version}\n"
        f"and, once the tag run is green: just ship {version}\n",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
