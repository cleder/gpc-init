"""Tests for scripts/mutmut_state.py: request validation."""

from typing import Any

import pytest

FN1 = "pkg.mod.x_fn__mutmut_1"


@pytest.fixture
def payload(state: Any) -> dict[str, Any]:
    """Return a valid record request."""
    return {
        "mutmut_version": "3.8.1",
        "gaps": [FN1],
        "gaps_checksum": state.ms.fnv1a32([FN1]),
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


def _record(state: Any, payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = state.ms.run_command(
        "record",
        state.root,
        payload,
        today="2026-11-25",
    )
    return out


def test_a_valid_record_request_is_accepted(
    state: Any, payload: dict[str, Any]
) -> None:
    assert _record(state, payload)["killed"] == [FN1]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("verify_ok", "false"),
        ("verify_ok", 1),
        ("gaps", "pkg.mod.x_fn__mutmut_1"),
        ("gaps", [1]),
        ("analyses", "none"),
        ("analyses", ["not an object"]),
        ("written", "all"),
        ("write_failures", {FN1: 3}),
        ("write_failures", []),
        ("config_problems", [None]),
        ("unanalyzed", {}),
        ("status", {FN1: None}),
        ("status", [FN1]),
        ("mutmut_version", 3),
    ],
)
def test_a_malformed_field_is_refused_and_named(
    state: Any,
    payload: dict[str, Any],
    field: str,
    value: object,
) -> None:
    payload[field] = value
    with pytest.raises(state.ms.StateError, match=field):
        _record(state, payload)


def test_a_missing_field_is_named(state: Any, payload: dict[str, Any]) -> None:
    del payload["verify_ok"]
    with pytest.raises(state.ms.StateError, match="verify_ok"):
        _record(state, payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("colour", "red"), ("evidence", "path:1"), ("depends_on", [1]), ("reason", 5)],
)
def test_an_analysis_with_a_bad_field_is_refused(
    state: Any,
    payload: dict[str, Any],
    field: str,
    value: object,
) -> None:
    payload["analyses"][0][field] = value
    with pytest.raises(state.ms.StateError, match="analysis"):
        _record(state, payload)


def test_a_triage_request_needs_a_list_of_names(state: Any) -> None:
    with pytest.raises(state.ms.StateError, match="gaps"):
        state.ms.run_command(
            "triage",
            state.root,
            {"mutmut_version": "3.8.1", "gaps": [FN1, 2], "gaps_checksum": 1},
            today="2026-11-25",
        )


def _signed(state: Any, body: str) -> str:
    return f"#fnv1a32 {state.ms.fnv1a32([body])}\n{body}"


def test_a_signed_request_is_decoded(state: Any) -> None:
    text = _signed(state, '{"gaps": ["é"], "written": []}')
    assert state.ms.decode_request(text) == {"gaps": ["é"], "written": []}


def test_a_request_altered_in_transit_is_refused(state: Any) -> None:
    text = _signed(state, '{"written": ["a", "b"]}')
    altered = text.replace('"a", "b"', "")
    with pytest.raises(state.ms.StateError, match="checksum"):
        state.ms.decode_request(altered)


@pytest.mark.parametrize("text", ['{"gaps": []}', "", "#fnv1a32 x\n{}"])
def test_an_unsigned_request_is_refused(state: Any, text: str) -> None:
    with pytest.raises(state.ms.StateError, match="checksum"):
        state.ms.decode_request(text)


def test_a_trailing_newline_after_the_body_is_not_an_alteration(state: Any) -> None:
    text = _signed(state, '{"a": 1}') + "\n"
    assert state.ms.decode_request(text) == {"a": 1}
