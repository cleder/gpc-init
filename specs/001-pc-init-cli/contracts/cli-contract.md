# CLI Contract: pc-init

## Command

`pc-init --lang <LANG> [--lang <LANG> ...] [--framework <FRAMEWORK> ...] [--force]`

## Inputs

- `--lang` (required, repeatable)
  - Canonical language ids: `py`, `js`, `go`, `ru`.
  - Accepted aliases: `python` -> `py`, `javascript` -> `js`, `rust` -> `ru`.
  - At least one value is required.
  - Values must exist in language profile catalog after normalization.
- `--framework` (optional, repeatable)
  - Canonical framework id.
  - Values must exist in framework catalog.
  - Frameworks can be selected with any combination of languages; primary_languages are recommendations only.
- `--force` (optional, flag)
  - When present, allows overwrite of existing `.pre-commit-config.yaml`.

## Output File

- Path: `.pre-commit-config.yaml` in current working directory.
- Encoding: UTF-8 text.
- Format: YAML compatible with `pre-commit`.

## Success Behavior

- Exit code: `0`.
- Side effect: file written (or overwritten when `--force` used).
- Stdout: concise success message including selected languages, selected frameworks, and output path.

## Error Behavior

- Exit code: non-zero.
- Stderr: actionable message.

### Error Cases

1. Unsupported language

- Condition: `--lang` not in language catalog.
- Message includes supported language ids.

2. Unsupported framework

- Condition: `--framework` not in framework catalog.
- Message includes supported framework ids.

3. Existing target without force

- Condition: `.pre-commit-config.yaml` already exists and `--force` absent.
- Message tells user to rerun with `--force` to overwrite.

4. Write failure

- Condition: permission/path or IO error while writing output file.
- Message includes target path and OS error summary.

## Determinism Guarantee

For identical inputs and tool version, produced YAML must be semantically equivalent:

- Merge order: common baseline, then languages in CLI order, then frameworks in CLI order.
- Stable repository/hook ordering.
- Stable key ordering in rendered maps when serializer permits.
- No random or time-based fields.
