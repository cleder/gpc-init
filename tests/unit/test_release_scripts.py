"""Tests for the pure helpers of scripts/release.py and scripts/ship.py."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).parents[2] / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _load("release")
ship = _load("ship")


@pytest.mark.parametrize(
    "version", ["v0.9.0", "0.9", "0.9.0.1", "0.9.0rc1", "", "a.b.c"]
)
def test_parse_version_rejects_bad_versions(version: str) -> None:
    with pytest.raises(release.ReleaseError):
        release.parse_version(version)


def test_parse_version_compares_numerically() -> None:
    assert release.parse_version("0.10.0") > release.parse_version("0.9.9")


def test_latest_version_ignores_other_tags() -> None:
    tags = ["0.8.1", "0.10.0", "0.9.5", "v1.0.0", "nightly"]
    assert release.latest_version(tags) == (0, 10, 0)


def test_latest_version_none_without_tags() -> None:
    assert release.latest_version([]) is None


def test_bump_pyproject_changes_only_the_project_version() -> None:
    text = (
        '[project]\nname = "pc-init"\nversion = "0.8.1"\n\n'
        '[tool.x]\nversion_file = "a"\n'
    )
    bumped = release.bump_pyproject(text, "0.9.0")
    assert 'version = "0.9.0"' in bumped
    assert 'version_file = "a"' in bumped
    assert "0.8.1" not in bumped


def test_bump_pyproject_requires_a_version_line() -> None:
    with pytest.raises(release.ReleaseError):
        release.bump_pyproject('[project]\nname = "x"\n', "0.9.0")


def test_real_pyproject_can_be_bumped() -> None:
    text = (SCRIPTS.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "9.9.9"' in release.bump_pyproject(text, "9.9.9")


def test_successful_run_needs_matching_sha_and_success() -> None:
    runs = [
        {"headSha": "aaa", "status": "completed", "conclusion": "failure"},
        {"headSha": "bbb", "status": "completed", "conclusion": "success"},
        {"headSha": "ccc", "status": "in_progress", "conclusion": ""},
    ]
    assert ship.successful_run(runs, "bbb")
    assert not ship.successful_run(runs, "aaa")
    assert not ship.successful_run(runs, "ccc")
    assert not ship.successful_run(runs, "zzz")


def test_ship_out_returns_stdout() -> None:
    assert ship.out("echo", "hello") == "hello"


def test_ship_out_reports_the_command_error() -> None:
    code = "import sys; sys.stderr.write('boom'); sys.exit(1)"
    with pytest.raises(ship.ShipError, match="boom"):
        ship.out(sys.executable, "-c", code)
