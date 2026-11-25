#!/usr/bin/env python3
"""
State helper of the ``mutmut-kill-survivors`` workflow.

The workflow's agents propose tests and verdicts; this script decides what counts
as an attempt, which mutants are parked, which stay known and which reopen. It is
plain deterministic code with a small JSON-in/JSON-out command line::

    mutmut_state.py triage  < request   split the unkilled mutants
    mutmut_state.py record  < request   count attempts, park, persist, summarise
    mutmut_state.py migrate < request   one-off: .mutmut-equivalents.json -> v2

A request is a line ``#fnv1a32 <n>`` followed by one line of JSON. ``n`` is the
checksum of that JSON text, so a request an agent retyped differently is refused
instead of being read as something else.

State lives in ``.mutmut-analysis/<dotted.module>.json``, one file per module. A
record is keyed by the mutant's function hash, the mutmut version and the hash of
the mutation settings in ``[tool.mutmut]``, and it lists the files its verdict
rests on with their hashes. Any change to those reopens the mutant. The budgets
(``max_attempts_per_mutant``, ``max_mutants_per_pass``) live in
``[tool.mutmut-workflow]`` and are not part of the key.

Exits 0 on success and 1 on a bad request, printing ``{"error": ...}``.
"""

import argparse
import ast
import hashlib
import json
import re
import sys
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

STATE_DIR = ".mutmut-analysis"
V1_FILE = ".mutmut-equivalents.json"
STATE_VERSION = 2
DEFAULT_MAX_ATTEMPTS = 2
GAP_STATUSES = ("survived", "no tests")
# Settings that choose which tests run, not which mutants exist.
TEST_SELECTION_KEYS = frozenset(
    {"pytest_add_cli_args_test_selection", "pytest_add_cli_args", "tests_dir"},
)
CLASS_SEPARATOR = "ǁ"
FNV_OFFSET = 0x811C9DC5
FNV_PRIME = 0x01000193
MASK_32 = 0xFFFFFFFF
MUTANT = re.compile(r"^(?P<module>.+)\.(?P<base>[^.]+)__mutmut_(?P<number>\d+)$")
SIGNATURE = re.compile(r"^#fnv1a32 (?P<sum>\d+)\n")
CITATION = re.compile(r"(?P<path>[\w@~./+-]+\.\w+):(?P<line>\d+)")

OUTCOMES = ("suspected_bug", "dead_code", "test_design", "equivalent", "missing_test")
LISTS = (
    "equivalent",
    "test_design",
    "suspected_bug",
    "parked",
    "deferred",
    "to_analyze",
)


class StateError(Exception):
    """The request or the stored state cannot be used."""


# ─── hashing and parsing ──────────────────────────────────────────────────────


def fnv1a32(names: Iterable[str]) -> int:
    """Return FNV-1a 32 over the UTF-8 bytes of the sorted names joined by newlines."""
    value = FNV_OFFSET
    for byte in "\n".join(sorted(names)).encode():
        value = ((value ^ byte) * FNV_PRIME) & MASK_32
    return value


def blob_hash(path: Path) -> str:
    """Return the git blob hash of a file, as ``git hash-object`` prints it."""
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


@dataclass(frozen=True)
class MutantRef:
    """The parts of a mutmut mutant name."""

    module: str
    class_name: str | None
    function: str
    number: int


def parse_mutant(name: str) -> MutantRef:
    """Split ``pkg.mod.x_fn__mutmut_3`` or ``pkg.mod.xǁClassǁfn__mutmut_3``."""
    match = MUTANT.match(name)
    if match is None:
        raise _not_a_mutant(name)
    base, number = match["base"], int(match["number"])
    if base.startswith(f"x{CLASS_SEPARATOR}"):
        _, class_name, *function = base.split(CLASS_SEPARATOR)
        return MutantRef(
            match["module"], class_name, CLASS_SEPARATOR.join(function), number
        )
    if base.startswith("x_"):
        return MutantRef(match["module"], None, base[2:], number)
    raise _not_a_mutant(name)


def _not_a_mutant(name: str) -> StateError:
    return StateError(f"not a mutmut mutant name: {name}")


def mutant_sort_key(name: str) -> tuple[str, str, str, int]:
    """Order mutants by module, class, function and mutant number."""
    ref = parse_mutant(name)
    return (ref.module, ref.class_name or "", ref.function, ref.number)


def _scope(tree: ast.Module, class_name: str | None) -> list[ast.stmt]:
    """Return the statements a function is looked up in: the module or one class."""
    if class_name is None:
        return tree.body
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node.body
    return []


def function_hash(source: str, class_name: str | None, function: str) -> str | None:
    """Hash one function's syntax tree, so layout and comments do not matter."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in _scope(tree, class_name):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
            node.name == function
        ):
            return hashlib.sha256(ast.dump(node).encode()).hexdigest()
    return None


def config_hash(config: Mapping[str, Any]) -> str:
    """Hash the mutation settings, leaving out the test selection."""
    kept = {k: v for k, v in config.items() if k not in TEST_SELECTION_KEYS}
    text = json.dumps(kept, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


# ─── settings and context ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Settings:
    """The workflow's budgets."""

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    max_mutants_per_pass: int | None = None


@dataclass(frozen=True)
class Context:
    """Everything a decision depends on besides the mutants themselves."""

    root: Path
    mutmut_version: str
    today: str
    settings: Settings
    config_hash: str


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _positive(table: Mapping[str, Any], key: str) -> int | None:
    value = table.get(key)
    if value is None:
        return None
    if not _is_positive_int(value):
        msg = f"[tool.mutmut-workflow] {key} must be a positive integer"
        raise StateError(msg)
    return cast("int", value)


def load_context(root: Path, *, mutmut_version: str, today: str) -> Context:
    """Read the budgets and the mutation settings from ``pyproject.toml``."""
    path = root / "pyproject.toml"
    tool: dict[str, Any] = {}
    if path.is_file():
        tool = tomllib.loads(path.read_text(encoding="utf-8")).get("tool", {})
    workflow = tool.get("mutmut-workflow", {})
    settings = Settings(
        max_attempts=_positive(workflow, "max_attempts_per_mutant")
        or DEFAULT_MAX_ATTEMPTS,
        max_mutants_per_pass=_positive(workflow, "max_mutants_per_pass"),
    )
    return Context(
        root=root,
        mutmut_version=mutmut_version,
        today=today,
        settings=settings,
        config_hash=config_hash(tool.get("mutmut", {})),
    )


# ─── records and storage ──────────────────────────────────────────────────────


@dataclass
class Record:
    """What is known about one mutant."""

    mutant: str
    status: str
    function_hash: str
    mutmut_version: str
    config_hash: str
    dependencies: dict[str, str] = field(default_factory=dict)
    attempts: int = 0
    history: list[dict[str, str]] = field(default_factory=list)
    last_reason: str = ""
    evidence: list[str] = field(default_factory=list)
    summary: str = ""


def _state_path(root: Path, module: str) -> Path:
    return root / STATE_DIR / f"{module}.json"


def load_records(root: Path, module: str) -> list[Record]:
    """Return the stored records of one module."""
    path = _state_path(root, module)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Record(**item) for item in data["records"]]


def _save_records(root: Path, module: str, records: list[Record]) -> None:
    path = _state_path(root, module)
    if not records:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": STATE_VERSION,
        "module": module,
        "records": [
            asdict(r) for r in sorted(records, key=lambda r: mutant_sort_key(r.mutant))
        ],
    }
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _source_path(root: Path, module: str) -> Path | None:
    relative = Path(*module.split("."))
    for base in (root, root / "src"):
        for candidate in (
            base / relative.with_suffix(".py"),
            base / relative / "__init__.py",
        ):
            if candidate.is_file():
                return candidate
    return None


def current_function_hash(ctx: Context, ref: MutantRef) -> str | None:
    """Return the hash of the mutant's function as it is on disk now."""
    path = _source_path(ctx.root, ref.module)
    if path is None:
        return None
    source = path.read_text(encoding="utf-8")
    return function_hash(source, ref.class_name, ref.function)


def _resolve(ctx: Context, name: str) -> Path:
    path = Path(name)
    return path if path.is_absolute() else ctx.root / path


def _unchanged(ctx: Context, name: str, recorded: str) -> bool:
    path = _resolve(ctx, name)
    return path.is_file() and blob_hash(path) == recorded


def is_current(ctx: Context, record: Record, current_hash: str | None) -> bool:
    """Return whether the record is valid for the code, mutmut and settings now."""
    same_key = (
        current_hash is not None
        and record.function_hash == current_hash
        and record.mutmut_version == ctx.mutmut_version
        and record.config_hash == ctx.config_hash
    )
    return same_key and all(
        _unchanged(ctx, name, recorded)
        for name, recorded in record.dependencies.items()
    )


class Store:
    """The records of the modules a run touches, loaded once and written once."""

    def __init__(self, ctx: Context) -> None:
        """Start with nothing loaded."""
        self.ctx = ctx
        self._modules: dict[str, dict[str, Record]] = {}
        self._written: set[str] = set()
        self._touched: set[str] = set()

    def _module(self, module: str) -> dict[str, Record]:
        if module not in self._modules:
            self._modules[module] = {
                r.mutant: r for r in load_records(self.ctx.root, module)
            }
        return self._modules[module]

    def current(self, name: str) -> Record | None:
        """Return the mutant's record if it is still valid."""
        ref = parse_mutant(name)
        record = self._module(ref.module).get(name)
        if record is None:
            return None
        if name in self._written:
            return record
        if is_current(self.ctx, record, current_function_hash(self.ctx, ref)):
            return record
        return None

    def put(self, record: Record) -> None:
        """Store a record written in this run."""
        module = parse_mutant(record.mutant).module
        self._module(module)[record.mutant] = record
        self._written.add(record.mutant)
        self._touched.add(module)

    def delete(self, name: str) -> None:
        """Forget a mutant, for example because it is killed."""
        module = parse_mutant(name).module
        if self._module(module).pop(name, None) is not None:
            self._touched.add(module)

    def flush(self) -> None:
        """Write the touched modules, dropping records that are no longer valid."""
        for module in sorted(self._touched):
            records = self._modules[module]
            keep = [r for name in records if (r := self.current(name)) is not None]
            _save_records(self.ctx.root, module, keep)


# ─── triage ───────────────────────────────────────────────────────────────────


@dataclass
class Triage:
    """The unkilled mutants split by what happens to them this run."""

    equivalent: list[str] = field(default_factory=list)
    test_design: list[str] = field(default_factory=list)
    suspected_bug: list[str] = field(default_factory=list)
    parked: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    to_analyze: list[str] = field(default_factory=list)


def _triage(store: Store, gaps: Iterable[str]) -> Triage:
    result = Triage()
    candidates: list[str] = []
    for name in sorted(set(gaps), key=mutant_sort_key):
        record = store.current(name)
        if record is None or record.status == "open":
            candidates.append(name)
        else:
            getattr(result, record.status).append(name)
    limit = store.ctx.settings.max_mutants_per_pass
    cut = len(candidates) if limit is None else limit
    result.to_analyze = candidates[:cut]
    result.deferred = candidates[cut:]
    return result


def triage(ctx: Context, gaps: Iterable[str]) -> Triage:
    """Split the unkilled mutants into known, parked, deferred and to-analyse."""
    return _triage(Store(ctx), gaps)


# ─── recording ────────────────────────────────────────────────────────────────


@dataclass
class Analysis:
    """One analysis verdict, as an agent proposed it."""

    mutant: str
    outcome: str
    evidence: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    reason: str = ""
    summary: str = ""
    test_file: str = ""
    test_name: str = ""


@dataclass
class Run:
    """What happened in one workflow pass."""

    gaps: list[str]
    analyses: list[Analysis]
    written: list[str]
    write_failures: dict[str, str]
    config_problems: list[str]
    unanalyzed: list[str]
    verify_ok: bool
    status: dict[str, str]


def _citations(ctx: Context, evidence: Iterable[str]) -> list[str]:
    """Return the files cited as ``path:line`` where that line exists."""
    paths: list[str] = []
    for text in evidence:
        for match in CITATION.finditer(text):
            path = _resolve(ctx, match["path"])
            if not path.is_file():
                continue
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            if 1 <= int(match["line"]) <= lines and match["path"] not in paths:
                paths.append(match["path"])
    return paths


def _dependencies(
    ctx: Context,
    analysis: Analysis,
    *,
    cited_required: bool,
) -> dict[str, str]:
    """Hash the declared and cited files, or raise why the verdict cannot be kept."""
    cited = _citations(ctx, analysis.evidence)
    if cited_required and not cited:
        msg = "the verdict must cite its evidence as path:line, naming a real line"
        raise StateError(msg)
    paths = list(dict.fromkeys([*cited, *analysis.depends_on]))
    missing = [p for p in paths if not _resolve(ctx, p).is_file()]
    if missing:
        msg = f"depends_on names files that do not exist: {', '.join(missing)}"
        raise StateError(msg)
    return {p: blob_hash(_resolve(ctx, p)) for p in paths}


def _new_record(ctx: Context, analysis: Analysis, key: str) -> Record:
    return Record(
        mutant=analysis.mutant,
        status="open",
        function_hash=key,
        mutmut_version=ctx.mutmut_version,
        config_hash=ctx.config_hash,
        last_reason=analysis.reason,
        evidence=list(analysis.evidence),
        summary=analysis.summary,
    )


def _validate_counts(sent: list[str], run: Run) -> None:
    analysed = [a.mutant for a in run.analyses]
    reported = [*analysed, *run.unanalyzed]
    if len(set(reported)) != len(reported):
        msg = "a mutant was analysed or reported as unanalysed twice"
        raise StateError(msg)
    extra = sorted(set(reported) - set(sent))
    if extra:
        msg = f"{extra[0]} was not sent to analysis"
        raise StateError(msg)
    missing = sorted(set(sent) - set(reported))
    if missing:
        msg = (
            f"{len(missing)} mutant(s) sent to analysis were not analysed "
            f"or reported as unanalysed: {missing[0]}"
        )
        raise StateError(msg)


@dataclass
class _Findings:
    """What one pass concluded that is not stored."""

    dead_code: list[dict[str, str]] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    unresolved: set[str] = field(default_factory=set)
    config_problems: set[str] = field(default_factory=set)


class _Pass:
    """One recording pass: applies the analyses of a run to the stored state."""

    def __init__(self, store: Store, run: Run) -> None:
        """Start with no findings."""
        self.store = store
        self.run = run
        self.findings = _Findings()

    def apply(self) -> _Findings:
        """Apply every analysis, then forget the mutants that are now killed."""
        for analysis in sorted(
            self.run.analyses, key=lambda a: mutant_sort_key(a.mutant)
        ):
            self._one(analysis)
        self.findings.unresolved.update(self.run.unanalyzed)
        for name in self.run.gaps:
            if self.run.status.get(name) == "killed":
                self.store.delete(name)
        return self.findings

    def _reject(self, analysis: Analysis, why: str) -> None:
        self.findings.rejected.append(
            {"mutant": analysis.mutant, "outcome": analysis.outcome, "why": why},
        )
        self.findings.unresolved.add(analysis.mutant)

    def _one(self, analysis: Analysis) -> None:
        if analysis.outcome not in OUTCOMES:
            msg = f"unknown outcome {analysis.outcome!r} for {analysis.mutant}"
            raise StateError(msg)
        if analysis.outcome == "dead_code":
            self.findings.dead_code.append(
                {"mutant": analysis.mutant, "reason": analysis.reason},
            )
            return
        key = current_function_hash(self.store.ctx, parse_mutant(analysis.mutant))
        if key is None:
            self._reject(analysis, "the mutant's function was not found in its source")
        elif analysis.outcome == "missing_test":
            self._missing_test(analysis, key)
        else:
            self._verdict(analysis, key)

    def _verdict(self, analysis: Analysis, key: str) -> None:
        """Store an equivalent, suspected_bug or test_design verdict, or reject it."""
        try:
            dependencies = _dependencies(
                self.store.ctx,
                analysis,
                cited_required=analysis.outcome in {"equivalent", "suspected_bug"},
            )
        except StateError as error:
            self._reject(analysis, str(error))
            return
        record = _new_record(self.store.ctx, analysis, key)
        record.status = analysis.outcome
        record.dependencies = dependencies
        self.store.put(record)

    def _missing_test(self, analysis: Analysis, key: str) -> None:
        name = analysis.mutant
        if name in self.run.config_problems:
            self.findings.config_problems.add(name)
        elif name in self.run.write_failures:
            self._attempt(analysis, key, self.run.write_failures[name])
        else:
            self._verified(analysis, key)

    def _verified(self, analysis: Analysis, key: str) -> None:
        """Judge a mutant a test was written for by what Verify saw."""
        name = analysis.mutant
        if name not in self.run.written or not self.run.verify_ok:
            self.findings.unresolved.add(name)
            return
        outcome = self.run.status.get(name)
        if outcome == "survived":
            reason = f"test {analysis.test_name} written; the mutant still survives"
            self._attempt(analysis, key, reason)
        elif outcome in {None, "no tests"}:
            self.findings.unresolved.add(name)

    def _attempt(self, analysis: Analysis, key: str, reason: str) -> None:
        """Count one failed attempt and park the mutant at the budget."""
        ctx = self.store.ctx
        record = self.store.current(analysis.mutant) or _new_record(ctx, analysis, key)
        record.attempts += 1
        record.last_reason = reason
        record.summary = analysis.summary or record.summary
        record.history.append(
            {
                "date": ctx.today,
                "reason": reason,
                "test_file": analysis.test_file,
                "test_name": analysis.test_name,
            },
        )
        parked = record.attempts >= ctx.settings.max_attempts
        record.status = "parked" if parked else "open"
        self.store.put(record)


def _records_with(store: Store, gaps: list[str], status: str) -> list[Record]:
    found = [store.current(g) for g in sorted(set(gaps), key=mutant_sort_key)]
    return [r for r in found if r is not None and r.status == status]


def record(ctx: Context, run: Run) -> dict[str, Any]:
    """Count the pass, update the state files and return the summary."""
    store = Store(ctx)
    split = _triage(store, run.gaps)
    _validate_counts(split.to_analyze, run)
    findings = _Pass(store, run).apply()
    summary = _summary(store, run, split, findings)
    store.flush()
    return summary


def _killed(run: Run, gaps: list[str]) -> list[str]:
    return [g for g in gaps if run.status.get(g) == "killed"]


def _other(run: Run, gaps: list[str]) -> list[dict[str, str]]:
    states = {g: run.status.get(g, "survived") for g in gaps}
    return [
        {"mutant": g, "status": s}
        for g, s in states.items()
        if s not in {"killed", *GAP_STATUSES}
    ]


def _still(run: Run, gaps: list[str]) -> list[str]:
    return [g for g in gaps if run.status.get(g, "survived") in GAP_STATUSES]


def _row(record: Record) -> dict[str, Any]:
    return {"mutant": record.mutant, "reason": record.last_reason}


def _parked_row(record: Record) -> dict[str, Any]:
    return {
        "mutant": record.mutant,
        "attempts": record.attempts,
        "last_reason": record.last_reason,
        "summary": record.summary,
        "history": record.history,
    }


def _bug_row(record: Record) -> dict[str, Any]:
    return {**_row(record), "evidence": record.evidence}


def _summary(
    store: Store,
    run: Run,
    split: Triage,
    findings: _Findings,
) -> dict[str, Any]:
    gaps = sorted(set(run.gaps), key=mutant_sort_key)
    still = _still(run, gaps)

    def listed(status: str) -> list[Record]:
        return _records_with(store, still, status)

    return {
        "killed": _killed(run, gaps),
        "equivalent": [_row(r) for r in listed("equivalent")],
        "parked": [_parked_row(r) for r in listed("parked")],
        "deferred": split.deferred,
        "suspected_bugs": [_bug_row(r) for r in listed("suspected_bug")],
        "dead_code": findings.dead_code,
        "test_design": [_row(r) for r in listed("test_design")],
        "unresolved": sorted(findings.unresolved, key=mutant_sort_key),
        "other": _other(run, gaps),
        "still_surviving": still,
        "rejected": findings.rejected,
        "config_problems": sorted(findings.config_problems, key=mutant_sort_key),
    }


# ─── migration ────────────────────────────────────────────────────────────────


def migrate_v1(ctx: Context) -> tuple[int, int]:
    """
    Move ``.mutmut-equivalents.json`` into the per-module state.

    A record whose source file still has the recorded hash and whose function is
    still found is kept. The rest was already invalid under the old key.
    Returns ``(migrated, dropped)``.
    """
    path = ctx.root / V1_FILE
    if not path.is_file():
        return (0, 0)
    store = Store(ctx)
    migrated = dropped = 0
    for entry in json.loads(path.read_text(encoding="utf-8")):
        source = ctx.root / entry["source_file"]
        key = None
        if source.is_file() and blob_hash(source) == entry["file_hash"]:
            key = current_function_hash(ctx, parse_mutant(entry["mutant_name"]))
        if key is None:
            dropped += 1
            continue
        store.put(
            Record(
                mutant=entry["mutant_name"],
                status="equivalent",
                function_hash=key,
                mutmut_version=ctx.mutmut_version,
                config_hash=ctx.config_hash,
                last_reason=entry["equivalent_reason"],
                evidence=[f"migrated from {V1_FILE}"],
            ),
        )
        migrated += 1
    store.flush()
    return (migrated, dropped)


# ─── command line ─────────────────────────────────────────────────────────────


ANALYSIS_STRINGS = ("mutant", "outcome", "reason", "summary", "test_file", "test_name")
ANALYSIS_LISTS = ("evidence", "depends_on")


def _require(ok: object, message: str) -> None:
    if not ok:
        raise StateError(message)


def _is_kind(value: object, kind: type) -> bool:
    """Return whether the value has the type; a bool is not an int here."""
    if kind is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, kind)


def _is_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _is_string_map(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return _is_strings(list(value)) and _is_strings(list(value.values()))


def _field[T](payload: Mapping[str, Any], key: str, kind: type[T]) -> T:
    """Return a request field of one type, or raise naming the field."""
    _require(key in payload, f"missing field: {key}")
    value = payload[key]
    _require(_is_kind(value, kind), f"field {key} must be a {kind.__name__}")
    return value


def _strings(value: object, key: str) -> list[str]:
    _require(_is_strings(value), f"field {key} must be a list of strings")
    return cast("list[str]", value)


def _string_map(value: object, key: str) -> dict[str, str]:
    _require(_is_string_map(value), f"field {key} must be an object of strings")
    return cast("dict[str, str]", value)


def _checked(payload: Mapping[str, Any], key: str) -> list[str]:
    names = _strings(_field(payload, key, list), key)
    if fnv1a32(names) != _field(payload, f"{key}_checksum", int):
        msg = f"checksum mismatch for {key}: the relayed list differs from its source"
        raise StateError(msg)
    return names


def _listed(names: list[str]) -> dict[str, Any]:
    return {"names": names, "checksum": fnv1a32(names)}


def _analysis_from(item: object) -> Analysis:
    """Build one analysis from a request entry, refusing anything unexpected."""
    _require(isinstance(item, dict), "field analyses must contain objects")
    try:
        analysis = Analysis(**cast("dict[str, Any]", item))
    except TypeError as error:
        msg = f"analysis entry is not valid: {error}"
        raise StateError(msg) from error
    for key in ANALYSIS_STRINGS:
        message = f"analysis field {key} must be a string"
        _require(isinstance(getattr(analysis, key), str), message)
    for key in ANALYSIS_LISTS:
        message = f"analysis field {key} must be a list of strings"
        _require(_is_strings(getattr(analysis, key)), message)
    return analysis


def _run_from(payload: Mapping[str, Any]) -> Run:
    return Run(
        gaps=_checked(payload, "gaps"),
        analyses=[_analysis_from(a) for a in _field(payload, "analyses", list)],
        written=_strings(_field(payload, "written", list), "written"),
        write_failures=_string_map(
            _field(payload, "write_failures", dict),
            "write_failures",
        ),
        config_problems=_strings(
            _field(payload, "config_problems", list),
            "config_problems",
        ),
        unanalyzed=_strings(_field(payload, "unanalyzed", list), "unanalyzed"),
        verify_ok=_field(payload, "verify_ok", bool),
        status=_string_map(_field(payload, "status", dict), "status"),
    )


def run_command(
    command: str,
    root: Path,
    payload: Mapping[str, Any],
    *,
    today: str,
) -> dict[str, Any]:
    """Run one command on a decoded request and return the decoded response."""
    version = _field(payload, "mutmut_version", str)
    ctx = load_context(root, mutmut_version=version, today=today)
    if command == "triage":
        split = triage(ctx, _checked(payload, "gaps"))
        return {name: _listed(getattr(split, name)) for name in LISTS}
    if command == "record":
        return record(ctx, _run_from(payload))
    if command == "migrate":
        migrated, dropped = migrate_v1(ctx)
        return {"migrated": migrated, "dropped": dropped}
    msg = f"unknown command: {command}"
    raise StateError(msg)


def decode_request(text: str) -> dict[str, Any]:
    """Check the request's checksum line and decode its JSON body."""
    match = SIGNATURE.match(text)
    if match is None:
        msg = "request checksum missing: the first line must be '#fnv1a32 <number>'"
        raise StateError(msg)
    body = text[match.end() :].rstrip("\n")
    if fnv1a32([body]) != int(match["sum"]):
        msg = "request checksum mismatch: the request was altered in transit"
        raise StateError(msg)
    request = json.loads(body)
    _require(isinstance(request, dict), "the request must be a JSON object")
    return cast("dict[str, Any]", request)


def main(argv: list[str] | None = None) -> int:
    """Read a JSON request on stdin, print the JSON response."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("command", choices=["triage", "record", "migrate"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        payload = decode_request("" if sys.stdin.isatty() else sys.stdin.read())
        today = datetime.now(UTC).date().isoformat()
        out = run_command(args.command, args.root, payload, today=today)
    except (StateError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}))  # noqa: T201
        return 1
    print(json.dumps(out, sort_keys=True))  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
