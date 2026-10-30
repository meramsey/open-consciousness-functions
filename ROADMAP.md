# Roadmap

Current status: **authoring/content/platform foundation in progress**. Transcript,
voice/audio build, localization, reusable semantic stages, cue-binding validation
and measured-ledger DSP dispatch are shipped. Cue playback and the dedicated
preparation CLI remain unshipped. Preparation Learning en-US RC1 has a verified
development audition; three function rehearsals are draft pilots requiring review.

Current inventory snapshot (2026-10-25): the verified registry has **58 OCF
function records**: 55 legacy-mapped targets plus 3 OCF-original records. The
55 legacy mappings split into 39 source-available and 16 source-unavailable;
source availability does not mean that an OCF function is absent. The registry
has 83 structured command records and 58 generated English session plans.
Plan validity, rendering/technical verification, human listening approval and
publication authorization remain independent statuses.

Legend: `[x] done · [~] in progress · [ ] planned`

## Current foundation checkpoints

- [x] Extend permanent `docs/NARRATION_STANDARD.md` with purposeful operations,
      sensory flexibility, secular framing, silence and original expression.
- [x] `corpus inventory`:277 local files/all55 historical targets; fingerprints and candidate
      locators, no reference wording redistributed or mockups promoted.
- [x] Relax/Hearing/Sleep Easy DRAFT PILOT rehearsals and local voice previews;
      no mass conversion or human content approval implied.
- [x] `capabilities --json`, `functions list|describe --json`, concise agent entry.
- [x] Combined-suite coverage audit; see `docs/TEST_COVERAGE.md` for the actual gap.
- [x] Separate function evidence/specification/decision/binding schemas and rich
      discovery; uncertain values remain explicit and separate from runtime defaults.
- [x] Complete available-evidence analytical extraction for all55 historical specifications,
      full-source reviews and source locators; no historical/narration approval implied.
- [ ] Unit-only100% lines/branches and CI gates across the documented testable scope.
- [x] Cross-OS core CI configuration, installed-wheel data discovery and Linux smoke.
- [ ] Actual macOS/Windows runtime verification and remaining process adapters.
- [x] Event-mapped prerecorded narration alternative to TTS, measured timing and
      original-file provenance; directory import/GUI recording still planned.
- [x] Idempotent native core setup planner and optional non-root CPU container;
      actual Linux setup/reuse/build/recording-render smoke checks completed.
- [x] Metadata-only community voice registry with separate model/software/data/voice
      rights; no models bundled/downloaded. Distribution/install service still planned.
- [x] Deterministic structured authoring-plan preflight; no natural-language engine
      or mass wording generator. Full guided wizard remains planned.
- [ ] Desktop/mobile GUI using the same schemas/APIs; no framework selected.
- [ ] Approximately ten high-impact languages chosen from speaker/digital/
      geographic reach, accessibility, TTS/review capacity and script support.
      No population-only ranking or fixed final list; translate semantic purpose.
- [ ] Community functions/meditations/languages/narration/voices/backgrounds/cues
      with provenance, licensing and compatibility validation.
- [ ] Mobile/GUI recording per semantic utterance, playback/re-record/trim, exporting
      the same future prerecorded package as the CLI.

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
- [x] Three OCF-original function records, separate from legacy-source counts.
- [x] Interactive contributor CLI (`./scripts/ocf`) with wizards.
- [x] Validation (schema, duplicate id/command, command rules, invariants).
- [x] Generated indexes with freshness checks and CI enforcement.
- [x] Farfield integration stub with graceful degradation.
- [x] Test suite.

## v0.2 — Reimplementation content

- [~] First original OCF training scripts for the 16 source-unavailable
      legacy functions (proposal pathway).
- [ ] Community review of the remaining function command-review records:
      1 `review-required` and 2 `needs-review` (55 approved, 58 functions total).
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

## Additional approved backlog — 2026-10-29

These are approved future tasks, not shipped behavior. The three proposed
functions below remain editorial backlog only and must not be registered until
their separate authoring/review process is authorized. The verified registry
remains at 58 functions.

### Function knowledge, localization, and guides

- [ ] Per-locale comprehensive OCF function handbook, including general use
      guidance, definitions for all current functions, and a fundamentals-first
      suggested learning pathway.
- [ ] Per-locale displayed/spoken activation-cue reference and complete cue
      index, sourced from the authoritative localized data.
- [ ] Verified complementary-function maps, common-use examples, related
      learning guidance, and complementary functions in user-facing guides.
- [ ] Individual downloadable function PDFs containing readable complete
      canonical transcripts: title, stable ID, locale, description, display and
      exact spoken cues, uses, activation instructions, opener/body/closer and
      approved sections, secondary commands, complementary functions, concise
      cue reminder, and version metadata. Playback repetition is not duplicate
      canonical transcript text.
- [ ] Simplify bloated localized YAML metadata and comments; retain meaningful
      evidence/provenance/history in the established structured audit system.
- [ ] Make localized YAML the authority for localized function data, with
      first-class title, description, primary displayed/spoken cues, secondary
      cues, tags, common uses, complementary relationship descriptions,
      narration, and concise changelog fields. Keep stable IDs and
      locale-independent command IDs in their technical registries.
- [ ] Remove generated cue-preview comment banners as an authority. Generate
      master indexes, command lists, and guides from structured localized YAML.
- [ ] Migrate localized filenames to stable-ID-first readable names such as
      `OCF-EMO-003-Empathize.yaml`, with stable-ID lookup and backward-compatible
      path/ID resolution during migration.
- [ ] Preserve approved spoken narration and cues byte-for-byte during
      structural conversion; verify resolved-text hashes and immutable
      provenance before migration.

### Audio baselines, voice privacy, and listening review

- [ ] Treat the latest approved, technically verified 58-function session
      settings as the current baseline for future editions; preserve historical
      editions and immutable source/profile manifests.
- [ ] Retire superseded temporary pilot references only after inventory and
      verified preservation of immutable historical records and editions.
- [ ] Beginner-friendly zero-shot voice-cloning documentation: recording,
      reference preparation, pack creation/import, audition, narrator selection,
      complete-session render, portable private backup/restore, optional runtime
      setup, troubleshooting, privacy, licensing boundaries, and limitations.
- [ ] Private daily affirmations generator using user-owned voice packs; local
      output only unless separately authorized.
- [ ] Accessible user-facing discovery of private voice profiles, references,
      auditions, and completed renders, with stable workspace/path reporting.
- [ ] Portable private voice-pack backup/export/restore, with checksum
      validation, consent/provenance preservation, and isolated restore tests.
- [ ] Canonical shared `.ocf-work` runtime across linked worktrees, explicit
      `OCF_WORK_DIR`, safe legacy nested-workspace discovery/migration, and
      per-project isolation. Migrate existing private assets only with an
      inventory, verified copy, and ownership/provenance checks.
- [ ] Focus 11 narrator/background intelligibility analysis and corrected
      audition candidates; preserve approved DSP and require human listening
      preference before promoting a profile.
- [ ] Controlled authentic Farfield/reference-V4 A/B comparisons using one
      verified speech source and the shared OCF mixer, with reproducible level,
      timeline, DSP, and provenance receipts.
- [ ] Separate technical QC from human listening feedback and explicit approval
      tracking; neither technical renderability nor successful packaging is
      human approval or publication authorization.
- [ ] Bounded private workspace retention, compact default coverage summaries,
      opt-in detailed coverage diagnostics, active-job protection, and receipts
      for cleanup of verified disposable artifacts.

### Proposed function concepts — editorial backlog only

- [ ] `PLUS LUCKY`: positive intention, favorable opportunities, and recognition
      of beneficial possibilities.
- [ ] `PLUS PROTECT`: rapid one-breath REBAL/resonant energy-balloon activation,
      preserving original OCF wording and mechanics.
- [ ] `PLUS HAIR GROWTH`: intention-based focus for encouraging desired hair
      growth in selected regions; do not present unverified physiological
      outcomes as established medical effects.

## Post-v1.0 — Per-state narration intelligibility

- [ ] Add explicit, opt-in foreground/background preferences per semantic
      state, including background level and speech-aware ducking depth, attack,
      and release. Preserve stereo/binaural relationships with linked-channel
      gain; retain current defaults unless separately approved. Keep user-level
      overrides distinct from immutable DSP/profile locks, version every
      approved successor, and require measured QC plus human listening before
      promotion. Do not apply a Focus 11 preference to Focus 10, sleep,
      transitions, or closure by inheritance.

## Non-goals

- Redistribute or reconstruct Monroe audio.
- Claim medical/psychological/paranormal efficacy.
- Provide therapeutic guidance.
