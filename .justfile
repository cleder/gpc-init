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
    uv run pytest tests --cov=gpc_init tests
    uv run complexipy --failed gpc_init
    uv run ruff check gpc_init tests
    uv run ruff format gpc_init tests
    uv run pyrefly check gpc_init tests
    uv run ty check gpc_init tests
