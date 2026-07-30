#!/usr/bin/env python3
"""
Validate the bundled lang/framework metadata catalog.

Checks that every lang/<id>/ and framework/<id>/ directory in this repo's
bundled catalog has a metadata.yaml file (required for the bundled catalog,
even though gpc_init.catalog.load_catalog tolerates a missing one for
third-party --presets catalogs), and that the catalog as a whole loads
without conflicting extensions/filenames/aliases.

Usage:
    python scripts/validate_metadata.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
# gpc-init isn't installed into the dev venv (not packaged for editable install),
# so make the repo root importable when this script is run standalone.
sys.path.insert(0, str(PROJECT_ROOT))

from gpc_init.catalog import load_catalog  # noqa: E402
from gpc_init.exceptions import MetadataConflictError, PresetParseError  # noqa: E402


def _dirs_with_preset(
    kind_dir: Path, *, exclude: frozenset[str] = frozenset()
) -> list[Path]:
    if not kind_dir.is_dir():
        return []
    return sorted(
        d
        for d in kind_dir.iterdir()
        if d.is_dir() and d.name not in exclude and (d / "preset.yaml").exists()
    )


def main() -> None:
    """Fail with a clear message if metadata.yaml is missing or invalid."""
    missing = [
        d
        for d in [
            *_dirs_with_preset(PROJECT_ROOT / "lang", exclude=frozenset({"common"})),
            *_dirs_with_preset(PROJECT_ROOT / "framework"),
        ]
        if not (d / "metadata.yaml").exists()
    ]
    if missing:
        for d in missing:
            print(f"Missing metadata.yaml: {d}", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    try:
        load_catalog(PROJECT_ROOT)
    except (MetadataConflictError, PresetParseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    print("Catalog OK: every lang/framework has metadata.yaml, no conflicts.")  # noqa: T201


if __name__ == "__main__":
    main()
