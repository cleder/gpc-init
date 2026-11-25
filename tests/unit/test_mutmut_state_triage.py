"""Tests for scripts/mutmut_state.py: triage."""

from typing import Any

FN1 = "pkg.mod.x_fn__mutmut_1"
FN2 = "pkg.mod.x_fn__mutmut_2"
FN10 = "pkg.mod.x_fn__mutmut_10"
OTHER1 = "pkg.mod.x_other__mutmut_1"
EVIDENCE = ["lib/yaml.py:2"]


def test_triage_sends_unknown_mutants_to_analysis_in_stable_order(state: Any) -> None:
    result = state.ms.triage(state.ctx(), [FN10, OTHER1, FN2, FN1])
    assert result.to_analyze == [FN1, FN2, FN10, OTHER1]
    assert result.parked == result.equivalent == result.deferred == []


def test_a_parked_mutant_is_skipped_after_failing_twice(state: Any) -> None:
    state.attempt(FN1)
    second = state.attempt(FN1)
    assert [p["mutant"] for p in second["parked"]] == [FN1]
    again = state.ms.triage(state.ctx(), [FN1])
    assert again.parked == [FN1]
    assert again.to_analyze == []


def test_a_mutant_under_budget_stays_open_and_is_analysed_again(state: Any) -> None:
    summary = state.attempt(FN1)
    assert summary["parked"] == []
    assert state.ms.triage(state.ctx(), [FN1]).to_analyze == [FN1]


def test_a_function_change_reopens_a_parked_mutant_with_the_count_reset(
    module_source: str, state: Any
) -> None:
    state.attempt(FN1)
    state.attempt(FN1)
    mod_path = state.root / "pkg" / "mod.py"
    mod_path.write_text(
        module_source.replace("return x + 1", "return x + 2"), encoding="utf-8"
    )
    assert state.ms.triage(state.ctx(), [FN1]).to_analyze == [FN1]
    summary = state.attempt(FN1)
    assert summary["parked"] == []


def test_an_edit_elsewhere_in_the_file_does_not_reopen_a_parked_mutant(
    module_source: str, state: Any
) -> None:
    state.attempt(FN1)
    state.attempt(FN1)
    mod_path = state.root / "pkg" / "mod.py"
    mod_path.write_text(
        module_source.replace("return y * 2", "return y * 3"), encoding="utf-8"
    )
    assert state.ms.triage(state.ctx(), [FN1]).parked == [FN1]


def test_a_dependency_change_reopens_a_parked_mutant(state: Any) -> None:
    ctx = state.ctx()
    state.ms.record(
        ctx,
        state.run(
            [FN1],
            [
                state.analysis(
                    FN1, "equivalent", evidence=EVIDENCE, reason="same output"
                )
            ],
        ),
    )
    assert state.ms.triage(state.ctx(), [FN1]).equivalent == [FN1]
    (state.root / "lib" / "yaml.py").write_text("a = 1\nb = 3\n", encoding="utf-8")
    assert state.ms.triage(state.ctx(), [FN1]).to_analyze == [FN1]


def test_a_mutmut_version_change_reopens_records(state: Any) -> None:
    state.attempt(FN1)
    state.attempt(FN1)
    assert state.ms.triage(state.ctx("3.9.0"), [FN1]).to_analyze == [FN1]


def test_a_mutation_config_change_reopens_records(pyproject: str, state: Any) -> None:
    state.attempt(FN1)
    state.attempt(FN1)
    (state.root / "pyproject.toml").write_text(
        pyproject.replace('["data"]', '["data", "more"]'),
        encoding="utf-8",
    )
    assert state.ms.triage(state.ctx(), [FN1]).to_analyze == [FN1]


def test_max_mutants_per_pass_defers_the_rest_in_stable_order(
    pyproject: str, state: Any
) -> None:
    (state.root / "pyproject.toml").write_text(
        pyproject + "max_mutants_per_pass = 2\n",
        encoding="utf-8",
    )
    result = state.ms.triage(state.ctx(), [OTHER1, FN10, FN2, FN1])
    assert result.to_analyze == [FN1, FN2]
    assert result.deferred == [FN10, OTHER1]


def test_the_pass_budget_counts_only_mutants_sent_to_analysis(
    pyproject: str,
    state: Any,
) -> None:
    ctx = state.ctx()
    state.ms.record(
        ctx,
        state.run(
            [FN1], [state.analysis(FN1, "equivalent", evidence=EVIDENCE, reason="r")]
        ),
    )
    (state.root / "pyproject.toml").write_text(
        pyproject + "max_mutants_per_pass = 1\n",
        encoding="utf-8",
    )
    result = state.ms.triage(state.ctx(), [FN1, FN2, OTHER1])
    assert result.equivalent == [FN1]
    assert result.to_analyze == [FN2]
    assert result.deferred == [OTHER1]
