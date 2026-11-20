#!/usr/bin/env python3
"""
Validate, extract and promote sections of CHANGELOG.md.

One script serves the whole release so the check and the release notes cannot
disagree:

    changelog_section.py check VERSION      fail unless VERSION has a non-empty
                                            section and [Unreleased] is empty
    changelog_section.py notes VERSION      print the VERSION section (release notes)
    changelog_section.py promote VERSION    move the [Unreleased] entries under a
                                            new VERSION heading

``check`` runs in the tag workflow, ``notes`` feeds ``gh release create`` and
``promote`` is used by ``just release``. Exits 0 on success, 1 on a changelog
problem.
"""

import argparse
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).parent.parent / "CHANGELOG.md"
HEADING = re.compile(r"^## \[(?P<name>[^\]]+)\]", re.MULTILINE)
ENTRY = re.compile(r"^\s*[-*] ", re.MULTILINE)
UNRELEASED = "Unreleased"


class ChangelogError(Exception):
    """The changelog does not satisfy the release rules."""


def section(text: str, name: str) -> str | None:
    """Return the body of the ``## [name]`` section, or None if it is absent."""
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        if match["name"] == name:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            return text[match.end() : end].strip()
    return None


def has_entries(body: str) -> bool:
    """Return True if a section body contains at least one list entry."""
    return ENTRY.search(body) is not None


def problems(text: str, version: str) -> list[str]:
    """Return every reason why ``version`` cannot be released from this changelog."""
    found: list[str] = []
    body = section(text, version)
    if body is None:
        found.append(f"no '## [{version}]' section")
    elif not has_entries(body):
        found.append(f"the '## [{version}]' section has no entries")
    unreleased = section(text, UNRELEASED)
    if unreleased is None:
        found.append(f"no '## [{UNRELEASED}]' section")
    elif has_entries(unreleased):
        found.append(
            f"'## [{UNRELEASED}]' still has entries; move them under {version}"
        )
    return found


def promote(text: str, version: str) -> str:
    """Move the [Unreleased] entries under a new ``## [version]`` heading."""
    unreleased = section(text, UNRELEASED)
    if unreleased is None or not has_entries(unreleased):
        msg = f"'## [{UNRELEASED}]' has no entries to release"
        raise ChangelogError(msg)
    if section(text, version) is not None:
        msg = f"'## [{version}]' already exists"
        raise ChangelogError(msg)
    heading = f"## [{UNRELEASED}]"
    return text.replace(heading, f"{heading}\n\n## [{version}]", 1)


def notes(text: str, version: str) -> str:
    """Return the release notes for ``version``."""
    body = section(text, version)
    if body is None or not has_entries(body):
        msg = f"no release notes for {version}"
        raise ChangelogError(msg)
    return f"{body}\n"


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["check", "notes", "promote"])
    parser.add_argument("version")
    parser.add_argument("--file", type=Path, default=CHANGELOG)
    args = parser.parse_args(argv)
    text = args.file.read_text(encoding="utf-8")
    try:
        if args.command == "check":
            found = problems(text, args.version)
            if found:
                sys.stderr.write(
                    "\n".join(f"changelog: {item}" for item in found) + "\n"
                )
                return 1
        elif args.command == "notes":
            sys.stdout.write(notes(text, args.version))
        else:
            args.file.write_text(promote(text, args.version), encoding="utf-8")
    except ChangelogError as error:
        sys.stderr.write(f"changelog: {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
