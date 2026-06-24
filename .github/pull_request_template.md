## Description

<!-- Describe what this PR adds or changes and why. -->

## Pre-submission checklist

- [ ] This PR touches exactly one language or framework preset

Run the following commands against the preset file and confirm each passes.

- [ ] `pre-commit validate-config <preset-file>` passes without errors
- [ ] `prek validate-config <preset-file>` passes without errors
- [ ] `pre-commit autoupdate -c <preset-file>` was run and hook revisions are up to date
- [ ] `prek autoupdate -c <preset-file>` was run and hook revisions are up to date
- [ ] All hooks listed in the preset are publicly available and actively maintained
