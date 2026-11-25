export const meta = {
  name: 'mutmut-kill-survivors',
  description: 'Analyze surviving mutmut mutants and write targeted tests to kill them',
  phases: [
    { title: 'Preflight', detail: 'Check mutmut version, repeated test sessions and also_copy before anything is counted' },
    { title: 'Discover', detail: 'Run mutmut and list survivors and mutants without tests, with checksums' },
    { title: 'Triage', detail: 'The state helper splits the mutants: known, parked, deferred, to analyse' },
    { title: 'Analyze', detail: 'Give each mutant of a function one outcome: bug, dead code, test design, equivalent or missing test' },
    { title: 'Write', detail: 'Add tests grouped by test file' },
    { title: 'Verify', detail: 'Re-run the targeted mutants, then one fresh full run, and report the delta' },
    { title: 'Record', detail: 'The state helper counts attempts, parks, persists and builds the summary' },
  ],
}

// Project root: pass as args (string path), or leave unset to auto-detect via git.
const PROJECT = typeof args === 'string' && args.trim() ? args.trim() : null

// The first mutmut that behaves as this workflow needs: a named run re-runs only the
// mutants it names, and deleting mutants/mutmut-stats.json makes it map new tests.
const MIN_MUTMUT = [3, 8, 1]

// Statuses `mutmut results` prints for a mutant that no test killed.
const GAP_STATUSES = ['survived', 'no tests']

// ─── Deterministic helpers ────────────────────────────────────────────────────
// Agents run commands and relay their output; this code decides what that output means.

// UTF-8 bytes of a string, as Python's str.encode() gives them. mutmut names the mutants of a
// class method "pkg.mod.xǁClassǁmethod__mutmut_1", and ǁ (U+01C1) is not ASCII.
function utf8Bytes(text) {
  const out = []
  for (const ch of text) {
    const c = ch.codePointAt(0)
    if (c < 0x80) out.push(c)
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63))
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
  }
  return out
}

// FNV-1a 32 over the UTF-8 bytes of the sorted names joined by "\n". LIST_SNIPPET computes the
// same value in Python. There is no `crypto` in the workflow sandbox, hence a checksum this small.
// Sorting by UTF-16 unit equals Python's sort by code point for names outside the astral planes.
function fnv1a32(names) {
  let h = 0x811c9dc5
  for (const b of utf8Bytes([...names].sort().join('\n'))) {
    h = Math.imul(h ^ b, 0x01000193) >>> 0
  }
  return h
}

// Reads `mutmut results --all true` on stdin and prints every status group with its
// count, sorted names and checksum. The agent relays this JSON; verifyListing checks it.
const LIST_SNIPPET = String.raw`import sys, re, json
def fnv(names):
    h = 0x811c9dc5
    for b in "\n".join(sorted(names)).encode():
        h = ((h ^ b) * 0x01000193) & 0xffffffff
    return h
by = {}
for line in sys.stdin:
    m = re.match(r"^\s+(\S+__mutmut_\d+): (.+?)\s*$", line)
    if m:
        by.setdefault(m.group(2), []).append(m.group(1))
groups = [{"status": s, "count": len(n), "checksum": fnv(n), "names": sorted(n)} for s, n in sorted(by.items())]
print(json.dumps({"total": sum(g["count"] for g in groups), "groups": groups}))`

// Prints the test selection and the repo-root modules the tests import but mutmut would
// not copy into mutants/ (neither a source path, nor tests/, nor an also_copy entry).
const CONFIG_SNIPPET = String.raw`import ast, json, pathlib, tomllib
root = pathlib.Path(".")
cfg = tomllib.loads(root.joinpath("pyproject.toml").read_text()).get("tool", {}).get("mutmut", {})
selection = list(cfg.get("pytest_add_cli_args_test_selection", [])) + list(cfg.get("tests_dir", []))
first = lambda p: str(p).strip("/").split("/")[0]
copied = {first(p) for p in cfg.get("source_paths", [])} | {"tests", "test"} | {first(p) for p in cfg.get("also_copy", [])}
imported = set()
for f in root.joinpath("tests").rglob("*.py"):
    try:
        tree = ast.parse(f.read_text())
    except SyntaxError:
        continue
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            imported.add(n.module.split(".")[0])
local = {m for m in imported if (root / m).is_dir() or (root / (m + ".py")).is_file()}
print(json.dumps({"selection": selection, "missing_also_copy": sorted(local - copied)}))`

// Throws unless one group's count, uniqueness and checksum match its names.
function verifyGroup(step, g) {
  if (g.names.length !== g.count) {
    throw new Error(`${step}: status "${g.status}" claims ${g.count} mutants but lists ${g.names.length}; the relayed list is incomplete.`)
  }
  if (new Set(g.names).size !== g.names.length) {
    throw new Error(`${step}: status "${g.status}" lists a mutant twice.`)
  }
  if (fnv1a32(g.names) !== g.checksum) {
    throw new Error(`${step}: checksum mismatch for status "${g.status}"; the relayed list differs from the command output.`)
  }
}

// Throws unless every group checks out and the groups add up to the reported total.
function verifyListing(step, listing) {
  for (const g of listing.groups) verifyGroup(step, g)
  const sum = listing.groups.reduce((acc, g) => acc + g.count, 0)
  if (sum !== listing.total) {
    throw new Error(`${step}: groups add up to ${sum} mutants but the listing reports ${listing.total}.`)
  }
}

function namesWith(listing, statuses) {
  return listing.groups.filter((g) => statuses.includes(g.status)).flatMap((g) => g.names)
}

function statusByName(listing) {
  const map = new Map()
  for (const g of listing.groups) for (const n of g.names) map.set(n, g.status)
  return map
}

// Throws unless `parts` hold exactly the names in `expected`, each once. Used for every
// split of a list that agents relay (cache hits vs. to-analyse, per-function analyses).
function assertPartition(step, expected, parts) {
  const want = new Set(expected)
  const seen = new Set()
  for (const n of parts) {
    if (!want.has(n)) throw new Error(`${step}: "${n}" was not in the list that was sent.`)
    if (seen.has(n)) throw new Error(`${step}: "${n}" appears twice.`)
    seen.add(n)
  }
  const dropped = expected.filter((n) => !seen.has(n))
  if (dropped.length > 0) {
    throw new Error(`${step}: ${dropped.length} mutant(s) were dropped: ${dropped.slice(0, 5).join(', ')}`)
  }
}

// Map the mutant names an agent relayed back onto the full names they were sent. Agents shorten
// what they copy ("x_f__mutmut_1" for "pkg.mod.x_f__mutmut_1"), so a name also matches when it is
// the unique tail of a full name. Anything that matches nothing is returned, not dropped.
function resolveNames(returned, universe) {
  const known = new Set(universe)
  const resolved = new Set()
  const unknown = []
  for (const name of returned) {
    const tails = universe.filter((u) => u.endsWith(`.${name}`))
    if (known.has(name)) resolved.add(name)
    else if (tails.length === 1) resolved.add(tails[0])
    else unknown.push(name)
  }
  return { names: [...resolved].sort(), unknown }
}

// "pkg.mod.x_func__mutmut_3" → "pkg.mod.x_func": one function, many mutants.
function functionKey(mutantName) {
  return mutantName.replace(/__mutmut_\d+$/, '')
}

function parseVersion(text) {
  const m = /(\d+)\.(\d+)\.(\d+)/.exec(text || '')
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null
}

function versionAtLeast(version, min) {
  for (let i = 0; i < 3; i++) {
    if (version[i] !== min[i]) return version[i] > min[i]
  }
  return true
}

// A project-relative path without a leading "./": agents sometimes return the absolute path
// that `find ${project}/...` prints.
function relativeTo(root, file) {
  let f = file.trim()
  const prefix = root.replace(/\/+$/, '') + '/'
  if (f.startsWith(prefix)) f = f.slice(prefix.length)
  return f.replace(/^\.\//, '')
}

// Is `file` under one of mutmut's test selection entries (a directory, a file, or a node id)?
function inSelection(file, selection) {
  const f = file.replace(/^\.\//, '')
  return selection.some((entry) => {
    const e = entry.split('::')[0].replace(/^\.\//, '')
    if (e.endsWith('.py')) return f === e
    const dir = e.replace(/\/+$/, '')
    return f === dir || f.startsWith(`${dir}/`)
  })
}

// mutmut only reads stale results unless it is actually run, so an empty survivor list
// proves nothing by itself. Both the Discover and Verify agents must report that
// "mutmut run" executed (exit 0) and that it produced mutants; anything else is a failure,
// never a green result.
function assertMutmutRan(step, report) {
  if (report.run_exit_code !== 0) {
    throw new Error(
      `${step}: "mutmut run" exited with ${report.run_exit_code}; refusing to report results from a run that did not complete.`,
    )
  }
  if (!(report.total > 0)) {
    throw new Error(
      `${step}: mutmut reported ${report.total} mutants, so it did not actually run; an empty survivor list is not a result.`,
    )
  }
}

// The state helper (scripts/mutmut_state.py) owns keying, counting, parking, reopening,
// ordering, deferral and the summary. Agents run it by exact command and relay its JSON;
// this script checks what comes back.
const HELPER = 'scripts/mutmut_state.py'
const TRIAGE_LISTS = ['equivalent', 'test_design', 'suspected_bug', 'parked', 'deferred', 'to_analyze']
const OUTCOMES = ['suspected_bug', 'dead_code', 'test_design', 'equivalent', 'missing_test']

// ─── Schemas ──────────────────────────────────────────────────────────────────

const PREFLIGHT_SCHEMA = {
  type: 'object',
  properties: {
    project: { type: 'string' },
    mutmut_bin: { type: 'string' },
    pytest_bin: { type: 'string' },
    python_bin: { type: 'string' },
    mutmut_version: { type: 'string' },
    test_selection: { type: 'array', items: { type: 'string' } },
    missing_also_copy: { type: 'array', items: { type: 'string' } },
    repeat_session_exit_code: { type: 'number' },
    repeat_session_output: { type: 'string' },
    random_order: { type: 'string', enum: ['passed', 'failed', 'unavailable'] },
  },
  required: ['project', 'mutmut_bin', 'pytest_bin', 'python_bin', 'mutmut_version', 'test_selection', 'missing_also_copy'],
}

const LISTING_PROPERTIES = {
  total: { type: 'number' },
  groups: {
    type: 'array',
    items: {
      type: 'object',
      properties: {
        status: { type: 'string' },
        count: { type: 'number' },
        checksum: { type: 'number' },
        names: { type: 'array', items: { type: 'string' } },
      },
      required: ['status', 'count', 'checksum', 'names'],
    },
  },
}

const DISCOVERY_SCHEMA = {
  type: 'object',
  properties: { run_exit_code: { type: 'number' }, ...LISTING_PROPERTIES },
  required: ['run_exit_code', 'total', 'groups'],
}

const LISTED_NAMES = {
  type: 'object',
  properties: { names: { type: 'array', items: { type: 'string' } }, checksum: { type: 'number' } },
  required: ['names', 'checksum'],
}

// The helper prints {"error": ...} and exits 1 on a bad request; the agent relays only that.
const TRIAGE_SCHEMA = {
  type: 'object',
  properties: {
    error: { type: 'string' },
    ...Object.fromEntries(TRIAGE_LISTS.map((name) => [name, LISTED_NAMES])),
  },
  required: [],
}

const ANALYSIS_ITEM_SCHEMA = {
  type: 'object',
  properties: {
    mutant_name: { type: 'string' },
    source_file: { type: 'string' },
    test_file: { type: 'string' },
    outcome: { type: 'string', enum: OUTCOMES },
    reason: { type: 'string' },
    evidence: { type: 'array', items: { type: 'string' } },
    depends_on: { type: 'array', items: { type: 'string' } },
    mutation_summary: { type: 'string' },
    test_method_name: { type: 'string' },
    test_code: { type: 'string' },
  },
  required: ['mutant_name', 'source_file', 'outcome', 'mutation_summary'],
}

const FUNCTION_ANALYSIS_SCHEMA = {
  type: 'object',
  properties: { analyses: { type: 'array', items: ANALYSIS_ITEM_SCHEMA } },
  required: ['analyses'],
}

const WRITE_SCHEMA = {
  type: 'object',
  properties: {
    test_file: { type: 'string' },
    tests_written: { type: 'number' },
    mutants_targeted: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
  required: ['test_file', 'tests_written', 'mutants_targeted'],
}

const TARGETED_VERIFY_SCHEMA = {
  type: 'object',
  properties: { run_exit_code: { type: 'number' }, ...LISTING_PROPERTIES },
  required: ['run_exit_code', 'total', 'groups'],
}

const FRESH_VERIFY_SCHEMA = TARGETED_VERIFY_SCHEMA

const OBJECTS = { type: 'array', items: { type: 'object' } }
const NAMES = { type: 'array', items: { type: 'string' } }

const RECORD_SCHEMA = {
  type: 'object',
  properties: {
    error: { type: 'string' },
    killed: NAMES,
    equivalent: OBJECTS,
    parked: OBJECTS,
    deferred: NAMES,
    suspected_bugs: OBJECTS,
    dead_code: OBJECTS,
    test_design: OBJECTS,
    unresolved: NAMES,
    other: OBJECTS,
    still_surviving: NAMES,
    rejected: OBJECTS,
    config_problems: NAMES,
  },
  required: [],
}

// The command an agent runs for one helper call. The request goes in on stdin through a
// quoted heredoc, so the shell leaves every character alone. An agent that relays it has to
// copy it, and agents shorten what they copy, so the first line signs the second: the helper
// refuses any request that differs from what was signed, whatever the difference.
function helperPrompt(project, pythonBin, command, request) {
  const body = JSON.stringify(request)
  return `Run the state helper and report what it prints.

The request below is two lines: a checksum line and one line of JSON. The checksum covers
that JSON line exactly, so copy BOTH lines character for character: do not shorten, reorder,
reformat or summarise anything, even a long list. The helper refuses any difference.

  cd ${project} && ${pythonBin} ${HELPER} ${command} --root . <<'JSON'
#fnv1a32 ${fnv1a32([body])}
${body}
JSON

Its stdout is one JSON object. Copy it into the result exactly as printed: do not drop,
reorder, merge or edit any name, count, checksum or text. If it prints {"error": ...}
(exit code 1), report only that text as "error". Do not fix anything.`
}

// A refused request writes nothing, so asking again is safe. Retry with the reason: most
// refusals are a relay that was not copied exactly.
async function callHelper(step, command, request, schema) {
  const attempts = 3
  let note = ''
  let error = ''
  for (let attempt = 1; attempt <= attempts; attempt++) {
    const result = await agent(
      helperPrompt(project, pythonBin, command, request) + note,
      { schema, phase: step, label: `${command}:${attempt}` },
    )
    if (!result.error) return result
    error = result.error
    log(`${step}: the helper refused attempt ${attempt} of ${attempts}: ${error}`)
    note = `

Your previous attempt was refused with: ${error}
The request above is correct as printed. A refusal means it was not copied exactly, so copy
the checksum line and the whole JSON line again, character for character, and run it again.`
  }
  throw new Error(`${step}: the state helper refused the request ${attempts} times: ${error}`)
}

// ─── Phase 0: Preflight ───────────────────────────────────────────────────────
// A problem here is the environment's fault, not the model's: stop before anything is
// analysed, written or counted.

phase('Preflight')

const preflight = await agent(
  `Check that this project can run mutation testing. Run the commands below exactly and report what they print.

${PROJECT ? `Project directory: ${PROJECT}` : `Step 0 — Detect the project root: git rev-parse --show-toplevel`}
Use it as <project>. Run every later command from <project>.

Step 1 — Find the mutmut and pytest binaries (use the first that exists):
  <project>/.venv/bin/mutmut, <project>/venv/bin/mutmut, then "which mutmut"
  <project>/.venv/bin/pytest, <project>/venv/bin/pytest, then "which pytest"
  Also find the Python of the same environment: <project>/.venv/bin/python, <project>/venv/bin/python, then python3 (call it <python_bin> and report its path as python_bin).

Step 2 — Version. Run "<mutmut_bin> --version" and report its output as mutmut_version.

Step 3 — Configuration. Run this and copy its JSON into test_selection and missing_also_copy:
  <python_bin> -c '${CONFIG_SNIPPET}'

Cheap checks first: if the version in step 2 is older than 3.8.1, or step 3 reports a
  non-empty missing_also_copy or an empty test_selection, STOP here and leave
  repeat_session_exit_code and random_order out: the slow steps below are not needed.

Step 4 — Repeated sessions. mutmut runs the selected tests twice in one process (a stats
  session, then a clean session). Run them twice in one process, using the test_selection
  entries from step 3 in place of <selection>:
  <python_bin> -c 'import sys, pytest; a = sys.argv[1:]; r = [pytest.main(a), pytest.main(a)]; sys.exit(max(r))' <selection> -q -p no:randomly
  Report the exit code as repeat_session_exit_code and, if it is not 0, the last 40 lines of output as repeat_session_output.

Step 5 — Random order. If pytest-randomly or pytest-random-order is installed, run
  "<pytest_bin> <selection> -q" once with random ordering enabled in a fresh process and report
  random_order as "passed" or "failed". If neither plugin is installed, report "unavailable".

Do not fix anything and do not retry a failure: report exactly what happened.`,
  { schema: PREFLIGHT_SCHEMA, phase: 'Preflight' },
)

const mutmutVersion = parseVersion(preflight.mutmut_version)
if (!mutmutVersion || !versionAtLeast(mutmutVersion, MIN_MUTMUT)) {
  throw new Error(
    `Preflight: mutmut ${mutmutVersion ? mutmutVersion.join(".") : preflight.mutmut_version} is older than ${MIN_MUTMUT.join('.')}; a named re-run does not behave as Verify needs.`,
  )
}
if (preflight.missing_also_copy.length > 0) {
  throw new Error(
    `Preflight: the tests import ${preflight.missing_also_copy.join(', ')}, which mutmut does not copy into mutants/. Add them to also_copy in [tool.mutmut].`,
  )
}
if (preflight.test_selection.length === 0) {
  throw new Error('Preflight: [tool.mutmut] has no pytest_add_cli_args_test_selection, so no proposed test file can be checked against it.')
}
if (preflight.repeat_session_exit_code === undefined) {
  throw new Error('Preflight: the repeated test session was not run.')
}
if (preflight.repeat_session_exit_code !== 0) {
  throw new Error(
    `Preflight: the selected tests fail when run twice in one process (exit ${preflight.repeat_session_exit_code}), as mutmut runs them. Fix that first.\n${preflight.repeat_session_output || ''}`,
  )
}
if (preflight.random_order === 'failed') {
  log('Preflight warning: the selected tests fail in random order. Mutants may be falsely killed or survive depending on order.')
} else if (preflight.random_order === 'unavailable') {
  log('Preflight: no random-order plugin installed; order dependence was not checked.')
}

const project = PROJECT || preflight.project
const mutmutBin = preflight.mutmut_bin
const pytestBin = preflight.pytest_bin
const pythonBin = preflight.python_bin
const mutmutVersionText = mutmutVersion.join('.')
const testSelection = preflight.test_selection

// ─── Phase 1: Discover ────────────────────────────────────────────────────────

phase('Discover')

// The listing command: its stdout carries the counts and checksums the script verifies.
const listCommand = `cd ${project} && ${mutmutBin} results --all true 2>/dev/null | python3 -c '${LIST_SNIPPET}'`

const discovery = await agent(
  `You are a mutation testing assistant. Run mutmut for real and list its results.

Step 1 — Run mutmut. Never skip this: "mutmut results" alone only reads stale data and
  reports no survivors when nothing has run.
  cd ${project} && ${mutmutBin} run
  Record the command's exit code as run_exit_code. Do not retry or hide a failure: report
  a non-zero exit code as it is.

Step 2 — List the results (only after step 1):
  ${listCommand}
  Its stdout is one JSON object with "total" and "groups". Copy it into total and groups
  exactly as printed: do not drop, reorder, merge or edit any name, count or checksum.`,
  { schema: DISCOVERY_SCHEMA, phase: 'Discover' },
)

assertMutmutRan('Discover', discovery)
verifyListing('Discover', discovery)

// A mutant no test killed is a gap: "survived" ran and passed, "no tests" never ran.
const gaps = namesWith(discovery, GAP_STATUSES).sort()
const noTestsAtStart = new Set(namesWith(discovery, ['no tests']))

if (gaps.length === 0) {
  log(`No surviving mutants out of ${discovery.total} — mutation score is 100%.`)
  return { status: 'complete', started_with: 0, killed: [], still_surviving: [] }
}

log(`Found ${gaps.length} unkilled mutants (${gaps.length - noTestsAtStart.size} survived, ${noTestsAtStart.size} with no tests) in ${project}`)


// ─── Phase 2: Triage ──────────────────────────────────────────────────────────
// The helper splits the unkilled mutants by what the stored state says about them. A
// record is valid only while the mutant's function, the mutmut version, the mutation
// settings and every file its verdict rests on are unchanged.

phase('Triage')

const triaged = await callHelper(
  'Triage',
  'triage',
  { mutmut_version: mutmutVersionText, gaps, gaps_checksum: fnv1a32(gaps) },
  TRIAGE_SCHEMA,
)

for (const name of TRIAGE_LISTS) {
  const listed = triaged[name]
  if (!listed || fnv1a32(listed.names) !== listed.checksum) {
    throw new Error(`Triage: the "${name}" list is missing or its checksum does not match its names.`)
  }
}
assertPartition('Triage', gaps, TRIAGE_LISTS.flatMap((name) => triaged[name].names))

// The helper's order (module, function, mutant number) is kept: it is the stable order
// the pass budget cuts at.
const toAnalyze = triaged.to_analyze.names

log(
  `Triage: ${toAnalyze.length} to analyse  |  ${triaged.equivalent.names.length} equivalent  |  ` +
  `${triaged.test_design.names.length} test design  |  ${triaged.suspected_bug.names.length} suspected bug  |  ` +
  `${triaged.parked.names.length} parked  |  ${triaged.deferred.names.length} deferred`,
)

const statusAtStart = statusByName(discovery)

let analyses = []
let unanalyzed = []
let configProblems = []
let actionable = []

// ─── Phase 3: Analyze ─────────────────────────────────────────────────────────
// One agent per function: it sees all of that function's mutants, so one test can kill
// several of them. Each mutant gets exactly one outcome.

if (toAnalyze.length > 0) {
  phase('Analyze')

  const byFunction = new Map()
  for (const name of toAnalyze) {
    const key = functionKey(name)
    if (!byFunction.has(key)) byFunction.set(key, [])
    byFunction.get(key).push(name)
  }

  log(`Analyzing ${toAnalyze.length} mutant(s) in ${byFunction.size} function(s)`)

  const analysisRuns = (await pipeline(
    [...byFunction.entries()],
    async ([key, names]) => ({ key, names, run: await agent(
      `Analyze the unkilled mutmut mutants of one function, "${key}", in the project at ${project}.

Mutants (all of them need one entry in "analyses", none may be left out):
${names.map((n) => `  ${n}  [${noTestsAtStart.has(n) ? 'no tests: no test reaches this function' : 'survived'}]`).join('\n')}

STEP 1 — See each diff:
  cd ${project} && ${mutmutBin} show "<mutant name>"

STEP 2 — Identify the source file:
  The mutant name encodes the source module. Examples:
    "pkg.module.x_function__mutmut_N"  →  source_file = "pkg/module.py"
    "src.utils.x_helper__mutmut_1"     →  source_file = "src/utils.py"
  Derive the path from the mutant name, then read the mutated function in ${project}/<source_file>.

STEP 3 — Give each mutant ONE outcome. Take the first that fits, in this order:
  1. suspected_bug — the mutant's behaviour is MORE correct than the original code.
     You must trace a real production caller where the original misbehaves and cite it in
     evidence as "path:line". "The mutant looks reasonable" is not enough. No test is written.
  2. dead_code — no production code calls this function. Say what you searched in reason.
  3. test_design — the mutant survives because of how the existing tests are written, not
     because a test is missing: the only covering test patches out the mutated call, or the
     compared values are None or the default on both sides, or a fixture hides the difference.
     Say which, in reason; cite it in evidence as "path:line".
  4. equivalent — no test can observe the change. Cite the proof in evidence as "path:line"
     (library source, compiled SQL, the callers) and list in depends_on every other file the
     verdict rests on. Every path must be an exact path to a file that exists: no wildcards or
     globs (find a library file with: <python> -c "import yaml; print(yaml.__file__)").
     A verdict without a real "path:line", or naming a file that does not exist, is rejected.
  5. missing_test — the mutation exposes behaviour that should be tested but isn't.
  Never choose equivalent to avoid writing a test.

STEP 4 — For missing_test only, find the test file:
  mutmut only runs tests in its test selection: ${JSON.stringify(testSelection)}.
  The test file you choose MUST be inside that selection. If a test file that exercises
  this function lives outside it, say so in mutation_summary and still name that file:
  the workflow will report it as a configuration problem.
  Search by the source module name (replace <module> with the last segment of the module path):
    find ${project}/tests -name "test_<module>*.py" 2>/dev/null | head -5
  Or broader if nothing found:
    find ${project} -name "test_<module>*.py" -not -path "*/.venv/*" -not -path "*/venv/*" | head -5
  Pick the best match. If none exists, choose a sensible location inside the selection
  (e.g. tests/unit/test_<module>.py).
  Read the test file to understand the existing structure, fixtures, and naming style.
  A "no tests" mutant needs a test that actually calls this function.
  Write a pytest test method (test_method_name + test_code) that:
      • PASSES against the original code
      • would FAIL if the mutated line were applied
  Follow the style of the existing tests exactly and keep the test minimal — test one thing.
  Where one test can kill several of this function's mutants, give the same test_method_name
  and test_code to each of them.

Return one entry per mutant listed above, with mutant_name copied exactly.
source_file and test_file are paths relative to the project root (tests/unit/test_x.py), never absolute.`,
      { label: `analyze:${key}`, schema: FUNCTION_ANALYSIS_SCHEMA, phase: 'Analyze' },
    ) }),
  )).filter(Boolean)

  // An analysis that does not cover exactly its function's mutants is an analysis failure:
  // nothing from it is used, and its mutants are retried next run.
  const analyzedKeys = new Set(analysisRuns.map((r) => r.key))
  for (const [key, names] of byFunction) {
    if (!analyzedKeys.has(key)) {
      unanalyzed.push(...names)
      log(`Analysis of ${key} did not return; its ${names.length} mutant(s) are retried next run.`)
    }
  }
  for (const { key, names, run } of analysisRuns) {
    if (!run) {
      unanalyzed.push(...names)
      log(`Analysis of ${key} failed; its ${names.length} mutant(s) are retried next run.`)
      continue
    }
    try {
      assertPartition(`Analyze ${key}`, names, run.analyses.map((a) => a.mutant_name))
      analyses.push(...run.analyses.map((a) => ({
        ...a,
        source_file: relativeTo(project, a.source_file),
        test_file: a.test_file ? relativeTo(project, a.test_file) : a.test_file,
      })))
    } catch (err) {
      unanalyzed.push(...names)
      log(`${err.message} Its ${names.length} mutant(s) are retried next run.`)
    }
  }

  // Only missing_test outcomes with a test get written. A test file outside mutmut's
  // selection is never run against a mutant, so it cannot kill one however good it is:
  // that is a configuration problem, not a failed attempt.
  const proposed = analyses.filter((a) => a.outcome === 'missing_test' && a.test_code && a.test_file)
  configProblems = proposed.filter((a) => !inSelection(a.test_file, testSelection)).map((a) => a.mutant_name)
  actionable = proposed.filter((a) => inSelection(a.test_file, testSelection))

  const counts = {}
  for (const a of analyses) counts[a.outcome] = (counts[a.outcome] || 0) + 1
  log(`Outcomes: ${JSON.stringify(counts)}  |  ${configProblems.length} outside the test selection`)
}

// ─── Phase 4: Write ───────────────────────────────────────────────────────────

let totalWritten = 0
let targeted = []
const writeFailures = {}

if (actionable.length > 0) {
  phase('Write')

  // Group by test file so no two agents edit the same file concurrently. Several mutants of
  // one function may share one test: write it once.
  const byTestFile = {}
  for (const analysis of actionable) {
    const key = analysis.test_file
    if (!byTestFile[key]) byTestFile[key] = []
    byTestFile[key].push(analysis)
  }

  const writeRuns = await parallel(
    Object.entries(byTestFile).map(([testFile, group]) => async () => ({
      testFile,
      group,
      result: await agent(
        `Add tests to ${project}/${testFile} to kill ${group.length} surviving mutant(s).

Tests to add
============
${group.map((a, i) => `
### ${i + 1}. ${a.mutant_name}
Mutation: ${a.mutation_summary}
Method name: ${a.test_method_name}

\`\`\`python
${a.test_code}
\`\`\`
`).join('\n')}

Instructions
============
1. Read ${project}/${testFile} — note the existing class structure, fixtures, and imports.
2. Insert each test method into the appropriate class (or at module level if no class fits),
   exactly matching the indentation and naming conventions already present.
   Entries that share a method name and code are one test: add it once.
3. Add any missing imports at the top of the file.
4. Run: cd ${project} && ${pytestBin} ${testFile} -x -q
   The tests MUST PASS against the original (unmutated) code.
   If a test fails to collect (syntax/import error), fix it.
   If a test fails at runtime, the test logic is wrong — revise it once, then skip it
   and say in the notes field why it failed, rather than writing a broken test.
5. Report how many tests were successfully written (tests_written) and which
   mutant names they target (mutants_targeted): every mutant of an entry whose test you wrote,
   each copied exactly as listed above, with its full dotted prefix.`,
        { label: `write:${testFile}`, schema: WRITE_SCHEMA, phase: 'Write' },
      ),
    })),
  )

  const finished = writeRuns.filter((r) => r && r.result)
  totalWritten = finished.reduce((sum, r) => sum + r.result.tests_written, 0)
  log(`Wrote ${totalWritten} tests across ${finished.length} file(s)`)

  // Only mutants the Write agents claim a test for, and that were really sent to them. A name
  // that cannot be matched is reported: dropping it silently would skip its Verify.
  const sent = actionable.map((a) => a.mutant_name)
  const claimed = resolveNames(finished.flatMap((r) => r.result.mutants_targeted), sent)
  targeted = claimed.names
  if (claimed.unknown.length > 0) {
    log(`Write returned ${claimed.unknown.length} mutant name(s) that match none sent: ${claimed.unknown.slice(0, 3).join(', ')}`)
  }

  // A proposed test that could not be made to pass is an attempt. A Write agent that never
  // came back is not: that is the infrastructure's failure, and the mutant is retried.
  for (const { group, result } of finished) {
    for (const a of group) {
      if (!targeted.includes(a.mutant_name)) {
        writeFailures[a.mutant_name] = (result.notes || '').trim() || 'the proposed test could not be made to pass'
      }
    }
  }
}

// ─── Phase 5: Verify ──────────────────────────────────────────────────────────
// Step A re-runs only the targeted mutants. mutmut keeps an existing result unless the
// mutant is named on the command line, and does not map new tests to functions unless
// mutants/mutmut-stats.json is gone, so the plain "mutmut run" of Discover would report the
// same survivors again. mutmut copies tests/ into mutants/ on every run.
// Step B is one fresh full run: the final word, and a check on step A.
// A Verify that fails or whose lists do not check out counts nothing: the pass is still
// recorded (verdicts are kept, no attempt is counted) and says why.

const verify = {
  ok: true,
  error: null,
  status: Object.fromEntries(gaps.map((n) => [n, statusAtStart.get(n)])),
  newGaps: [],
  contradictions: [],
}

if (targeted.length > 0) {
  phase('Verify')

  try {
    const targetedGlobs = [...new Set(targeted.map((n) => `${functionKey(n)}__mutmut_*`))].sort()

    const targetedRun = await agent(
      `Re-run only the mutants of the functions that just got new tests, in ${project}.

Steps:
  1. cd ${project} && rm -f mutants/mutmut-stats.json
     (without this, mutmut does not map the new tests to their functions)
  2. cd ${project} && ${mutmutBin} run ${targetedGlobs.map((g) => `"${g}"`).join(' ')}
     Record the command's exit code as run_exit_code; report a non-zero code as it is.
  3. ${listCommand}
     Its stdout is one JSON object with "total" and "groups". Copy it into total and groups
     exactly as printed: do not drop, reorder, merge or edit any name, count or checksum.`,
      { schema: TARGETED_VERIFY_SCHEMA, phase: 'Verify', label: 'verify:targeted' },
    )

    assertMutmutRan('Verify (targeted)', targetedRun)
    verifyListing('Verify (targeted)', targetedRun)

    const targetedStatus = statusByName(targetedRun)

    const freshRun = await agent(
      `Run mutmut from scratch in ${project} and list the results.

Steps:
  1. cd ${project} && rm -rf mutants
  2. cd ${project} && ${mutmutBin} run
     Record the command's exit code as run_exit_code; report a non-zero code as it is.
  3. ${listCommand}
     Its stdout is one JSON object with "total" and "groups". Copy it into total and groups
     exactly as printed: do not drop, reorder, merge or edit any name, count or checksum.`,
      { schema: FRESH_VERIFY_SCHEMA, phase: 'Verify', label: 'verify:fresh' },
    )

    assertMutmutRan('Verify (fresh)', freshRun)
    verifyListing('Verify (fresh)', freshRun)

    // Per mutant, from the fresh run alone: the helper counts "killed" only if mutmut says so.
    const freshStatus = statusByName(freshRun)
    verify.status = Object.fromEntries(gaps.map((n) => [n, freshStatus.get(n) || 'missing from the fresh run']))
    const gapSet = new Set(gaps)
    verify.newGaps = namesWith(freshRun, GAP_STATUSES).filter((n) => !gapSet.has(n)).sort()

    // The targeted run and the fresh run must agree on what the new tests killed.
    verify.contradictions = targeted
      .filter((n) => targetedStatus.get(n) === 'killed' && freshStatus.get(n) !== 'killed')
      .map((n) => ({ name: n, targeted: 'killed', fresh: freshStatus.get(n) || 'missing' }))
    if (verify.contradictions.length > 0) {
      log(`${verify.contradictions.length} mutant(s) were killed in the targeted run but not in the fresh run; the fresh run wins.`)
    }
  } catch (err) {
    verify.ok = false
    verify.error = err.message
    log(`Verify failed, so no attempt is counted this pass: ${err.message}`)
  }
}

// ─── Phase 6: Record ──────────────────────────────────────────────────────────
// The helper counts attempts, parks mutants at the budget, writes the state files and
// builds the summary. Agents proposed; this is where the decisions are made.

phase('Record')

// Free text is cut short: it is only for the report, and every extra character is one more an
// agent has to copy.
const brief = (text, max) => (text && text.length > max ? `${text.slice(0, max - 1)}…` : text || '')

const recorded = await callHelper(
  'Record',
  'record',
  {
    mutmut_version: mutmutVersionText,
    gaps,
    gaps_checksum: fnv1a32(gaps),
    analyses: analyses.map((a) => ({
      mutant: a.mutant_name,
      outcome: a.outcome,
      evidence: a.evidence || [],
      depends_on: a.depends_on || [],
      reason: brief(a.reason, 300),
      summary: brief(a.mutation_summary, 160),
      test_file: a.test_file || '',
      test_name: a.test_method_name || '',
    })),
    written: targeted,
    write_failures: writeFailures,
    config_problems: configProblems,
    unanalyzed,
    verify_ok: verify.ok,
    status: verify.status,
  },
  RECORD_SCHEMA,
)


// Every unkilled mutant ends up killed, still surviving or in another state, exactly once.
assertPartition('Record', gaps, [
  ...recorded.killed,
  ...recorded.still_surviving,
  ...recorded.other.map((o) => o.mutant),
])

log(
  `Started: ${gaps.length}  |  Killed: ${recorded.killed.length}  |  Parked: ${recorded.parked.length}  |  ` +
  `Equivalent: ${recorded.equivalent.length}  |  Suspected bugs: ${recorded.suspected_bugs.length}  |  ` +
  `Dead code: ${recorded.dead_code.length}  |  Deferred: ${recorded.deferred.length}  |  ` +
  `Still unkilled: ${recorded.still_surviving.length}`,
)

return {
  status: 'complete',
  started_with: gaps.length,
  tests_written: totalWritten,
  ...recorded,
  new_gaps: verify.newGaps,
  contradictions: verify.contradictions,
  verify_error: verify.error,
}
