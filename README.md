# pc-init

I use pre-commit (and now are beginning to migrate to prek) extensively in all my projects (work and hobby), and create a lot of repositories (every other month or so, enough for this to be a pain point, but not enough to have the workflow committed to my muscle memory).

Whenever I create a new repo, I have to cut and paste the .pre-commit-config.yaml into the new project - which requires remembering what other project has the most appropriate and up-to-date configuration.


## Summary

pc-init

The `pc-init` command (init) accepts optional --lang (language) and --framework parameters. 

This would allow the tool to automatically scaffold a more relevant and production-ready initial configuration file (.pre-commit-config.yaml) based on the project's primary technology stack.

## Motivation

Many languages and frameworks have popular, community-standard custom linters, formatters, and code quality tools (e.g., black for Python, eslint for JavaScript/React, go fmt for Go).

Currently, setting up a new project requires the user to manually:

1. Identify the recommended quality tools for their stack.
2. Look up the corresponding pre-commit hook repository URLs, revisions, and arguments.
3. Manually edit the `.pre-commit-config.yaml` file.

`pc-init`s  `--lang` and `--framework` parameters drastically simplify onboarding, encourage the adoption of best practices, and reduce boilerplate, allowing developers to set up a comprehensive quality gate with a single command.

## Example Commands

### Initialize with standard Python hooks (e.g., black, flake8/ruff, isort)

`pc-init --lang=python`

### Initialize with JavaScript hooks, including React-specific linters (e.g., eslint + react-hooks plugin)

`pc-init --lang=javascript --framework=react`

### Initialize for a simple Go project (e.g., go fmt, go vet)

`pc-init --lang go`

### rust with bevy game engine (cargo fmt, clippy, bevy cli)

`pc-init --lang=rust --framework=bevy`



