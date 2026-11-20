export const meta = {
  name: 'mutmut-kill-survivors',
  description: 'Analyze surviving mutmut mutants and write targeted tests to kill them',
  phases: [
    { title: 'Discover', detail: 'Find project root, mutmut binary, and surviving mutants' },
    { title: 'Cache', detail: 'Skip re-analysis of equivalent mutants whose source file is unchanged' },
    { title: 'Analyze', detail: 'Classify each uncached mutant: missing test vs equivalent' },
    { title: 'Write', detail: 'Add tests grouped by test file' },
    { title: 'Verify', detail: 'Re-run mutmut and report the delta' },
  ],
}

// Project root: pass as args (string path), or leave unset to auto-detect via git.
const PROJECT = typeof args === 'string' && args.trim() ? args.trim() : null

const DISCOVERY_SCHEMA = {
  type: 'object',
  properties: {
    project: { type: 'string' },
    mutmut_bin: { type: 'string' },
    pytest_bin: { type: 'string' },
    run_exit_code: { type: 'number' },
    total_mutants: { type: 'number' },
    survivors: { type: 'array', items: { type: 'string' } },
  },
  required: ['project', 'mutmut_bin', 'pytest_bin', 'run_exit_code', 'total_mutants', 'survivors'],
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

const ANALYSIS_SCHEMA = {
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

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    run_exit_code: { type: 'number' },
    total_mutants: { type: 'number' },
    remaining_count: { type: 'number' },
    remaining: { type: 'array', items: { type: 'string' } },
  },
  required: ['run_exit_code', 'total_mutants', 'remaining_count', 'remaining'],
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
  if (!(report.total_mutants > 0)) {
    throw new Error(
      `${step}: mutmut reported ${report.total_mutants} mutants, so it did not actually run; an empty survivor list is not a result.`,
    )
  }
}

// ─── Phase 1: Discover ────────────────────────────────────────────────────────

phase('Discover')

const discovery = await agent(
  `You are a mutation testing assistant. Find the project, tool binaries, and surviving mutants.

${PROJECT ? `Project directory: ${PROJECT}` : `Step 0 — Detect the project root:
  Run: git rev-parse --show-toplevel
  Use this path as <project> in all subsequent steps.`}

Step 1 — Find the mutmut binary (try each in order, use the first that exists):
  <project>/.venv/bin/mutmut
  <project>/venv/bin/mutmut
  which mutmut

Step 2 — Find the pytest binary (try each in order):
  <project>/.venv/bin/pytest
  <project>/venv/bin/pytest
  which pytest

Step 3 — Run mutmut for real. Never skip this: "mutmut results" alone only reads stale
  data and reports no survivors when nothing has run.
  cd <project> && <mutmut_bin> run
  Record the command's exit code as run_exit_code. Do not retry or hide a failure:
  report the non-zero exit code as it is.

Step 4 — Count and list the mutants (only after step 3):
  cd <project> && <mutmut_bin> results --all true 2>&1
  total_mutants = the number of lines of the form "<name>: <status>".
  survivors = the names (part before ": survived") of the lines whose status is "survived".

Return: the resolved project path, mutmut_bin path, pytest_bin path, run_exit_code,
total_mutants, and the survivors list.`,
  { schema: DISCOVERY_SCHEMA },
)

assertMutmutRan('Discover', discovery)

const project = PROJECT || discovery.project
const mutmutBin = discovery.mutmut_bin
const pytestBin = discovery.pytest_bin

if (discovery.survivors.length === 0) {
  log(`No surviving mutants out of ${discovery.total_mutants} — mutation score is 100%.`)
  return { status: 'complete', killed: 0, equivalent: 0, remaining: 0 }
}

log(`Found ${discovery.survivors.length} surviving mutants in ${project}`)

// ─── Phase 2: Cache ───────────────────────────────────────────────────────────

phase('Cache')

const cacheCheck = await agent(
  `Load the equivalents cache and identify which surviving mutants still need analysis.

Cache file: ${project}/.mutmut-equivalents.json
All surviving mutants: ${JSON.stringify(discovery.survivors)}

Steps:
1. Try to read ${project}/.mutmut-equivalents.json.
   If the file does not exist or cannot be parsed, set cached_equivalents = [] and
   survivors_to_analyze = all survivors — do not error.
2. Parse the JSON array. For each cache entry whose mutant_name appears in the survivors list:
   a. Run: cd ${project} && git hash-object <entry.source_file>
   b. If the hash matches entry.file_hash exactly: file is unchanged → include in cached_equivalents.
   c. If the hash differs, the command errors, or the source file is missing: discard from cache.
3. survivors_to_analyze = all survivors NOT covered by a valid (still-matching) cache entry.

Return cached_equivalents (valid cache hits) and survivors_to_analyze (need fresh analysis).`,
  { schema: CACHE_LOAD_SCHEMA, phase: 'Cache' },
)

const cachedEquivalents = cacheCheck.cached_equivalents
const survivorsToAnalyze = cacheCheck.survivors_to_analyze

if (cachedEquivalents.length > 0) {
  log(`Cache: ${cachedEquivalents.length} equivalent mutant(s) skipped (source file unchanged)`)
}

if (survivorsToAnalyze.length === 0) {
  log('All surviving mutants are cached equivalents — nothing to analyze.')
  return {
    status: 'complete',
    tests_written: 0,
    equivalent: cachedEquivalents.length,
    equivalent_mutants: cachedEquivalents.map((e) => ({ name: e.mutant_name, reason: e.equivalent_reason })),
  }
}

log(`Analyzing ${survivorsToAnalyze.length} uncached survivor(s)`)

// ─── Phase 3: Analyze ─────────────────────────────────────────────────────────

phase('Analyze')

const analyses = (await pipeline(
  survivorsToAnalyze,
  (name) => agent(
    `Analyze the surviving mutmut mutant "${name}" in the project at ${project}.

STEP 1 — See the diff:
  cd ${project} && ${mutmutBin} show "${name}"

STEP 2 — Identify the source file:
  The mutant name encodes the source module. Examples:
    "pkg.module.x__function__mutmut_N"  →  source_file = "pkg/module.py"
    "src.utils.x__helper__mutmut_1"     →  source_file = "src/utils.py"
  Derive the path from the mutant name, then read the mutated function in ${project}/<source_file>.

STEP 3 — Find the test file:
  Search by the source module name (replace <module> with the last segment of the module path):
    find ${project}/tests -name "test_<module>*.py" 2>/dev/null | head -5
  Or broader if nothing found:
    find ${project} -name "test_<module>*.py" -not -path "*/.venv/*" -not -path "*/venv/*" | head -5
  Pick the best match. If none exists, choose a sensible location (e.g. tests/unit/test_<module>.py).
  Read the test file to understand the existing structure, fixtures, and naming style.

STEP 4 — Classify:
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
  → keep the test minimal — test one thing`,
    { label: `analyze:${name}`, schema: ANALYSIS_SCHEMA, phase: 'Analyze' },
  ),
)).filter(Boolean)

const equivalent = analyses.filter((a) => a.is_equivalent)
const actionable = analyses.filter((a) => !a.is_equivalent && a.test_code)

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

if (actionable.length === 0) {
  return {
    status: 'complete',
    tests_written: 0,
    equivalent: equivalent.length + cachedEquivalents.length,
    equivalent_mutants: [
      ...equivalent.map((a) => ({ name: a.mutant_name, reason: a.equivalent_reason })),
      ...cachedEquivalents.map((e) => ({ name: e.mutant_name, reason: e.equivalent_reason })),
    ],
  }
}

// ─── Phase 4: Write ───────────────────────────────────────────────────────────

phase('Write')

// Group by test file so no two agents edit the same file concurrently
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
3. Add any missing imports at the top of the file.
4. Run: cd ${project} && ${pytestBin} ${testFile} -x -q
   The tests MUST PASS against the original (unmutated) code.
   If a test fails to collect (syntax/import error), fix it.
   If a test fails at runtime, the test logic is wrong — revise it once, then skip it
   and note it in the notes field rather than writing a broken test.
5. Report how many tests were successfully written (tests_written) and which
   mutant names they target (mutants_targeted).`,
      { label: `write:${testFile}`, schema: WRITE_SCHEMA, phase: 'Write' },
    ),
  ),
)).filter(Boolean)

const totalWritten = writeResults.reduce((sum, r) => sum + r.tests_written, 0)
log(`Wrote ${totalWritten} tests across ${writeResults.length} file(s)`)

// ─── Phase 5: Verify ──────────────────────────────────────────────────────────

phase('Verify')

const verification = await agent(
  `Re-run mutmut in ${project} and report the surviving mutants after the new tests were added.

Steps:
  cd ${project} && ${mutmutBin} run
  Record the command's exit code as run_exit_code; report a non-zero code as it is.
  cd ${project} && ${mutmutBin} results --all true 2>&1
  total_mutants = the number of lines of the form "<name>: <status>".
  remaining = the names (part before ": survived") of the lines whose status is "survived".

Return run_exit_code, total_mutants, the remaining names, and remaining_count (their number).`,
  { schema: VERIFY_SCHEMA, phase: 'Verify' },
)

assertMutmutRan('Verify', verification)

const started = discovery.survivors.length
const remaining = verification.remaining_count
const totalEquivalent = equivalent.length + cachedEquivalents.length
const newlyKilled = started - remaining

log(`Started: ${started}  |  Killed: ${newlyKilled}  |  Equivalent: ${totalEquivalent} (${cachedEquivalents.length} cached)  |  Still surviving: ${remaining}`)

return {
  started_with: started,
  newly_killed: newlyKilled,
  equivalent_mutants: [
    ...equivalent.map((a) => ({ name: a.mutant_name, reason: a.equivalent_reason })),
    ...cachedEquivalents.map((e) => ({ name: e.mutant_name, reason: e.equivalent_reason })),
  ],
  tests_written: totalWritten,
  still_surviving: remaining,
  remaining_survivors: verification.remaining,
}
