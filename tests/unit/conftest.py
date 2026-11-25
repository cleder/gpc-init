"""Fixtures shared by the tests of scripts/mutmut_state.py."""

import importlib.util
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


class StateHarness:
    """The helper module, a project and the factories the tests build requests with."""

    def __init__(self, ms: ModuleType, root: Path) -> None:
        """Bind the helper module and the project it runs against."""
        self.ms = ms
        self.root = root

    def ctx(self, version: str = "3.8.1") -> Any:
        """Return the helper's context for this project."""
        return self.ms.load_context(
            self.root,
            mutmut_version=version,
            today="2026-11-25",
        )

    def analysis(self, mutant: str, outcome: str, **kwargs: object) -> Any:
        """Return one analysis verdict; a missing test states a rule by default."""
        if outcome == "missing_test":
            kwargs.setdefault("business_rule", "a blocked app must stay blocked")
        return self.ms.Analysis(mutant=mutant, outcome=outcome, **kwargs)

    def run(self, gaps: list[str], analyses: list[Any], **kwargs: object) -> Any:
        """Return one workflow pass, with quiet defaults."""
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
        return self.ms.Run(**values)

    def attempt(self, mutant: str, status: str = "survived") -> dict[str, Any]:
        """Run one pass in which a test was written for `mutant`."""
        analysis = self.analysis(
            mutant,
            "missing_test",
            test_file="tests/t.py",
            test_name="t",
        )
        summary: dict[str, Any] = self.ms.record(
            self.ctx(),
            self.run([mutant], [analysis], written=[mutant], status={mutant: status}),
        )
        return summary


@pytest.fixture
def state(ms: ModuleType, root: Path) -> StateHarness:
    """Return the harness for a fresh project."""
    return StateHarness(ms, root)
