# Roadmap

Current status: **authoring/content/platform foundation in progress**. Transcript,
voice/audio build, localization, reusable semantic stages, cue-binding validation
and measured-ledger DSP dispatch are shipped. Cue playback and the dedicated
preparation CLI remain unshipped. Preparation Learning en-US RC1 has a verified
development audition; its wording/edition remains frozen. A separate v3 learning
successor and active shared-session v3 are implemented as selectable compositions;
audio rendering/listening approval remains separate.

Current inventory snapshot (2026-11-06): the canonical en-US locale has **58 OCF
function definitions**: 55 legacy-mapped targets plus 3 OCF-original records. The
55 legacy mappings split into 39 source-available and 16 source-unavailable;
source availability does not mean that an OCF function is absent. The canonical catalog
has 83 structured command records and 58 generated English session plans.
Plan validity, rendering/technical verification, human listening approval and
publication authorization remain independent statuses.

Legend: `[x] done · [~] in progress · [ ] planned`

Reconciliation: every pre-existing workstream below is retained. An old checked
milestone records its original scope, not a claim that its current successor is
complete. Partial implementations do not close broader unchecked goals. The
three editorial requests already recorded here are expanded in place, not
duplicated; two new high-priority performance workstreams are added separately.
See [reconciliation evidence](docs/ROADMAP_RECONCILIATION_20261106.md).

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
      discovery; these function-specific layers are now embedded in canonical
      locale resources, not separate definition files. Uncertainty remains
      explicit and separate from runtime defaults.
- [x] Complete available-evidence analytical extraction for all55 historical specifications,
      full-source reviews and source locators; no historical/narration approval implied.
- [ ] Unit-only100% lines/branches and CI gates across the documented testable scope.
- [x] Cross-OS core CI configuration, installed-wheel data discovery and Linux smoke.
- [ ] Actual macOS/Windows runtime verification and remaining process adapters.
      PR 27's historical head passed cross-platform Python 3.11/3.12 CI; this
      does not close native audio-engine, private-asset or remaining adapter work.
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

- [ ] Optional Voicebox backend integration is deferred. Retain Chatterbox Nano
      and its current defaults; future opt-in support needs verified runtime,
      model/reference identities, recovery and private profile portability.

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

- [x] Reviewed shared-session v3: one initial One-to-Ten body scan, explicit Ten
      recognition, shared Access Channel cues, optional preparation blocks, and
      separate three-visit/510-second Preparation Learning edition. RC1 and prior
      routine editions remain selectable and immutable; no listening/publication
      approval is implied. See `docs/releases/OCF_SHARED_SESSION_V3_2026-11-08.md`.

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
- [x] Complete per-locale function records: each locale owns its full localized
      definition (structure, cues, instructions, lifecycle, narration order and
      readable speech); English never silently substitutes for a partial locale.
      See `docs/PER_LOCALE_FUNCTION_AUTHORITY.md`.
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

Unchecked items remain approved future tasks, not shipped behavior; checked
items record completed implementation within their stated locale/scope. The three proposed
functions below remain editorial backlog only and must not be registered until
their separate authoring/review process is authorized. The verified registry
remains at 58 functions.

### Function knowledge, localization, and guides

- [x] Source-driven en-US reader edition 0.5.0: comprehensive handbook with
      all 58 functions, general guidance, and fundamentals-first navigation.
- [x] en-US displayed/spoken cue reference and complete current cue index,
      sourced from the authoritative localized function YAML.
- [x] Approved optional complementary-function maps and source-backed uses in
      en-US guides; no relationships or examples invented where none are approved.
- [x] All 58 en-US function PDFs containing readable complete
      canonical transcripts: title, stable ID, locale, description, display and
      exact spoken cues, uses, activation instructions, opener/body/closer and
      approved sections, secondary commands, complementary functions, concise
      cue reminder, and version metadata. Playback repetition is not duplicate
      canonical transcript text.
- [x] Simplify all 58 en-US function YAMLs and comments; retain meaningful
      evidence/provenance/history in the established structured audit system.
- [x] Make the implemented en-US function YAMLs the localized authority, with
      first-class title, description, primary displayed/spoken cues, secondary
      cues, tags, common uses, complementary relationship descriptions,
      narration, and concise changelog fields. Keep stable IDs and
      locale-independent command IDs within the same canonical resources;
      generated technical indexes are read-only views.
- [x] Remove generated cue-preview comment banners from active function YAML.
      Generate
      master indexes, command lists, and guides from structured localized YAML.
- [x] Migrate all 58 active en-US filenames to stable-ID-first readable names such as
      `OCF-EMO-003-Empathize.yaml`, with stable-ID lookup and backward-compatible
      stable-ID resolution. Predecessor path readers are retired; immutable
      audio dependency keys remain provenance only.
- [x] Preserve approved spoken narration and cues byte-for-byte during
      structural conversion; verify resolved-text hashes and immutable
      provenance before migration.
- [ ] Complete additional locale translations and corresponding handbooks,
      cue references and PDFs. Spanish remains partial; no complete Spanish
      guide edition is claimed.
- [ ] Add further human-approved common-use examples where the current source
      provides none; generation must not fabricate editorial content.
- [x] Populate all 58 en-US function YAMLs with source-based **draft** tags and
      common-use examples, and separately labeled, evidenced optional companion
      proposals; these do not count as human editorial approval.
- [x] Remove the 65 unlisted historical-reference stubs from active en-US storage
      after canonical-resource equivalence verification. Historical records are
      recoverable from Git only; no archive reader or replay fallback remains.

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
- [x] A short user-facing zero-shot voice-pack quick start linked from the
      repository entry points; reuse and verify the existing voice-pack CLI and
      `docs/VOICE_PACKS.md` and capability/privacy guidance in `docs/VOICE_CLONING.md`
      rather than creating a second workflow.
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
- [ ] Complete the private Farfield A3/A4 listening decision. A4 tests a fixed
      -11 dB gain on the entire active Focus 11 bed, including speech gaps and
      closure; preserve A3. The user has listened to the complete A4 Hearing
      session and likes its mix, and requested a private A5 successor with only
      an additional fixed -1 dB on Focus 10 while preserving A4 Focus 11. A5
      listening remains pending; neither edition is publicly authorized.
      Technical QC and favorable A4 feedback are not publication authorization.
- [ ] Validate and deploy an independent Linux production service with mandatory
      machine-level heartbeat/watchdog reconciliation, bounded safe recovery and
      deduplicated engineering escalation. Keep frozen rendering inputs and
      verified outputs intact; see [production supervision](docs/PRODUCTION_SUPERVISION.md).
- [ ] Enforce one crash-recoverable owner per complete-render artifact identity:
      atomic reservation, verified process identity, terminal-state recovery,
      cache-only synthesis blocking when requested, safe stage retention, and
      idempotent reuse of verified outputs. Post-publication reporting failures
      must not misreport or invalidate a verified artifact.
- [ ] Finish the private six-session V4 Hearing/Seeing narrator comparison
      across Amy Medium, the original voice, and the TTS.ai-derived reference;
      reuse verified editions and cache receipts, preserve one V4 background
      baseline, and provide an offline index with relative links and hashes.
- [ ] Keep portable private voice-pack metadata minimally identifying: preserve
      accurate consent/provenance and checksums while excluding account names,
      usernames, absolute machine/repository/virtual-environment paths, and
      unrelated personal voice metadata. Voice audio remains potentially
      identifying and private unless separately authorized.
- [ ] Separate technical QC from human listening feedback and explicit approval
      tracking; neither technical renderability nor successful packaging is
      human approval or publication authorization.
- [ ] Bounded private workspace retention, compact default coverage summaries,
      opt-in detailed coverage diagnostics, active-job protection, and receipts
      for cleanup of verified disposable artifacts.
- [ ] Retire only clean, inactive Git worktrees whose source is proven integrated;
      inventory and preserve unique private assets first. Inspect legacy nested
      `.ocf-work` locations, migrate only verified unique artifacts, remove only
      proven disposable duplicates, and retain a hash/path cleanup receipt.

### High-priority engineering — measurement before optimization

- [ ] **TODO D — HIGH / P1: automated test performance, including full coverage.**
  - Scope: baseline full pytest without coverage, instrumented FULL verification,
    unit and integration tiers, setup/install, collection/import and slowest 50
    tests/modules. Profile fixture setup, subprocess startup, audio generation,
    schema/catalog/index loading, temporary I/O and cleanup, coverage subprocess
    startup/combining/reporting, worker contention and platform process overhead.
  - Evidence: record exact SHA, test node population, Python/platform/dependencies,
    worker count, run fingerprint, cache state, wall/CPU time, peak RAM, disk I/O,
    failures and retained CI job/critical-path timings. Compare repeated equivalent
    runs; investigate both pytest-xdist distribution and bounded resource limits.
  - Acceptance: all meaningful tests, integration/failure-path checks and OS gates
    remain; no blanket skips/xfails, unjustified exclusions, reduced test counts
    claimed as speedups or weakened checks. Statement floor stays >=89.5% and
    branch floor >=84.0%; aim to retain/exceed 89.7314% / 84.5798% rather than
    merely clear floors. A reproducible >=30% wall-time reduction is a target,
    not permission to compromise correctness or a guaranteed result.
  - Deliver FAST selected-tier commands without instrumentation and a mandatory
    FULL all-tests statement/branch/subprocess coverage gate, both optimized.
    Preserve Python 3.11/3.12 and Linux/macOS/Windows; publish a performance report
    with equivalent before/after populations, resources, failures and coverage.
  - Dependencies: audited test taxonomy and current full-suite baseline. Immutable
    parsed inputs may be reused only with mutation isolation and correct cache
    invalidation. Never move expensive required checks outside the mandatory gate.
    Engineering work belongs on its own branch/PR, not PR 27.

- [ ] **TODO E — HIGH / P1: batch and bulk session generation performance.**
  - Scope: profile bulk/complete-session planning, TTS and speech-cache reuse,
    Farfield/DSP, composition/mixing, repeated ffmpeg startup, PCM copies,
    hashing/validation, manifests, encoding/packaging and resource scheduling.
  - Benchmarks: public synthetic single-session and multi-function cold/warm
    workloads; partial resume; cache reuse; failure/recovery; worker scaling;
    all 58 planning identities where feasible. Do not rerender private editions
    merely to benchmark. Record wall time/session, sessions/hour, stage timings,
    CPU/GPU utilization, peak RAM/VRAM, temporary disk/I/O, cache hits/misses,
    failed/retried jobs and integrity results with exact SHA/environment/cache state.
  - Acceptance: reproducible equivalent before/after cold, warm, partial-resume,
    recovery and scaling runs demonstrate actual improvement. Deterministic
    output remains byte-exact where contracted; nondeterministic stages need
    documented PCM/sample/semantic invariants and measured tolerances. Preserve
    narration, voices, IDs/order, Focus 10/11, crossfades, loudness, DSP/default
    locks, manifests/fingerprints, privacy, checkpoints, resumability, job identity,
    collision protection and atomic publication. No silent mix change.
  - Deliver profile-backed changes only, lightweight performance smoke tests,
    an optional benchmark workflow, and a report of remaining bottlenecks and
    resource-aware concurrency limits. Keep long benchmarks out of ordinary PR
    checks; retain real integration checks. No private models/recordings published.
  - Dependencies: verified rendering/cache/reservation contracts, reproducible
    public fixtures and independent watchdog/recovery. Reuse TODO D's measurement
    conventions, not its performance claims. Use a separate engineering branch/PR.

### Planned editorial reviews — approval pending

- [x] The approved original long-form relaxation is the one initial shared v3
      induction, not a second ascent. Historical LONG-002 remains selectable.
- [ ] **PLANNED — short relaxation alternative deferred.** No short wording is
      authored or activated; only design a selectable short mode after separate
      explicit wording/flow approval. It must not replace the current long-form
      default or alter historical editions implicitly.
- [ ] **PLANNED — editorial approval pending: optional short relaxation
      preparation mode (TODO A / P2).**
  - Scope: review and design a short preparation variant, including
    review of proposed wording, pacing, holds and transitions.
    Keep the current default unchanged
    until the revised wording and behavior receive explicit approval.
  - Acceptance criteria: each proposed mode has separately reviewed wording,
    pacing, and transition behavior; the selected mode is explicit; the current
    default and its plan/lock remain unchanged until approval; tests verify that
    opting into a variant does not silently alter the default. Preserve Focus
    10/11 entry, validate localized narration and generated session plans, and
    require explicit human editorial AND listening approval before production
    adoption. No successor default is approved by this TODO.
  - Dependencies: composable preparation and locale/timing contracts; distinguish
    short/long relaxation duration from the older expert-mode stage omission.
    Proposed order: current-text review → wording proposals → owner review →
    opt-in configuration/planning tests → timed auditions → listening decision.

- [ ] **PLANNED — editorial approval pending: OCF-BOD-010 Nutricia mode
      persistence and activation (TODO B / P2).**
  - Scope: review and design whether a last-used mode is remembered or selected
    only at activation, and define the change/reset controls and approved
    behavior semantics. Review current modes, activation semantics and narration.
    Desired convenience: default to the last selected mode without repeatedly
    selecting or activating the same mode. Separately evaluate persisted mode
    selection, persisted activation state, automatic behavior or a combination;
    remembering a choice must not silently activate a function. Do not claim or
    imply weight-loss efficacy; this supports a weight-management practice.
  - Acceptance criteria: an approved specification distinguishes mode selection,
    persistence, and activation; defines the change and reset behavior; preserves
    existing command/lifecycle semantics unless explicitly approved otherwise;
    and contains no weight-loss efficacy claim. Add behavior tests before any
    implementation is considered complete. Preserve explicit user control,
    manual override and reset; review any activation wording and persistence
    semantic changes before implementation, including restart/default behavior.
  - Dependencies/order: inspect canonical Nutricia modes/lifecycle → specify
    distinct selection/activation/automatic options and reset → owner semantic
    and wording review → persistence implementation and restart/override tests.
- [ ] **PLANNED — editorial approval pending: Focus 11 opener and closer review
      (TODO C / P2).**
  - Scope: review and rewrite the opener and closer while preserving the current
    Focus 10/11 transitions and timing. Inspect `locales/en-US/hplus-focus11-open.yaml`
    and `locales/en-US/hplus-focus11-close.yaml`; improve wording, clarity, natural
    delivery and consistency. Do not edit or replace immutable editions;
    leave `audio/scripts/attention.yaml` untouched and do not change the V2.1
    induction curve or level before the V2/V2.1 listening comparison.
  - Acceptance criteria: approved successor wording is versioned separately;
    event order, focus transitions, and measured timing anchors remain intact;
    existing immutable editions and their hashes are unchanged; and validation
    tests cover the transition/timing contract. Listening and release approval
    remain separate decisions. Preserve the count sequence and repeated Ten
    cues unless separately approved, established exit crossfade and timing
    contracts; require owner wording approval before production replacement.
  - Dependencies/order: capture current text/timing/crossfade contracts → propose
    opening/closing text together → owner wording review → localized/timing
    validation → separately versioned audition → listening/release decisions.

### Proposed order for the five additions

1. Finish PR 27 authoring-boundary verification and exact-head CI; wait for
   required independent human review and owner merge authorization.
2. TODO D: freeze a comparable baseline, profile, implement measured test changes
   separately, then run equivalent full-suite/coverage/cross-platform verification.
3. TODO E: establish cold/warm/resume/recovery baselines, then optimize measured
   rendering bottlenecks separately and prove output equivalence and resource safety.
4. TODO A and TODO C: prepare human-review wording proposals together where
   transition contracts overlap, but approve and version each change separately.
5. TODO B: review persistence semantics independently, then implement only after
   the owner approves behavior and wording. Editorial review may proceed in
   parallel with D/E; no pending human approval blocks unrelated safe engineering.

This order prioritizes measurement and safety; it does not defer or remove
localization, guides, private voice packs, audio profiles, preparation stages,
supervision, cleanup, UI/mobile work or the proposed function concepts below.

### Proposed function concepts — editorial backlog only

- [ ] `PLUS LUCKY`: positive intention, favorable opportunities, and recognition
      of beneficial possibilities.
- [ ] Energy Ball / REBAL (resonant energy balloon): draft original OCF exercises
      using proposed spoken cue `Plus Inflate` to expand and `Plus Deflate` to
      withdraw, per Michael's November 12 direction. These names replace the
      earlier editorial placeholder `PLUS PROTECT`; they are not released cues.
- [ ] Plus Hair Growth: draft an original exercise using proposed spoken cue
      `Plus Sprout`, from a user suggestion confirmed by Michael on November 12.
      Treat this as an experimental visualization/intention concept, not evidence
      of hair regrowth or an established medical effect.
- [ ] After the website fixes, prepare both exercise mockups for owner review.
      Keep them as editorial drafts, separate from canonical function definitions,
      activation instructions, narration and published audio. Do not promote them
      to approved/released content or rerender audio without explicit review.

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
