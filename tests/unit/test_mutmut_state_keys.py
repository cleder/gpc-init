"""Tests for scripts/mutmut_state.py: keys."""

from pathlib import Path
from typing import Any

FN10 = "pkg.mod.x_fn__mutmut_10"
PUT1 = "pkg.mod.xǁBoxǁput__mutmut_1"


def test_fnv1a32_matches_the_vector_the_workflow_script_uses(ms: Any) -> None:
    assert ms.fnv1a32(["b", "a", "c"]) == 3588977911
    names = [
        "pc_init.catalog.xǁCatalogǁcommon_preset__mutmut_1",
        "pc_init.m.x_f__mutmut_2",
    ]
    assert ms.fnv1a32(names) == 3033286041


def test_blob_hash_is_the_git_blob_hash(tmp_path: Path, ms: Any) -> None:
    path = tmp_path / "f.txt"
    path.write_text("hello\n", encoding="utf-8")
    assert ms.blob_hash(path) == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_parse_mutant_reads_function_and_method_names(ms: Any) -> None:
    func = ms.parse_mutant(FN10)
    assert (func.module, func.class_name, func.function, func.number) == (
        "pkg.mod",
        None,
        "fn",
        10,
    )
    method = ms.parse_mutant(PUT1)
    assert (method.module, method.class_name, method.function, method.number) == (
        "pkg.mod",
        "Box",
        "put",
        1,
    )


def test_function_hash_ignores_comments_and_layout_but_not_code(
    ms: Any, module_source: str
) -> None:
    base = ms.function_hash(module_source, None, "fn")
    assert base
    commented = module_source.replace("return x + 1", "return x+1  # a comment")
    assert ms.function_hash(commented, None, "fn") == base
    changed = module_source.replace("return x + 1", "return x + 2")
    assert ms.function_hash(changed, None, "fn") != base


def test_function_hash_is_unaffected_by_edits_to_other_functions(
    ms: Any, module_source: str
) -> None:
    base = ms.function_hash(module_source, None, "fn")
    edited = module_source.replace("return y * 2", "return y * 3")
    assert ms.function_hash(edited, None, "fn") == base


def test_function_hash_finds_methods_and_returns_none_for_unknown_names(
    ms: Any, module_source: str
) -> None:
    assert ms.function_hash(module_source, "Box", "put")
    assert ms.function_hash(module_source, None, "missing") is None
    assert ms.function_hash(module_source, "Box", "missing") is None


def test_config_hash_ignores_test_selection_and_changes_with_mutation_settings(
    ms: Any,
) -> None:
    cfg = {"source_paths": ["pkg/"], "pytest_add_cli_args_test_selection": ["tests/"]}
    base = ms.config_hash(cfg)
    same = {"source_paths": ["pkg/"], "pytest_add_cli_args_test_selection": ["t2/"]}
    assert ms.config_hash(same) == base
    assert ms.config_hash({**cfg, "do_not_mutate_patterns": ["x"]}) != base


def test_budgets_default_when_the_workflow_table_is_absent(
    root: Path, make_ctx: Any
) -> None:
    (root / "pyproject.toml").write_text("[tool.mutmut]\n", encoding="utf-8")
    ctx = make_ctx(root)
    assert ctx.settings.max_attempts == 2
    assert ctx.settings.max_mutants_per_pass is None


def test_budgets_are_read_from_the_workflow_table(
    root: Path, pyproject: str, make_ctx: Any
) -> None:
    (root / "pyproject.toml").write_text(
        pyproject.replace("= 2", "= 3") + "max_mutants_per_pass = 5\n",
        encoding="utf-8",
    )
    ctx = make_ctx(root)
    assert ctx.settings.max_attempts == 3
    assert ctx.settings.max_mutants_per_pass == 5


def test_changing_a_budget_does_not_change_the_config_hash(
    root: Path, pyproject: str, make_ctx: Any
) -> None:
    before = make_ctx(root).config_hash
    (root / "pyproject.toml").write_text(
        pyproject.replace("= 2", "= 9"), encoding="utf-8"
    )
    assert make_ctx(root).config_hash == before
