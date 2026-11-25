"""Tests for scripts/mutmut_state.py: storage."""

import json
from pathlib import Path
from typing import Any

import pytest

FN1 = "pkg.mod.x_fn__mutmut_1"
FN2 = "pkg.mod.x_fn__mutmut_2"
OTHER1 = "pkg.mod.x_other__mutmut_1"
PUT1 = "pkg.mod.xǁBoxǁput__mutmut_1"


def test_state_is_one_file_per_module_and_survives_a_round_trip(
    root: Path, attempt: Any
) -> None:
    attempt(root, FN1)
    attempt(root, PUT1)
    path = root / ".mutmut-analysis" / "pkg.mod.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert [r["mutant"] for r in data["records"]] == [FN1, PUT1]
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_migrating_v1_keeps_matching_records_and_drops_stale_ones(
    root: Path, ms: Any, make_ctx: Any
) -> None:
    mod_path = root / "pkg" / "mod.py"
    v1 = [
        {
            "mutant_name": FN1,
            "source_file": "pkg/mod.py",
            "file_hash": ms.blob_hash(mod_path),
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
    assert ms.migrate_v1(make_ctx(root)) == (1, 1)
    [record] = ms.load_records(root, "pkg.mod")
    assert (record.mutant, record.status, record.last_reason) == (
        FN1,
        "equivalent",
        "kept",
    )
    assert ms.triage(make_ctx(root), [FN1]).equivalent == [FN1]


def test_the_cli_triage_prints_lists_with_checksums(root: Path, ms: Any) -> None:
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


def test_the_cli_refuses_a_gap_list_whose_checksum_does_not_match(
    root: Path, ms: Any
) -> None:
    with pytest.raises(ms.StateError, match="checksum"):
        ms.run_command(
            "triage",
            root,
            {"mutmut_version": "3.8.1", "gaps": [FN1], "gaps_checksum": 1},
            today="2026-11-25",
        )


def test_the_cli_record_round_trips_a_payload(root: Path, ms: Any) -> None:
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
