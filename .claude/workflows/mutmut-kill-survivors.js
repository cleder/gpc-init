export const meta = {
  name: 'mutmut-kill-survivors',
  description: 'Analyze surviving mutmut mutants and write targeted tests to kill them',
  phases: [
    { title: 'Preflight', detail: 'Check mutmut version, repeated test sessions and also_copy before anything is counted' },
    { title: 'Discover', detail: 'Run mutmut and list survivors and mutants without tests, with checksums' },
    { title: 'Cache', detail: 'Skip re-analysis of equivalent mutants whose source file is unchanged' },
    { title: 'Analyze', detail: 'Classify the uncached mutants of each function: missing test vs equivalent' },
    { title: 'Write', detail: 'Add tests grouped by test file' },
    { title: 'Verify', detail: 'Re-run the targeted mutants, then one fresh full run, and report the delta' },
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

// Throws unless every group's count and checksum match its names and the groups add up.
function verifyListing(step, listing) {
  let sum = 0
  for (const g of listing.groups) {
    if (g.names.length !== g.count) {
      throw new Error(`${step}: status "${g.status}" claims ${g.count} mutants but lists ${g.names.length}; the relayed list is incomplete.`)
    }
    if (new Set(g.names).size !== g.names.length) {
      throw new Error(`${step}: status "${g.status}" lists a mutant twice.`)
    }
    if (fnv1a32(g.names) !== g.checksum) {
      throw new Error(`${step}: checksum mismatch for status "${g.status}"; the relayed list differs from the command output.`)
    }
    sum += g.count
  }
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

// Every return has these keys. still_surviving counts unkilled mutants that are not known to be
// equivalent, so it means the same thing whichever phase the run ended in.
function report({
  startedWith, killed = [], equivalents = [], other = [], testsWritten = 0, unkilled = [],
  newGaps = [], configProblems = [], noTestProposed = [], unanalyzed = [], contradictions = [],
}) {
  const known = new Set(equivalents.map((e) => e.name))
  const open = unkilled.filter((n) => !known.has(n))
  return {
    status: 'complete',
    started_with: startedWith,
    killed,
    equivalent_mutants: equivalents,
    other,
    tests_written: testsWritten,
    still_surviving: open.length,
    remaining_survivors: open,
    new_gaps: newGaps,
    config_problems: configProblems.map((a) => ({ name: a.mutant_name, test_file: a.test_file })),
    no_test_proposed: noTestProposed,
    unanalyzed,
    contradictions,
  }
}

// ─── Schemas ──────────────────────────────────────────────────────────────────

const PREFLIGHT_SCHEMA = {
  type: 'object',
  properties: {
    project: { type: 'string' },
    mutmut_bin: { type: 'string' },
    pytest_bin: { type: 'string' },
    mutmut_version: { type: 'string' },
    test_selection: { type: 'array', items: { type: 'string' } },
    missing_also_copy: { type: 'array', items: { type: 'string' } },
    repeat_session_exit_code: { type: 'number' },
    repeat_session_output: { type: 'string' },
    random_order: { type: 'string', enum: ['passed', 'failed', 'unavailable'] },
  },
  required: ['project', 'mutmut_bin', 'pytest_bin', 'mutmut_version', 'test_selection', 'missing_also_copy'],
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

const CACHE_LOAD_SCHEMA = {
  type: 'object',
  properties: {
    cached_equivalents: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          mutant_name: { type: 'string' },
          source_file: { type: 'string' },
          file_hash: { type: 'string' },
          equivalent_reason: { type: 'string' },
        },
        required: ['mutant_name', 'source_file', 'file_hash', 'equivalent_reason'],
      },
    },
    survivors_to_analyze: { type: 'array', items: { type: 'string' } },
  },
  required: ['cached_equivalents', 'survivors_to_analyze'],
}

const ANALYSIS_ITEM_SCHEMA = {
  type: 'object',
  properties: {
    mutant_name: { type: 'string' },
    source_file: { type: 'string' },
    test_file: { type: 'string' },
    is_equivalent: { type: 'boolean' },
    equivalent_reason: { type: 'string' },
    mutation_summary: { type: 'string' },
    test_method_name: { type: 'string' },
    test_code: { type: 'string' },
  },
  required: ['mutant_name', 'source_file', 'is_equivalent', 'mutation_summary'],
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
  Also find the Python of the same environment: <project>/.venv/bin/python, <project>/venv/bin/python, then python3 (call it <python_bin>).

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
  return report({ startedWith: 0 })
}

log(`Found ${gaps.length} unkilled mutants (${gaps.length - noTestsAtStart.size} survived, ${noTestsAtStart.size} with no tests) in ${project}`)

// ─── Phase 2: Cache ───────────────────────────────────────────────────────────

phase('Cache')

const cacheCheck = await agent(
  `Load the equivalents cache and identify which unkilled mutants still need analysis.

Cache file: ${project}/.mutmut-equivalents.json
All unkilled mutants: ${JSON.stringify(gaps)}

Steps:
1. Try to read ${project}/.mutmut-equivalents.json.
   If the file does not exist or cannot be parsed, set cached_equivalents = [] and
   survivors_to_analyze = all unkilled mutants — do not error.
2. Parse the JSON array. For each cache entry whose mutant_name appears in the list:
   a. Run: cd ${project} && git hash-object <entry.source_file>
   b. If the hash matches entry.file_hash exactly: file is unchanged → include in cached_equivalents.
   c. If the hash differs, the command errors, or the source file is missing: discard from cache.
3. survivors_to_analyze = all unkilled mutants NOT covered by a valid (still-matching) cache entry.

Every mutant must end up in exactly one of the two results: do not drop or duplicate any.

Return cached_equivalents (valid cache hits) and survivors_to_analyze (need fresh analysis).`,
  { schema: CACHE_LOAD_SCHEMA, phase: 'Cache' },
)

const cachedEquivalents = cacheCheck.cached_equivalents
const survivorsToAnalyze = [...cacheCheck.survivors_to_analyze].sort()

assertPartition('Cache', gaps, [
  ...cachedEquivalents.map((e) => e.mutant_name),
  ...survivorsToAnalyze,
])

if (cachedEquivalents.length > 0) {
  log(`Cache: ${cachedEquivalents.length} equivalent mutant(s) skipped (source file unchanged)`)
}

if (survivorsToAnalyze.length === 0) {
  log('All unkilled mutants are cached equivalents — nothing to analyze.')
  return report({
    startedWith: gaps.length,
    equivalents: cachedEquivalents.map((e) => ({ name: e.mutant_name, reason: e.equivalent_reason })),
    unkilled: gaps,
  })
}

// ─── Phase 3: Analyze ─────────────────────────────────────────────────────────
// One agent per function: it sees all of that function's mutants, so one test can kill
// several of them.

phase('Analyze')

const byFunction = new Map()
for (const name of survivorsToAnalyze) {
  const key = functionKey(name)
  if (!byFunction.has(key)) byFunction.set(key, [])
  byFunction.get(key).push(name)
}

log(`Analyzing ${survivorsToAnalyze.length} uncached mutant(s) in ${byFunction.size} function(s)`)

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

STEP 3 — Find the test file:
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

STEP 4 — Classify each mutant:
  EQUIVALENT mutant: the mutation cannot be detected by any test because the change
  does not alter observable behaviour (e.g. changing a default arg callers always override,
  reordering commutative ops, modifying an internal string no test checks).
  → set is_equivalent=true, explain in equivalent_reason, leave test fields empty.

  MISSING TEST: the mutation exposes behaviour that should be tested but isn't.
  → set is_equivalent=false
  → write a pytest test method (test_method_name + test_code) that:
      • PASSES against the original code
      • would FAIL if the mutated line were applied
  → follow the style of the existing tests exactly
  → keep the test minimal — test one thing
  → where one test can kill several of this function's mutants, give the same test_method_name
    and test_code to each of them.

Return one entry per mutant listed above, with mutant_name copied exactly.
source_file and test_file are paths relative to the project root (tests/unit/test_x.py), never absolute.`,
    { label: `analyze:${key}`, schema: FUNCTION_ANALYSIS_SCHEMA, phase: 'Analyze' },
  ) }),
)).filter(Boolean)

// An analysis that does not cover exactly its function's mutants is an analysis failure:
// nothing from it is used, and its mutants are retried next run.
const analyses = []
const unanalyzed = []
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

const equivalent = analyses.filter((a) => a.is_equivalent)
const notEquivalent = analyses.filter((a) => !a.is_equivalent)
const proposed = notEquivalent.filter((a) => a.test_code && a.test_file)
// Not equivalent, yet no usable test came back: reported, and retried next run.
const noTestProposed = notEquivalent.filter((a) => !(a.test_code && a.test_file)).map((a) => a.mutant_name)

// A test file outside mutmut's selection is never run against a mutant, so it cannot kill
// one however good it is. That is a configuration problem, not a failed attempt.
const configProblems = proposed.filter((a) => !inSelection(a.test_file, testSelection))
const actionable = proposed.filter((a) => inSelection(a.test_file, testSelection))

if (configProblems.length > 0) {
  log(`${configProblems.length} proposed test(s) are outside the test selection ${JSON.stringify(testSelection)} and are not written.`)
}
log(`${actionable.length} need tests  |  ${equivalent.length} newly equivalent  |  ${cachedEquivalents.length} cache hit(s)`)

// Save updated equivalents cache (merge kept entries + newly found)
if (equivalent.length > 0 || cachedEquivalents.length > 0) {
  await agent(
    `Update the equivalents cache at ${project}/.mutmut-equivalents.json.

Previously cached entries (already have file_hash — keep as-is unless superseded):
${JSON.stringify(cachedEquivalents, null, 2)}

Newly classified equivalents (compute file_hash for each):
${JSON.stringify(equivalent.map((a) => ({ mutant_name: a.mutant_name, source_file: a.source_file, equivalent_reason: a.equivalent_reason })), null, 2)}

Steps:
1. For each entry in "newly classified equivalents", compute the git blob hash:
   cd ${project} && git hash-object <source_file>
   Add the output as the "file_hash" field.
2. Build the merged array: previously cached entries + new entries.
   If the same mutant_name appears in both, the new entry wins.
3. Write the merged array as pretty-printed JSON (2-space indent, keys sorted
   alphabetically within each object) to ${project}/.mutmut-equivalents.json.
   Use Python: python3 -c "import json,sys; d=json.load(open('.mutmut-equivalents.json')); open('.mutmut-equivalents.json','w').write(json.dumps(d,indent=2,sort_keys=True,ensure_ascii=True)+'\\n')"
   Run this command from ${project} after writing the file to guarantee correct formatting.`,
    { phase: 'Analyze' },
  )
}

const allEquivalents = [
  ...equivalent.map((a) => ({ name: a.mutant_name, reason: a.equivalent_reason })),
  ...cachedEquivalents.map((e) => ({ name: e.mutant_name, reason: e.equivalent_reason })),
]

if (actionable.length === 0) {
  return report({
    startedWith: gaps.length,
    equivalents: allEquivalents,
    unkilled: gaps,
    configProblems,
    noTestProposed,
    unanalyzed,
  })
}

// ─── Phase 4: Write ───────────────────────────────────────────────────────────

phase('Write')

// Group by test file so no two agents edit the same file concurrently. Several mutants of
// one function may share one test: write it once.
const byTestFile = {}
for (const analysis of actionable) {
  const key = analysis.test_file
  if (!byTestFile[key]) byTestFile[key] = []
  byTestFile[key].push(analysis)
}

const writeResults = (await parallel(
  Object.entries(byTestFile).map(([testFile, group]) => () =>
    agent(
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
   and note it in the notes field rather than writing a broken test.
5. Report how many tests were successfully written (tests_written) and which
   mutant names they target (mutants_targeted): every mutant of an entry whose test you wrote.`,
      { label: `write:${testFile}`, schema: WRITE_SCHEMA, phase: 'Write' },
    ),
  ),
)).filter(Boolean)

const totalWritten = writeResults.reduce((sum, r) => sum + r.tests_written, 0)
log(`Wrote ${totalWritten} tests across ${writeResults.length} file(s)`)

// Only mutants the Write agents claim a test for, and that were really sent to them.
const actionableNames = new Set(actionable.map((a) => a.mutant_name))
const targeted = [...new Set(writeResults.flatMap((r) => r.mutants_targeted))]
  .filter((n) => actionableNames.has(n))
  .sort()

if (targeted.length === 0) {
  log('No test was written, so there is nothing to verify.')
  return report({
    startedWith: gaps.length,
    equivalents: allEquivalents,
    testsWritten: totalWritten,
    unkilled: gaps,
    configProblems,
    noTestProposed,
    unanalyzed,
  })
}

// ─── Phase 5: Verify ──────────────────────────────────────────────────────────
// Step A re-runs only the targeted mutants. mutmut keeps an existing result unless the
// mutant is named on the command line, and does not map new tests to functions unless
// mutants/mutmut-stats.json is gone, so the plain "mutmut run" of Discover would report the
// same survivors again. mutmut copies tests/ into mutants/ on every run.
// Step B is one fresh full run: the final word, and a check on step A.

phase('Verify')

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

const freshStatus = statusByName(freshRun)
const stillGap = new Set(namesWith(freshRun, GAP_STATUSES))

// Per mutant, from the fresh run alone: killed only if mutmut says "killed".
// Anything that is neither killed nor a gap (timeout, suspicious, segfault, ...) is "other".
const killed = []
const other = []
for (const name of gaps) {
  const status = freshStatus.get(name)
  if (status === 'killed') killed.push(name)
  else if (!stillGap.has(name)) other.push({ name, status: status || 'missing from the fresh run' })
}
const remaining = gaps.filter((n) => stillGap.has(n))
const newGaps = [...stillGap].filter((n) => !gaps.includes(n)).sort()

// The targeted run and the fresh run must agree on what the new tests killed.
const contradictions = targeted
  .filter((n) => targetedStatus.get(n) === 'killed' && freshStatus.get(n) !== 'killed')
  .map((n) => ({ name: n, targeted: 'killed', fresh: freshStatus.get(n) || 'missing' }))

if (contradictions.length > 0) {
  log(`${contradictions.length} mutant(s) were killed in the targeted run but not in the fresh run; the fresh run wins.`)
}

log(`Started: ${gaps.length}  |  Killed: ${killed.length}  |  Equivalent: ${allEquivalents.length} (${cachedEquivalents.length} cached)  |  Other: ${other.length}  |  Still unkilled: ${remaining.length}`)

return report({
  startedWith: gaps.length,
  killed,
  equivalents: allEquivalents,
  other,
  testsWritten: totalWritten,
  unkilled: remaining,
  newGaps,
  configProblems,
  noTestProposed,
  unanalyzed,
  contradictions,
})
