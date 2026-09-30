# Timed Transcripts and Timed Lyrics

How OCF turns timed narration — including lyric-style `.lrc` files — into a
canonical script, a function record, and a built audio implementation … and
exactly what is supported at each step.

In this document the terms **timed lyrics** and **LRC** refer to the lyric
standard: timestamped lines such as `[00:03:30.00]Let the body settle.`.

## Status at a glance

Every capability below is either **implemented** (shipped in the current CLI),
**specified** (fully defined in
`OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md`, tracked in
`ROADMAP.md`, not yet shipped), or **planned** (designed in the docs below,
tracked in `ROADMAP.md` v0.5, not yet specified or shipped). Nothing here
claims a tool exists until it does.

| Capability                                              | Status      |
| ------------------------------------------------------- | ----------- |
| Function records, proposals, audio/background manifests | implemented |
| LRC / SRT / WebVTT / txt / md import → OCF timed YAML    | implemented |
| Canonical OCF timed YAML schema + template               | implemented |
| Structural analysis (`analyze`) and section roles (`segment`/`apply`) | implemented |
| Timeline resolution (`at` / `after`+`offset`), exports (SRT/VTT/LRC) | implemented |
| Timing-only template extraction (`extract-template --timing-only`) | implemented |
| State/focus assignment (`review --state-profile`)        | implemented |
| Voice backends (`voice` command; render narration WAV)   | implemented |
| Mixing, mastering, render manifests (`audio build`)      | implemented |
| Background engines (Farfield · SBaGenX · reference-master) | implemented |
| Even-spaced count re-timing (`voice render --even-counts`) | implemented |
| Session composition templates + slots (`ocf session`)       | implemented |
| Multi-format tagged outputs (WAV/FLAC/MP3 via `audio build`) | implemented |
| Reusable section-template library (`audio/templates/`)   | implemented |
| State-profile library + state-aware Farfield backgrounds | specified   |
| Voice cloning profiles (OpenVoice/Kokoro/pre-recorded)   | specified   |
| Preparation Module (learn-once, `OCF-PREP-*`)            | specified   |
| Composable preparation stages (relaxation · ECB · optional affirmation · optional oHm · focus transitions) | planned (see [`PREPARATION_MODULE.md`](PREPARATION_MODULE.md)) |
| Focus-state auditory cue events (`focus11_open` / `focus11_ready` / `focus11_close` / `session_complete`) | planned (see below) |
| Localization / locale packs / language-aware TTS (incl. translated timed text) | planned (see [`LOCALIZATION.md`](LOCALIZATION.md)) |

The normative sections are **§32, §44–50** (transcripts, states, sections) and
**§27–43, §51–61** (voices, mixing, preparation) of the v3 bootstrap prompt.

## Concepts

### The pipeline in one line

```text
timed lyrics (.lrc / SRT / WebVTT / txt / md)
   →  OCF timed YAML (canonical, editable)
   →  sections + state/focus assignment
   →  function record + audio-implementation manifest
   →  voice (TTS backend) + background (Farfield · SBaGenX · reference-master) + mix (PCM/ffmpeg)
   →  lossless master + render manifest + checksums
```

### Why LRC is import-only

OCF timed YAML is the **canonical editable format** because narration needs
more than a timestamp and a line: segment *duration*, `pause_after`, `gain`,
`voice` profile, state/focus level, and relative placement (`after` +
`offset`). LRC, SRT, and WebVTT cannot express that. They are therefore
**import-only / interoperability formats**: the importer preserves their exact
text and timestamps, and OCF timed YAML becomes the working document.

### Supported input formats

| Input format      | Role                                    | Notes |
| ----------------- | --------------------------------------- | ----- |
| `.lrc`            | timed lyrics (import)                   | handles metadata tags, centisecond/millisecond timestamps |
| `.srt`            | interoperability (import + export)      | | 
| `.vtt`            | interoperability (import + export)      | |
| `.txt` / `.md`    | plain transcript (import)               | untimed; becomes a schedule-less script |
| `OCF timed YAML`  | canonical editable format               | also importable to re-bootstrap a session |

Export targets from OCF timed YAML: **SRT**, **WebVTT**, **LRC** — shipped via
`ocf transcript export FILE --format srt|vtt|lrc [--output]`. Export requires
every event to be timed; a schedule-less (untimed) script must be timed first
(e.g. by re-importing a timed source or editing `at` values).

### Authoring modes

| Mode                | For who                                        |
| ------------------- | ---------------------------------------------- |
| Import + review     | Contributor with an existing timed transcript  |
| Guided template     | Non-technical contributor writing new content  |
| Advanced / freeform | Direct editing of the canonical timed YAML     |

## End-to-end walkthrough: add a function from timed lyrics

### 0. Where things live

| Artifact                 | Path                                          |
| ------------------------ | --------------------------------------------- |
| Timed script (canonical) | `audio/scripts/<slug>.yaml`                   |
| Timed transcript schema  | `schemas/timed-transcript.schema.json`        |
| Template                 | `templates/timed-transcript.yaml`             |
| Function records         | `functions/<domain>/<slug>.yaml`              |
| Audio manifests          | `audio/manifests/OCF-AUDIO-*.yaml`            |
| State profiles           | `audio/states/profiles/`                      |
| Reusable sections        | `audio/templates/`                            |
| Voice profiles           | `audio/voices/profiles/`                      |
| Outputs                  | `audio/rendered/`                             |

### 1. Prepare the timed-lyrics file

Any of these are acceptable starting points:

- an `.lrc` file (most common for existing timed meditation lyrics);
- `.srt` or `.vtt`;
- a plain `.md` / `.txt` narration you want to time later;
- an already-authored `.yaml`.

Example `attention.lrc` (synthetic OCF example, original wording):

```lrc
[ti:Attention — OCF example]
[ar:Open Consciousness Functions]
[00:00:00.00]
[00:00:08.00]Allow your breathing to become easy and natural.
[00:00:24.50]With each exhale, let the day settle behind you.
[00:03:18.00]You are now entering the standard learning state.
[00:03:30.00]10... 9... 8... 7... 6... 5... 4... 3... 2... 1...
[00:07:40.00]In this state, learn the function of Attention.
[00:07:45.00]The command is PLUS-FOCUS.
[00:07:52.00]PLUS-FOCUS.
[00:08:50.00]Use roughly ten comfortable breaths to practice PLUS-FOCUS.
[00:11:30.00]The learning is complete. The command PLUS-FOCUS remains yours.
[00:12:50.00]Returning now to full, alert, waking awareness.
[00:13:10.00]1... 2... 3... wide awake, clear, and refreshed.
```

The importer deliberately copes with imperfect material: metadata before the
first timed line, blank lines, repeated timestamps, centiseconds or
milliseconds, long pauses, and countdown/numbers-only lines. It never
"fixes" wording — the source text is preserved verbatim in the import
snapshot.

### 2. Import

```bash
ocf transcript import attention.lrc
# import attention.lrc --format auto --output audio/scripts/attention.yaml
```

The importer:

1. detects format by extension/content;
2. records source filename + SHA-256 and the metadata tags
   (`[ti:]`, `[ar:]`, `[length:]`, `[re:]`, …) under `source.metadata`;
3. normalizes timestamps into OCF's canonical timeline;
4. keeps the **exact source text** in an import snapshot (`source.snapshot`);
5. writes an editable OCF timed YAML document and validates it.

Result (canonical OCF timed YAML — abridged; import snapshot omitted):

```yaml
schema_version: "1.0"

title: "Attention — OCF example"
source:
  format: "lrc"
  filename: "attention.lrc"
  sha256: "…"
  metadata:
    ti: "Attention — OCF example"
    ar: "Open Consciousness Functions"

timeline:
  - id: e001
    at: "00:00:08.000"
    text: "Allow your breathing to become easy and natural."

  - id: e002
    at: "00:00:24.500"
    text: "With each exhale, let the day settle behind you."

  - id: e003
    at: "00:03:30.000"
    text: "10... 9... 8... 7... 6... 5... 4... 3... 2... 1..."

  - id: e004
    at: "00:07:45.000"
    text: "The command is PLUS-FOCUS."

  - id: e005
    at: "00:07:52.000"
    text: "PLUS-FOCUS."
    timing:
      pause_after: 10.0
```

Event ids are auto-generated (`e001`, `e002`, …) on import and may be renamed
as the script becomes a section-grouped document.

### 3. Assign section roles

```bash
ocf transcript segment attention.yaml --apply        # apply suggested boundaries
ocf transcript segment attention.yaml                # interactive: accept/reject each boundary
ocf transcript analyze attention.yaml --interactive  # same review loop
```

Group flat entries into semantic roles: `preparation`, `induction`,
`access-open`, `function-intro`, `installation`, `rehearsal`, `integration`,
`access-close`, `consolidation`, `sleep`, `return`, `outro`, or
`state-transition`. The analyzer's findings are **suggestions only** — the
contributor accepts or rejects every boundary (`--apply`/`--force` write the
result; a long pause or a countdown is a candidate boundary, never a fact).

```yaml
sections:
  - id: sec-001
    type: preparation
    timeline: [e001, e002, e003]
  - id: sec-002
    type: installation
    timeline: [e004, e005]
```

### 4. Assign state / focus

```bash
# validate + set a state profile, then write it back:
ocf transcript review attention.yaml --state-profile OCF-STATEPROFILE-HPLUS-LEGACY-001 --write
# or inspect without writing:
ocf transcript review attention.yaml
```

Choose a state profile (e.g. the reference-derived
`OCF-STATEPROFILE-HPLUS-LEGACY-001`, or an original OCF profile), then assign
a state at **session**, **section**, or **event** level — the most specific
wins. Auto-detected transitions stay suggestions awaiting confirmation.

```yaml
state_profile: "OCF-STATEPROFILE-HPLUS-LEGACY-001"

sections:
  - id: preparation
    type: preparation
    state: {from: waking, to: "focus-10"}
  - id: function-install
    type: installation
    state: {from: "access-11", to: "instruction-12"}
    timeline:
      - id: install-001
        state: "instruction-12"
```

### 5. Create the function record

```bash
ocf new function
```

Associate the script with a function (`functions/<domain>/<slug>.yaml`). If
none exists yet, the wizard walks you through it. The function record holds
the purpose, canonical command (`PLUS-FOCUS`, …), legacy mapping, safety
level, and audio status — the timed script itself stays in `audio/scripts/`.

### 6. Register the audio implementation

```bash
ocf new audio
```

`ocf new audio` also walks through voice selection automatically. It records
which function, which script, which voice, which background strategy, the
training type (`training` / `reinforcement` / `quick` / `sleep` / …), and the
legacy-cue bridge and release rehearsal design.

### 7. Choose a voice

The shipped toolchain detects optional TTS backends on PATH and renders each
cue independently (placement is **exact**: every cue sits at its `at`
timestamp; an overlapping cue cuts the previous one at that point — see the
*Import invariants* section). Wording is never rewritten.

```bash
ocf voice list-backends        # what's detected: espeak-ng, espeak, piper
ocf voice doctor               # backend + voice-profile health
ocf voice list                 # installed profiles (audio/voices/profiles/)
ocf voice render audio/scripts/attention-timing-template.yaml \
    --voice espeak-en --output audio/rendered/attention-narration.wav
```

Pacing flags (see `docs/USER_GUIDE.md`): `--fit` (adaptive per-cue pacing),
`--flow` (merge fragmented sentences into flowing ones), and `--even-counts`
(re-time pure-count runs onto even grids anchored by each run's first/last
count — `timing_mode …+even-counts`). Wording is never rewritten by any flag.

Voice profiles are small YAML files in `audio/voices/profiles/` (see
`templates/voice-profile.yaml` + `schemas/voice-profile.schema.json`) that
select a backend, language, and words-per-minute. Voice cloning via
OpenVoice/Kokoro and pre-recorded narration remain **specified**, not shipped;
the `ocf new audio` wizard records the voice/background design regardless.

### 8. Choose a background

```bash
ocf audio render-background OCF-BG-0001
ocf audio render-background OCF-BG-0002 --engine sbagenx
ocf audio render-background OCF-BG-0004 --engine reference-master
```

Backgrounds are `OCF-BG-*` presets independent of the narration, rendered by
one of three engines: **Farfield** (synthesis), **SBaGenX** (synthesis), or
**reference-master** (even-timbre beds composed from operator-supplied
reference files that stay local and citation-only). A preset's manifest
`engine` is used automatically; an explicit `--engine` overrides it. If the
script has a **state timeline**, you may instead choose a *state-aware
background program* that maps each state to a preset and crossfades between
them, preserving stereo/binaural relationships (specified, not yet shipped).

### 9. Preview and build

```bash
ocf audio render-speech audio/scripts/attention-timing-template.yaml   # narration WAV
ocf audio mix --speech narration.wav [--background bg.wav] --output final.wav
ocf audio build OCF-AUDIO-0001             # narration + background + master (WAV)
ocf audio build OCF-AUDIO-0001 --format flac|mp3
ocf audio inspect final.wav                # metadata + SHA-256
```

The build validates the function and script, renders the narration, mixes in
the configured background (Farfield/SBaGenX beds via pure stdlib PCM;
reference-master beds via ffmpeg), encodes to FLAC/MP3 via ffmpeg/flac when
requested, computes checksums, and writes an `OCF-RENDER-*` manifest. Lossless
output (WAV/FLAC) is always available; MP3 is an optional derivative. Missing
TTS backends, missing encoders, and a missing background engine degrade
gracefully with guidance instead of failing silently. If a TTS backend is
absent, install one (e.g. `sudo apt install espeak-ng`).

### 10. Compose a session from templates (declared-slot contract)

For people who supply only the function-specific wording of a learning
session — not the full timed script — `ocf session` fills a **session
template** with that wording and produces the canonical timed YAML:

```bash
ocf session list-templates
ocf session compose \
    --opener my-opener.txt \
    --focus11 my-focus11.txt \
    --sleep20 my-sleep20.txt \
    --closer my-closer.txt \
    --title "Focus session" --id my-session \
    --output audio/scripts/my-session.yaml
```

Each template declares the slots it needs (`slots.required` /
`slots.optional`); the composer accepts **only** declared slots, so the
optional `--NAME FILE` flags (and the generic `--slot NAME=PATH`) line up with
whatever a particular template asks for. The default
`OCF-TPL-SESSION-LEARN-001` shell requires four:

- `--opener FILE` — the opener wording (e.g. a Focus-11 opener);
- `--focus11 FILE` — the **actual function material delivered while in the
  focus-11 state**: function intro, installation, and cue rehearsal;
- `--sleep20 FILE` — the **function reinforcement spoken while in the
  twentieth/sleep state** (this is the part that replaces any repeated
  access-channel wording at the sleep level with the contributor's own
  function wording);
- `--closer FILE` — the closer wording, spoken **after** returning from the
  twentieth state back to the tenth state, before the track ends.

What OCF provides (the shell): opening the access channel, closing access,
consolidation, a count up to the twentieth state, the sleep hold, a count back
to the tenth state, and the wake. The default `OCF-TPL-SESSION-LEARN-001`
shell is **original OCF placeholder wording**; a citation-only,
reference-derived shell can be used locally via `--template /path/to/file.yaml`
and is never committed.

Slot files are plain text, one spoken line per line. Lines may carry an
`[MM:SS.xx]` LRC-style timestamp, which is honoured as an absolute track
time; untimed lines are paced evenly (`--line-seconds N`, default 3). A
section may declare `repeat` to run its slot wording once per band across the
section window (`even-span`), so reinforcement floats through the session;
`from_slot` reuses another slot's wording without declaring it (the Attention
template's `sleep20` repeats `focus11` this way as a `-24 dB` underlay). The
composed document records `template` provenance and the exact slot wording
under `slots`, and passes `timed-transcript.schema.json` validation. The
committed `OCF-TPL-SESSION-ATTENTION-001` template is an adapted legacy-arc
working reference with a single required slot:

```bash
ocf session compose --template OCF-TPL-SESSION-ATTENTION-001 \
    --focus11 audio/slots/attention/focus11.txt \
    --id OCF-SCRIPT-ATTENTION-001 --output audio/scripts/attention-ocf.yaml --force
```

### Quiet sections (`gain_db`)

A session section may declare `gain_db` (number; negative = quieter). The
window runs from that section's first event to the next section's first event,
and `ocf audio build` applies it to the narration in both the pure-stdlib and
the ffmpeg mixing paths, recording what it applied in the render manifest as
`narration_gain_windows`:

```yaml
- id: sleep20
  type: reinforcement
  gain_db: -24.0
  timeline: [...]
```

This is how a twentieth-state reinforcement can be *present but barely
audible* — a faint underlay beneath the bed instead of narrated speech or a
silent gap. Verify it by measurement rather than assumption: compare the
speech-band RMS under the reinforcement with the RMS in the silence between
lines (see `technical.loudness_notes` in `OCF-AUDIO-0001.yaml`).

### Planned: focus-state auditory cue events

Status: **planned** (v0.5, `ROADMAP.md`). Not shipped. Cue events are the
non-narration layer of the same timeline: an audio event fired at a
focus-state transition, independent of the TTS wording.

- Semantic event ids (extensible per focus level/state profile):
  `focus11_open`, `focus11_ready`, `focus11_close`, `session_complete`.
- Resolution chain: semantic event → **configured cue** → rendered/generated
  sound | bundled audio asset | user-supplied audio asset | disabled. Replaced
  per preset without touching session logic.
- Alignment: cues key off the state timeline (§48) and the state-aware
  background program's transition points (§49), not off per-word timing.
- Naming is distinct from two existing uses of *cue*: the VTT/SRT import
  identifier `cue_id`, and the §48 `cue: {type: state-transition}` structural
  marker. The new events are a *played-now* contract; a proposal will choose
  field names so the three never collide.
- **TODO: Finalize focus-state auditory cue sound design.** Identity is not a
  frequency (528/639 Hz trials in `ocf-focus-state-cue-prototypes.zip` are
  exploratory placeholders); the shipped cue is an OCF-owned or clearly
  licensed audio asset or a render, replaceable and license-annotated per
  `SOURCE_ATTRIBUTION.md`.

### Original vs citation-only narration

The render manifest records a `source_text_policy`, and FLAC/MP3 carry it in
the `comment` tag. A document counts as committable OCF wording only when it
was composed from an `original-ocf` session template or declares
`source.format: manual` with no import snapshot; everything else is reported
as citation-only. Imported wording is never relabelled as OCF-authored.

The track is then built and tagged in all three formats at once:

```bash
ocf audio build OCF-AUDIO-0001 --format wav --format flac --format mp3 \
    --tag artist="Your Name" --tag comment="Session for personal use"
```

## Reference

### OCF timed YAML anatomy

| Field           | Meaning                                              |
| --------------- | ---------------------------------------------------- |
| `title`         | script name                                          |
| `source`        | original filename, SHA-256, source metadata snapshot |
| `state_profile` | profile used for state/focus levels (§47)            |
| `sections` or `timeline` | flat list, or grouped sections each with a `timeline` |
| `at` / `after`+`offset` | absolute or relative placement; circular references are rejected |
| `text`          | narration text (verbatim when imported)              |
| `voice`         | profile, `rate`, `gain_db`                           |
| `timing`        | `preferred_duration`, `maximum_duration`, `pause_after` |
| `state`         | state assignment at session/section/event level      |

### Timing modes for synthesized speech

| Mode             | Behavior |
| ---------------- | -------- |
| `natural`        | render at normal speed; timeline may grow |
| `fit-soft` (default) | modest speed/time-stretch within safe bounds; report otherwise |
| `fit-strict`     | force the window; warn beyond recommended bounds |
| `timeline-shift` | keep natural speech, shift later relative events |

Never force speech into a window at the cost of intelligibility. Timing
decisions are recorded in the render manifest.

### Import invariants

- Source wording and timestamps are preserved exactly; the importer never
  silently rewrites drafts.
- The original source filename and SHA-256 are stored.
- Auto-detected sections/states are always suggestions.
- Imported proprietary or reference transcripts stay **citation-only**: they
  may be used locally for structural analysis, and timing-only templates can
  be extracted, but their wording is not copied into public reusable OCF
  templates unless clearly lawful to redistribute.
- **Local generation from a lawfully held file is explicitly permitted.** If
  you own a lawful copy of the source audio/transcript (e.g. a purchased or
  officially licensed recording), you may run the full local pipeline against
  it — import, analyze, segment, review, `voice render`, and `audio build` —
  to create narration/audio for your own use. What is restricted is *committing
  the transcript wording to this repository*, not processing the file on your
  own machine. Rendered narration generated from such a file is a recreation of
  copyrighted expression and remains personal / clearly-lawful use; it must not
  be distributed through OCF without proper authorization. When in doubt,
  distribute timing templates and render manifests, and keep wording local.

### Relationship to other docs

Current docs:

- [`AUDIO_STANDARD.md`](AUDIO_STANDARD.md) — audio-implementation manifests.
- [`BACKGROUND_AUDIO.md`](BACKGROUND_AUDIO.md) — background engines (Farfield,
  SBaGenX, reference-master), presets, and state-aware background programs.
- [`SAFETY_POLICY.md`](SAFETY_POLICY.md) and
  [`EVIDENCE_AND_CLAIMS.md`](EVIDENCE_AND_CLAIMS.md) — what OCF does and does
  not claim.
- [`SUBMISSION_GUIDELINES.md`](SUBMISSION_GUIDELINES.md) — how to submit
  scripts and audio.
- [`PREPARATION_MODULE.md`](PREPARATION_MODULE.md) — planned preparation-stage
  design (relaxation · ECB · optional affirmation · optional oHm · focus
  transitions).
- [`LOCALIZATION.md`](LOCALIZATION.md) — planned locale packs, language
  fallback, and language-aware TTS.

Specified in the v3 bootstrap prompt, to be authored alongside the remaining
(specification-only) toolchain: `STATE_AND_FOCUS_LEVELS.md`,
`AUDIO_SECTIONS.md`, `MIXING_AND_MASTERING.md`, `VOICE_BACKENDS.md`,
`VOICE_RECORDING_GUIDE.md`. Until those exist, the corresponding sections of
`OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md`
(§28–§31, §35–§37, §46–§47, §51–§54) are the authoritative references.