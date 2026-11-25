"""Tests for scripts/mutmut_state.py: mutants without a business rule."""

from typing import Any

import pytest

FN1 = "pkg.mod.x_fn__mutmut_1"
FN2 = "pkg.mod.x_fn__mutmut_2"


def _record_without_rule(state: Any, rule: str, **kwargs: object) -> dict[str, Any]:
    analysis = state.analysis(
        FN1,
        "missing_test",
        business_rule=rule,
        test_file="tests/t.py",
        test_name="t",
        **kwargs,
    )
    summary: dict[str, Any] = state.ms.record(
        state.ctx(),
        state.run([FN1], [analysis], status={FN1: "survived"}),
    )
    return summary


@pytest.mark.parametrize("rule", ["", "   ", "\n"])
def test_a_missing_test_without_a_rule_is_low_value_not_an_attempt(
    state: Any,
    rule: str,
) -> None:
    summary = _record_without_rule(state, rule)
    [row] = summary["low_value"]
    assert row["mutant"] == FN1
    assert "business rule" in row["reason"]
    [record] = state.ms.load_records(state.root, "pkg.mod")
    assert (record.status, record.attempts) == ("low_value", 0)
    assert summary["unresolved"] == []
    assert summary["parked"] == []


def test_the_analysts_reason_is_kept_with_the_low_value_finding(state: Any) -> None:
    summary = _record_without_rule(state, "", reason="only the log wording changes")
    assert "only the log wording changes" in summary["low_value"][0]["reason"]


def test_a_missing_test_with_a_rule_is_not_low_value(state: Any) -> None:
    summary = state.attempt(FN1)
    assert summary["low_value"] == []
    [record] = state.ms.load_records(state.root, "pkg.mod")
    assert record.status == "open"


def test_a_low_value_mutant_is_skipped_by_the_next_triage(state: Any) -> None:
    _record_without_rule(state, "")
    split = state.ms.triage(state.ctx(), [FN1, FN2])
    assert split.low_value == [FN1]
    assert split.to_analyze == [FN2]


def test_a_function_change_reopens_a_low_value_mutant(
    state: Any,
    module_source: str,
) -> None:
    _record_without_rule(state, "")
    path = state.root / "pkg" / "mod.py"
    path.write_text(
        module_source.replace("return x + 1", "return x + 2"), encoding="utf-8"
    )
    assert state.ms.triage(state.ctx(), [FN1]).to_analyze == [FN1]


def test_a_low_value_mutant_that_is_killed_later_is_forgotten(state: Any) -> None:
    _record_without_rule(state, "")
    summary = state.ms.record(
        state.ctx(),
        state.run([FN1], [], status={FN1: "killed"}),
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
