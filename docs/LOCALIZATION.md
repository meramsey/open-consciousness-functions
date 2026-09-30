# Localization, Language Fallback, and Language-Aware TTS

Status: **planned** (v0.5, tracked in `ROADMAP.md`). This document is a design
target, not a shipped capability. Nothing here is implemented until a live
`ocf` command exists and `docs/TIMED_TRANSCRIPTS.md` marks it implemented.

The goal is a session pipeline that is **language-independent by structure**:
one canonical timed/session definition (semantic events plus authored
narration) renders into a localized, spoken audio track in any supported
language without editing the binaural/SAM/background DSP or the timeline.

## Decided requirements

These are the fixed requirements this design must satisfy:

1. **Full-pipeline, not UI-only, localization.** Localizable output includes
   UI strings, CLI prompts, wizard text, user-facing validation/error
   messages, preparation narration, affirmations, function-install narration,
   focus-state and Access Channel instructions, exit/return instructions,
   reusable spoken templates, metadata/titles/descriptions,
   subtitles/SRT/lyrics, TTS voices, and documentation/examples. English
   narration must not be embedded in program logic.
2. **Locale packs and fallback.** Text lives in data-driven locale packs.
   Fallback chain is regional → language → English (e.g. `es-MX` → `es` →
   `en`). A missing **required** localization is a hard, clearly-reported
   error before any render; missing **optional** resources may fall back
   silently.
3. **Language-aware TTS.** A render request carries locale, text, voice,
   backend, speech rate, pronunciation/phoneme hints, and timing requirements.
   Backends report which languages/voices they support; the wizard filters
   voices by language. TTS is not bound to a single provider — it is an
   optional external backend selected at render time, exactly as today
   (espeak-ng/espeak/piper detected on PATH, graceful degradation).
4. **Timed text/translation separation.** The canonical timed document keeps
   four distinct layers — semantic event/timing, source-language text,
   translated text, and generated speech timing — so that a translated
   subtitle track never inherits English word-level timestamps. Translations
   re-time against the *event* timeline, not against the source words.
5. **User-created functions are localizable.** A function record has one
   source language plus zero or more translations; its session/DSP structure
   is language-independent; narration, metadata, and pronunciation hints are
   per-locale.
6. **DSP stays language-independent.** Binaural configuration, SAM
   configuration, background beds, focus-state transitions, crossfade timing,
   and auditory cue events are shared, never duplicated per language.

## Proposed architecture

All data-model details below are **proposals and TBD**; they require a
proposal (`proposals/`, `OCFP-*`) and coordinated schema/template/generator
updates per `docs/DESIGN_SPEC.md`.

### Localization pipeline

```text
semantic meaning / structure   (timed YAML: events, sections, states, timing)
   → localization key          (e.g. section-installation, cue-focus11-open)
   → locale                    (en, es, es-MX, …)
   → localized text            (locale pack lookup with fallback)
   → selected TTS backend      (language-aware, optional)
   → localized audio           (voice/rate/prompts/timing applied)
```

The key abstraction is that the canonical timed document carries *semantics
and structure*; localized strings are resolved at render time through locale
packs, never folded into the ship structure.

### Locale packs (proposal)

Conceptual, data-driven layout (final names TBD, to be decided by proposal):

```text
locales/
  en/      messages.yaml  preparation.yaml  affirmations.yaml
           functions.yaml metadata.yaml
  es/      …                             (translation of the above)
  es-MX/   …                             (regional overrides)
```

- A locale pack declares its language and (where relevant) region.
- Required vs optional lookup keys are declared per pack/section so the
  fallback policy (decided requirement 2) is deterministic.
- Packs are independently contributable; a missing required key surfaces as a
  pre-render validation error with the exact key and locale.

### Language-aware TTS (proposal)

Extends the existing `voice`-layer contract: a render request carries locale,
text, voice profile, backend, rate, pronunciation/phoneme hints, and timing
(mode + windows). Backends advertise `supported.voices[]` and `language`. The
wizard and CLI prompt only for voices that cover the requested locale, and
record per-layer wording never being rewritten by tools (import invariants in
`docs/TIMED_TRANSCRIPTS.md` still apply — the importer preserves source text
exactly).

Note on backend selection: today the backend auto-pick order chooses
espeak-ng before piper (see `docs/TIMED_TRANSCRIPTS.md`), so locale-aware
selection must also let a user pin a backend/voice explicitly — a
locale-aware default is not a substitute for explicit choice.

### Timed text and subtitles

Four layers restate the timed-transcript model:

| Layer                          | Lives in                        | Notes |
| ------------------------------ | ------------------------------- | ----- |
| Semantic event / timing         | section/event `id` + `at`/`after` | language-independent anchors |
| Source-language text            | `text` (source language)        | verbatim on import |
| Translated text                | per-locale `text`               | translation units are events, not words |
| Generated speech timing        | render manifest                 | duration differs per language/voice/TTS |

SRT/VTT/LRC export (`ocf transcript export`) must therefore offer both
"as-authored" and "translated-in-current-locale" output. Translation retiming
keeps the semantic anchors (event ids, section boundaries, gain dB windows)
and recomputes relative placement — it never copies English word timestamps.

### User-created functions

Per `docs/DESIGN_SPEC.md` model separation, a function's *capability/command*
is language-neutral. For localization a function record carries:

- a **source language** for its authored narration;
- an optional list of **translations** (locale → narration + metadata +
  pronunciation hints) — TBD fields, proposal required.

Its session definition and DSP configuration are reused untouched across
languages; only the audible narration/labels differ.

### Versioning and backward compatibility

- New fields are **optional** and default to today's behavior; existing
  presets must rebuild identically.
- Locale packs and translated function records carry their own version
  metadata; a stale or partial translation is reported, not silently merged.
- `schema_version` evolution for `timed-transcript.schema.json` (currently a
  `const: "1.0"`) and related schemas follows the proposal process; a
  versioned, non-breaking migration path is part of the proposal.

## Open questions (TBD)

- Locale pack directory layout and schema (`locales/…` above is illustrative).
- Whether locale resolution belongs in schema, in `scripts/ocf_tools/`, or
  both (see `docs/ARCHITECTURE.md` for the current tooling split).
- How translations attach to function records (metadata block vs separate
  files) — schema decision.
- Pronunciation-hint format for TTS (per-word IPA, phoneme, or backend
  dialect tags).

## Integration points

- `schemas/timed-transcript.schema.json` — section/event `id`, `state`,
  `timing`, `gain_db` stay language-neutral; `text` remains the authored
  language's wording.
- `schemas/session-template.schema.json` — slots become the function-specific
  narration seams; slot wording may be localized per pack.
- `schemas/voice-profile.schema.json` — already has a `language` field;
  locale-aware selection builds on it.
- `schemas/audio-implementation.schema.json` — already has a `language` field
  for the rendered artifact.
- `scripts/ocf_tools/transcript.py` — export pipeline (SRT/VTT/LRC) gains
  translation-aware output.
- `docs/PREPARATION_MODULE.md` — preparation/affirmation/oHm wording is fully
  localized narration; the stage structure is language-independent.
- `docs/TIMED_TRANSCRIPTS.md` — status matrix and import invariants.

## Relationship to this repo's standards

- `docs/AUDIO_STANDARD.md` — "language / locale metadata" on audio
  implementations already exists; this design generalizes it across the
  pipeline.
- `AGENTS.md` — provenance and citation rules still apply to translated text:
  never fabricate translations or claim a translation is OCF-authored unless
  it is.