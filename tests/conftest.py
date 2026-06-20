"""Pytest fixtures shared across the test suite."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the tests/fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_preset_dir(tmp_path: Path, fixtures_dir: Path) -> Path:
    """Create a temp directory with the fixture presets for isolated testing."""
    import shutil

    shutil.copytree(fixtures_dir / "lang", tmp_path / "lang")
    shutil.copytree(fixtures_dir / "framework", tmp_path / "framework")
    return tmp_path
