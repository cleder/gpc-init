"""Tests for scripts/changelog_section.py."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "changelog_section.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("changelog_section", SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cs = _load()

UNRELEASED_ONLY = """# Changelog

## [Unreleased]

### Enhancements

- Add a thing.

## [0.8.1]

### Bug Fixes

- Fix a thing.
"""

RELEASED = """# Changelog

## [Unreleased]

## [0.9.0]

### Enhancements

- Add a thing.

## [0.8.1]

- Fix a thing.
"""


def test_section_returns_body_up_to_next_heading() -> None:
    assert cs.section(UNRELEASED_ONLY, "0.8.1") == "### Bug Fixes\n\n- Fix a thing."


def test_section_is_none_when_absent() -> None:
    assert cs.section(UNRELEASED_ONLY, "9.9.9") is None


def test_section_is_not_confused_by_version_prefixes() -> None:
    assert cs.section(RELEASED, "0.9") is None


def test_has_entries() -> None:
    assert cs.has_entries("### X\n\n- item")
    assert cs.has_entries("  * item")
    assert not cs.has_entries("### Enhancements\n\n")


def test_problems_empty_when_released_correctly() -> None:
    assert cs.problems(RELEASED, "0.9.0") == []


def test_problems_missing_version() -> None:
    assert any(
        "no '## [0.9.0]'" in item for item in cs.problems(UNRELEASED_ONLY, "0.9.0")
    )


def test_problems_empty_version_section() -> None:
    text = "## [Unreleased]\n\n## [1.0.0]\n\n### Enhancements\n\n## [0.9.0]\n\n- x\n"
    assert any("has no entries" in item for item in cs.problems(text, "1.0.0"))


def test_problems_unreleased_not_empty() -> None:
    text = "## [Unreleased]\n\n- late\n\n## [1.0.0]\n\n- x\n"
    assert any("still has entries" in item for item in cs.problems(text, "1.0.0"))


def test_problems_missing_unreleased_section() -> None:
    assert any(
        "[Unreleased]" in item for item in cs.problems("## [1.0.0]\n\n- x\n", "1.0.0")
    )


def test_promote_moves_entries_under_new_version() -> None:
    promoted = cs.promote(UNRELEASED_ONLY, "0.9.0")
    assert cs.problems(promoted, "0.9.0") == []
    assert cs.section(promoted, "0.9.0") == "### Enhancements\n\n- Add a thing."
    assert promoted.index("## [Unreleased]") < promoted.index("## [0.9.0]")
    assert cs.section(promoted, "0.8.1") == cs.section(UNRELEASED_ONLY, "0.8.1")


def test_promote_refuses_empty_unreleased() -> None:
    with pytest.raises(cs.ChangelogError, match="no entries"):
        cs.promote(RELEASED, "1.0.0")


def test_promote_refuses_existing_version() -> None:
    text = "## [Unreleased]\n\n- x\n\n## [0.8.1]\n\n- y\n"
    with pytest.raises(cs.ChangelogError, match="already exists"):
        cs.promote(text, "0.8.1")


def test_notes_returns_section_with_trailing_newline() -> None:
    assert cs.notes(RELEASED, "0.9.0") == "### Enhancements\n\n- Add a thing.\n"


def test_notes_refuses_missing_section() -> None:
    with pytest.raises(cs.ChangelogError, match="no release notes"):
        cs.notes(RELEASED, "2.0.0")


def test_main_check_reports_problems(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = tmp_path / "CHANGELOG.md"
    file.write_text(UNRELEASED_ONLY, encoding="utf-8")
    assert cs.main(["check", "0.9.0", "--file", str(file)]) == 1
    assert "changelog:" in capsys.readouterr().err


def test_main_check_passes(tmp_path: Path) -> None:
    file = tmp_path / "CHANGELOG.md"
    file.write_text(RELEASED, encoding="utf-8")
    assert cs.main(["check", "0.9.0", "--file", str(file)]) == 0


def test_main_notes_prints_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = tmp_path / "CHANGELOG.md"
    file.write_text(RELEASED, encoding="utf-8")
    assert cs.main(["notes", "0.9.0", "--file", str(file)]) == 0
    assert capsys.readouterr().out == "### Enhancements\n\n- Add a thing.\n"


def test_main_promote_rewrites_file(tmp_path: Path) -> None:
    file = tmp_path / "CHANGELOG.md"
    file.write_text(UNRELEASED_ONLY, encoding="utf-8")
    assert cs.main(["promote", "0.9.0", "--file", str(file)]) == 0
    assert cs.problems(file.read_text(encoding="utf-8"), "0.9.0") == []


def test_main_promote_failure_leaves_file_unchanged(tmp_path: Path) -> None:
    file = tmp_path / "CHANGELOG.md"
    file.write_text(RELEASED, encoding="utf-8")
    assert cs.main(["promote", "1.0.0", "--file", str(file)]) == 1
    assert file.read_text(encoding="utf-8") == RELEASED


def test_real_changelog_has_unreleased_section() -> None:
    assert (
        cs.section(cs.CHANGELOG.read_text(encoding="utf-8"), "Unreleased") is not None
    )


def test_main_unreleased_passes_with_entries(tmp_path: Path) -> None:
    file = tmp_path / "CHANGELOG.md"
    file.write_text(UNRELEASED_ONLY, encoding="utf-8")
    assert cs.main(["unreleased", "--file", str(file)]) == 0


def test_main_unreleased_fails_when_empty(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    file = tmp_path / "CHANGELOG.md"
    file.write_text(RELEASED, encoding="utf-8")
    assert cs.main(["unreleased", "--file", str(file)]) == 1
    assert "no entries" in capsys.readouterr().err


def test_main_version_commands_require_a_version(tmp_path: Path) -> None:
    file = tmp_path / "CHANGELOG.md"
    file.write_text(RELEASED, encoding="utf-8")
    with pytest.raises(SystemExit):
        cs.main(["check", "--file", str(file)])
