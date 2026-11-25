"""Tests for scripts/mutmut_state.py: attempts."""

from typing import Any

import pytest

FN1 = "pkg.mod.x_fn__mutmut_1"


def test_a_test_that_kills_the_mutant_is_not_an_attempt(state: Any) -> None:
    summary = state.attempt(FN1, status="killed")
    assert summary["killed"] == [FN1]
    assert state.ms.load_records(state.root, "pkg.mod") == []


def test_a_surviving_mutant_records_the_attempt_with_its_history(state: Any) -> None:
    state.attempt(FN1)
    [record] = state.ms.load_records(state.root, "pkg.mod")
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


def test_the_parked_summary_carries_attempts_reason_and_tests_tried(state: Any) -> None:
    state.attempt(FN1)
    summary = state.attempt(FN1)
    [parked] = summary["parked"]
    assert parked["attempts"] == 2
    assert parked["last_reason"] == "test t written; the mutant still survives"
    assert len(parked["history"]) == 2


def test_a_failed_verify_run_counts_nothing(state: Any) -> None:
    ctx = state.ctx()
    state.ms.record(
        ctx,
        state.run(
            [FN1],
            [state.analysis(FN1, "missing_test", test_file="t.py", test_name="t")],
            written=[FN1],
            status={FN1: "survived"},
            verify_ok=False,
        ),
    )
    assert state.ms.load_records(state.root, "pkg.mod") == []


@pytest.mark.parametrize("status", ["timeout", "suspicious", "segfault"])
def test_a_mutant_that_moved_to_another_state_is_other_not_an_attempt(
    status: str, state: Any
) -> None:
    summary = state.attempt(FN1, status=status)
    assert state.ms.load_records(state.root, "pkg.mod") == []
    assert summary["other"] == [{"mutant": FN1, "status": status}]
    assert summary["killed"] == []


def test_a_written_test_that_mutmut_does_not_reach_is_not_an_attempt(
    state: Any,
) -> None:
    summary = state.attempt(FN1, status="no tests")
    assert state.ms.load_records(state.root, "pkg.mod") == []
    assert summary["still_surviving"] == [FN1]
    assert summary["unresolved"] == [FN1]


def test_a_proposed_test_that_could_not_be_made_to_pass_is_an_attempt(
    state: Any,
) -> None:
    ctx = state.ctx()
    state.ms.record(
        ctx,
        state.run(
            [FN1],
            [state.analysis(FN1, "missing_test", test_file="t.py", test_name="t")],
            write_failures={FN1: "the test failed against the original code"},
            status={FN1: "survived"},
        ),
    )
    [record] = state.ms.load_records(state.root, "pkg.mod")
    assert record.attempts == 1
    assert record.last_reason == "the test failed against the original code"


def test_an_analysis_failure_is_not_counted_and_is_retried(state: Any) -> None:
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run([FN1], [], unanalyzed=[FN1], status={FN1: "survived"}),
    )
    assert state.ms.load_records(state.root, "pkg.mod") == []
    assert summary["unresolved"] == [FN1]
    assert state.ms.triage(state.ctx(), [FN1]).to_analyze == [FN1]


def test_no_usable_test_is_not_an_attempt(state: Any) -> None:
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run(
            [FN1], [state.analysis(FN1, "missing_test")], status={FN1: "survived"}
        ),
    )
    assert state.ms.load_records(state.root, "pkg.mod") == []
    assert summary["unresolved"] == [FN1]


def test_a_test_outside_the_selection_is_a_config_problem_not_an_attempt(
    state: Any,
) -> None:
    ctx = state.ctx()
    summary = state.ms.record(
        ctx,
        state.run(
            [FN1],
            [state.analysis(FN1, "missing_test", test_file="x/t.py", test_name="t")],
            config_problems=[FN1],
            status={FN1: "survived"},
        ),
    )
    assert state.ms.load_records(state.root, "pkg.mod") == []
    assert summary["config_problems"] == [FN1]
