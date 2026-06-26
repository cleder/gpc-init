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
