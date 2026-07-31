"""Unit tests for gpc_init/util.py."""

from gpc_init.util import deduplicate_preserving_order


class TestDeduplicatePreservingOrder:
    def test_removes_duplicates(self) -> None:
        assert deduplicate_preserving_order(["py", "js", "py"]) == ["py", "js"]

    def test_preserves_first_occurrence(self) -> None:
        assert deduplicate_preserving_order(["js", "py", "js"]) == ["js", "py"]

    def test_empty_list(self) -> None:
        assert deduplicate_preserving_order([]) == []

    def test_no_duplicates(self) -> None:
        assert deduplicate_preserving_order(["py", "js"]) == ["py", "js"]
