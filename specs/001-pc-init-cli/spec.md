# Feature Specification: pc-init CLI Scaffold

**Feature Branch**: `[001-pc-init-cli]`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "I want to build the pc-int command line tool as laid out in the README.md"

## Clarifications

### Session 2026-06-20

- Q: How should existing `.pre-commit-config.yaml` overwrite behavior work?
  → A: Use `--force` to overwrite existing `.pre-commit-config.yaml`; without it, command exits with error and keeps file unchanged.
- Q: Should frameworks be tied to language profiles?
  → A: Frameworks are language-agnostic with optional primary language recommendations.
- Q: Can a repository specify multiple languages and frameworks?
  → A: Yes.
  `--lang` and `--framework` are repeatable flags; merge order follows CLI input order.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Base Configuration (Priority: P1)

As a developer creating a new repository, I want a single command that generates a baseline `.pre-commit-config.yaml` for my chosen language so I can start with a reliable quality gate immediately.

**Why this priority**: This is the core value of the product and the minimum useful outcome.

**Independent Test**: Run `pc-init --lang=<supported-language>` or multiple `--lang` values in an empty project and verify a valid `.pre-commit-config.yaml` is created with the selected language baselines.

**Acceptance Scenarios**:

1. **Given** a new repository with no existing pre-commit config, **When** the user runs `pc-init --lang=py`, **Then** a `.pre-commit-config.yaml` file is created with a production-ready Python baseline profile.
2. **Given** a supported language, **When** the user runs `pc-init --lang=<language>`, **Then** the generated file includes only the hooks relevant to that language baseline.
3. **Given** multiple supported languages, **When** the user runs `pc-init --lang=py --lang=js`, **Then** the generated file includes merged baselines for both languages in deterministic order.

---

### User Story 2 - Apply Framework-Specific Enhancements (Priority: P2)

As a developer using a framework, I want optional framework tuning on top of language defaults so my generated config better matches common framework workflows.

**Why this priority**: Framework support improves relevance and reduces manual edits, but depends on having language defaults first.

**Independent Test**: Run `pc-init --lang=<language> [--lang=<language>...] --framework=<supported-framework> [--framework=<supported-framework>...]` and verify framework additions apply universally.

**Acceptance Scenarios**:

1. **Given** a supported language and framework pair, **When** the user runs `pc-init --lang=js --framework=react`, **Then** the output includes JavaScript baseline hooks plus React-specific linting additions.
2. **Given** a supported language and framework pair, **When** config is generated, **Then** framework additions do not remove required baseline language checks.
3. **Given** multiple selected languages, **When** the user runs `pc-init --lang=py --lang=js --framework=react`, **Then** the framework is accepted regardless of language selection.

---

### User Story 3 - Safe and Clear CLI Behavior (Priority: P3)

As a developer, I want clear error messages and predictable overwrite behavior so I can use the tool confidently in fresh and existing repositories.

**Why this priority**: Safety and clarity prevent accidental file loss and improve user trust.

**Independent Test**: Run commands with unsupported options and with existing config files; verify informative errors and deterministic behavior for overwrite/no-overwrite paths.

**Acceptance Scenarios**:

1. **Given** an unsupported language, **When** the user runs `pc-init --lang=<unsupported>`, **Then** the command fails with a clear, actionable message listing supported options.
2. **Given** `.pre-commit-config.yaml` already exists, **When** the user runs `pc-init` without overwrite intent, **Then** the command preserves the existing file and reports next steps.
3. **Given** `.pre-commit-config.yaml` already exists, **When** the user runs `pc-init --lang=<supported-language> --force`, **Then** the command overwrites the file non-interactively and reports success.

### Edge Cases

- Existing `.pre-commit-config.yaml` is present and user does not want to overwrite it.
- Existing `.pre-commit-config.yaml` is present and user provides `--force` to overwrite.
- User repeats the same `--lang` or `--framework` value multiple times.
- User provides mixed casing or surrounding whitespace in language/framework values.
- Unknown framework is provided for an otherwise supported language.
- Multiple selected frameworks modify the same hook definition.
- File generation target path is not writable.
- Generated profile has no framework-specific additions for a valid framework and should gracefully fall back to language baseline.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a CLI command `pc-init` that accepts one or more `--lang` parameters.
- **FR-002**: System MUST accept zero or more `--framework` parameters that augment the selected language profiles when supported.
- **FR-003**: System MUST generate a valid `.pre-commit-config.yaml` file in the current project directory.
- **FR-004**: System MUST provide deterministic output for identical inputs and tool version.
- **FR-004a**: System MUST load language baseline presets from `lang/<language>/` folders.
- **FR-004b**: System MUST load framework presets from `framework/<framework>/` folders.
- **FR-005**: System MUST include production-ready baseline hook sets for at least Python, JavaScript, Go, and Rust.
- **FR-006**: System MUST include framework-specific augmentations for at least React and Bevy, with optional primary language recommendations per framework.
- **FR-007**: System MUST reject unsupported language or framework inputs with actionable error messages.
  Framework primary language recommendations are informational only and do not block framework selection.
- **FR-008**: System MUST define behavior-level tests in `pytest` for every new or changed behavior before implementation begins.
- **FR-009**: System MUST pass strict static type checking (`pyrefly` strictest settings) for all changed Python code.
- **FR-010**: System MUST preserve existing config by default when a target file already exists, returning a non-zero exit with guidance to use `--force`.
- **FR-011**: System MUST emit user-facing success output that summarizes selected languages/frameworks and output path.
- **FR-012**: System MUST overwrite an existing `.pre-commit-config.yaml` only when the user explicitly provides `--force`, without interactive prompts.
- **FR-013**: System MUST model frameworks independently from language profiles and optionally declare primary_languages for informational guidance.
- **FR-014**: System MUST merge language and framework presets in deterministic order: common baseline, then languages in CLI order, then frameworks in CLI order.

### Key Entities *(include if feature involves data)*

- **Language Profile**: A named baseline configuration describing default hook repositories, revisions, and hooks for a specific language.
- **Framework Profile**: An optional additive configuration independent from language profiles that declares framework-specific hooks/arguments and optional primary language recommendations.
- **Preset Source**: Filesystem-backed preset directories where language presets live under `lang/` and framework presets live under `framework/`.
- **Generation Request**: User-provided command inputs (`langs[]`, optional `frameworks[]`, overwrite intent) used to resolve a final output profile.
- **Generated Configuration**: The final `.pre-commit-config.yaml` document produced from resolved baseline plus optional framework additions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95% of first-time users can generate a working baseline config in under 60 seconds from reading command help.
- **SC-002**: 100% of supported language and language+framework combinations produce a valid YAML configuration document.
- **SC-003**: 100% of repeated runs with identical inputs produce semantically equivalent output.
- **SC-004**: At least 90% of invalid-input runs provide an error message that users can resolve without external documentation.
- **SC-005**: Task completion for new-repository pre-commit setup is reduced from multiple manual steps to a single command invocation.

## Assumptions

- The tool is run in the root of a repository where `.pre-commit-config.yaml` should be created.
- Users can install and run pre-commit tooling separately after config generation.
- Initial release scope includes Python, JavaScript, Go, and Rust baseline profiles, with React and Bevy framework augmentations.
- Overwrite behavior is opt-in to prevent accidental loss of existing configuration files.
- Output structure should remain minimal and extensible to support additional languages and frameworks later without breaking existing behavior.
