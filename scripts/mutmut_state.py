#!/usr/bin/env python3
"""
State helper of the ``mutmut-kill-survivors`` workflow.

The workflow's agents propose tests and verdicts; this script decides what counts
as an attempt, which mutants are parked, which stay known and which reopen. It is
plain deterministic code with a small JSON-in/JSON-out command line::

    mutmut_state.py triage  < request.json   split the unkilled mutants
    mutmut_state.py record  < request.json   count attempts, park, persist, summarise
    mutmut_state.py migrate                  one-off: .mutmut-equivalents.json -> v2

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
    module, _, tail = name.rpartition(".")
    base, separator, number = tail.rpartition("__mutmut_")
    if not (module and separator and number.isdigit()):
        msg = f"not a mutmut mutant name: {name}"
        raise StateError(msg)
    if base.startswith(f"x{CLASS_SEPARATOR}"):
        _, class_name, *function = base.split(CLASS_SEPARATOR)
        return MutantRef(
            module, class_name, CLASS_SEPARATOR.join(function), int(number)
        )
    if base.startswith("x_"):
        return MutantRef(module, None, base[2:], int(number))
    msg = f"not a mutmut mutant name: {name}"
    raise StateError(msg)


def mutant_sort_key(name: str) -> tuple[str, str, str, int]:
    """Order mutants by module, class, function and mutant number."""
    ref = parse_mutant(name)
    return (ref.module, ref.class_name or "", ref.function, ref.number)


def function_hash(source: str, class_name: str | None, function: str) -> str | None:
    """Hash one function's syntax tree, so layout and comments do not matter."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    scope: list[ast.stmt] = tree.body
    if class_name is not None:
        classes = [
            node
            for node in scope
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if not classes:
            return None
        scope = classes[0].body
    for node in scope:
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


def _positive(table: Mapping[str, Any], key: str) -> int | None:
    value = table.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        msg = f"[tool.mutmut-workflow] {key} must be a positive integer"
        raise StateError(msg)
    return value


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


def is_current(ctx: Context, record: Record, current_hash: str | None) -> bool:
    """Return whether the record is valid for the code, mutmut and settings now."""
    if current_hash is None or record.function_hash != current_hash:
        return False
    if record.mutmut_version != ctx.mutmut_version:
        return False
    if record.config_hash != ctx.config_hash:
        return False
    for name, recorded in record.dependencies.items():
        path = _resolve(ctx, name)
        if not path.is_file() or blob_hash(path) != recorded:
            return False
    return True


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


def _new_record(
    ctx: Context,
    analysis: Analysis,
    status: str,
    key: str,
    dependencies: dict[str, str],
) -> Record:
    return Record(
        mutant=analysis.mutant,
        status=status,
        function_hash=key,
        mutmut_version=ctx.mutmut_version,
        config_hash=ctx.config_hash,
        dependencies=dependencies,
        last_reason=analysis.reason,
        evidence=list(analysis.evidence),
        summary=analysis.summary,
    )


def _attempt(
    store: Store,
    analysis: Analysis,
    key: str,
    reason: str,
) -> None:
    """Count one failed attempt and park the mutant at the budget."""
    ctx = store.ctx
    existing = store.current(analysis.mutant)
    record = existing or _new_record(ctx, analysis, "open", key, {})
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
    record.status = "parked" if record.attempts >= ctx.settings.max_attempts else "open"
    store.put(record)


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


def _store_verdict(
    store: Store,
    analysis: Analysis,
    key: str,
    findings: _Findings,
) -> None:
    status = analysis.outcome
    try:
        dependencies = _dependencies(
            store.ctx,
            analysis,
            cited_required=status in {"equivalent", "suspected_bug"},
        )
    except StateError as error:
        findings.rejected.append(
            {"mutant": analysis.mutant, "outcome": status, "why": str(error)},
        )
        findings.unresolved.add(analysis.mutant)
        return
    store.put(_new_record(store.ctx, analysis, status, key, dependencies))


def _missing_test(
    store: Store,
    analysis: Analysis,
    key: str,
    run: Run,
    findings: _Findings,
) -> None:
    name = analysis.mutant
    if name in run.config_problems:
        findings.config_problems.add(name)
    elif name in run.write_failures:
        _attempt(store, analysis, key, run.write_failures[name])
    elif name not in run.written or not run.verify_ok:
        findings.unresolved.add(name)
    else:
        outcome = run.status.get(name)
        if outcome == "survived":
            reason = f"test {analysis.test_name} written; the mutant still survives"
            _attempt(store, analysis, key, reason)
        elif outcome == "no tests" or outcome is None:
            findings.unresolved.add(name)


def _apply(store: Store, run: Run) -> _Findings:
    findings = _Findings(config_problems=set())
    for analysis in sorted(run.analyses, key=lambda a: mutant_sort_key(a.mutant)):
        if analysis.outcome not in OUTCOMES:
            msg = f"unknown outcome {analysis.outcome!r} for {analysis.mutant}"
            raise StateError(msg)
        if analysis.outcome == "dead_code":
            findings.dead_code.append(
                {"mutant": analysis.mutant, "reason": analysis.reason},
            )
            continue
        key = current_function_hash(store.ctx, parse_mutant(analysis.mutant))
        if key is None:
            findings.rejected.append(
                {
                    "mutant": analysis.mutant,
                    "outcome": analysis.outcome,
                    "why": "the mutant's function was not found in its source",
                },
            )
            findings.unresolved.add(analysis.mutant)
        elif analysis.outcome == "missing_test":
            _missing_test(store, analysis, key, run, findings)
        else:
            _store_verdict(store, analysis, key, findings)
    findings.unresolved.update(run.unanalyzed)
    for name in run.gaps:
        if run.status.get(name) == "killed":
            store.delete(name)
    return findings


def _records_with(store: Store, gaps: list[str], status: str) -> list[Record]:
    found = [store.current(g) for g in sorted(set(gaps), key=mutant_sort_key)]
    return [r for r in found if r is not None and r.status == status]


def record(ctx: Context, run: Run) -> dict[str, Any]:
    """Count the pass, update the state files and return the summary."""
    store = Store(ctx)
    split = _triage(store, run.gaps)
    _validate_counts(split.to_analyze, run)
    findings = _apply(store, run)
    summary = _summary(store, run, split, findings)
    store.flush()
    return summary


def _summary(
    store: Store,
    run: Run,
    split: Triage,
    findings: _Findings,
) -> dict[str, Any]:
    gaps = sorted(set(run.gaps), key=mutant_sort_key)
    killed = [g for g in gaps if run.status.get(g) == "killed"]
    other = [
        {"mutant": g, "status": run.status[g]}
        for g in gaps
        if run.status.get(g, "survived") not in {"killed", *GAP_STATUSES}
    ]
    still = [
        g
        for g in gaps
        if run.status.get(g, "survived") in GAP_STATUSES and g not in killed
    ]

    def listed(status: str) -> list[Record]:
        return _records_with(store, still, status)

    return {
        "killed": killed,
        "equivalent": [
            {"mutant": r.mutant, "reason": r.last_reason} for r in listed("equivalent")
        ],
        "parked": [
            {
                "mutant": r.mutant,
                "attempts": r.attempts,
                "last_reason": r.last_reason,
                "summary": r.summary,
                "history": r.history,
            }
            for r in listed("parked")
        ],
        "deferred": split.deferred,
        "suspected_bugs": [
            {"mutant": r.mutant, "reason": r.last_reason, "evidence": r.evidence}
            for r in listed("suspected_bug")
        ],
        "dead_code": findings.dead_code,
        "test_design": [
            {"mutant": r.mutant, "reason": r.last_reason} for r in listed("test_design")
        ],
        "unresolved": sorted(findings.unresolved, key=mutant_sort_key),
        "other": other,
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


def _checked(payload: Mapping[str, Any], key: str) -> list[str]:
    names = cast("list[str]", payload[key])
    if fnv1a32(names) != payload[f"{key}_checksum"]:
        msg = f"checksum mismatch for {key}: the relayed list differs from its source"
        raise StateError(msg)
    return names


def _listed(names: list[str]) -> dict[str, Any]:
    return {"names": names, "checksum": fnv1a32(names)}


def _run_from(payload: Mapping[str, Any]) -> Run:
    return Run(
        gaps=_checked(payload, "gaps"),
        analyses=[Analysis(**a) for a in payload["analyses"]],
        written=list(payload["written"]),
        write_failures=dict(payload["write_failures"]),
        config_problems=list(payload["config_problems"]),
        unanalyzed=list(payload["unanalyzed"]),
        verify_ok=bool(payload["verify_ok"]),
        status=dict(payload["status"]),
    )


def run_command(
    command: str,
    root: Path,
    payload: Mapping[str, Any],
    *,
    today: str,
) -> dict[str, Any]:
    """Run one command on a decoded request and return the decoded response."""
    version = str(payload.get("mutmut_version", ""))
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


def main(argv: list[str] | None = None) -> int:
    """Read a JSON request on stdin, print the JSON response."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("command", choices=["triage", "record", "migrate"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        text = "" if sys.stdin.isatty() else sys.stdin.read()
        payload = json.loads(text) if text.strip() else {}
        today = datetime.now(UTC).date().isoformat()
        out = run_command(args.command, args.root, payload, today=today)
    except (StateError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}))  # noqa: T201
        return 1
    print(json.dumps(out, sort_keys=True))  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
