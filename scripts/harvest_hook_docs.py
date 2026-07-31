#!/usr/bin/env python3
"""
Harvest per-hook documentation from upstream .pre-commit-hooks.yaml manifests.

Backfills missing `description:` fields in our preset.yaml files, and
discovers hook ids offered by an already-used repo that we don't yet
include, adding the genuinely new capabilities (skipping alternate install
variants and upstream-deprecated ids).

Usage:
    python scripts/harvest_hook_docs.py            # dry run, prints a report
    python scripts/harvest_hook_docs.py --write     # applies changes in place
    python scripts/harvest_hook_docs.py --only lang/py/preset.yaml --write
"""

from __future__ import annotations

import argparse
import base64
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml as pyyaml
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

if TYPE_CHECKING:
    from ruamel.yaml.comments import CommentedMap

PROJECT_ROOT = Path(__file__).parent.parent
LANG_DIR = PROJECT_ROOT / "lang"
FRAMEWORK_DIR = PROJECT_ROOT / "framework"

_GH = shutil.which("gh")

# Alternate install-strategy suffixes for the same underlying capability.
_VARIANT_SUFFIXES = ("-system", "-docker", "-src")

# (owner/repo, hook_id) -> reason. Hooks that would otherwise be auto-added
# by the naming-variant heuristic but were rejected on manual review: either
# they require repo-specific setup to avoid failing by default, they're a
# functional duplicate of an already-included hook (install-method variants
# the naming heuristic doesn't recognize, or alternate "modes" of the same
# check), the underlying tool is unmaintained, or the repo is a multi-purpose
# grab-bag where most of its hooks are unrelated to the preset they'd land in.
_MANUAL_DENYLIST: dict[tuple[str, str], str] = {
    ("bufbuild/buf", "buf-breaking"): "requires a repo-specific --against git ref",
    (
        "bufbuild/buf",
        "buf-generate",
    ): "requires a buf.gen.yaml with no sensible default",
    # django already has djlint-django/djlint-reformat-django; the rest of
    # djLint's hooks target other template engines entirely (Golang, Jinja,
    # Handlebars, Nunjucks) or are the generic non-Django variant.
    ("djlint/djLint", "djlint"): "generic variant; django-specific hook already used",
    ("djlint/djLint", "djlint-golang"): "targets Go templates, not Django",
    ("djlint/djLint", "djlint-handlebars"): "targets Handlebars, not Django",
    ("djlint/djLint", "djlint-jinja"): "targets Jinja, not Django",
    ("djlint/djLint", "djlint-nunjucks"): "targets Nunjucks, not Django",
    (
        "djlint/djLint",
        "djlint-reformat",
    ): "generic variant; django-specific hook already used",
    ("djlint/djLint", "djlint-reformat-golang"): "targets Go templates, not Django",
    ("djlint/djLint", "djlint-reformat-handlebars"): "targets Handlebars, not Django",
    ("djlint/djLint", "djlint-reformat-jinja"): "targets Jinja, not Django",
    ("djlint/djLint", "djlint-reformat-nunjucks"): "targets Nunjucks, not Django",
    # Bare hook requires --schemafile args to do anything; the ~30 specific
    # check-* hooks we already use are the pre-configured, useful form.
    (
        "python-jsonschema/check-jsonschema",
        "check-jsonschema",
    ): "needs args to be useful",
    # gruntwork-io/pre-commit is a multi-purpose grab-bag; only helmlint is
    # relevant to the k8s framework, the rest duplicate our go/tf/sh presets
    # with less-maintained tooling or are unrelated (Packer, Sentinel, yapf).
    (
        "gruntwork-io/pre-commit",
        "check-terratest-skip-env",
    ): "unrelated to k8s (Go test tooling)",
    (
        "gruntwork-io/pre-commit",
        "gofmt",
    ): "unrelated to k8s; go preset owns Go formatting",
    (
        "gruntwork-io/pre-commit",
        "goimports",
    ): "unrelated to k8s; go preset owns Go formatting",
    (
        "gruntwork-io/pre-commit",
        "golangci-lint",
    ): "unrelated to k8s; go preset owns Go linting",
    (
        "gruntwork-io/pre-commit",
        "golint",
    ): "unrelated to k8s; go preset owns Go linting",
    ("gruntwork-io/pre-commit", "markdown-link-check"): "unrelated to k8s",
    ("gruntwork-io/pre-commit", "packer-validate"): "unrelated to k8s",
    ("gruntwork-io/pre-commit", "sentinel-fmt"): "unrelated to k8s",
    ("gruntwork-io/pre-commit", "shellcheck"): "unrelated to k8s; sh preset owns this",
    (
        "gruntwork-io/pre-commit",
        "terraform-fmt",
    ): "unrelated to k8s; tf preset owns this",
    (
        "gruntwork-io/pre-commit",
        "terraform-validate",
    ): "unrelated to k8s; tf preset owns this",
    ("gruntwork-io/pre-commit", "terragrunt-hcl-fmt"): "unrelated to k8s",
    (
        "gruntwork-io/pre-commit",
        "terragrunt-hclfmt",
    ): "unrelated to k8s; duplicate of terragrunt-hcl-fmt",
    ("gruntwork-io/pre-commit", "tflint"): "unrelated to k8s; tf preset owns this",
    ("gruntwork-io/pre-commit", "tofu-fmt"): "unrelated to k8s",
    ("gruntwork-io/pre-commit", "tofu-validate"): "unrelated to k8s",
    ("gruntwork-io/pre-commit", "yapf"): "unrelated to k8s (Python formatting)",
    # uncrustify/oclint overlap heavily with clang-format/clang-tidy already
    # used; not enough distinct value to run three formatters/analyzers.
    (
        "pocc/pre-commit-hooks",
        "uncrustify",
    ): "redundant formatter alongside clang-format",
    ("pocc/pre-commit-hooks", "oclint"): "overlaps heavily with clang-tidy",
    # checkov's own manifest bundles diff-based, full-scan, docker-image, and
    # secrets-scanning variants together; we intentionally use only the diff
    # variant (checkov_diff) for speed, and secrets are already covered by
    # lang/common's gitleaks/trufflehog/detect-secrets.
    ("bridgecrewio/checkov", "checkov"): "full-scan duplicate of checkov_diff",
    (
        "bridgecrewio/checkov",
        "checkov_container",
    ): "docker-image variant of checkov, not image scanning",
    (
        "bridgecrewio/checkov",
        "checkov_diff_container",
    ): "docker-image variant of checkov_diff",
    (
        "bridgecrewio/checkov",
        "checkov_secrets",
    ): "redundant with lang/common secret scanners",
    (
        "bridgecrewio/checkov",
        "checkov_secrets_container",
    ): "redundant with lang/common secret scanners",
    # biome-check already runs both lint and format together.
    ("biomejs/pre-commit", "biome-ci"): "redundant with biome-check",
    ("biomejs/pre-commit", "biome-format"): "redundant with biome-check",
    ("biomejs/pre-commit", "biome-lint"): "redundant with biome-check",
    # language-formatters-pre-commit-hooks bundles formatters for many
    # languages; only pretty-format-kotlin is relevant to the kt preset.
    (
        "macisamuele/language-formatters-pre-commit-hooks",
        "pretty-format-golang",
    ): "unrelated to Kotlin",
    (
        "macisamuele/language-formatters-pre-commit-hooks",
        "pretty-format-ini",
    ): "unrelated to Kotlin",
    (
        "macisamuele/language-formatters-pre-commit-hooks",
        "pretty-format-java",
    ): "unrelated to Kotlin",
    (
        "macisamuele/language-formatters-pre-commit-hooks",
        "pretty-format-rust",
    ): "unrelated to Kotlin",
    (
        "macisamuele/language-formatters-pre-commit-hooks",
        "pretty-format-toml",
    ): "unrelated to Kotlin",
    (
        "macisamuele/language-formatters-pre-commit-hooks",
        "pretty-format-yaml",
    ): "unrelated to Kotlin",
    # Needs a custom rule-package build; not useful without that setup.
    (
        "DavidAnson/markdownlint-cli2",
        "markdownlint-cli2-rules-docker",
    ): "needs custom rule packaging",
    # nbQA bundles wrappers for many Python tools; we standardize on ruff
    # elsewhere (lang/py) and don't want flake8/black/pylint/autopep8/yapf
    # applied only to notebooks, inconsistently with plain .py files.
    ("nbQA-dev/nbQA", "nbqa"): "generic wrapper needs args to be useful",
    (
        "nbQA-dev/nbQA",
        "nbqa-autopep8",
    ): "conflicts with ruff-based formatting used elsewhere",
    (
        "nbQA-dev/nbQA",
        "nbqa-black",
    ): "conflicts with ruff-based formatting used elsewhere",
    ("nbQA-dev/nbQA", "nbqa-flake8"): "superseded by ruff, used elsewhere",
    ("nbQA-dev/nbQA", "nbqa-pydocstyle"): "not used for plain .py files either",
    ("nbQA-dev/nbQA", "nbqa-pylint"): "superseded by ruff, used elsewhere",
    (
        "nbQA-dev/nbQA",
        "nbqa-yapf",
    ): "conflicts with ruff-based formatting used elsewhere",
    ("nbQA-dev/nbQA", "nbqa-ruff-check"): "exact duplicate of existing nbqa-ruff",
    # ruff-check+ruff-format (already used) supersede the combined 'ruff' hook.
    ("astral-sh/ruff-pre-commit", "ruff"): "redundant with ruff-check + ruff-format",
    # pip-compile assumes a pip-tools workflow that conflicts with the
    # uv-lock/uv-sync workflow already used.
    (
        "astral-sh/uv-pre-commit",
        "pip-compile",
    ): "conflicts with uv-lock/uv-sync workflow",
    # antonbabenko/pre-commit-terraform bundles several checkov/terrascan
    # wrappers, alternate terraform_docs modes, and niche/unmaintained tools.
    (
        "antonbabenko/pre-commit-terraform",
        "infracost_breakdown",
    ): "requires an Infracost API key",
    (
        "antonbabenko/pre-commit-terraform",
        "terraform_checkov",
    ): "redundant with existing checkov_diff",
    (
        "antonbabenko/pre-commit-terraform",
        "terraform_docs_replace",
    ): "alternate mode of terraform_docs already used",
    (
        "antonbabenko/pre-commit-terraform",
        "terraform_docs_without_aggregate_type_defaults",
    ): "alternate mode of terraform_docs already used",
    (
        "antonbabenko/pre-commit-terraform",
        "terraform_wrapper_module_for_each",
    ): "niche codegen utility, not a check",
    (
        "antonbabenko/pre-commit-terraform",
        "terrascan",
    ): "upstream tenable/terrascan is archived",
    # Self-described as removed/superseded in their own upstream description
    # text (not caught by the nearby-comment deprecation scan).
    (
        "pre-commit/pre-commit-hooks",
        "check-byte-order-marker",
    ): "removed upstream; superseded by fix-byte-order-marker (already used)",
    (
        "pre-commit/pre-commit-hooks",
        "fix-encoding-pragma",
    ): "removed upstream; superseded by pyupgrade (already used)",
    # Would fight with ruff-format's enforced double-quote style in lang/py.
    (
        "pre-commit/pre-commit-hooks",
        "double-quote-string-fixer",
    ): "conflicts with ruff-format's quote style",
    # Stricter, conflicting policy vs. the already-used forbid-new-submodules
    # (that one permits pre-existing submodules; this one forbids all of them).
    (
        "pre-commit/pre-commit-hooks",
        "forbid-submodules",
    ): "conflicts with forbid-new-submodules policy already chosen",
    # --dry-run means it never fails the commit; not a real enforced gate.
    ("semgrep/semgrep", "semgrep-ci"): "dry-run mode; does not enforce/block",
    # Docker variant pinned to semgrep's unstable "develop" build.
    (
        "semgrep/semgrep",
        "semgrep-docker-develop",
    ): "unstable develop build; also a docker variant",
    # Own description: "there is no default module path, so this hook fails
    # until configured."
    (
        "cleder/vercheck",
        "vercheck-py",
    ): "fails until configured with a required --py path",
}

yaml_rt = YAML()
yaml_rt.preserve_quotes = True
yaml_rt.width = 4096
yaml_rt.indent(mapping=2, sequence=4, offset=2)
yaml_rt.explicit_start = True

_manifest_cache: dict[tuple[str, str], tuple[dict[str, dict[str, str]], set[str]]] = {}
_repo_desc_cache: dict[str, str] = {}


def _run_gh(args: list[str]) -> str | None:
    if not _GH:
        return None
    try:
        result = subprocess.run(  # noqa: S603
            [_GH, *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def owner_repo_from_url(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub repo URL."""
    parts = repo_url.rstrip("/").removesuffix(".git").split("/")
    return "/".join(parts[-2:])


def gh_repo_description(owner_repo: str) -> str:
    """Fetch the repo-level GitHub description, cached."""
    if owner_repo in _repo_desc_cache:
        return _repo_desc_cache[owner_repo]
    out = _run_gh(
        ["repo", "view", owner_repo, "--json", "description", "--jq", ".description"]
    )
    desc = (out or "").strip()
    if out is None:
        print(  # noqa: T201
            f"Warning: could not fetch repo description for {owner_repo}",
            file=sys.stderr,
        )
    _repo_desc_cache[owner_repo] = desc
    return desc


def _hook_blocks(raw_text: str) -> list[tuple[str, str]]:
    """
    Split a .pre-commit-hooks.yaml file into (hook_id, raw_block) pairs.

    Comment lines immediately preceding an "- id:" line (with no blank line
    in between) are treated as *leading* comments for the hook that follows,
    not trailing comments for the hook before it — this matches how repos
    like bufbuild/buf annotate deprecated hooks (the deprecation note sits
    directly above the deprecated hook's own "- id:" line).
    """
    lines = raw_text.splitlines(keepends=True)
    id_pattern = re.compile(r"^-\s+id:\s*['\"]?([\w.\-]+)['\"]?\s*$")

    id_lines = [
        (i, m.group(1)) for i, line in enumerate(lines) if (m := id_pattern.match(line))
    ]

    starts = []
    for line_idx, hook_id in id_lines:
        true_start = line_idx
        j = line_idx - 1
        while j >= 0 and lines[j].strip().startswith("#"):
            true_start = j
            j -= 1
        starts.append((true_start, hook_id))

    blocks = []
    for i, (true_start, hook_id) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
        blocks.append((hook_id, "".join(lines[true_start:end])))
    return blocks


def fetch_manifest(
    owner_repo: str, rev: str
) -> tuple[dict[str, dict[str, str]], set[str]]:
    """
    Fetch a repo's .pre-commit-hooks.yaml at the given rev.

    Returns (hooks_by_id, deprecated_ids) where hooks_by_id maps hook id to
    {"name": ..., "description": ...}.
    """
    key = (owner_repo, rev)
    if key in _manifest_cache:
        return _manifest_cache[key]

    out = _run_gh(
        [
            "api",
            f"repos/{owner_repo}/contents/.pre-commit-hooks.yaml?ref={rev}",
            "--jq",
            ".content",
        ]
    )
    if not out or not out.strip():
        print(  # noqa: T201
            f"Warning: no .pre-commit-hooks.yaml for {owner_repo}@{rev}",
            file=sys.stderr,
        )
        result = ({}, set())
        _manifest_cache[key] = result
        return result

    try:
        raw_text = base64.b64decode(out.strip()).decode("utf-8", errors="replace")
        manifest = pyyaml.safe_load(raw_text)
    except (ValueError, pyyaml.YAMLError) as exc:
        print(  # noqa: T201
            f"Warning: could not parse manifest for {owner_repo}@{rev}: {exc}",
            file=sys.stderr,
        )
        result = ({}, set())
        _manifest_cache[key] = result
        return result

    if not isinstance(manifest, list):
        result = ({}, set())
        _manifest_cache[key] = result
        return result

    hooks_by_id: dict[str, dict[str, str]] = {}
    for entry in manifest:
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        hooks_by_id[str(entry["id"])] = {
            "name": str(entry.get("name") or ""),
            "description": str(entry.get("description") or ""),
        }

    deprecated_ids = {
        hook_id
        for hook_id, block in _hook_blocks(raw_text)
        if "deprecated" in block.lower()
    }

    result = (hooks_by_id, deprecated_ids)
    _manifest_cache[key] = result
    return result


def _set_description(hook: CommentedMap, text: str) -> None:
    """
    Set a hook's description, preserving ruamel's comment attachment.

    ruamel attaches a "between items" comment (e.g. a banner preceding the
    next hook, as seen throughout lang/go/preset.yaml) to the *last key* of
    the preceding mapping. Appending a new key after it would otherwise
    silently detach that comment from the item it visually follows, so the
    comment is moved to trail the new last key instead.
    """
    old_last_key = next(reversed(hook), None)
    hook["description"] = DoubleQuotedScalarString(text)
    ca_items = getattr(hook, "ca", None) and hook.ca.items
    if ca_items and old_last_key is not None and old_last_key in ca_items:
        ca_items["description"] = ca_items.pop(old_last_key)


def _normalize(text: str) -> str:
    return re.sub(r"[-_]", " ", text).strip().lower()


def harvest_description(
    hook_id: str, upstream: dict[str, str], owner_repo: str
) -> tuple[str, str] | None:
    """Return (text, source_label) for a hook id, or None if nothing usable found."""
    description = upstream.get("description", "").strip()
    if description:
        return description, "hook description"

    name = upstream.get("name", "").strip()
    if name and _normalize(name) != _normalize(hook_id):
        return name, "hook name"

    repo_desc = gh_repo_description(owner_repo)
    if repo_desc:
        return repo_desc, "repo description"

    return None


def is_variant(candidate_id: str, existing_ids: set[str]) -> str | None:
    """Return the base hook id candidate_id is a variant of, if any."""
    for suffix in _VARIANT_SUFFIXES:
        if candidate_id.endswith(suffix):
            base = candidate_id[: -len(suffix)]
            if base in existing_ids:
                return base
    return None


def _update_existing_hooks(
    hooks_list: list[Any],
    hooks_by_id: dict[str, dict[str, str]],
    owner_repo: str,
    file_report: dict[str, list[Any]],
    *,
    write: bool,
) -> bool:
    """Backfill descriptions on hooks already in hooks_list. Returns True if changed."""
    changed = False
    for hook in hooks_list:
        hook_id = str(hook.get("id", ""))
        if "description" in hook:
            continue
        upstream = hooks_by_id.get(hook_id)
        if upstream is None:
            continue
        found = harvest_description(hook_id, upstream, owner_repo)
        if found is None:
            file_report["left_bare"].append((owner_repo, hook_id))
            continue
        text, source = found
        file_report["updated"].append((owner_repo, hook_id, source, text))
        if write:
            _set_description(hook, text)
            changed = True
    return changed


def _is_already_mentioned(candidate_id: str, raw_text: str) -> bool:
    """Check whether a hook id already appears in the file, even if commented out."""
    return (
        re.search(
            rf"id:\s*['\"]?{re.escape(candidate_id)}['\"]?\s*$",
            raw_text,
            re.MULTILINE,
        )
        is not None
    )


def _skip_reason(
    candidate_id: str,
    existing_ids: set[str],
    deprecated_ids: set[str],
    owner_repo: str,
    raw_text: str,
) -> tuple[str, tuple[Any, ...] | None] | None:
    """Return (report_bucket, entry) if candidate_id should be skipped, else None."""
    variant_of = is_variant(candidate_id, existing_ids)
    if variant_of:
        return "skipped_variant", (owner_repo, candidate_id, variant_of)
    if candidate_id in deprecated_ids:
        return "skipped_deprecated", (owner_repo, candidate_id)
    deny_reason = _MANUAL_DENYLIST.get((owner_repo, candidate_id))
    if deny_reason:
        return "skipped_manual", (owner_repo, candidate_id, deny_reason)
    if _is_already_mentioned(candidate_id, raw_text):
        # Already present, even if commented out — respect the deliberate
        # exclusion instead of re-adding it. Not worth a report entry.
        return "skipped_manual", None
    return None


def _build_candidate_hook(
    candidate_id: str, upstream: dict[str, str], owner_repo: str, *, write: bool
) -> tuple[dict[str, Any], tuple[str, str]]:
    """Build the new hook dict and its report entry (source, text) for a candidate."""
    new_hook: dict[str, Any] = {"id": candidate_id}
    found = harvest_description(candidate_id, upstream, owner_repo)
    if found is None:
        return new_hook, ("none", "")
    text, source = found
    new_hook["description"] = DoubleQuotedScalarString(text) if write else text
    return new_hook, (source, text)


def _add_candidate_hooks(  # noqa: PLR0913
    *,
    hooks_list: list[Any],
    existing_ids: set[str],
    hooks_by_id: dict[str, dict[str, str]],
    deprecated_ids: set[str],
    owner_repo: str,
    raw_text: str,
    file_report: dict[str, list[Any]],
    write: bool,
) -> bool:
    """Add genuinely new hook ids from hooks_by_id. Returns True if changed."""
    changed = False
    for candidate_id in sorted(set(hooks_by_id) - existing_ids):
        skip = _skip_reason(
            candidate_id, existing_ids, deprecated_ids, owner_repo, raw_text
        )
        if skip:
            bucket, entry = skip
            if entry is not None:
                file_report[bucket].append(entry)
            continue

        new_hook, (source, text) = _build_candidate_hook(
            candidate_id, hooks_by_id[candidate_id], owner_repo, write=write
        )
        file_report["added"].append((owner_repo, candidate_id, source, text))
        if write:
            hooks_list.append(new_hook)
            existing_ids.add(candidate_id)
            changed = True
    return changed


def _new_file_report() -> dict[str, list[Any]]:
    return {
        "updated": [],
        "left_bare": [],
        "added": [],
        "skipped_variant": [],
        "skipped_deprecated": [],
        "skipped_manual": [],
    }


def process_preset(path: Path, report: dict[str, Any], *, write: bool) -> None:
    """Harvest and (optionally) apply hook documentation updates for one preset file."""
    raw_text = path.read_text(encoding="utf-8")
    data = yaml_rt.load(raw_text)
    if not isinstance(data, dict) or "repos" not in data:
        return

    file_report = _new_file_report()
    changed = False

    for repo_entry in data["repos"]:
        repo_url = str(repo_entry.get("repo", ""))
        if repo_url in ("meta", "local"):
            continue
        rev = str(repo_entry.get("rev", ""))
        if not rev:
            continue
        owner_repo = owner_repo_from_url(repo_url)

        hooks_by_id, deprecated_ids = fetch_manifest(owner_repo, rev)
        if not hooks_by_id:
            continue

        hooks_list = repo_entry.get("hooks", [])
        existing_ids = {str(h.get("id", "")) for h in hooks_list}

        changed |= _update_existing_hooks(
            hooks_list, hooks_by_id, owner_repo, file_report, write=write
        )
        changed |= _add_candidate_hooks(
            hooks_list=hooks_list,
            existing_ids=existing_ids,
            hooks_by_id=hooks_by_id,
            deprecated_ids=deprecated_ids,
            owner_repo=owner_repo,
            raw_text=raw_text,
            file_report=file_report,
            write=write,
        )

    if any(file_report.values()):
        report[str(path.relative_to(PROJECT_ROOT))] = file_report

    if write and changed:
        buf = io.StringIO()
        yaml_rt.dump(data, buf)
        path.write_text(buf.getvalue(), encoding="utf-8")


def _truncate(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _format_updated(entry: tuple[Any, ...]) -> str:
    owner_repo, hook_id, source, text = entry
    return f"  [updated] {owner_repo}::{hook_id} ({source}): {_truncate(text)}"


def _format_bare(entry: tuple[Any, ...]) -> str:
    owner_repo, hook_id = entry
    return f"  [bare]    {owner_repo}::{hook_id} — no usable upstream text found"


def _format_added(entry: tuple[Any, ...]) -> str:
    owner_repo, hook_id, source, text = entry
    return f"  [added]   {owner_repo}::{hook_id} ({source}): {_truncate(text)}"


def _format_skipped_variant(entry: tuple[Any, ...]) -> str:
    owner_repo, hook_id, base = entry
    return f"  [skip]    {owner_repo}::{hook_id} — variant of {base}"


def _format_skipped_deprecated(entry: tuple[Any, ...]) -> str:
    owner_repo, hook_id = entry
    return f"  [skip]    {owner_repo}::{hook_id} — upstream-deprecated"


def _format_skipped_manual(entry: tuple[Any, ...]) -> str:
    owner_repo, hook_id, reason = entry
    return f"  [skip]    {owner_repo}::{hook_id} — {reason}"


_BUCKET_FORMATTERS = {
    "updated": _format_updated,
    "left_bare": _format_bare,
    "added": _format_added,
    "skipped_variant": _format_skipped_variant,
    "skipped_deprecated": _format_skipped_deprecated,
    "skipped_manual": _format_skipped_manual,
}


def print_report(report: dict[str, Any], *, write: bool) -> None:
    """Print a human-readable summary of what was found/changed per preset file."""
    mode = "APPLIED" if write else "DRY RUN — pass --write to apply"
    print(f"\n=== Hook doc harvest report ({mode}) ===\n")  # noqa: T201
    for path, file_report in sorted(report.items()):
        print(f"--- {path} ---")  # noqa: T201
        for bucket, formatter in _BUCKET_FORMATTERS.items():
            for entry in file_report[bucket]:
                print(formatter(entry))  # noqa: T201
        print()  # noqa: T201


def discover_presets(only: list[str] | None) -> list[Path]:
    """Return the preset.yaml paths to process, or all of them if only is unset."""
    if only:
        return [PROJECT_ROOT / p for p in only]
    return sorted(LANG_DIR.glob("*/preset.yaml")) + sorted(
        FRAMEWORK_DIR.glob("*/preset.yaml")
    )


def main() -> None:
    """Entry point: parse arguments, run the harvest, and print the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="Apply changes (default: dry run)"
    )
    parser.add_argument(
        "--only", nargs="*", help="Limit to specific preset.yaml paths (relative)"
    )
    args = parser.parse_args()

    if not _GH:
        print("Error: gh CLI not found on PATH.", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    report: dict[str, Any] = {}
    for path in discover_presets(args.only):
        process_preset(path, report, write=args.write)

    print_report(report, write=args.write)


if __name__ == "__main__":
    main()
