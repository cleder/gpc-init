#!/usr/bin/env python3
"""
Fail if a preset references an insecure, archived or missing hook repository.

Every ``repo:`` in a preset must be an ``https://`` URL (the pre-commit
pseudo-repositories ``local`` and ``meta`` are exempt); ssh, ``git://`` and
``http://`` URLs are rejected, which also stops them slipping past the
archived check below.

Archived repositories no longer receive fixes or revision bumps, so presets
must not point at them. Scans every ``preset*.yaml`` under lang/ and
framework/, queries the GitHub API once per unique repository and exits
non-zero listing the offenders.

Set GITHUB_TOKEN (or GH_TOKEN) to avoid the anonymous rate limit; CI does.
Transient failures (429, 5xx, network errors) are retried with backoff. If a
repository still cannot be checked the script exits 2 with a one-line reason,
so an infrastructure problem is distinguishable from an offending preset (1).

Usage:
    python scripts/check_archived_repos.py
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
PSEUDO_REPOS = frozenset({"local", "meta"})
GITHUB_URL = re.compile(r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$")
RETRY_CODES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
RETRY_DELAY = 2.0


class RepoCheckError(Exception):
    """The status of a repository could not be determined."""


def preset_urls(preset: Path) -> list[str]:
    """Return every ``repo:`` value of one preset file."""
    data: dict[str, Any] = yaml.safe_load(preset.read_text()) or {}
    return [str(entry.get("repo", "")) for entry in data.get("repos", [])]


def insecure_urls(urls: list[str]) -> list[str]:
    """Return the repo URLs that are neither a pseudo-repo nor ``https://``."""
    return [
        url
        for url in urls
        if url not in PSEUDO_REPOS and not url.startswith("https://")
    ]


def preset_slugs(preset: Path) -> list[str]:
    """Return the GitHub ``owner/name`` slugs referenced by one preset file."""
    matches = (GITHUB_URL.match(url) for url in preset_urls(preset))
    return [match.group(1) for match in matches if match]


def collect_insecure() -> list[str]:
    """List ``preset: url`` for every non-https hook repository in the catalog."""
    found: list[str] = []
    for kind in ("lang", "framework"):
        for preset in sorted((PROJECT_ROOT / kind).glob("*/preset*.yaml")):
            rel = preset.relative_to(PROJECT_ROOT)
            found.extend(f"{rel}: {url}" for url in insecure_urls(preset_urls(preset)))
    return found


def collect_repos() -> dict[str, list[Path]]:
    """Map each GitHub ``owner/name`` to the preset files that reference it."""
    repos: dict[str, list[Path]] = defaultdict(list)
    for kind in ("lang", "framework"):
        for preset in sorted((PROJECT_ROOT / kind).glob("*/preset*.yaml")):
            for slug in preset_slugs(preset):
                repos[slug].append(preset.relative_to(PROJECT_ROOT))
    return repos


def _fetch_info(slug: str, token: str | None) -> dict[str, Any] | None:
    """Query the GitHub API once; return None if the repo is missing (404/410)."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{slug}",
        headers={"Accept": "application/vnd.github+json"},
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            info: dict[str, Any] = json.load(response)
    except urllib.error.HTTPError as err:
        if err.code in (404, 410):
            return None
        raise
    return info


def _failure_reason(err: urllib.error.URLError | TimeoutError) -> tuple[str, bool]:
    """Return a short reason and whether the failure is worth retrying."""
    if isinstance(err, urllib.error.HTTPError):
        reason = f"HTTP {err.code}"
        if err.code in (403, 429):
            reason += " (rate limited? set GITHUB_TOKEN)"
        return reason, err.code in RETRY_CODES
    return str(getattr(err, "reason", err) or type(err).__name__), True


def repo_status(slug: str, token: str | None) -> str:
    """
    Return ``ok``, ``archived`` or ``missing``.

    Transient failures are retried; raises RepoCheckError if the repository
    still cannot be checked.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            info = _fetch_info(slug, token)
        except (urllib.error.URLError, TimeoutError) as err:
            reason, retryable = _failure_reason(err)
            if not retryable or attempt == MAX_ATTEMPTS:
                msg = f"could not check {slug}: {reason}"
                raise RepoCheckError(msg) from err
            time.sleep(RETRY_DELAY * 2 ** (attempt - 1))
        else:
            if info is None:
                return "missing"
            return "archived" if info.get("archived") else "ok"
    msg = f"could not check {slug}"  # pragma: no cover
    raise RepoCheckError(msg)  # pragma: no cover


def main() -> None:
    """Exit 1 if a hook repository is archived or missing, 2 if a check fails."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repos = collect_repos()
    problems = [f"NOT HTTPS {entry}" for entry in collect_insecure()]
    for slug in sorted(repos):
        try:
            status = repo_status(slug, token)
        except RepoCheckError as err:
            print(f"Error: {err}", file=sys.stderr)  # noqa: T201
            sys.exit(2)
        if status != "ok":
            files = ", ".join(str(p) for p in repos[slug])
            problems.append(f"{status.upper():8} {slug}  ({files})")
    print(f"Checked {len(repos)} hook repositories.")  # noqa: T201
    if problems:
        print("\n".join(problems))  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
