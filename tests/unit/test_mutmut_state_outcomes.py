"""Tests for scripts/mutmut_state.py: outcomes."""

from typing import Any

import pytest

FN1 = "pkg.mod.x_fn__mutmut_1"
FN2 = "pkg.mod.x_fn__mutmut_2"
OTHER1 = "pkg.mod.x_other__mutmut_1"
EVIDENCE = ["lib/yaml.py:2"]


def test_an_equivalent_with_evidence_is_recorded_and_never_parked(state: Any) -> None:
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run(
            [FN1],
            [
                state.analysis(
                    FN1, "equivalent", evidence=EVIDENCE, reason="same output"
                )
            ],
            status={FN1: "survived"},
        ),
    )
    assert summary["equivalent"] == [{"mutant": FN1, "reason": "same output"}]
    [record] = state.ms.load_records(state.root, "pkg.mod")
    assert (record.status, record.attempts) == ("equivalent", 0)
    assert record.dependencies == {
        "lib/yaml.py": state.ms.blob_hash(state.root / "lib" / "yaml.py")
    }


@pytest.mark.parametrize(
    ("outcome", "evidence", "listed"),
    [
        ("equivalent", ["it looks the same"], "equivalent"),
        ("suspected_bug", [], "suspected_bugs"),
    ],
)
def test_a_verdict_without_evidence_is_rejected_and_not_recorded(
    outcome: str,
    evidence: list[str],
    listed: str,
    state: Any,
) -> None:
    summary = state.ms.record(
        state.ctx(),
        state.run(
            [FN1],
            [state.analysis(FN1, outcome, evidence=evidence, reason="r")],
            status={FN1: "survived"},
        ),
    )
    assert state.ms.load_records(state.root, "pkg.mod") == []
    assert summary[listed] == []
    assert [r["mutant"] for r in summary["rejected"]] == [FN1]
    assert summary["unresolved"] == [FN1]


def test_depends_on_files_are_hashed_with_the_cited_evidence(state: Any) -> None:
    (state.root / "lib" / "other.py").write_text("x = 1\n", encoding="utf-8")
    ctx = state.ctx()
    state.ms.record(
        ctx,
        state.run(
            [FN1],
            [
                state.analysis(
                    FN1,
                    "equivalent",
                    evidence=EVIDENCE,
                    depends_on=["lib/other.py"],
                    reason="r",
                ),
            ],
        ),
    )
    [record] = state.ms.load_records(state.root, "pkg.mod")
    assert set(record.dependencies) == {"lib/yaml.py", "lib/other.py"}


def test_a_suspected_bug_with_a_traced_path_is_reported_never_attempted(
    state: Any,
) -> None:
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run(
            [FN1],
            [
                state.analysis(
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
    [record] = state.ms.load_records(state.root, "pkg.mod")
    assert (record.status, record.attempts) == ("suspected_bug", 0)
    assert state.ms.triage(state.ctx(), [FN1]).suspected_bug == [FN1]


def test_a_citation_beyond_the_end_of_the_file_is_not_evidence(state: Any) -> None:
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run(
            [FN1],
            [
                state.analysis(
                    FN1, "suspected_bug", evidence=["pkg/mod.py:999"], reason="r"
                )
            ],
        ),
    )
    assert summary["suspected_bugs"] == []


def test_dead_code_is_reported_every_run_and_never_stored(state: Any) -> None:
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run(
            [FN1],
            [state.analysis(FN1, "dead_code", reason="no production caller")],
            status={FN1: "survived"},
        ),
    )
    assert summary["dead_code"] == [{"mutant": FN1, "reason": "no production caller"}]
    assert state.ms.load_records(state.root, "pkg.mod") == []
    assert state.ms.triage(state.ctx(), [FN1]).to_analyze == [FN1]


def test_test_design_is_stored_and_not_attempted(state: Any) -> None:
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run(
            [FN1],
            [state.analysis(FN1, "test_design", reason="the only test mocks fn")],
            status={FN1: "survived"},
        ),
    )
    assert summary["test_design"] == [
        {"mutant": FN1, "reason": "the only test mocks fn"}
    ]
    assert state.ms.triage(state.ctx(), [FN1]).test_design == [FN1]


def test_counts_must_match_the_mutants_sent_to_analysis(state: Any) -> None:
    ctx = state.ctx()
    with pytest.raises(state.ms.StateError, match="analysed"):
        state.ms.record(
            ctx,
            state.run([FN1, FN2], [state.analysis(FN1, "dead_code", reason="r")]),
        )


def test_an_analysis_for_a_mutant_that_was_not_sent_is_refused(state: Any) -> None:
    ctx = state.ctx()
    with pytest.raises(state.ms.StateError, match="not sent"):
        state.ms.record(
            ctx,
            state.run([FN1], [state.analysis(FN2, "dead_code", reason="r")]),
        )


def test_the_summary_lists_killed_deferred_and_still_surviving(
    pyproject: str,
    state: Any,
) -> None:
    (state.root / "pyproject.toml").write_text(
        pyproject + "max_mutants_per_pass = 1\n",
        encoding="utf-8",
    )
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run(
            [FN1, FN2, OTHER1],
            [state.analysis(FN1, "dead_code", reason="r")],
            status={FN1: "survived", FN2: "killed", OTHER1: "survived"},
        ),
    )
    assert summary["deferred"] == [FN2, OTHER1]
    assert summary["killed"] == [FN2]
    assert summary["still_surviving"] == [FN1, OTHER1]
