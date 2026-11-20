#!/usr/bin/env python3
"""
Merge a tagged release into ``main`` and publish it: ``just ship X.Y.Z``.

Refuses to continue unless the tag exists locally and on the remote, points at
the current ``origin/develop`` and its ``test-build-publish`` run succeeded.
Then it opens (or reuses) the ``develop`` to ``main`` pull request, merges it
with a merge commit, checks that ``main`` has exactly the tagged contents and
fast-forwards ``develop``. The push to ``main`` makes CI publish to PyPI.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
WORKFLOW = "test-build-publish.yml"


class ShipError(Exception):
    """A shipping precondition is not met."""


def successful_run(runs: list[dict[str, str]], sha: str) -> bool:
    """Return True if a completed, successful run exists for commit ``sha``."""
    return any(
        run.get("headSha") == sha
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        for run in runs
    )


def out(*args: str) -> str:
    """Run a command in the repository root and return its output."""
    result = subprocess.run(  # noqa: S603
        args,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        msg = f"{' '.join(args[:3])}: {detail}"
        raise ShipError(msg)
    return result.stdout.strip()


def run(*args: str) -> None:
    """Run a command in the repository root, showing its output."""
    subprocess.run(args, cwd=ROOT, check=True)  # noqa: S603


def check_tag(version: str) -> None:
    """Raise ShipError unless the tag is pushed, on develop and green in CI."""
    run("git", "fetch", "origin", "--tags", "--quiet")
    if not out("git", "tag", "--list", version):
        msg = f"tag {version} does not exist locally"
        raise ShipError(msg)
    if not out("git", "ls-remote", "--tags", "origin", f"refs/tags/{version}"):
        msg = f"tag {version} is not pushed to origin"
        raise ShipError(msg)
    sha = out("git", "rev-parse", f"{version}^{{commit}}")
    if sha != out("git", "rev-parse", "origin/develop"):
        msg = f"tag {version} does not point at origin/develop"
        raise ShipError(msg)
    runs = json.loads(
        out(
            "gh",
            "run",
            "list",
            "--workflow",
            WORKFLOW,
            "--branch",
            version,
            "--json",
            "headSha,status,conclusion",
            "--limit",
            "10",
        ),
    )
    if not successful_run(runs, sha):
        msg = f"no successful {WORKFLOW} run for tag {version} yet"
        raise ShipError(msg)


def open_pull_request(version: str) -> str:
    """Return the number of the develop to main pull request, creating it if needed."""
    numbers = out(
        "gh",
        "pr",
        "list",
        "--head",
        "develop",
        "--base",
        "main",
        "--json",
        "number",
        "--jq",
        ".[].number",
    ).split()
    if numbers:
        return numbers[0]
    notes = out(
        sys.executable, str(ROOT / "scripts" / "changelog_section.py"), "notes", version
    )
    url = out(
        "gh",
        "pr",
        "create",
        "--base",
        "main",
        "--head",
        "develop",
        "--title",
        f"Release {version}",
        "--body",
        notes,
    )
    return url.rstrip("/").rsplit("/", 1)[-1]


def main(argv: list[str]) -> int:
    """Merge the release and publish."""
    if len(argv) != 1:
        sys.stderr.write("usage: ship.py X.Y.Z\n")
        return 2
    version = argv[0]
    try:
        check_tag(version)
        number = open_pull_request(version)
        answer = input(
            f"Merge PR #{number} into main and publish {version} to PyPI?\n"
            "Type the version to confirm: "
        )
        if answer.strip() != version:
            sys.stderr.write("ship: aborted\n")
            return 1
        run("gh", "pr", "merge", number, "--merge")
        run("git", "fetch", "origin", "--quiet")
        if subprocess.run(  # noqa: S603
            ["git", "diff", "--quiet", version, "origin/main"],  # noqa: S607
            cwd=ROOT,
            check=False,
        ).returncode:
            sys.stderr.write(
                f"ship: merged, but origin/main differs from tag {version}; "
                "stop the publish run in GitHub Actions and investigate\n",
            )
            return 1
        run("git", "switch", "develop")
        run("git", "merge", "--ff-only", "origin/main")
    except ShipError as error:
        sys.stderr.write(f"ship: {error}\n")
        return 1
    except subprocess.CalledProcessError as error:
        sys.stderr.write(f"ship: command failed: {' '.join(map(str, error.cmd))}\n")
        return 1
    sys.stdout.write("Merged. Watch the publish run: gh run watch\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
