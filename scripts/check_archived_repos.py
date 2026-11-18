#!/usr/bin/env python3
"""
Fail if any hook repository referenced by a preset is archived (or gone).

Archived repositories no longer receive fixes or revision bumps, so presets
must not point at them. Scans every ``preset*.yaml`` under lang/ and
framework/, queries the GitHub API once per unique repository and exits
non-zero listing the offenders.

Set GITHUB_TOKEN (or GH_TOKEN) to avoid the anonymous rate limit; CI does.

Usage:
    python scripts/check_archived_repos.py
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
GITHUB_URL = re.compile(r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$")


def collect_repos() -> dict[str, list[Path]]:
    """Map each GitHub ``owner/name`` to the preset files that reference it."""
    repos: dict[str, list[Path]] = defaultdict(list)
    for kind in ("lang", "framework"):
        for preset in sorted((PROJECT_ROOT / kind).glob("*/preset*.yaml")):
            data = yaml.safe_load(preset.read_text()) or {}
            for entry in data.get("repos", []):
                match = GITHUB_URL.match(str(entry.get("repo", "")))
                if match:
                    repos[match.group(1)].append(preset.relative_to(PROJECT_ROOT))
    return repos


def repo_status(slug: str, token: str | None) -> str:
    """Return ``ok``, ``archived``, or ``missing`` (or raise on other errors)."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{slug}",
        headers={"Accept": "application/vnd.github+json"},
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            info = json.load(response)
    except urllib.error.HTTPError as err:
        if err.code in (404, 410):
            return "missing"
        raise
    return "archived" if info.get("archived") else "ok"


def main() -> None:
    """Exit 1 if any referenced hook repository is archived or missing."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repos = collect_repos()
    problems: list[str] = []
    for slug in sorted(repos):
        status = repo_status(slug, token)
        if status != "ok":
            files = ", ".join(str(p) for p in repos[slug])
            problems.append(f"{status.upper():8} {slug}  ({files})")
    print(f"Checked {len(repos)} hook repositories.")  # noqa: T201
    if problems:
        print("\n".join(problems))  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
