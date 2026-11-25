set default-list := true

# Validate target configurations. Usage: just validate [target] [type]. Defaults to all.
validate target="all" type="lang":
    @if [ "{{target}}" = "all" ]; then \
        find lang framework -name "preset*.yaml" | xargs -I{} pre-commit validate-config {};\
        find lang framework -name "preset*.yaml" | xargs -I{} prek validate-config {};\
    else \
        echo "Validating {{target}} ..."; \
        pre-commit validate-config "{{type}}/{{target}}/preset.yaml"; \
        prek validate-config "{{type}}/{{target}}/preset.yaml"; \
    fi

# Autoupdate target configurations. Usage: just update [target] [type]. defaults to all.
update target="all" type="lang":
    @if [ "{{target}}" = "all" ]; then \
        find lang framework -name "preset*.yaml" | xargs -I{} prek autoupdate -c {};\
    else \
        echo 'Autoupdating {{target}}...';\
        prek autoupdate -c "{{type}}/{{target}}/preset.yaml";\
    fi

# Create the AWESOME list. (internal use only)
awesome:
    @echo "Creating awesome list"
    uv run scripts/generate_awesome_list.py
    uv run rumdl fmt AWESOME.md
    cp AWESOME.md ../awesome-pre-commit-hooks/README.md

# Run python tests and linters
test:
    uv run pytest tests --cov=pc_init tests
    uv run complexipy --failed pc_init
    uv run ruff check pc_init tests
    uv run ruff format pc_init tests
    uv run pyrefly check pc_init tests
    uv run ty check pc_init tests
    uv run zuban check pc_init tests

# Fail if a preset references a non-https, archived or missing hook repo.
check-archived:
    GITHUB_TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null)}" uv run scripts/check_archived_repos.py

# Bring every dependency and hook revision to the latest version. Run before tagging a release.
prepare-release:
    uv lock --upgrade
    uv sync
    prek autoupdate
    just update
    just test

# Fail if the lockfile, the local pre-commit config or any preset is not at the latest versions.
check-release-ready:
    prek autoupdate --check
    find lang framework -name "preset*.yaml" | xargs -I{} prek autoupdate --check -c {}
    ! uv lock --upgrade --dry-run 2>&1 | grep -E '^(Update|Add|Remove) '

# Prepare a release on develop: upgrade, bump, promote the changelog, commit and tag (no push).
release version:
    uv run scripts/release.py {{version}}

# Merge a tagged, green release into main so CI publishes it to PyPI.
ship version:
    uv run scripts/ship.py {{version}}
