# Data Model: pc-init CLI Scaffold

## Entity: LanguageProfile
- Purpose: Baseline hook configuration for a programming language.
- Fields:
  - `id` (string): canonical language key (e.g., `python`, `javascript`, `go`, `rust`).
  - `display_name` (string): user-facing language name.
  - `repos` (list[RepoConfig]): ordered repository/hook definitions.
- Validation rules:
  - `id` must be unique and lowercase.
  - `repos` must be non-empty.
  - Hook order must be stable.

## Entity: FrameworkProfile
- Purpose: Optional additive configuration independent from language profiles.
- Fields:
  - `id` (string): canonical framework key (e.g., `react`, `bevy`).
  - `display_name` (string): user-facing framework name.
  - `primary_languages` (list[string], optional): recommended language IDs for this framework.
  - `repos` (list[RepoConfig]): additive hooks/args to merge into baseline.
- Validation rules:
  - `primary_languages` is optional and informational only.
  - Framework IDs must be unique.
  - Additive hooks must not delete baseline hooks.

## Entity: RepoConfig
- Purpose: A pre-commit repository entry.
- Fields:
  - `repo` (string): repository URL.
  - `rev` (string): pinned revision.
  - `hooks` (list[HookConfig]): ordered hook definitions.
- Validation rules:
  - `repo` must be non-empty URI-like string.
  - `rev` must be non-empty and pinned.
  - `hooks` must contain at least one hook.

## Entity: HookConfig
- Purpose: Individual pre-commit hook item.
- Fields:
  - `id` (string): hook id.
  - `args` (list[string], optional): hook args.
  - `additional_dependencies` (list[string], optional): extra deps.
  - `stages` (list[string], optional): optional stages.
- Validation rules:
  - `id` must be non-empty.
  - Optional lists must preserve order for deterministic output.

## Entity: GenerationRequest
- Purpose: User request parsed from CLI.
- Fields:
  - `langs` (list[string]): requested languages in CLI order.
  - `frameworks` (list[string]): requested frameworks in CLI order.
  - `force` (bool): overwrite intent.
  - `target_path` (string): output file path (defaults `.pre-commit-config.yaml`).
- Validation rules:
  - `langs` must be non-empty after normalization and deduplication.
  - each value in `langs` must exist in language profile catalog.
  - each value in `frameworks` must exist in framework catalog.
  - `primary_languages` in framework presets are informational; they do not block framework selection.

## Entity: GenerationResult
- Purpose: Deterministic rendering and write outcome.
- Fields:
  - `content` (string): rendered YAML.
  - `path` (string): output file path.
  - `overwritten` (bool): whether existing file was replaced.
- Validation rules:
  - `content` must parse as valid YAML.
  - identical requests must yield semantically equivalent `content`.

## State Transitions
1. `GenerationRequest` parsed from CLI input.
2. Request validated against language and framework catalogs.
3. Effective config assembled: common baseline + ordered `LanguageProfile[]` + ordered `FrameworkProfile[]`.
4. YAML rendered deterministically into `GenerationResult.content`.
5. File write applied or rejected based on `force` and file existence rules.
