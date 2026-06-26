@default:
    @just --list

validate_update_all:
    find . -name "preset*.yaml" | xargs -I{} pre-commit validate-config {}
    find . -name "preset*.yaml" | xargs -I{} prek validate-config {}
    find . -name "preset*.yaml" | xargs -I{} pre-commit autoupdate -c {}
    find . -name "preset*.yaml" | xargs -I{} prek autoupdate -c {}

validate target:
    @echo 'Validating {{target}}...'
    pre-commit validate-config lang/{{target}}/preset.yaml
    prek validate-config lang/{{target}}/preset.yaml

autoupdate target:
    @echo 'Autoupdating {{target}}...'
    pre-commit autoupdate -c lang/{{target}}/preset.yaml
    prek autoupdate -c lang/{{target}}/preset.yaml

validate_update target:
    @echo 'Validating {{target}}...'
    pre-commit validate-config lang/{{target}}/preset.yaml
    prek validate-config lang/{{target}}/preset.yaml
    @echo 'Autoupdating {{target}}...'
    pre-commit autoupdate -c lang/{{target}}/preset.yaml
    prek autoupdate -c lang/{{target}}/preset.yaml
