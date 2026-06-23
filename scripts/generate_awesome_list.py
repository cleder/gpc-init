#!/usr/bin/env python3
"""
Generate an AWESOME.md skeleton from pc-init preset files.

Usage:
    python scripts/generate_awesome_list.py [--output AWESOME.md]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
LANG_DIR = PROJECT_ROOT / "lang"
FRAMEWORK_DIR = PROJECT_ROOT / "framework"


def load_preset(path: Path) -> dict:
    """Load and parse a preset YAML file, returning an empty dict if missing."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def discover_sorted(base: Path, exclude: frozenset[str] = frozenset()) -> list[str]:
    """Return sorted names of subdirectories that contain a preset.yaml."""
    return sorted(
        d.name
        for d in base.iterdir()
        if d.is_dir() and d.name not in exclude and (d / "preset.yaml").exists()
    )


_GH = shutil.which("gh")
_description_cache: dict[str, str] = {}


def gh_description(owner_repo: str) -> str:
    """Fetch the GitHub repository description via the gh CLI, with caching."""
    if owner_repo in _description_cache:
        return _description_cache[owner_repo]
    if not _GH:
        _description_cache[owner_repo] = ""
        return ""
    try:
        result = subprocess.run(  # noqa: S603
            [
                _GH,
                "repo",
                "view",
                owner_repo,
                "--json",
                "description",
                "--jq",
                ".description",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            desc = result.stdout.strip()
        else:
            print(  # noqa: T201
                f"Warning: could not fetch description for {owner_repo}",
                file=sys.stderr,
            )
            desc = ""
    except (subprocess.TimeoutExpired, OSError):
        print(  # noqa: T201
            f"Warning: gh timed out or failed for {owner_repo}",
            file=sys.stderr,
        )
        desc = ""
    _description_cache[owner_repo] = desc
    return desc


def repo_link(repo_url: str) -> tuple[str, str]:
    """Return (markdown link text, description) for a repo URL."""
    if repo_url in ("meta", "local"):
        return f"**{repo_url}**", ""
    parts = repo_url.rstrip("/").split("/")
    owner_repo = "/".join(parts[-2:])
    repo_name = parts[-1]
    desc = gh_description(owner_repo)
    return f"[{repo_name}]({repo_url})", desc


def render_repos(repos: list[dict]) -> list[str]:
    """Render a deduplicated, sorted list of repo bullet points."""
    seen: set[str] = set()
    entries: list[tuple[str, str, str]] = []  # (sort_key, link, desc)
    for repo in repos:
        url = repo["repo"]
        if url not in seen and repo.get("hooks"):
            seen.add(url)
            link, desc = repo_link(url)
            sort_key = url.rstrip("/").split("/")[-1].lower()
            entries.append((sort_key, link, desc))
    return [
        f"- {link}" + (f" — {desc}" if desc else "")
        for _, link, desc in sorted(entries)
    ]


def render_section(title: str, preset: dict, note: str = "") -> list[str]:
    """Render a language or framework section with an optional note."""
    repos = preset.get("repos", [])
    repo_lines = render_repos(repos)
    lines = [f"### {title}", ""]
    if note:
        lines += [f"> {note}", ""]
    lines += repo_lines or ["_No hooks defined yet._"]
    lines.append("")
    return lines


def toc_anchor(name: str) -> str:
    """Convert a section title to a GitHub markdown anchor."""
    return name.lower().replace(" ", "-")


def build_awesome_list(languages: list[str], frameworks: list[str]) -> str:
    """Build the full AWESOME.md content string."""
    common = load_preset(LANG_DIR / "common" / "preset.yaml")

    toc = [
        "## Contents",
        "",
        "- [Common](#common)",
        "- [Languages](#languages)",
    ]
    toc.extend(f"  - [{lang}](#{toc_anchor(lang)})" for lang in languages)
    toc += ["- [Frameworks](#frameworks)"]
    toc.extend(f"  - [{fw}](#{toc_anchor(fw)})" for fw in frameworks)

    header = [
        "# Awesome Pre-commit Hooks",
        "",
        "A curated collection of [pre-commit](https://pre-commit.com) and "
        "[prek](https://github.com/j178/prek/) hooks, "
        "organized by language and framework.",
        "",
        "_Auto-generated from [gpc-init](https://github.com/cleder/gpc-init) presets"
        " — to add or update a hook, open a PR there rather than editing this file"
        " directly._",
        "",
    ]

    sections: list[str] = []

    sections += [
        "---",
        "",
        "## Common",
        "",
        "> Applied to every generated configuration, "
        "regardless of language or framework.",
        "",
    ]
    sections.extend(render_repos(common.get("repos", [])))
    sections.append("")

    sections += ["---", "", "## Languages", ""]
    for lang in languages:
        preset = load_preset(LANG_DIR / lang / "preset.yaml")
        sections.extend(render_section(lang, preset))

    sections += ["---", "", "## Frameworks", ""]
    for fw in frameworks:
        preset = load_preset(FRAMEWORK_DIR / fw / "preset.yaml")
        primary = preset.get("primary_languages", [])
        note = f"Primary language(s): {', '.join(primary)}." if primary else ""
        sections.extend(render_section(fw, preset, note=note))

    all_lines = header + toc + [""] + sections
    return "\n".join(all_lines) + "\n"


def main() -> None:
    """Entry point: parse arguments, generate, and write AWESOME.md."""
    parser = argparse.ArgumentParser(
        description="Generate AWESOME.md skeleton from pc-init presets",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "AWESOME.md"),
        help="Output file path (default: AWESOME.md at project root)",
    )
    args = parser.parse_args()

    languages = discover_sorted(LANG_DIR, exclude=frozenset({"common"}))
    frameworks = discover_sorted(FRAMEWORK_DIR)

    content = build_awesome_list(languages, frameworks)

    output = Path(args.output)
    output.write_text(content, encoding="utf-8")
    print(f"Generated {output} ({output.stat().st_size} bytes)")  # noqa: T201
    print(f"  Languages: {', '.join(languages)}")  # noqa: T201
    print(f"  Frameworks: {', '.join(frameworks)}")  # noqa: T201


if __name__ == "__main__":
    main()
