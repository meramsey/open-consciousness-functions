# Design Specification

This document binds the OCF data model. **Schema changes require a proposal
and coordinated updates to schemas, templates, generators, and tests.**

## 1. Core separation

The repository models these independently:

- function capability
- canonical name
- canonical command (primary + modes)
- legacy name
- legacy command(s)
- command aliases
- intended purpose
- training script
- audio implementation
- background-audio preset
- release/cancel behavior
- activation mode
- persistence / lifecycle
- evidence / claim status
- provenance / source information

A **function is not the same thing as its audio recording**, and a background
preset is neither a function nor a script.

## 2. Identifiers

| Object           | Format            | Example         |
| ---------------- | ----------------- | --------------- |
| Function         | `OCF-<DOMAIN>-<N>`| `OCF-FND-002`   |
| Proposal         | `OCFP-<N>`        | `OCFP-0001`     |
| Audio impl.      | `OCF-AUDIO-<N>`   | `OCF-AUDIO-0001`|
| Background       | `OCF-BG-<N>`      | `OCF-BG-0001`   |

Domains: `FND COG EMO COM BOD PRF SEN SLP LIF EMG AUT EXP`. IDs are stable
across renames.

## 3. Canonical format

Function records are YAML conforming to `schemas/function.schema.json` and
following `templates/function.yaml`. Key blocks:

| Block           | Meaning                                                   |
| --------------- | --------------------------------------------------------- |
| `canonical`     | OCF name + primary command + mode commands                |
| `legacy`        | legacy name, commands, command status, source availability|
| `ocf`           | reimplementation status + command review state            |
| `compatibility` | compatibility state + rationale for changed commands      |
| `classification`| primary + secondary domains                               |
| `lifecycle`     | persistence, activation, release behavior                 |
| `safety`        | level, notes, medical relevance                           |
| `claims`        | intended effects + prohibited claims                      |
| `audio`         | script/implementation status + background strategy        |
| `sources`       | citations (never fabricated)                              |

## 4. Command statuses

`unchanged` · `normalized` · `proposed` · `review-required`

## 5. Compatibility states

`unchanged` · `alias-listed` · `bridge-trainable` · `canonical-first` ·
`legacy-first` · `none`

## 6. Command syntax rules

Covered by `COMMAND_GRAMMAR.md`. Enforced by `ocf review commands` and
`ocf validate`.

## 7. Lifecycle states

`draft → review → experimental → accepted → deprecated/superseded` plus
`rejected/withdrawn`. See `FUNCTION_LIFECYCLE.md`.

## 8. Controllers

- `docs/ARCHITECTURE.md` — process and module flow.
- `schemas/*` — the formal contract.
- `tests/` — behavioral contract.
- `AGENTS.md` — invariants agents must not break.

## 9. Planned extensions (v0.5, not shipped)

Designed in `docs/PREPARATION_MODULE.md` and `docs/TIMED_TRANSCRIPTS.md`;
tracked in `ROADMAP.md`. Each requires a proposal (`OCFP-*`) plus coordinated
schema, template, generator, and test updates.

Shipped since the previous revision, by
`proposals/draft/ocfp-0001-semantic-narration-keys-and-locale-packs.md`:

- **Language identifiers** — `locale` on timed transcripts, session templates,
  and locale packs; `narration_key` + `variables` on timed events and template
  lines; narration resolution provenance on resolved documents.
- **Locale packs** — `locales/<tag>/` with manifest + resource files, plural
  rules, translation provenance, and semantic versioning.
- **Pronunciation / locale TTS hints** — per-entry `pronunciation` metadata
  applied to TTS input only.

Still planned:

- **Composable preparation stages** — optional stage roles
  (`affirmation`, `ohm`, …) with default-skipped semantics.
- **Focus-state auditory cue events** — semantic transition events mapped to
  configurable sound cues; field names must not collide with the existing
  `cue_id` import identifiers or §48 `cue` markers.

## 10. Backward-compatibility policy

New optional fields and stage roles default to **no behavior change**: an
existing preset, script, template, or audio implementation must validate and
rebuild identically. Additions are versioned (records carry explicit
versions; `schema_version` evolution for `timed-transcript.schema.json`,
currently `const: "1.0"`, follows a non-breaking migration path in a
proposal). Data-model changes are never made silently.