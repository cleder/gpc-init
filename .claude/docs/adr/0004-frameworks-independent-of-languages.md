# 0004: Frameworks are independent of languages; recommendations are advisory

## Status

Accepted

## Context

Frameworks relate to languages (`react` wants `js`, `ts` and `css`), but not one-to-one: a framework can span languages, and users may want one without the others.

## Decision

- Frameworks and languages are separate Preset kinds (`framework/<id>/` and `lang/<id>/`) and are selected with separate repeatable flags.
  Any framework can be combined with any languages.
- A framework Preset may declare `recommended: {lang: [...], framework: [...]}`.
  When the selection does not already include those entries, they are shown as suggestions, together with a ready-to-run command that adds them.
  They are never applied automatically and never block generation.
- Framework Presets merge after language Presets, so a framework can refine what a language contributes (ADR 0002).
- Frameworks are additive: they add or refine hooks rather than removing baseline ones.

The field started life as `primary_languages` and became `recommended` once frameworks could recommend other frameworks as well.

## Alternatives considered

- **Nest frameworks under languages.**
  Simpler lookup, but cannot express a cross-language framework.
- **Make recommendations a hard requirement (validation gate).**
  Would reject valid combinations and make partial setups impossible.

## Consequences

- Selecting a framework alone produces a valid config, just possibly an incomplete one; the suggestion tells the user what is missing.
- Adding a framework requires only a Preset; no code change.
