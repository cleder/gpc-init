# Tasks: pc-init CLI Scaffold

**Input**: Design documents from `/specs/001-pc-init-cli/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks are REQUIRED. For every behavior change, tests MUST be written first and fail before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project structure: `gpc_init/` for modules, `tests/` for test suite
- Presets: `lang/` and `framework/` directories at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create `gpc_init/` package with `__init__.py` and type stubs
- [ ] T002 Create `tests/` directory structure with `unit/` and `integration/` subdirectories
- [ ] T003 Create `tests/conftest.py` with pytest fixtures for preset loading and temp directories
- [ ] T004 Create `tests/fixtures/` directory with minimal YAML preset samples for testing
- [ ] T005 Configure `pyproject.toml` to enable pytest discovery and pyrefly strict checking
- [ ] T006 Create `.github/workflows/` or equivalent CI configuration to run tests and type checks on PR

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core loading, merging, and rendering infrastructure for all user stories

### Profile Loading and Type Definitions

- [ ] T007 Define `gpc_init/profiles.py` data classes: `LanguageProfile`, `FrameworkProfile`, `RepoConfig`, `HookConfig`, `GenerationRequest`, `GenerationResult` with type annotations
- [ ] T008 Create `tests/unit/test_profiles.py` with unit tests for profile entity validation (missing repos, invalid hook ids, etc.)
- [ ] T009 Implement `gpc_init/profiles.py` data classes with field validation and immutability guards

### Preset Loader

- [ ] T010 [P] Write `tests/unit/test_loader.py` with tests for: discovering `lang/<lang>/baseline.yaml`, `framework/<fw>/preset.yaml`, `lang/common/default.yaml`; handling missing presets; parsing invalid YAML
- [ ] T011 [P] Write `tests/unit/test_loader.py` additional tests for: loading preset as Python dict, preserving hook order, detecting repos key
- [ ] T012 Implement `gpc_init/loader.py` with `load_language_preset(lang_id)`, `load_framework_preset(framework_id)`, `load_common_preset()` functions; return raw dicts with validation
- [ ] T013 Implement `gpc_init/loader.py` error handling: raise `PresetNotFoundError` for missing files, `PresetParseError` for invalid YAML

### Preset Merger

- [ ] T014 [P] Write `tests/unit/test_merger.py` with tests for: merging common + single language preset; preserving repo order and hook order
- [ ] T015 [P] Write `tests/unit/test_merger.py` tests for: merging multiple languages in CLI order; merging frameworks on top of languages; handling duplicate (repo, rev) pairs with hook merging by id
- [ ] T016 [P] Write `tests/unit/test_merger.py` tests for: replacing hook fields when id matches in higher layer; appending new hook ids; deep-merging top-level keys like `default_language_version`; deterministic output
- [ ] T017 Implement `gpc_init/merger.py` with `merge_presets(common, langs, frameworks)` function; enforce exact merge order and semantics per plan.md
- [ ] T018 Implement `gpc_init/merger.py` hook merging logic: `_merge_repos_list(lower, higher)` and `_merge_hook(lower, higher)` internal functions with stable ordering

### YAML Renderer

- [ ] T019 [P] Write `tests/unit/test_renderer.py` with tests for: rendering merged dict to valid YAML string; preserving key order for determinism; rendering repos, hooks, args arrays correctly
- [ ] T020 [P] Write `tests/unit/test_renderer.py` tests for: rendering `None` values properly; handling special YAML characters in args/ids; two identical inputs yield identical YAML strings
- [ ] T021 Implement `gpc_init/renderer.py` with `render_yaml(merged_dict, sort_keys=True)` function; use `yaml.dump()` with deterministic settings (default_flow_style=False, sort_keys=True, width=large)
- [ ] T022 Implement `gpc_init/renderer.py` to ensure YAML parsing round-trip produces semantically identical dict (test with `yaml.safe_load()`)

---

## Phase 3: User Story 1 - Generate Base Configuration (P1)

**Purpose**: Enable `pc-init --lang=<language>` to generate baseline `.pre-commit-config.yaml`

### CLI Interface with typer

- [ ] T023 [P] Write `tests/integration/test_cli_generation.py` with tests for: `pc-init --lang=py` in clean directory creates `.pre-commit-config.yaml`; exit code is 0; file is valid YAML
- [ ] T024 [P] Write `tests/integration/test_cli_generation.py` tests for: `pc-init --lang=py --lang=js` merges both baselines in correct order; exit code is 0
- [ ] T025 [P] Write `tests/integration/test_cli_generation.py` tests for: help text shows `--lang` as required, repeatable; shows `--framework` as optional; shows `--force` as optional flag
- [ ] T026 Implement `gpc_init/cli.py` as typer app with `@typer.command()` on `main()` function accepting `lang: list[str]` (required), `framework: list[str] = None`, `force: bool = False`, `target_path: str = ".pre-commit-config.yaml"`
- [ ] T027 [P] [US1] Implement `gpc_init/cli.py` argument normalization: lowercase all lang/framework values; deduplicate preserving first-occurrence order; validate non-empty langs after dedup
- [ ] T028 [P] [US1] Implement `gpc_init/cli.py` to output success message format: `"Generated .pre-commit-config.yaml with languages: <lang1, lang2> and frameworks: <fw1, fw2>"` or similar

### Request Resolver

- [ ] T029 [P] Write `tests/unit/test_resolver.py` with tests for: validating lang exists in `lang/*/baseline.yaml` catalog; validating framework exists in `framework/*/preset.yaml` catalog; raising `UnsupportedLanguageError` with list of supported options
- [ ] T030 [P] Write `tests/unit/test_resolver.py` tests for: raising `UnsupportedFrameworkError` with list of supported options
- [ ] T031 [P] Implement `gpc_init/resolver.py` with `validate_and_resolve(request)` function: discover supported languages from `lang/` directory; discover supported frameworks from `framework/` directory; validate request against catalogs
- [ ] T032 [P] Implement `gpc_init/resolver.py` catalog discovery to scan `lang/<lang>/baseline.yaml` and `framework/<fw>/preset.yaml` files at startup; cache catalogs; expose `get_supported_languages()` and `get_supported_frameworks()`

### Generation Flow Integration

- [ ] T033 Write `tests/integration/test_cli_generation.py` end-to-end test: `pc-init --lang=py` in temp dir → produces file → is valid pre-commit YAML → contains Python hooks
- [ ] T034 [P] [US1] Implement `gpc_init/cli.py` main function to: parse args → validate with resolver → load common + lang presets → merge → render → write to file → report success
- [ ] T035 [P] [US1] Implement `gpc_init/cli.py` to invoke loader, merger, resolver, renderer in sequence with error propagation; catch exceptions and output actionable error messages to stderr

---

## Phase 4: User Story 2 - Apply Framework-Specific Enhancements (P2)

**Purpose**: Enable `pc-init --lang=<lang> --framework=<fw>` to merge framework presets

### Framework Support

- [ ] T036 [P] Write `tests/unit/test_merger.py` additional tests for: merging framework presets on top of language baselines; framework hooks appended after language hooks; framework args override language args for same hook id
- [ ] T037 [P] Write `tests/integration/test_cli_generation.py` tests for: `pc-init --lang=js --framework=react` produces output with JS hooks + React hooks; exit code is 0
- [ ] T038 [P] Write `tests/integration/test_cli_generation.py` tests for: `pc-init --lang=py --lang=js --framework=django --framework=react` merges in deterministic order (common → py → js → django → react)
- [ ] T039 Write `tests/integration/test_cli_generation.py` test for Scenario B2 from quickstart: `pc-init --lang=py --lang=js --framework=django --framework=react` produces valid config with all four contributions
- [ ] T040 [P] [US2] Populate `framework/react/preset.yaml` with React-specific hooks and `primary_languages: [js]` metadata (informational only)
- [ ] T041 [P] [US2] Populate `framework/bevy/preset.yaml` with Bevy-specific hooks and `primary_languages: [ru]` metadata (informational only)
- [ ] T042 [P] [US2] Implement framework merging in `gpc_init/merger.py` to handle optional frameworks; framework presets are purely additive

### Framework Validation (Informational Only)

- [ ] T043 [P] [US2] Implement `gpc_init/resolver.py` to note but not enforce `primary_languages` from framework presets; output informational message if user-selected languages don't match any framework's primary languages (non-blocking, informational only)
- [ ] T044 [P] [US2] Write `tests/integration/test_cli_generation.py` test for: `pc-init --lang=go --framework=react` succeeds (no validation error); produces config with Go baseline + React additions (even though Go not in React's primary_languages)

---

## Phase 5: User Story 3 - Safe and Clear CLI Behavior (P3)

**Purpose**: Implement error messages, overwrite behavior, and file safety

### Error Handling

- [ ] T045 [P] Write `tests/integration/test_cli_generation.py` tests for: `pc-init --lang=unsupported-lang` fails with exit code non-zero; stderr includes list of supported languages
- [ ] T046 [P] Write `tests/integration/test_cli_generation.py` tests for: `pc-init --lang=py --framework=unsupported-fw` fails with exit code non-zero; stderr includes list of supported frameworks
- [ ] T047 [P] Implement `gpc_init/cli.py` error handling to catch `UnsupportedLanguageError` and `UnsupportedFrameworkError`; format as `"Error: unsupported language 'xxx'. Supported: py, js, go, ru"` and similar for frameworks
- [ ] T048 [P] Implement `gpc_init/cli.py` error handling for YAML parse errors; output `"Error: failed to parse preset YAML: <detail>"`

### Overwrite Behavior

- [ ] T049 [P] Write `tests/integration/test_cli_generation.py` tests for: file exists, `pc-init --lang=py` (no force) exits non-zero; file unchanged; stderr tells user to use `--force`
- [ ] T050 [P] Write `tests/integration/test_cli_generation.py` tests for: file exists, `pc-init --lang=py --force` exits 0; file overwritten; stdout confirms overwrite
- [ ] T051 [P] Implement `gpc_init/cli.py` to check file existence before write; if exists and not `force`, raise `FileExistsError` with guidance; if `force`, proceed with write
- [ ] T052 [P] Implement `gpc_init/cli.py` to track and report `overwritten: True` in success message when `--force` used and file existed

### Argument Normalization

- [ ] T053 [P] Write `tests/integration/test_cli_generation.py` tests for: `pc-init --lang=py --lang=python` normalizes alias and deduplicates to a single `py`; `pc-init --lang=py --lang=py` single result
- [ ] T054 [P] Write `tests/integration/test_cli_generation.py` tests for: mixed case `--lang=Python` normalized to canonical `py`
- [ ] T055 [P] [US3] Implement `gpc_init/cli.py` argument normalization in resolver: deduplicate `--lang` and `--framework` values preserving first occurrence; convert to lowercase; resolve aliases to canonical ids; validate after normalization

### File Permission Handling

- [ ] T056 [P] Write `tests/integration/test_cli_generation.py` tests for: target directory not writable → exit non-zero; stderr includes path and permission error detail
- [ ] T057 [P] [US3] Implement `gpc_init/cli.py` try-catch around file write; catch `PermissionError`, `OSError`; output `"Error: cannot write to <path>: <detail>"`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Type safety, comprehensive testing, documentation, and deployment readiness

### Type Safety & Code Quality

- [ ] T058 Implement complete type annotations across all modules: `gpc_init/profiles.py`, `gpc_init/loader.py`, `gpc_init/merger.py`, `gpc_init/renderer.py`, `gpc_init/resolver.py`, `gpc_init/cli.py`
- [ ] T059 Run `uv run pyrefly --strict` on all modules; resolve all type errors and warnings; ensure strict mode passes with no exceptions
- [ ] T060 [P] [US1] [US2] [US3] Add docstrings to all public functions and classes explaining purpose, arguments, return values, exceptions
- [ ] T061 [P] Implement custom exceptions: `PresetNotFoundError`, `PresetParseError`, `UnsupportedLanguageError`, `UnsupportedFrameworkError`, `FileExistsError` in `gpc_init/exceptions.py`

### Comprehensive Testing

- [ ] T062 Write `tests/integration/test_cli_scenarios.py` covering all quickstart scenarios: A (baseline), B (framework), B2 (polyglot), D (existing file), E (force), with fixture setup
- [ ] T063 [P] Write `tests/integration/test_determinism.py` to verify: same input twice produces identical output file; different language orders produce different but valid outputs; framework order matters for output order
- [ ] T064 [P] Add edge case tests to `tests/integration/`: empty framework list, single language, three+ languages, three+ frameworks, all combinations
- [ ] T065 Verify full test coverage with `pytest --cov=gpc_init --cov-report=term-missing`; aim for >= 90% coverage

### Build & Deployment

- [ ] T066 Update `main.py` or add entry point to `pyproject.toml` to invoke `gpc_init.cli.main()` when running `pc-init` command
- [ ] T067 Test `uv run pc-init --help` displays typer help with all flags and examples
- [ ] T068 Update `README.md` with usage examples: `pc-init --lang=py`, `pc-init --lang=js --framework=react`, error case explanations
- [ ] T069 Add quickstart validation script or CI check to run all Scenario A-E tests from `specs/001-pc-init-cli/quickstart.md`

### Code Review & Documentation

- [ ] T070 Review `gpc_init/merger.py` merge order implementation against plan.md Merge Semantics section; verify all hook replacement and append logic is correct
- [ ] T071 Review `gpc_init/resolver.py` catalog discovery to ensure it is efficient and deterministic (filesystem order neutral)
- [ ] T072 Document preset structure and extension patterns in `PRESET_DEVELOPMENT.md` for future language/framework additions

---

## Dependency Graph

### User Story Completion Order

1. **US1 (P1 - MVP)**: Can run independently. Prerequisite: Phase 2 (foundational loader/merger/renderer).
2. **US2 (P2)**: Depends on US1. Adds framework support on top of working language baseline.
3. **US3 (P3)**: Depends on US1. Adds safety checks and error messaging.

### Suggested MVP Scope

- **MVP Release**: Complete Phase 1, Phase 2, Phase 3 (US1 only)
- **Follow-up Release**: Phase 4 (US2)
- **Final Release**: Phase 5 (US3) + Phase 6 (Polish)

### Parallel Execution Opportunities

**Phase 2 Parallelization** (after Phase 1):
- T007-T009 (profiles) can run in parallel with T010-T013 (loader)
- T014-T018 (merger tests + impl) can run in parallel with T019-T022 (renderer) once profiles are done

**Phase 3 Parallelization** (after Phase 2):
- T023-T025 (CLI tests) can run in parallel with T029-T032 (resolver)
- T026-T028 (CLI impl) depends on both CLI tests and resolver; proceed after both are drafted

**Phase 4 Parallelization** (after Phase 3):
- T036-T044 (framework tests + impl) can all run in parallel; no inter-dependencies

**Phase 5 Parallelization** (after Phase 3):
- T045-T048 (error handling) and T049-T057 (overwrite + file ops) can run in parallel

---

## Implementation Strategy

1. **Red-Green-Refactor TDD**: Write test task first (T0XX with description ending in "write tests"), watch fail, implement (T0XX with "implement"), watch pass, refactor as needed.
2. **Type-Safe From Start**: Add type annotations as part of each implementation task; do not defer to Phase 6.
3. **Determinism Verification**: After each merge/render task, manually verify identical inputs produce identical output using `diff -u`.
4. **Error Messages First**: Before implementing a feature, decide error messages (per CLI contract); tests should verify message content.
5. **Incremental Integration**: After Phase 3 (US1), pause and run full quickstart scenario A; debug before proceeding to Phase 4.

---

## Testing Requirements Summary

- **Unit tests** (test_*.py files): Profile validation, loader, merger, renderer, resolver logic in isolation.
- **Integration tests** (tests/integration/): CLI end-to-end with real preset files and filesystem I/O.
- **Determinism tests**: Verify identical inputs → identical YAML output.
- **Error case tests**: Unsupported lang, unsupported fw, file exists, permission denied, invalid YAML, etc.
- **Quickstart validation**: Run all Scenario A-E commands and verify expected outcomes.

**Total test count target**: 40+ tests (unit + integration) covering all user stories and error cases.

---

## Files to Create/Modify

### Created
- `gpc_init/__init__.py`
- `gpc_init/profiles.py`
- `gpc_init/loader.py`
- `gpc_init/merger.py`
- `gpc_init/renderer.py`
- `gpc_init/resolver.py`
- `gpc_init/cli.py`
- `gpc_init/exceptions.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/fixtures/` (preset samples)
- `tests/unit/test_profiles.py`
- `tests/unit/test_loader.py`
- `tests/unit/test_merger.py`
- `tests/unit/test_renderer.py`
- `tests/unit/test_resolver.py`
- `tests/integration/test_cli_generation.py`
- `tests/integration/test_cli_scenarios.py`
- `tests/integration/test_determinism.py`
- `framework/react/preset.yaml`
- `framework/bevy/preset.yaml`
- `PRESET_DEVELOPMENT.md`

### Modified
- `main.py` (add entry point)
- `pyproject.toml` (ensure pytest, pyrefly configured)
- `README.md` (add usage examples)
