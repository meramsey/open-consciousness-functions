# Roadmap

Current status: **early bootstrap** — v0.3/v0.4 transcript + audio toolchain
shipping; v0.5 (localization, preparation stages, focus-state cues) designed,
not shipped.

Legend: `[x] done · [~] in progress · [ ] planned`

Planned items below are TODOs, not shipped features. Design notes for the
v0.5 items live in `docs/PREPARATION_MODULE.md`, `docs/LOCALIZATION.md`, and
the "Planned: focus-state auditory cue events" section of
`docs/TIMED_TRANSCRIPTS.md`.

## v0.1 — Bootstrap (this repository)

- [x] Repository scaffold and governance docs.
- [x] Canonical YAML function format + JSON Schemas (function, proposal,
      audio implementation, background audio).
- [x] All 55 documented legacy functions as OCF records
      (39 source-available, 16 source-unavailable reimplementation targets).
- [x] Interactive contributor CLI (`./scripts/ocf`) with wizards.
- [x] Validation (schema, duplicate id/command, command rules, invariants).
- [x] Generated indexes with freshness checks and CI enforcement.
- [x] Farfield integration stub with graceful degradation.
- [x] Test suite.

## v0.2 — Reimplementation content

- [~] First original OCF training scripts for the 16 source-unavailable
      legacy functions (proposal pathway).
- [ ] Community review of the 18 commands currently marked
      `review-required`.
- [ ] Bridge-training script design (legacy cue ↔ OCF cue association) as a
      labeled training design, not established science.

## v0.3 — Timed transcripts and timed lyrics

- [x] `timed-transcript.schema.json`, template, and CLI group
      (`ocf transcript import|segment|analyze|review|export|extract-template`).
- [x] LRC (timed lyrics), SRT, WebVTT, txt, md import → canonical OCF timed
      YAML with exact text/timestamp preservation and SHA-256 snapshots.
- [x] Section roles and segmentation (`ocf transcript segment|analyze`).
- [ ] Reusable section templates (`audio/templates/`, `AUDIO_SECTIONS.md`).
- [ ] State/focus profiles and state-aware Farfield background programs
      (`STATE_AND_FOCUS_LEVELS.md`, `audio/states/profiles/`).
- [x] `docs/TIMED_TRANSCRIPTS.md` walkthrough for adding a function from timed
      lyrics (README is updated to link it).

## v0.4 — Voices, preparation, and audio build

- [x] Voice profiles (`voice-profile.schema.json`, `audio/voices/profiles/`) +
      `ocf voice` CLI (`list-backends`, `doctor`, `list`, `render`).
- [x] TTS backends: espeak-ng, espeak, Piper (external-command, detected on
      PATH, graceful degradation when absent).
- [x] Audio build pipeline: `render-speech`, `mix`, `build`, `inspect` with
      `OCF-RENDER-*` manifests + SHA-256; mixing is pure stdlib PCM;
      WAV/FLAC/MP3 encode via ffmpeg/flac.
- [ ] Voice cloning: OpenVoice (reference/clone, consent-based), Kokoro and
      prerecorded narration profiles; state-aware background programs.
- [ ] Preparation Module (`preparation/`, `OCF-PREP-*`) with learn-once
      prerequisite metadata in function records (`ocf preparation …`); design
      in `docs/PREPARATION_MODULE.md`.
- [x] Session composition templates with editable function-specific slots
      (`ocf session compose`, `OCF-TPL-SESSION-*` shells, declared-slot
      contract). The dedicated §55 product templates (`OCF-SESSION-LEARN-001`,
      `OCF-SESSION-PREPARATION-001`, …) follow once the Preparation Module and
      composable preparation stages ship (v0.5).

## v0.5 — Localization, preparation stages, and focus-state cues

Localization shipped (see below); preparation stages and focus-state cues are
still planned. All items default to zero behavior change for existing presets;
schema additions require a proposal per `docs/DESIGN_SPEC.md`.

### Focus-state and transition audio cues

- [ ] Semantic cue events at focus-state transitions: `focus11_open`,
      `focus11_ready`, `focus11_close`, `session_complete` (extensible per
      focus level/state profile).
- [ ] Configurable cue resolution: semantic event → configured cue →
      rendered/generated sound | bundled asset | user-supplied asset |
      disabled. Replaceable per preset without touching session logic.
- [ ] Focus-state cue integration with the state/focus timeline (§48) and
      state-aware background programs (§49).
- [ ] Sound design. **TODO: Finalize focus-state auditory cue sound design.**
      Identity is not defined by a frequency or recipe (528/639 Hz trials are
      exploratory only); sounds are audio assets/renders, licensed or OCF-own.

### Composable preparation pipeline

- [ ] Modular preparation stages: relaxation → Energy Conversion Box →
      optional affirmation → optional oHm / resonant-tuning chant →
      Focus 10 transition → `focus11_open`/`focus11_ready` →
      function/exercise.
- [ ] Every stage optional and independently composable (standard, short,
      expert, custom, localized) without duplicating audio-generation code.
- [ ] Optional affirmation stage: disabled | built-in default | user text |
      multiple blocks | TTS | pre-recorded audio | pauses before/after | future
      wizard.
- [ ] Optional oHm / resonant-tuning chant: disabled | bundled default |
      generated chant | user recording | call-and-response/repetitions; chant
      vocal is language-independent, surrounding instructions localized.
- [ ] Preparation Module artifact (`OCF-PREP-*`, learn-once, `ocf preparation
      …`) building on the stage pipeline; see `docs/PREPARATION_MODULE.md`.

### Localization

Shipped by `proposals/draft/ocfp-0001-semantic-narration-keys-and-locale-packs.md`;
documented in `docs/LOCALIZATION.md` and `locales/README.md`.

- [x] Session-pipeline localization: semantic `narration_key`s for spoken
      narration, locale packs for UI/CLI/validation strings, and `--locale`
      on compose/resolve/render/export/build.
- [x] Locale packs + fallback chain (es-MX → es → en-US); missing **spoken**
      localization fails clearly before render, UI text may fall back, and an
      explicit override is available.
- [x] Language-aware TTS: locale, text, voice, backend, rate, pronunciation
      hints, and timing in the render request; backends report what they
      support; voice mismatch is reported instead of silently mis-rendering.
- [x] Timed-text separation: semantic event/timing, source text, resolved
      text, and measured speech timing stay distinct; measured per-cue
      durations in the render manifest drive localized subtitles, so
      translations never inherit English word-level timestamps.
- [x] DSP language-independence: binaural/SAM config, background, transitions,
      crossfades, and cue events are never duplicated per language.
- [ ] Translations on *function records* (one source language + zero or more
      translations); per-function narration is keyed and localizable today,
      but a translated function record needs its own schema change.
- [ ] Remaining surface: the preparation toolchain, RTL layout, translator
      review tooling, and a real ICU runtime.

### Versioning and backward compatibility

- [x] New optional fields/stages default to no behavior change; locale fields
      are additive and existing English scripts validate and render unchanged.
- [x] Versioning policy for locale packs (semantic version + translation
      provenance); preparation templates and function definitions follow.
- [x] Schema/data-model additions flow through the proposal process
      (`proposals/`, `OCFP-*`) before freeze; see `docs/DESIGN_SPEC.md`.

## v1.0 — Stable

- [ ] Schema 1.0 freeze after community review.
- [ ] Proposal-process stabilization.
- [ ] Accessibility pass (transcripts, loudness, captions).

## Non-goals

- Redistribute or reconstruct Monroe audio.
- Claim medical/psychological/paranormal efficacy.
- Provide therapeutic guidance.