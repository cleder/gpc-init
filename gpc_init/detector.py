"""Detect languages and frameworks present in a repository."""

import json
from collections.abc import Callable, Generator
from pathlib import Path

from gpc_init.resolver import deduplicate_preserving_order

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".tox",
        "dist",
        "build",
        ".eggs",
    }
)

_EXTENSION_TO_LANG: dict[str, str] = {
    ".py": "py",
    ".pyi": "py",
    ".js": "js",
    ".mjs": "js",
    ".cjs": "js",
    ".jsx": "js",
    ".ts": "ts",
    ".tsx": "ts",
    ".go": "go",
    ".rs": "ru",
    ".sh": "sh",
    ".bash": "sh",
    ".sql": "sql",
    ".tf": "tf",
    ".tfvars": "tf",
    ".md": "md",
    ".markdown": "md",
    ".ipynb": "nb",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".r": "r",
    ".png": "img",
    ".jpg": "img",
    ".jpeg": "img",
    ".gif": "img",
    ".webp": "img",
    ".svg": "img",
}

# Matched case-insensitively against the file stem (no extension).
_FILENAME_TO_LANG: dict[str, str] = {
    "dockerfile": "docker",
}


def _walk(repo_dir: Path) -> Generator[Path]:
    """Yield all files under repo_dir, skipping directories in _SKIP_DIRS."""
    for entry in repo_dir.iterdir():
        if entry.is_dir():
            if entry.name not in _SKIP_DIRS:
                yield from _walk(entry)
        else:
            yield entry


def detect_languages(repo_dir: Path, supported_langs: list[str]) -> list[str]:
    """
    Return detected language IDs for the given repository directory.

    Walks the directory tree (skipping common non-source dirs), maps file
    extensions and well-known filenames to language IDs, and filters the
    result to only IDs present in supported_langs.
    """
    supported = set(supported_langs)
    seen: list[str] = []
    for file in _walk(repo_dir):
        lang = _FILENAME_TO_LANG.get(file.stem.lower())
        if lang is None:
            lang = _EXTENSION_TO_LANG.get(file.suffix.lower())
        if lang and lang in supported:
            seen.append(lang)
    return deduplicate_preserving_order(seen)


def _has_package_json_dep(repo_dir: Path, dep: str) -> bool:
    pkg = repo_dir / "package.json"
    if not pkg.is_file():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    deps = {*data.get("dependencies", {}), *data.get("devDependencies", {})}
    return dep in deps


def _has_sphinx_conf(repo_dir: Path) -> bool:
    for candidate in [repo_dir / "conf.py", repo_dir / "docs" / "conf.py"]:
        if candidate.is_file() and "sphinx" in candidate.read_text(
            encoding="utf-8", errors="ignore"
        ):
            return True
    return False


def _has_kubernetes_files(repo_dir: Path) -> bool:
    github_dir = repo_dir / ".github"
    for file in _walk(repo_dir):
        if file.suffix.lower() not in {".yaml", ".yml"}:
            continue
        # Skip GitHub Actions workflows — signalled by the git framework instead.
        try:
            if file.is_relative_to(github_dir):
                continue
        except ValueError:
            pass
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "apiVersion:" in text and "kind:" in text:
            return True
    return False


def _has_github_workflows(repo_dir: Path) -> bool:
    workflows = repo_dir / ".github" / "workflows"
    if not workflows.is_dir():
        return False
    return any(
        f.suffix.lower() in {".yaml", ".yml"}
        for f in workflows.iterdir()
        if f.is_file()
    )


# Ordered list of (framework_id, detector) pairs.
_FRAMEWORK_DETECTORS: list[tuple[str, Callable[[Path], bool]]] = [
    ("django", lambda d: (d / "manage.py").is_file()),
    ("react", lambda d: _has_package_json_dep(d, "react")),
    ("sphinx", _has_sphinx_conf),
    ("k8s", _has_kubernetes_files),
    ("git", _has_github_workflows),
]


def detect_frameworks(repo_dir: Path, supported_frameworks: list[str]) -> list[str]:
    """
    Return detected framework IDs for the given repository directory.

    Checks each known framework against its indicator files/directories and
    filters to only IDs present in supported_frameworks.
    """
    supported = set(supported_frameworks)
    detected: list[str] = []
    for fw_id, detector in _FRAMEWORK_DETECTORS:
        if fw_id in supported and detector(repo_dir):
            detected.append(fw_id)
    return detected
