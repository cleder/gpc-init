# 0002: Preset merge model and precedence

## Status

Accepted

## Context

A Generation request can select several languages and frameworks, and every selected Preset contributes `repos:`/`hooks:` entries plus top-level keys such as `default_language_version`.
The merge needs a single, predictable rule for ordering and for what wins when two Presets define the same thing.

## Decision

- **Layer order, lowest to highest precedence:** `lang/common`, then language Presets in CLI order, then framework Presets in CLI order.
- **`repos`** merge by the identity key `(repo, rev)`.
  A repo seen first in a lower layer keeps its position; new repos from higher layers are appended.
- **Within a merged repo**, hooks merge by hook `id`.
  The lower layer fixes the hook's position, and the higher layer's fields replace the lower layer's fields.
- **Other top-level keys** are deep-merged; higher layers win on conflicts and non-mapping values are replaced, not combined.
- **Preset metadata** (`recommended`, `primary_languages`) is stripped from the merged result.
- Category filtering runs afterwards, on the merged result (see ADR 0001).

## Known limitation: same repo, different `rev`

`rev` is part of the key on purpose: silently picking one of two pinned revisions would hide a real disagreement between Presets.
The consequence is that two Presets pinning the same repo at different revisions are **not** merged.
The output then contains two `repos:` entries for that repo, and the same hook id can run twice.
`test_same_repo_different_rev_appends` in `tests/unit/test_merger.py` pins this merger behaviour.

The bundled Catalog avoids the situation by convention, and `TestBundledCatalogRevConsistency` in `tests/unit/test_catalog.py` enforces it: every repo is pinned at exactly one `rev` across the bundled Presets.
Custom Catalogs (`--presets`) are not checked and may pin differently.

## Alternatives considered

- **Key on `repo` only, higher layer's `rev` wins.**
  Never duplicates, but silently overrides the version a Preset author pinned.
- **Error on a `rev` conflict.**
  Safest, but breaks custom Catalogs that pin differently on purpose.
- **Replace a repo's hooks wholesale instead of merging by id.**
  Simpler, but a framework Preset could not add one hook to a language Preset's repo without restating all the others.

## Consequences

- Merge output depends only on the layer order, so the same request and Catalog give the same result (ADR 0003).
- Preset authors in a shared Catalog must keep `rev`s aligned themselves.
