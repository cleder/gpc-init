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
Transient failures (408, 429, 5xx, rate-limited 403s, network errors) are
retried, waiting as long as the server asks (Retry-After / rate-limit reset,
capped) and otherwise backing off. If a repository still cannot be checked the
script exits 2 with a one-line reason, so an infrastructure problem is
distinguishable from an offending preset (1).

Usage:
    python scripts/check_archived_repos.py
"""

import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from http import HTTPStatus
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
PSEUDO_REPOS = frozenset({"local", "meta"})
GITHUB_URL = re.compile(r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$")
RETRY_CODES = frozenset({408, 429})  # plus every 5xx
MAX_ATTEMPTS = 3
RETRY_DELAY = 2.0
MAX_RETRY_WAIT = 60.0  # longer server-requested waits fail instead of stalling CI


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


def _read_info(slug: str, response: Any) -> dict[str, Any]:  # noqa: ANN401
    """Parse a GitHub API response body; anything but a JSON object is invalid."""
    try:
        info = json.load(response)
    except ValueError as exc:
        msg = f"could not check {slug}: invalid response"
        raise RepoCheckError(msg) from exc
    if not isinstance(info, dict):
        msg = f"could not check {slug}: invalid response"
        raise RepoCheckError(msg)
    return info


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
            return _read_info(slug, response)
    except urllib.error.HTTPError as err:
        if err.code in (404, 410):
            return None
        raise


def _server_wait(err: urllib.error.HTTPError) -> float | None:
    """Return the seconds the server asks us to wait (Retry-After / reset), if any."""
    retry_after = err.headers.get("Retry-After", "")
    if retry_after.strip().isdigit():
        return float(retry_after)
    reset = err.headers.get("X-RateLimit-Reset", "")
    if err.headers.get("X-RateLimit-Remaining") == "0" and reset.isdigit():
        return max(0.0, float(reset) - time.time())
    return None


def _is_transient(err: urllib.error.HTTPError) -> bool:
    """Whether an HTTP error is worth retrying (a 403 only if rate limited)."""
    if err.code in RETRY_CODES or err.code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return True
    return err.code == HTTPStatus.FORBIDDEN and _server_wait(err) is not None


def _failure(
    err: OSError | http.client.HTTPException,
) -> tuple[str, bool, float | None]:
    """Return (reason, worth retrying, server-requested wait in seconds)."""
    if isinstance(err, urllib.error.HTTPError):
        reason = f"HTTP {err.code}"
        if err.code in (403, 429):
            reason += " (rate limited? set GITHUB_TOKEN)"
        return reason, _is_transient(err), _server_wait(err)
    reason = str(getattr(err, "reason", None) or err) or type(err).__name__
    return reason, True, None


def _exceeds_cap(wait: float | None) -> bool:
    """Whether a server-requested wait is too long to sit through."""
    return wait is not None and wait > MAX_RETRY_WAIT


def _wait_or_fail(
    slug: str, attempt: int, err: OSError | http.client.HTTPException
) -> None:
    """Sleep before the next attempt, or raise RepoCheckError if retrying is futile."""
    reason, retryable, wait = _failure(err)
    if retryable and _exceeds_cap(wait):
        msg = f"could not check {slug}: {reason}, retry after {wait:.0f}s"
        raise RepoCheckError(msg) from err
    if not retryable or attempt == MAX_ATTEMPTS:
        msg = f"could not check {slug}: {reason}"
        raise RepoCheckError(msg) from err
    time.sleep(wait if wait is not None else RETRY_DELAY * 2 ** (attempt - 1))


def repo_status(slug: str, token: str | None) -> str:
    """
    Return ``ok``, ``archived`` or ``missing``.

    Transient failures are retried; raises RepoCheckError if the repository
    still cannot be checked.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            info = _fetch_info(slug, token)
        except (OSError, http.client.HTTPException) as err:
            _wait_or_fail(slug, attempt, err)
            continue
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
