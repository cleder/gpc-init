"""Tests for scripts/mutmut_state.py: mutants without a business rule."""

from typing import Any

import pytest

FN1 = "pkg.mod.x_fn__mutmut_1"


def _record_without_rule(state: Any, rule: str, test_name: str = "t") -> dict[str, Any]:
    analysis = state.analysis(
        FN1,
        "missing_test",
        business_rule=rule,
        test_file="tests/t.py",
        test_name=test_name,
    )
    summary: dict[str, Any] = state.ms.record(
        state.ctx(),
        state.run([FN1], [analysis], written=[FN1], status={FN1: "survived"}),
    )
    return summary


@pytest.mark.parametrize("rule", ["", "   ", "\n"])
def test_a_survivor_without_a_rule_is_still_an_attempt(
    state: Any,
    rule: str,
) -> None:
    summary = _record_without_rule(state, rule)
    assert summary["still_surviving"] == [FN1]
    [record] = state.ms.load_records(state.root, "pkg.mod")
    assert (record.status, record.attempts) == ("open", 1)


def test_a_survivor_without_a_rule_is_parked_at_the_budget(state: Any) -> None:
    _record_without_rule(state, "")
    summary = _record_without_rule(state, "")
    assert [p["mutant"] for p in summary["parked"]] == [FN1]


def test_a_survivor_without_a_rule_that_is_killed_is_forgotten(state: Any) -> None:
    _record_without_rule(state, "")
    analysis = state.analysis(
        FN1, "missing_test", business_rule="", test_file="tests/t.py", test_name="t"
    )
    summary = state.ms.record(
        state.ctx(),
        state.run([FN1], [analysis], written=[FN1], status={FN1: "killed"}),
    )
    assert summary["killed"] == [FN1]
    assert state.ms.load_records(state.root, "pkg.mod") == []


def test_the_rule_and_its_source_are_kept_on_an_attempt(state: Any) -> None:
    analysis = state.analysis(
        FN1,
        "missing_test",
        business_rule="an admin block outranks an older consent",
        source="ISSUE-123",
        test_file="tests/t.py",
        test_name="t",
    )
    state.ms.record(
        state.ctx(),
        state.run([FN1], [analysis], written=[FN1], status={FN1: "survived"}),
    )
    [record] = state.ms.load_records(state.root, "pkg.mod")
    assert record.business_rule == "an admin block outranks an older consent"
    assert record.source == "ISSUE-123"
