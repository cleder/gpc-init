"""Tests for scripts/mutmut_state.py: outcomes."""

from pathlib import Path
from typing import Any

import pytest

FN1 = "pkg.mod.x_fn__mutmut_1"
FN2 = "pkg.mod.x_fn__mutmut_2"
OTHER1 = "pkg.mod.x_other__mutmut_1"
EVIDENCE = ["lib/yaml.py:2"]


def test_an_equivalent_with_evidence_is_recorded_and_never_parked(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    summary = ms.record(
        ctx,
        make_run(
            [FN1],
            [make_analysis(FN1, "equivalent", evidence=EVIDENCE, reason="same output")],
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
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    summary = ms.record(
        ctx,
        make_run(
            [FN1],
            [
                make_analysis(
                    FN1, "equivalent", evidence=["it looks the same"], reason="r"
                )
            ],
            status={FN1: "survived"},
        ),
    )
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["equivalent"] == []
    assert [r["mutant"] for r in summary["rejected"]] == [FN1]
    assert summary["unresolved"] == [FN1]


def test_depends_on_files_are_hashed_with_the_cited_evidence(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    (root / "lib" / "other.py").write_text("x = 1\n", encoding="utf-8")
    ctx = make_ctx(root)
    ms.record(
        ctx,
        make_run(
            [FN1],
            [
                make_analysis(
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
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    summary = ms.record(
        ctx,
        make_run(
            [FN1],
            [
                make_analysis(
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
    assert ms.triage(make_ctx(root), [FN1]).suspected_bug == [FN1]


def test_a_suspected_bug_without_evidence_is_not_recorded(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    summary = ms.record(
        ctx,
        make_run(
            [FN1],
            [
                make_analysis(
                    FN1, "suspected_bug", evidence=[], reason="looks more correct"
                )
            ],
            status={FN1: "survived"},
        ),
    )
    assert ms.load_records(root, "pkg.mod") == []
    assert summary["suspected_bugs"] == []
    assert [r["mutant"] for r in summary["rejected"]] == [FN1]


def test_a_citation_beyond_the_end_of_the_file_is_not_evidence(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    summary = ms.record(
        ctx,
        make_run(
            [FN1],
            [
                make_analysis(
                    FN1, "suspected_bug", evidence=["pkg/mod.py:999"], reason="r"
                )
            ],
        ),
    )
    assert summary["suspected_bugs"] == []


def test_dead_code_is_reported_every_run_and_never_stored(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    summary = ms.record(
        ctx,
        make_run(
            [FN1],
            [make_analysis(FN1, "dead_code", reason="no production caller")],
            status={FN1: "survived"},
        ),
    )
    assert summary["dead_code"] == [{"mutant": FN1, "reason": "no production caller"}]
    assert ms.load_records(root, "pkg.mod") == []
    assert ms.triage(make_ctx(root), [FN1]).to_analyze == [FN1]


def test_test_design_is_stored_and_not_attempted(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    summary = ms.record(
        ctx,
        make_run(
            [FN1],
            [make_analysis(FN1, "test_design", reason="the only test mocks fn")],
            status={FN1: "survived"},
        ),
    )
    assert summary["test_design"] == [
        {"mutant": FN1, "reason": "the only test mocks fn"}
    ]
    assert ms.triage(make_ctx(root), [FN1]).test_design == [FN1]


def test_counts_must_match_the_mutants_sent_to_analysis(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    with pytest.raises(ms.StateError, match="analysed"):
        ms.record(
            ctx,
            make_run([FN1, FN2], [make_analysis(FN1, "dead_code", reason="r")]),
        )


def test_an_analysis_for_a_mutant_that_was_not_sent_is_refused(
    root: Path, ms: Any, make_ctx: Any, make_analysis: Any, make_run: Any
) -> None:
    ctx = make_ctx(root)
    with pytest.raises(ms.StateError, match="not sent"):
        ms.record(
            ctx,
            make_run([FN1], [make_analysis(FN2, "dead_code", reason="r")]),
        )


def test_the_summary_lists_killed_deferred_and_still_surviving(
    root: Path,
    *,
    ms: Any,
    pyproject: str,
    make_ctx: Any,
    make_analysis: Any,
    make_run: Any,
) -> None:
    (root / "pyproject.toml").write_text(
        pyproject + "max_mutants_per_pass = 1\n",
        encoding="utf-8",
    )
    ctx = make_ctx(root)
    summary = ms.record(
        ctx,
        make_run(
            [FN1, FN2, OTHER1],
            [make_analysis(FN1, "dead_code", reason="r")],
            status={FN1: "survived", FN2: "killed", OTHER1: "survived"},
        ),
    )
    assert summary["deferred"] == [FN2, OTHER1]
    assert summary["killed"] == [FN2]
    assert summary["still_surviving"] == [FN1, OTHER1]
