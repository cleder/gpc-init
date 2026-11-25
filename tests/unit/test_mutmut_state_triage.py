"""Tests for scripts/mutmut_state.py: triage."""

from pathlib import Path
from typing import Any

FN1 = "pkg.mod.x_fn__mutmut_1"
FN2 = "pkg.mod.x_fn__mutmut_2"
FN10 = "pkg.mod.x_fn__mutmut_10"
OTHER1 = "pkg.mod.x_other__mutmut_1"
EVIDENCE = ["lib/yaml.py:2"]


def test_triage_sends_unknown_mutants_to_analysis_in_stable_order(
    root: Path, ms: Any, make_ctx: Any
) -> None:
    result = ms.triage(make_ctx(root), [FN10, OTHER1, FN2, FN1])
    assert result.to_analyze == [FN1, FN2, FN10, OTHER1]
    assert result.parked == result.equivalent == result.deferred == []


def test_a_parked_mutant_is_skipped_after_failing_twice(
    root: Path, ms: Any, make_ctx: Any, attempt: Any
) -> None:
    attempt(root, FN1)
    second = attempt(root, FN1)
    assert [p["mutant"] for p in second["parked"]] == [FN1]
    again = ms.triage(make_ctx(root), [FN1])
    assert again.parked == [FN1]
    assert again.to_analyze == []


def test_a_mutant_under_budget_stays_open_and_is_analysed_again(
    root: Path, ms: Any, make_ctx: Any, attempt: Any
) -> None:
    summary = attempt(root, FN1)
    assert summary["parked"] == []
    assert ms.triage(make_ctx(root), [FN1]).to_analyze == [FN1]


def test_a_function_change_reopens_a_parked_mutant_with_the_count_reset(
    root: Path, ms: Any, module_source: str, make_ctx: Any, attempt: Any
) -> None:
    attempt(root, FN1)
    attempt(root, FN1)
    mod_path = root / "pkg" / "mod.py"
    mod_path.write_text(
        module_source.replace("return x + 1", "return x + 2"), encoding="utf-8"
    )
    assert ms.triage(make_ctx(root), [FN1]).to_analyze == [FN1]
    summary = attempt(root, FN1)
    assert summary["parked"] == []


def test_an_edit_elsewhere_in_the_file_does_not_reopen_a_parked_mutant(
    root: Path, ms: Any, module_source: str, make_ctx: Any, attempt: Any
) -> None:
    attempt(root, FN1)
    attempt(root, FN1)
    mod_path = root / "pkg" / "mod.py"
    mod_path.write_text(
        module_source.replace("return y * 2", "return y * 3"), encoding="utf-8"
    )
    assert ms.triage(make_ctx(root), [FN1]).parked == [FN1]


def test_a_dependency_change_reopens_a_parked_mutant(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    ms.record(
        ctx,
        make_run(
            [FN1],
            [make_analysis(FN1, "equivalent", evidence=EVIDENCE, reason="same output")],
        ),
    )
    assert ms.triage(make_ctx(root), [FN1]).equivalent == [FN1]
    (root / "lib" / "yaml.py").write_text("a = 1\nb = 3\n", encoding="utf-8")
    assert ms.triage(make_ctx(root), [FN1]).to_analyze == [FN1]


def test_a_mutmut_version_change_reopens_records(
    root: Path, ms: Any, make_ctx: Any, attempt: Any
) -> None:
    attempt(root, FN1)
    attempt(root, FN1)
    assert ms.triage(make_ctx(root, "3.9.0"), [FN1]).to_analyze == [FN1]


def test_a_mutation_config_change_reopens_records(
    root: Path, ms: Any, pyproject: str, make_ctx: Any, attempt: Any
) -> None:
    attempt(root, FN1)
    attempt(root, FN1)
    (root / "pyproject.toml").write_text(
        pyproject.replace('["data"]', '["data", "more"]'),
        encoding="utf-8",
    )
    assert ms.triage(make_ctx(root), [FN1]).to_analyze == [FN1]


def test_max_mutants_per_pass_defers_the_rest_in_stable_order(
    root: Path, ms: Any, pyproject: str, make_ctx: Any
) -> None:
    (root / "pyproject.toml").write_text(
        pyproject + "max_mutants_per_pass = 2\n",
        encoding="utf-8",
    )
    result = ms.triage(make_ctx(root), [OTHER1, FN10, FN2, FN1])
    assert result.to_analyze == [FN1, FN2]
    assert result.deferred == [FN10, OTHER1]


def test_the_pass_budget_counts_only_mutants_sent_to_analysis(
    root: Path,
    *,
    ms: Any,
    pyproject: str,
    make_ctx: Any,
    make_analysis: Any,
    make_run: Any,
) -> None:
    ctx = make_ctx(root)
    ms.record(
        ctx,
        make_run(
            [FN1], [make_analysis(FN1, "equivalent", evidence=EVIDENCE, reason="r")]
        ),
    )
    (root / "pyproject.toml").write_text(
        pyproject + "max_mutants_per_pass = 1\n",
        encoding="utf-8",
    )
    result = ms.triage(make_ctx(root), [FN1, FN2, OTHER1])
    assert result.equivalent == [FN1]
    assert result.to_analyze == [FN2]
    assert result.deferred == [OTHER1]
