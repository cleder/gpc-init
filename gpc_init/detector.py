"""Detect languages and frameworks present in a repository."""

import fnmatch
import json
from collections.abc import Callable, Generator
from pathlib import Path

from gpc_init.catalog import load_catalog
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


def _walk(repo_dir: Path) -> Generator[Path]:
    """Yield all files under repo_dir, skipping directories in _SKIP_DIRS."""
    for root, dirs, files in repo_dir.walk(on_error=lambda _: None):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        yield from (root / f for f in files)


def _is_dotenv_file(name: str) -> bool:
    """Match .env, .env.local, .env.production, etc. (no fixed extension)."""
    lname = name.lower()
    return lname == ".env" or lname.startswith(".env.")


def detect_languages(
    repo_dir: Path,
    supported_langs: list[str],
    base_dir: Path | None = None,
) -> list[str]:
    """
    Return detected language IDs for the given repository directory.

    Walks the directory tree (skipping common non-source dirs), maps file
    extensions and well-known filenames — read from each lang's metadata.yaml —
    to language IDs, and filters the result to only IDs present in
    supported_langs.

    Args:
        repo_dir: Directory to scan.
        supported_langs: Language IDs to filter detection results to.
        base_dir: Override base directory for the metadata catalog (used in
            tests / custom --presets catalogs).

    """
    catalog = load_catalog(base_dir)
    supported = set(supported_langs)
    seen: list[str] = []
    for file in _walk(repo_dir):
        lang = catalog.filename_to_lang.get(file.stem.lower())
        if lang is None:
            lang = catalog.extension_to_lang.get(file.suffix.lower())
        if lang is None and _is_dotenv_file(file.name):
            lang = "env"
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
    if not isinstance(data, dict):
        return False
    deps = {*(data.get("dependencies") or {}), *(data.get("devDependencies") or {})}
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
    try:
        return any(
            f.suffix.lower() in {".yaml", ".yml"}
            for f in workflows.iterdir()
            if f.is_file()
        )
    except OSError:
        return False


# Fixed allowlist for the `python:<name>` escape hatch in framework metadata.yaml
# `detect` rules. Deliberately NOT a dotted import path: a custom --presets
# catalog (which may point at an arbitrary git URL) must only be able to
# reference gpc-init's own built-in detectors, never inject new code.
_DETECTOR_REGISTRY: dict[str, Callable[[Path], bool]] = {
    "_has_sphinx_conf": _has_sphinx_conf,
    "_has_kubernetes_files": _has_kubernetes_files,
    "_has_github_workflows": _has_github_workflows,
}


def _rule_file_exists(repo_dir: Path, path: str) -> bool:
    return (repo_dir / path).is_file()


def _rule_dir_exists(repo_dir: Path, path: str) -> bool:
    return (repo_dir / path).is_dir()


def _rule_glob(repo_dir: Path, pattern: str) -> bool:
    return any(fnmatch.fnmatchcase(f.name, pattern) for f in _walk(repo_dir))


def _rule_package_json_dep(repo_dir: Path, dep: str) -> bool:
    return _has_package_json_dep(repo_dir, dep)


# Declarative detect-rule handlers, keyed by the rule's single dict key
# (e.g. {"file_exists": "manage.py"}).
_RULE_HANDLERS: dict[str, Callable[[Path, str], bool]] = {
    "file_exists": _rule_file_exists,
    "dir_exists": _rule_dir_exists,
    "glob": _rule_glob,
    "package_json_dep": _rule_package_json_dep,
}


def _evaluate_detect_rule(repo_dir: Path, rule: object) -> bool:
    """Evaluate a single `detect:` rule (declarative dict or `python:<name>`)."""
    if isinstance(rule, str):
        name = rule.removeprefix("python:")
        handler = _DETECTOR_REGISTRY.get(name)
        if handler is None:
            msg = f"Unknown escape-hatch detector 'python:{name}'"
            raise ValueError(msg)
        return handler(repo_dir)
    if isinstance(rule, dict):
        if len(rule) != 1:
            msg = f"detect rule must have exactly one key: {rule!r}"
            raise ValueError(msg)
        ((rule_type, arg),) = rule.items()
        rule_handler = _RULE_HANDLERS.get(rule_type)
        if rule_handler is None:
            msg = f"Unknown detect rule type '{rule_type}'"
            raise ValueError(msg)
        return rule_handler(repo_dir, str(arg))
    msg = f"Invalid detect rule: {rule!r}"
    raise TypeError(msg)


def detect_frameworks(
    repo_dir: Path,
    supported_frameworks: list[str],
    base_dir: Path | None = None,
) -> list[str]:
    """
    Return detected framework IDs for the given repository directory.

    Checks each known framework against the detect rules declared in its
    metadata.yaml and filters to only IDs present in supported_frameworks.

    Args:
        repo_dir: Directory to scan.
        supported_frameworks: Framework IDs to filter detection results to.
        base_dir: Override base directory for the metadata catalog (used in
            tests / custom --presets catalogs).

    """
    catalog = load_catalog(base_dir)
    supported = set(supported_frameworks)
    detected: list[str] = []
    for fw_id in sorted(catalog.frameworks):
        if fw_id not in supported:
            continue
        meta = catalog.frameworks[fw_id]
        if any(_evaluate_detect_rule(repo_dir, rule) for rule in meta.detect):
            detected.append(fw_id)
    return detected
