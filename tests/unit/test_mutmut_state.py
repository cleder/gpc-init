"""Tests for scripts/mutmut_state.py, the state helper of the mutmut workflow."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "mutmut_state.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mutmut_state", SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ms = _load()

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

FN1 = "pkg.mod.x_fn__mutmut_1"
FN2 = "pkg.mod.x_fn__mutmut_2"
FN10 = "pkg.mod.x_fn__mutmut_10"
OTHER1 = "pkg.mod.x_other__mutmut_1"
PUT1 = "pkg.mod.xǁBoxǁput__mutmut_1"
EVIDENCE = ["lib/yaml.py:2"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "yaml.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return tmp_path


def _ctx(root: Path, version: str = "3.8.1") -> Any:
    return ms.load_context(root, mutmut_version=version, today="2026-11-25")


def _analysis(mutant: str, outcome: str, **kwargs: object) -> Any:
    return ms.Analysis(mutant=mutant, outcome=outcome, **kwargs)


def _run(
    gaps: list[str],
    analyses: list[Any],
    **kwargs: object,
) -> Any:
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


def _attempt(root: Path, mutant: str, status: str = "survived") -> dict[str, Any]:
    """One pass in which a test was written for `mutant` and Verify saw `status`."""
    ctx = _ctx(root)
    summary: dict[str, Any] = ms.record(
        ctx,
        _run(
            [mutant],
            [_analysis(mutant, "missing_test", test_file="tests/t.py", test_name="t")],
            written=[mutant],
            status={mutant: status},
        ),
    )
    return summary


# ─── hashing and parsing ──────────────────────────────────────────────────────


def test_fnv1a32_matches_the_vector_the_workflow_script_uses() -> None:
    assert ms.fnv1a32(["b", "a", "c"]) == 3588977911
    names = [
        "pc_init.catalog.xǁCatalogǁcommon_preset__mutmut_1",
        "pc_init.m.x_f__mutmut_2",
    ]
    assert ms.fnv1a32(names) == 3033286041


def test_blob_hash_is_the_git_blob_hash(tmp_path: Path) -> None:
    path = tmp_path / "f.txt"
    path.write_text("hello\n", encoding="utf-8")
    assert ms.blob_hash(path) == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_parse_mutant_reads_function_and_method_names() -> None:
    func = ms.parse_mutant(FN10)
    assert (func.module, func.class_name, func.function, func.number) == (
        "pkg.mod",
        None,
        "fn",
        10,
    )
    method = ms.parse_mutant(PUT1)
    assert (method.module, method.class_name, method.function, method.number) == (
        "pkg.mod",
        "Box",
        "put",
        1,
    )


def test_function_hash_ignores_comments_and_layout_but_not_code() -> None:
    base = ms.function_hash(SOURCE, None, "fn")
    assert base
    commented = SOURCE.replace("return x + 1", "return x+1  # a comment")
    assert ms.function_hash(commented, None, "fn") == base
    changed = SOURCE.replace("return x + 1", "return x + 2")
    assert ms.function_hash(changed, None, "fn") != base


def test_function_hash_is_unaffected_by_edits_to_other_functions() -> None:
    base = ms.function_hash(SOURCE, None, "fn")
    edited = SOURCE.replace("return y * 2", "return y * 3")
    assert ms.function_hash(edited, None, "fn") == base


def test_function_hash_finds_methods_and_returns_none_for_unknown_names() -> None:
    assert ms.function_hash(SOURCE, "Box", "put")
    assert ms.function_hash(SOURCE, None, "missing") is None
    assert ms.function_hash(SOURCE, "Box", "missing") is None


def test_config_hash_ignores_test_selection_and_changes_with_mutation_settings() -> (
    None
):
    cfg = {"source_paths": ["pkg/"], "pytest_add_cli_args_test_selection": ["tests/"]}
    base = ms.config_hash(cfg)
    same = {"source_paths": ["pkg/"], "pytest_add_cli_args_test_selection": ["t2/"]}
    assert ms.config_hash(same) == base
    assert ms.config_hash({**cfg, "do_not_mutate_patterns": ["x"]}) != base


# ─── settings ─────────────────────────────────────────────────────────────────


def test_budgets_default_when_the_workflow_table_is_absent(root: Path) -> None:
    (root / "pyproject.toml").write_text("[tool.mutmut]\n", encoding="utf-8")
    ctx = _ctx(root)
    assert ctx.settings.max_attempts == 2
    assert ctx.settings.max_mutants_per_pass is None


def test_budgets_are_read_from_the_workflow_table(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        PYPROJECT.replace("= 2", "= 3") + "max_mutants_per_pass = 5\n",
        encoding="utf-8",
    )
    ctx = _ctx(root)
    assert ctx.settings.max_attempts == 3
    assert ctx.settings.max_mutants_per_pass == 5


def test_changing_a_budget_does_not_change_the_config_hash(root: Path) -> None:
    before = _ctx(root).config_hash
    (root / "pyproject.toml").write_text(
        PYPROJECT.replace("= 2", "= 9"), encoding="utf-8"
    )
    assert _ctx(root).config_hash == before


# ─── triage ───────────────────────────────────────────────────────────────────


def test_triage_sends_unknown_mutants_to_analysis_in_stable_order(root: Path) -> None:
    result = ms.triage(_ctx(root), [FN10, OTHER1, FN2, FN1])
    assert result.to_analyze == [FN1, FN2, FN10, OTHER1]
    assert result.parked == result.equivalent == result.deferred == []


def test_a_parked_mutant_is_skipped_after_failing_twice(root: Path) -> None:
    _attempt(root, FN1)
    second = _attempt(root, FN1)
    assert [p["mutant"] for p in second["parked"]] == [FN1]
    again = ms.triage(_ctx(root), [FN1])
    assert again.parked == [FN1]
    assert again.to_analyze == []


def test_a_mutant_under_budget_stays_open_and_is_analysed_again(root: Path) -> None:
    summary = _attempt(root, FN1)
    assert summary["parked"] == []
    assert ms.triage(_ctx(root), [FN1]).to_analyze == [FN1]


def test_a_function_change_reopens_a_parked_mutant_with_the_count_reset(
    root: Path,
) -> None:
    _attempt(root, FN1)
    _attempt(root, FN1)
    source = root / "pkg" / "mod.py"
    source.write_text(SOURCE.replace("return x + 1", "return x + 2"), encoding="utf-8")
    assert ms.triage(_ctx(root), [FN1]).to_analyze == [FN1]
    summary = _attempt(root, FN1)
    assert summary["parked"] == []


def test_an_edit_elsewhere_in_the_file_does_not_reopen_a_parked_mutant(
    root: Path,
) -> None:
    _attempt(root, FN1)
    _attempt(root, FN1)
    source = root / "pkg" / "mod.py"
    source.write_text(SOURCE.replace("return y * 2", "return y * 3"), encoding="utf-8")
    assert ms.triage(_ctx(root), [FN1]).parked == [FN1]


def test_a_dependency_change_reopens_a_parked_mutant(root: Path) -> None:
    ctx = _ctx(root)
    ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "equivalent", evidence=EVIDENCE, reason="same output")],
        ),
    )
    assert ms.triage(_ctx(root), [FN1]).equivalent == [FN1]
    (root / "lib" / "yaml.py").write_text("a = 1\nb = 3\n", encoding="utf-8")
    assert ms.triage(_ctx(root), [FN1]).to_analyze == [FN1]


def test_a_mutmut_version_change_reopens_records(root: Path) -> None:
    _attempt(root, FN1)
    _attempt(root, FN1)
    assert ms.triage(_ctx(root, "3.9.0"), [FN1]).to_analyze == [FN1]


def test_a_mutation_config_change_reopens_records(root: Path) -> None:
    _attempt(root, FN1)
    _attempt(root, FN1)
    (root / "pyproject.toml").write_text(
        PYPROJECT.replace('["data"]', '["data", "more"]'),
        encoding="utf-8",
    )
    assert ms.triage(_ctx(root), [FN1]).to_analyze == [FN1]


def test_max_mutants_per_pass_defers_the_rest_in_stable_order(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        PYPROJECT + "max_mutants_per_pass = 2\n",
        encoding="utf-8",
    )
    result = ms.triage(_ctx(root), [OTHER1, FN10, FN2, FN1])
    assert result.to_analyze == [FN1, FN2]
    assert result.deferred == [FN10, OTHER1]


def test_the_pass_budget_counts_only_mutants_sent_to_analysis(root: Path) -> None:
    ctx = _ctx(root)
    ms.record(
        ctx,
        _run([FN1], [_analysis(FN1, "equivalent", evidence=EVIDENCE, reason="r")]),
    )
    (root / "pyproject.toml").write_text(
        PYPROJECT + "max_mutants_per_pass = 1\n",
        encoding="utf-8",
    )
    result = ms.triage(_ctx(root), [FN1, FN2, OTHER1])
    assert result.equivalent == [FN1]
    assert result.to_analyze == [FN2]
    assert result.deferred == [OTHER1]


# ─── recording attempts ───────────────────────────────────────────────────────


def test_a_test_that_kills_the_mutant_is_not_an_attempt(root: Path) -> None:
    summary = _attempt(root, FN1, status="killed")
    assert summary["killed"] == [FN1]
    assert ms.load_records(root, "pkg.mod") == []


def test_a_surviving_mutant_records_the_attempt_with_its_history(root: Path) -> None:
    _attempt(root, FN1)
    [record] = ms.load_records(root, "pkg.mod")
    assert record.status == "open"
    assert record.attempts == 1
    assert record.history == [
        {
            "date": "2026-11-25",
            "reason": "test t written; the mutant still survives",
            "test_file": "tests/t.py",
            "test_name": "t",
        },
    ]


def test_the_parked_summary_carries_attempts_reason_and_tests_tried(root: Path) -> None:
    _attempt(root, FN1)
    summary = _attempt(root, FN1)
    [parked] = summary["parked"]
    assert parked["attempts"] == 2
    assert parked["last_reason"] == "test t written; the mutant still survives"
    assert len(parked["history"]) == 2


def test_a_failed_verify_run_counts_nothing(root: Path) -> None:
    ctx = _ctx(root)
    ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "missing_test", test_file="t.py", test_name="t")],
            written=[FN1],
            status={FN1: "survived"},
            verify_ok=False,
        ),
    )
    assert ms.load_records(root, "pkg.mod") == []


@pytest.mark.parametrize("status", ["timeout", "suspicious", "segfault"])
def test_a_mutant_that_moved_to_another_state_is_other_not_an_attempt(
    root: Path,
    status: str,
) -> None:
    summary = _attempt(root, FN1, status=status)
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["other"] == [{"mutant": FN1, "status": status}]
    assert summary["killed"] == []


def test_a_written_test_that_mutmut_does_not_reach_is_not_an_attempt(
    root: Path,
) -> None:
    summary = _attempt(root, FN1, status="no tests")
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["still_surviving"] == [FN1]
    assert summary["unresolved"] == [FN1]


def test_a_proposed_test_that_could_not_be_made_to_pass_is_an_attempt(
    root: Path,
) -> None:
    ctx = _ctx(root)
    ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "missing_test", test_file="t.py", test_name="t")],
            write_failures={FN1: "the test failed against the original code"},
            status={FN1: "survived"},
        ),
    )
    [record] = ms.load_records(root, "pkg.mod")
    assert record.attempts == 1
    assert record.last_reason == "the test failed against the original code"


def test_an_analysis_failure_is_not_counted_and_is_retried(root: Path) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run([FN1], [], unanalyzed=[FN1], status={FN1: "survived"}),
    )
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["unresolved"] == [FN1]
    assert ms.triage(_ctx(root), [FN1]).to_analyze == [FN1]


def test_no_usable_test_is_not_an_attempt(root: Path) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run([FN1], [_analysis(FN1, "missing_test")], status={FN1: "survived"}),
    )
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["unresolved"] == [FN1]


def test_a_test_outside_the_selection_is_a_config_problem_not_an_attempt(
    root: Path,
) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "missing_test", test_file="x/t.py", test_name="t")],
            config_problems=[FN1],
            status={FN1: "survived"},
        ),
    )
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["config_problems"] == [FN1]


# ─── outcomes ─────────────────────────────────────────────────────────────────


def test_an_equivalent_with_evidence_is_recorded_and_never_parked(root: Path) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "equivalent", evidence=EVIDENCE, reason="same output")],
            status={FN1: "survived"},
        ),
    )
    assert summary["equivalent"] == [{"mutant": FN1, "reason": "same output"}]
    [record] = ms.load_records(root, "pkg.mod")
    assert (record.status, record.attempts) == ("equivalent", 0)
    assert record.dependencies == {
        "lib/yaml.py": ms.blob_hash(root / "lib" / "yaml.py")
    }


def test_an_equivalent_without_evidence_is_rejected_and_not_recorded(
    root: Path,
) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "equivalent", evidence=["it looks the same"], reason="r")],
            status={FN1: "survived"},
        ),
    )
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["equivalent"] == []
    assert [r["mutant"] for r in summary["rejected"]] == [FN1]
    assert summary["unresolved"] == [FN1]


def test_depends_on_files_are_hashed_with_the_cited_evidence(root: Path) -> None:
    (root / "lib" / "other.py").write_text("x = 1\n", encoding="utf-8")
    ctx = _ctx(root)
    ms.record(
        ctx,
        _run(
            [FN1],
            [
                _analysis(
                    FN1,
                    "equivalent",
                    evidence=EVIDENCE,
                    depends_on=["lib/other.py"],
                    reason="r",
                ),
            ],
        ),
    )
    [record] = ms.load_records(root, "pkg.mod")
    assert set(record.dependencies) == {"lib/yaml.py", "lib/other.py"}


def test_a_suspected_bug_with_a_traced_path_is_reported_never_attempted(
    root: Path,
) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1],
            [
                _analysis(
                    FN1,
                    "suspected_bug",
                    evidence=["pkg/mod.py:2"],
                    reason="x + 1 overflows for callers passing 9",
                ),
            ],
            status={FN1: "survived"},
        ),
    )
    assert [b["mutant"] for b in summary["suspected_bugs"]] == [FN1]
    [record] = ms.load_records(root, "pkg.mod")
    assert (record.status, record.attempts) == ("suspected_bug", 0)
    assert ms.triage(_ctx(root), [FN1]).suspected_bug == [FN1]


def test_a_suspected_bug_without_evidence_is_not_recorded(root: Path) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "suspected_bug", evidence=[], reason="looks more correct")],
            status={FN1: "survived"},
        ),
    )
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["suspected_bugs"] == []
    assert [r["mutant"] for r in summary["rejected"]] == [FN1]


def test_a_citation_beyond_the_end_of_the_file_is_not_evidence(root: Path) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "suspected_bug", evidence=["pkg/mod.py:999"], reason="r")],
        ),
    )
    assert summary["suspected_bugs"] == []


def test_dead_code_is_reported_every_run_and_never_stored(root: Path) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "dead_code", reason="no production caller")],
            status={FN1: "survived"},
        ),
    )
    assert summary["dead_code"] == [{"mutant": FN1, "reason": "no production caller"}]
    assert ms.load_records(root, "pkg.mod") == []
    assert ms.triage(_ctx(root), [FN1]).to_analyze == [FN1]


def test_test_design_is_stored_and_not_attempted(root: Path) -> None:
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1],
            [_analysis(FN1, "test_design", reason="the only test mocks fn")],
            status={FN1: "survived"},
        ),
    )
    assert summary["test_design"] == [
        {"mutant": FN1, "reason": "the only test mocks fn"}
    ]
    assert ms.triage(_ctx(root), [FN1]).test_design == [FN1]


def test_counts_must_match_the_mutants_sent_to_analysis(root: Path) -> None:
    ctx = _ctx(root)
    with pytest.raises(ms.StateError, match="analysed"):
        ms.record(
            ctx,
            _run([FN1, FN2], [_analysis(FN1, "dead_code", reason="r")]),
        )


def test_an_analysis_for_a_mutant_that_was_not_sent_is_refused(root: Path) -> None:
    ctx = _ctx(root)
    with pytest.raises(ms.StateError, match="not sent"):
        ms.record(
            ctx,
            _run([FN1], [_analysis(FN2, "dead_code", reason="r")]),
        )


def test_the_summary_lists_killed_deferred_and_still_surviving(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        PYPROJECT + "max_mutants_per_pass = 1\n",
        encoding="utf-8",
    )
    ctx = _ctx(root)
    summary = ms.record(
        ctx,
        _run(
            [FN1, FN2, OTHER1],
            [_analysis(FN1, "dead_code", reason="r")],
            status={FN1: "survived", FN2: "killed", OTHER1: "survived"},
        ),
    )
    assert summary["deferred"] == [FN2, OTHER1]
    assert summary["killed"] == [FN2]
    assert summary["still_surviving"] == [FN1, OTHER1]


# ─── storage and migration ────────────────────────────────────────────────────


def test_state_is_one_file_per_module_and_survives_a_round_trip(root: Path) -> None:
    _attempt(root, FN1)
    _attempt(root, PUT1)
    path = root / ".mutmut-analysis" / "pkg.mod.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert [r["mutant"] for r in data["records"]] == [FN1, PUT1]
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_migrating_v1_keeps_matching_records_and_drops_stale_ones(root: Path) -> None:
    source = root / "pkg" / "mod.py"
    v1 = [
        {
            "mutant_name": FN1,
            "source_file": "pkg/mod.py",
            "file_hash": ms.blob_hash(source),
            "equivalent_reason": "kept",
        },
        {
            "mutant_name": OTHER1,
            "source_file": "pkg/mod.py",
            "file_hash": "0" * 40,
            "equivalent_reason": "stale",
        },
    ]
    (root / ".mutmut-equivalents.json").write_text(json.dumps(v1), encoding="utf-8")
    assert ms.migrate_v1(_ctx(root)) == (1, 1)
    [record] = ms.load_records(root, "pkg.mod")
    assert (record.mutant, record.status, record.last_reason) == (
        FN1,
        "equivalent",
        "kept",
    )
    assert ms.triage(_ctx(root), [FN1]).equivalent == [FN1]


# ─── command line ─────────────────────────────────────────────────────────────


def test_the_cli_triage_prints_lists_with_checksums(root: Path) -> None:
    gaps = [FN2, FN1]
    out = ms.run_command(
        "triage",
        root,
        {"mutmut_version": "3.8.1", "gaps": gaps, "gaps_checksum": ms.fnv1a32(gaps)},
        today="2026-11-25",
    )
    assert out["to_analyze"] == {
        "names": [FN1, FN2],
        "checksum": ms.fnv1a32([FN1, FN2]),
    }
    assert out["parked"] == {"names": [], "checksum": ms.fnv1a32([])}


def test_the_cli_refuses_a_gap_list_whose_checksum_does_not_match(root: Path) -> None:
    with pytest.raises(ms.StateError, match="checksum"):
        ms.run_command(
            "triage",
            root,
            {"mutmut_version": "3.8.1", "gaps": [FN1], "gaps_checksum": 1},
            today="2026-11-25",
        )


def test_the_cli_record_round_trips_a_payload(root: Path) -> None:
    gaps = [FN1]
    payload: dict[str, Any] = {
        "mutmut_version": "3.8.1",
        "gaps": gaps,
        "gaps_checksum": ms.fnv1a32(gaps),
        "analyses": [
            {
                "mutant": FN1,
                "outcome": "missing_test",
                "test_file": "tests/t.py",
                "test_name": "t",
            },
        ],
        "written": [FN1],
        "write_failures": {},
        "config_problems": [],
        "unanalyzed": [],
        "verify_ok": True,
        "status": {FN1: "killed"},
    }
    out = ms.run_command("record", root, payload, today="2026-11-25")
    assert out["killed"] == [FN1]
