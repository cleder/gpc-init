"""Fixtures shared by the tests of scripts/mutmut_state.py."""

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "mutmut_state.py"

SOURCE = """\
def fn(x):
    return x + 1


def other(y):
    return y * 2


class Box:
    def put(self, z):
        return z
"""

PYPROJECT = """\
[tool.mutmut]
source_paths = ["pkg/"]
also_copy = ["data"]
pytest_add_cli_args_test_selection = ["tests/"]

[tool.mutmut-workflow]
max_attempts_per_mutant = 2
"""


@pytest.fixture(scope="session")
def ms() -> ModuleType:
    """Load scripts/mutmut_state.py, which is not an importable package."""
    spec = importlib.util.spec_from_file_location("mutmut_state", SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module_source() -> str:
    """Return the source of the module the mutants belong to."""
    return SOURCE


@pytest.fixture
def pyproject() -> str:
    """Return the project's pyproject.toml."""
    return PYPROJECT


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Create a small project with one module and one library file."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "yaml.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return tmp_path


@pytest.fixture
def make_ctx(ms: ModuleType) -> Callable[..., Any]:
    """Return a factory for the helper's context."""

    def make(root: Path, version: str = "3.8.1") -> Any:
        return ms.load_context(root, mutmut_version=version, today="2026-11-25")

    return make


@pytest.fixture
def make_analysis(ms: ModuleType) -> Callable[..., Any]:
    """Return a factory for one analysis verdict."""

    def make(mutant: str, outcome: str, **kwargs: object) -> Any:
        return ms.Analysis(mutant=mutant, outcome=outcome, **kwargs)

    return make


@pytest.fixture
def make_run(ms: ModuleType) -> Callable[..., Any]:
    """Return a factory for one workflow pass, with quiet defaults."""

    def make(gaps: list[str], analyses: list[Any], **kwargs: object) -> Any:
        values: dict[str, object] = {
            "gaps": gaps,
            "analyses": analyses,
            "written": [],
            "write_failures": {},
            "config_problems": [],
            "unanalyzed": [],
            "verify_ok": True,
            "status": {},
        }
        values.update(kwargs)
        return ms.Run(**values)

    return make


@pytest.fixture
def attempt(
    ms: ModuleType,
    make_ctx: Callable[..., Any],
    make_analysis: Callable[..., Any],
    make_run: Callable[..., Any],
) -> Callable[..., dict[str, Any]]:
    """Return a function that runs one pass writing a test for one mutant."""

    def run(root: Path, mutant: str, status: str = "survived") -> dict[str, Any]:
        summary: dict[str, Any] = ms.record(
            make_ctx(root),
            make_run(
                [mutant],
                [
                    make_analysis(
                        mutant,
                        "missing_test",
                        test_file="tests/t.py",
                        test_name="t",
                    ),
                ],
                written=[mutant],
                status={mutant: status},
            ),
        )
        return summary

    return run
