<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Modified principles:
	- Principle 1 -> I. Purpose-Driven CLI Output
	- Principle 2 -> II. Deterministic Configuration Generation
	- Principle 3 -> III. Test-First Delivery (NON-NEGOTIABLE)
	- Principle 4 -> IV. Strict Static Typing with Pyrefly
	- Principle 5 -> V. Minimal, Extensible Hook Profiles
- Added sections:
	- Technical Standards
	- Workflow & Quality Gates
- Removed sections: none
- Templates requiring updates:
	- ✅ updated .specify/templates/plan-template.md
	- ✅ updated .specify/templates/spec-template.md
	- ✅ updated .specify/templates/tasks-template.md
	- ✅ verified .specify/extensions/agent-context/commands/speckit.agent-context.update.md
- Follow-up TODOs: none
-->

# pc-init Constitution

## Core Principles

### I. Purpose-Driven CLI Output
The project MUST prioritize generating practical, production-ready
`.pre-commit-config.yaml` files from clear CLI inputs (`--lang`, optional
`--framework`). Every feature MUST directly improve initialization quality,
maintainability, or user guidance for repository setup.

Rationale: The tool exists to eliminate repetitive copy-paste setup and provide
reliable first-commit quality gates.

### II. Deterministic Configuration Generation
Given the same inputs and version, the generator MUST produce semantically
equivalent output every time. Default profiles, hook ordering, and revisions
MUST be explicitly encoded and test-covered.

Rationale: Deterministic output enables trust, easier review, and stable CI
behavior across environments.

### III. Test-First Delivery (NON-NEGOTIABLE)
All behavior changes MUST follow red-green-refactor with `pytest`.
Implementation code MUST NOT be merged unless tests for the new or changed
behavior were written first, observed failing, and then passing.

Rationale: TDD reduces regressions and keeps behavior specification close to the
user-facing contract.

### IV. Strict Static Typing with Pyrefly
All Python code MUST satisfy `pyrefly` under the strictest available settings.
Type errors MUST block merge, and new public functions MUST include explicit
type signatures.

Rationale: Strong static guarantees improve maintainability and reduce runtime
configuration bugs.

### V. Minimal, Extensible Hook Profiles
Generated configurations MUST remain minimal for each stack while preserving a
clear path for extension. Stack-specific additions are allowed only when they
provide concrete quality value and do not degrade baseline usability.

Rationale: The project serves many repository types; concise defaults with
explicit extension points balance simplicity and power.

## Technical Standards

- Runtime language MUST be Python.
- Tests MUST be authored and executed with `pytest`.
- Static typing MUST be enforced with strict `pyrefly`.
- Generated `.pre-commit-config.yaml` files MUST be valid YAML.
- Documentation and examples MUST reflect supported language/framework options.

## Workflow & Quality Gates

- Every change proposal MUST define expected CLI behavior and generated config
	deltas before implementation.
- Pull requests MUST include:
	- Failing-then-passing test evidence for behavior changes.
	- `pytest` results for affected scope.
	- strict `pyrefly` results.
- Reviews MUST reject changes that violate deterministic output, TDD sequence,
	or strict typing requirements.

## Governance

This constitution overrides conflicting local process notes. Amendments require
documentation of impact, explicit approval by project maintainers, and updates
to affected templates in `.specify/templates/`.

Versioning policy:
- MAJOR for principle removals or incompatible governance changes.
- MINOR for new principles or materially expanded mandatory guidance.
- PATCH for clarifications, wording, and non-semantic edits.

Compliance review expectations:
- Every plan MUST pass a constitution check before implementation starts.
- Every task list MUST include work for tests and strict type checking.
- Every merge review MUST verify constitution adherence explicitly.

**Version**: 1.0.0 | **Ratified**: 2026-06-20 | **Last Amended**: 2026-06-20
