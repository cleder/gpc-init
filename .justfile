@default:
    @just --list

validate_update_all:
    find lang framework -name "preset*.yaml" | xargs -I{} pre-commit validate-config {}
    find lang framework -name "preset*.yaml" | xargs -I{} prek validate-config {}
    find lang framework -name "preset*.yaml" | xargs -I{} pre-commit autoupdate -c {}
    find lang framework -name "preset*.yaml" | xargs -I{} prek autoupdate -c {}

validate target type="lang":
    @echo 'Validating {{target}}...'
    pre-commit validate-config "{{type}}/{{target}}/preset.yaml"
    prek validate-config "{{type}}/{{target}}/preset.yaml"

autoupdate target type="lang":
    @echo 'Autoupdating {{target}}...'
    pre-commit autoupdate -c "{{type}}/{{target}}/preset.yaml"
    prek autoupdate -c "{{type}}/{{target}}/preset.yaml"

validate_update target type="lang":
    @echo 'Validating {{target}}...'
    just validate "{{target}}" "{{type}}"
    @echo 'Autoupdating {{target}}...'
    just autoupdate "{{target}}" "{{type}}"

awesome:
    @echo "Creating awesome list"
    uv run scripts/generate_awesome_list.py
    cp AWESOME.md ../awesome-pre-commit-hooks/README.md

test:
    uv run pytest tests --cov=gpc_init tests
    uv run complexipy --failed gpc_init
    uv run ruff check gpc_init tests
    uv run ruff format gpc_init tests
    uv run pyrefly check gpc_init tests
    uv run ty check gpc_init tests
