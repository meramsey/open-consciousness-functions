# OCFP-0001: Semantic narration keys and locale packs

- Status: draft
- Date: 2026-09-30
- Authors: OCF working group

## Problem

Every listener-facing sentence in OCF is stored as inline English `text` inside
timed transcripts and session templates. That couples three things that change
for different reasons and at different rates:

1. **Timing.** A transcript edit changes when something is spoken.
2. **Wording.** An edit for clarity changes what is said.
3. **Language.** A request for a Spanish or Japanese version cannot be served at
   all, because the text has nowhere to live except the document that carries the
   timestamps.

The repository already has a working English voice pipeline and a session
composer, and the design specification reserves "open text space" for a
description of the intended focus function. Neither has a place to put a
translation, so the only ways to localize today are to fork the script or to
pre-render a separate English-derived document per language. Both produce a
second source of truth for timing, and both invite the failure mode the design
spec most wants to avoid: an English sentence appearing inside a translated
session because one line was forgotten.

`docs/LOCALIZATION.md` has described this gap since v0.4 as planned work. This
proposal lands the data model, the runtime, and the validation, and it states
plainly which parts of localization remain out of scope.

## Purpose

Add a language-independent layer between a session's structure and the words a
listener hears:

- a **semantic narration key** on each timed event,
- a **locale pack** per language holding the messages, their variable contracts,
  and their translation metadata,
- a **resolver** that turns keyed documents into text for a target locale,
  failing loudly when a translation is missing,
- and **validation** that reports hard-coded narration, missing translations,
  stale translations, and variable-contract drift.

Nothing in the existing model is removed. Inline `text` stays valid.

## Proposed name

Semantic narration keys (`narration_key`) and OCF locale packs.

## Proposed command

None. This is a data-model and tooling change; it adds no listener command and
changes no existing command spelling. Canonical commands such as `PLUS-FOCUS`
remain language-independent metadata inside a message, never translated
themselves.

## Command-length rationale

Not applicable — no command is added.

## Activation

Not applicable.

## Release

Not applicable.

## Persistence

Not applicable.

## Safety

Two safety-relevant properties are enforced rather than documented:

- **Strict spoken resolution.** Rendering or exporting in a locale that lacks a
  keyed narration message is an error. The toolchain never substitutes an
  English sentence into a translated session to keep a build green. An explicit
  `--allow-fallback` / `--no-strict` override exists for draft review, and every
  event records the locale its text actually came from.
- **Region-to-language fallback.** A regional tag is served by its installed
  parent (`es-MX` from `es`) because that is the same language to a listener,
  but canonical English is excluded from the strict spoken chain. Translators
  and reviewers see the missing key, not a mixed-language session.

## Compatibility

- Inline `text` remains valid and is untouched. Existing documents under
  `audio/scripts/` keep their wording byte-for-byte.
- All 55 legacy function records and their historical command names are
  untouched; legacy mapping metadata is never rewritten.
- `OCF-TPL-SESSION-ATTENTION-001` and `audio/scripts/attention.yaml` are not
  modified. The adapted OCF script remains adapted-from-legacy wording and is
  never relabelled as OCF-authored.
- Additive schema changes only: `narration_key`, `locale`, `variables` are
  optional everywhere, and both new schemas are new files.
- Default behavior with no locale packs configured is unchanged, apart from a
  new informational finding from `validate --all`.

## Evidence state

The design is derived from the repository's own constraints, not from a source
transcript. Narration wording introduced for the demonstration session is
original OCF phrasing written for this feature; it is not adapted from
Preparation Learning, Focus 10, Focus 11, or any legacy H-PLUS transcript. The
Spanish pack is a machine draft used as a test fixture and is explicitly not an
authoritative translation.

## Alternatives

1. **Separate documents per language** (`session-es.yaml`, `session-ja.yaml`).
   Rejected: timestamps get duplicated per language and drift, and the toolchain
   cannot tell a deliberate Spanish line from an untranslated English leftover.
2. **Translate at render time with a remote service.** Rejected: it makes the
   build depend on network availability, cannot be validated offline, and would
   put unreviewed machine output into listener audio by default.
3. **Keep everything inline and add a validator only.** Rejected: it reports
   the problem without giving anything a place to live; the validator would
   permanently flag the repository's own English scripts.
4. **A full ICU runtime (PyICU or Babel).** Deferred, not rejected: the
   repository prefers minimal runtime dependencies and only calls optional
   external CLIs. The implemented subset is ICU-*compatible* in syntax, so a
   pack can move to a full implementation later without rewriting messages. A
   proposal to adopt a real ICU runtime may follow if the subset is outgrown.

## Implementation

Schemas (`schemas/*.schema.json`, all additive):

| File                                  | Change                                                        |
| ------------------------------------- | ------------------------------------------------------------- |
| `locale-manifest.schema.json`         | new: locale, direction, status, semantic version, translation |
| `locale-resource.schema.json`         | new: message entries with variable + pronunciation metadata  |
| `timed-transcript.schema.json`        | optional `locale`, `narration_key`, `variables`, provenance  |
| `session-template.schema.json`        | optional `locale`, keyed `templateLine`                       |

Tooling (`scripts/ocf_tools/`):

- `locale.py` — BCP-47 normalization and fallback chains, a sandboxed plural-rule
  evaluator, the ICU MessageFormat subset, pack loading, coverage and staleness
  reporting, pseudo-locale generation, and document resolution.
- `session.py` — composition preserves `narration_key` and `variables`.
- `voice.py` — resolves the document for the requested locale, retargets the
  backend, applies pronunciation hints to TTS input only, and reports measured
  cue durations.
- `transcript.py` — `--locale` for export, with optional measured cue timings
  from a render manifest so subtitles follow real speech.
- `audio_build.py` — `--locale` for the build, plus `narration_timing` in the
  render manifest.
- `validators.py` — locale-pack schema, provenance, coverage, variable-contract,
  message-syntax, command-reference, and keyed-document checks.
- `cli.py` — `ocf locale list|coverage|validate|resolve|pseudo`.

Data:

- `locales/en-US/` — canonical pack (authoring happens here first).
- `locales/es/` — deliberately incomplete machine test fixture.

## Testing

- `tests/test_locale.py` — BCP-47 normalization and chains, direction, message
  formatting (plural, ordinal, select, offset, quoting, escaping), number
  formatting, pack loading, pseudo generation, strict/non-strict resolution,
  regional fallback, provenance, and pack validation.
- `tests/test_locale_render.py` — locale-aware render, strict render failure,
  measured cue durations, backend locale retargeting, pronunciation hints,
  localized subtitle export, and the `ocf locale` CLI surface.
- `make check` runs schema and rule validation plus index freshness; the
  existing suite runs with `python3 -m pytest`.

## Sources

- `docs/DESIGN_SPEC.md` (schema change control; open text space)
- `docs/TIMED_TRANSCRIPTS.md` (timed document semantics)
- `docs/LOCALIZATION.md` (planned design this implements)
- `templates/timed-transcript.yaml`, `templates/proposal.md`

## Licensing

Apache-2.0. No third-party audio or copyrighted text is vendored; imported
transcripts remain citation-only under `docs/SOURCE_ATTRIBUTION.md`.
