# OCF Audio Pipeline

This document describes the current shipped pipeline. It is an implementation
map, not a promise that every designed preparation feature is shipped.

## Layers

Function records declare capability and identity. Session templates and timed
YAML declare operations, event identity, ordering, narration references, and
semantic state directives. Locale resources supply spoken text. Voice profiles
select a backend. Background manifests and semantic DSP profiles select audio
programs. Render manifests record measured timing, provenance, commands,
checksums, and output identity.

The main implementation modules are:

- `scripts/ocf_tools/cli.py`: command parsing and dispatch;
- `scripts/ocf_tools/session.py`: template composition and semantic document
  binding;
- `scripts/ocf_tools/transcript.py`: timed-YAML parsing, timeline resolution,
  analysis, and subtitle export;
- `scripts/ocf_tools/locale.py`: locale resolution and provenance;
- `scripts/ocf_tools/voice.py`: recording, disabled narration, or TTS rendering;
- `scripts/ocf_tools/narration_cli.py` and `narration_sources.py`: private import,
  compatibility preflight and explicit per-event/resource/unit source selection;
- `scripts/ocf_tools/recording_audio.py`: non-destructive preparation, objective
  metrics and verified content-addressed recording receipts;
- `scripts/ocf_tools/narration_stems.py`: complete recorded stems with explicit
  all-event marker ledgers and preserved interior cadence;
- `scripts/ocf_tools/narration_first.py`: explicit resource-bound narration
  plans, pacing presets, dynamically measured segment timing, and safe local
  audition publication;
- `scripts/ocf_tools/narration_pacing.py`: Unicode sentence-unit segmentation
  and resolution of entry-specific semantic timing roles;
- `scripts/ocf_tools/semantic_dsp.py`: measured-ledger state dispatch;
- `scripts/ocf_tools/audio_build.py`: background selection, mixing, encoding,
  tags, and render manifests;
- `scripts/ocf_tools/artifact_names.py`: safe deterministic localized artifact
  filenames;
- `scripts/ocf_tools/release.py`: release artwork validation, metadata read-back,
  transcript export, manifest validation, and staged publication;
- `scripts/ocf_tools/farfield.py` and `sbagenx.py`: optional external adapters.

## Current sequence

1. Compose or load a semantic session and validate its template/schema
   references.
2. Resolve keyed narration for the requested locale. Spoken fallback is strict
   by default; an explicit draft fallback is recorded in provenance.
3. Resolve narration sources: TTS, explicitly mapped recordings, declared hybrid
   recording/TTS selection, or a complete marked recorded stem. Explicitly disabled
   narration is only for a speech-free document; it cannot suppress required speech.
4. Resolve event timing, including measured speech-end/event-end dependencies,
   and render a narration stem. Localized speech gets its own measured ledger;
   English timing is never copied into another locale.
5. Select a static background or semantic DSP profile. Semantic DSP consumes the
   measured ledger independently of TTS. A state approach may begin before the
   semantic state directive, but the semantic state event remains the arrival
   boundary and must not replay a second ramp.
6. Apply section narration gain windows and mix narration/background. Background
   paths use the configured engine or reference-master path; no unrelated preset
   or silent source-loop substitution is allowed.
7. Encode requested outputs and emit the render manifest with timing, source
   provenance, preset/engine information, tags, and artifact checksums.

## Recorded and hybrid source contracts

[Recorded narration](RECORDED_NARRATION.md) covers `narration sources`, `init`,
`import`, `preview`, `validate`, `inspect` and `preprocess`, plus explicit segment
cuts after file preparation. [Hybrid narration](HYBRID_NARRATION.md) specifies
event override → event voice → resource → stage → function → automatic/default
precedence, whole-take versus unit coverage, and explicit fallback/speaker policy.

Use `audio render FUNCTION --narration-sources FILE` in complete-session mode;
`--narration-source recording|hybrid` may override the manifest mode. `--voice` is
optional for recorded-only sessions. Ordinary per-cue `narration validate` is
source-compatibility preflight, not full audio decode. Use `narration inspect`
or queued `ocf_validate_recordings` for technical measurements. Complete marked
stems also prepare/measure audio during preflight. Preview is not successful TTS
inference, transcript fidelity or listening/release approval.

Whole-event recordings retain interior cadence without inserted sentence gaps;
unit takes use declared semantic inter-unit gaps. Whole-session stems require
markers for every composed event, including nonspoken DSP boundaries, and insert
no extra silence in the stem adapter. State anchors are never guessed from audio.
Measured source durations/markers feed the same ledger used by TTS and semantic
DSP; the complete-session renderer's ordinary mix envelope/tail remains separate.

Preparation preserves originals and defaults to format conversion without
effects. Explicit processing, finite settings, source/processed checksums,
tool versions and measurements are captured in coherent cache receipts. Source
`output_channels` selects mono/stereo narration; this never downmixes the stereo
binaural bed or applies narration filters to it. See the recorded guide for metric
proxy limits and the `verify_narration_engine2.py` prepare/verify/benchmark driver.
Its fixtures are synthetic tones, not human narration matching a transcript.

## Explicit source-neutral mix profiles

Complete-session rendering, `audio build` and `audio mix` accept an optional
`--mix-profile FILE`. Without it, the established engineering mix is preserved.
The JSON contract is `schemas/mix-profile.schema.json`: optional shared-envelope
stereo background ducking, headroom attenuation, limiter settings, explicit
final-mix fades and streamed loudness measurements. Narration preprocessing is
still separate from the bed. Ducking changes a shared amplitude envelope; it
does not downmix, crossfeed or phase-process the binaural channels.

For example, a local profile may contain:

```json
{"output_headroom_db": 3, "measure_loudness": true,
 "background_ducking": {"enabled": true, "ratio": 2}}
```

```bash
python scripts/ocf.py audio render OCF-SLP-005 --voice OCF-VOICE-0002 --mix-profile .ocf-work/my-mix.json --dry-run
```

The retained background stem and DSP preset selection remain independent of
final-mix processing. Existing ending fades are not inferred or repeated by a
mix profile; final-mix fades default to zero. Filter graphs, parameters and
requested loudness measurements are recorded in the audition report. Sample
peak limiting is not a guarantee of true-peak compliance or listening approval.

## Final release packages

`python3 scripts/ocf.py audio release <AUDIO_ID|FUNCTION_ID> --artwork
<approved-cover.png> --locale en-US --format flac --format mp3 --output
<release-root> --dry-run` previews package paths. Remove `--dry-run` to render
and publish after verification. A function ID is accepted only when exactly
one audio implementation is registered; otherwise select an audio ID. The
command accepts a PNG/JPEG supplied explicitly by the operator, or an explicitly
selected `--artwork-theme` for an original OCF candidate cover. Custom artwork
takes precedence. Generated covers record their brand/theme fingerprint and
candidate status; they never infer publication approval or use reference-corpus
artwork. See [branding](BRANDING.md) for offline generation and independent UI/
artwork themes.

Each release directory contains localized audio filenames, a UTF-8 text
transcript, `cover.png` or `cover.jpg`, and `manifest.json`. Filenames use
`<FUNCTION_ID> - <localized title> - <requested locale>` with optional voice
variant and explicit version components. Names use Unicode NFC, remove unsafe
path characters, guard Windows device names, and truncate long components.
Locale title fallback is resolved through `LocaleCatalog` and recorded in
`title_resolution`; spoken narration resolution and fallback provenance are
preserved separately in `narration_resolution`. Duplicate case-insensitive
filenames are disambiguated.

The transcript is assembled from each utterance's final `spoken_text` in the
measured render ledger, after locale resolution and voice-specific
pronunciation transformations. It is not reconstructed from source YAML or
speech recognition. Empty narration yields a UTF-8 transcript containing its
required final newline.

MP3 uses FFmpeg's ID3v2.3 metadata mapping and an attached front-cover picture;
FLAC uses Vorbis comments and a native embedded picture. Release metadata
includes localized title, album, configured narrator/artist, OCF album artist,
language, and function/release IDs, with date or additional known fields only
when configured. No personal narrator, copyright, or license attribution is
invented. The packager decodes each file with FFmpeg, reads tags with ffprobe,
extracts the cover image, and compares the extracted bytes before publication.

`schemas/audio-release.schema.json` defines manifest version 1.0. The manifest
records requested and resolved locale provenance, voice and render settings,
source narration reference, file metadata, relative filenames, byte sizes, and
SHA-256 checksums. It never contains its own checksum or machine-specific
artifact paths. `--force` is required to replace an existing release; the prior
directory is archived beside the new package. Staging is cleaned up on failure
and a failed validation never publishes a partial directory.

Reproduce with an existing audio implementation and locally available TTS and
codec tools:

```bash
python3 scripts/ocf.py voice doctor
python3 scripts/ocf.py audio release OCF-AUDIO-0001 --locale en-US \
  --format flac --format mp3 --artwork /path/to/approved-cover.png \
  --output ./releases --dry-run
python3 scripts/ocf.py audio release OCF-AUDIO-0001 --locale en-US \
  --format flac --format mp3 --artwork /path/to/approved-cover.png \
  --output ./releases
```

Packaging fixture tests use synthetic PCM and real FFmpeg codecs when FFmpeg and
ffprobe are installed; codec round-trip cases skip when those optional tools are
unavailable. They verify packaging, encoding, tags, and artwork but do not claim
successful natural-language synthesis. Function records without a registered
audio implementation cannot be released until an implementation and timed
narration are authored.

## Complete-session and narration-only auditions

Use [explicit session overrides](SESSION_OVERRIDES.md) for reviewed function
differences. `audio review-sessions` compares actual bindings and optionally
synthesizes short exact-sentence excerpts; category names never infer endings.

See [bulk sessions](BULK_SESSIONS.md) for engine-independent `audio plan`,
derived TTS eligibility, configuration locking and resumable `audio render-many`.
All current function bindings select the LOCKED shared engineering baseline;
the earlier STANDARD draft remains available explicitly for comparison.

`audio render` defaults to a complete session and requires a bound template that
declares `session_completeness: complete` and selects a semantic DSP profile.
It composes the template with the function's bound canonical narration, measures
the spoken events, renders the state program, and verifies the stereo WAV,
background activity, stage/state report, transcript, and artifact checksums.
Preview the plan, then render to a new audition directory:

```bash
python3 scripts/ocf.py audio render OCF-SLP-005 --locale en-US \
  --voice OCF-VOICE-0002 --pacing sleep --dry-run
python3 scripts/ocf.py audio render OCF-SLP-005 --locale en-US \
  --voice OCF-VOICE-0002 --pacing sleep
```

Sleep Easy uses `OCF-TPL-SESSION-HPLUS-LOCKED-001` and
`OCF-DSP-HPLUS-LOCKED-001` by default. The DSP profile selects the
Focus 10 candidate OCF-BG-0012 as the default bed from the opening. The only
DSP exception is the explicit Focus 10 → Focus 11 entry, two-pass function
programming section, and Focus 11 → Focus 10 close, using canonical newer Focus
11 preset OCF-BG-0006. Preparation narration and logical sleep/return labels do
not select different audio states: Focus 10 remains active through sleep entry,
the hold, both low-level function-body passes, return, closer, and outro. The
existing sleep-body gain remains configurable as `underlay.gain_db` in the
pacing profile (currently -24 dB). The Focus 10 bed receives a 10-second
raised-cosine ending fade; there is no delayed Focus 10 onset or ordinary-waking
silence before the closer. Logical Focus 20/ordinary-waking directives are
listed as ignored DSP directives in this selected profile; no Focus 20 DSP
state or preset is generated. Stage labels, logical state, and selected audio
background remain separate.

If a selected steady Farfield preset is shorter than the measured session, the
renderer may continue that single segment in a temporary variant without
changing its audio parameters; the duration extension is recorded in the
audition report. Other preset segment layouts are not silently retimed or
looped.

The complete-session output contains a stereo master WAV, retained background
stem, UTF-8 transcript, composed session plan, measured session timing report,
and JSON report. Profile-declared pacing excerpts and per-excerpt timing reports
are written under `pacing-auditions/`. It does not require an audio
implementation manifest or release metadata; its configured companion artwork
is generated automatically. The report marks the
draft template and function review state and never approves a release. Existing
audition directories are never overwritten.

New full-session and narration-only audition renders automatically retain a
companion `cover.png`, including WAV-only renders. They use the configured OCF
artwork surface and a visible **BETA / PRIVATE** marker rather than hiding art
when release approval is pending. New private sessions initialize an explicitly
private `audition_version: 0.1.0`; full sessions can select another deliberate
edition using `audio render --audition-version X.Y.Z`. `--artwork` and
`--artwork-theme` override full-session cover selection. These rendering
workflows require the existing optional artwork dependencies (`.[artwork]`);
development/test environments include them. They never infer a production
release version or approval. Existing completed sessions are updated through
the non-rendering export step below, preserving their original reports.
Registered `audio build` outputs likewise generate a companion cover and embed
it into FLAC/MP3 by default, using their registered audio version. An explicit
cover supplied by the release/package layer retains priority.

### Private listening exports from completed sessions

`audio export-audition` is the ordinary FLAC/MP3 listening-copy step after
`audio render` or `audio render-many`. It never runs TTS, background synthesis,
mixing or the production release workflow. Artwork defaults to the configured
artwork surface (`ocf-cosmic-dark`), with visible `vX.Y.Z` edition labeling.
Private covers also display `BETA / PRIVATE`; pending approval never suppresses
their artwork.

```bash
python scripts/ocf.py audio export-audition .ocf-work/renders/YOUR_COMPLETED_SESSION \
  --edition-version 0.1.0 --dry-run
python scripts/ocf.py audio export-audition .ocf-work/renders/YOUR_COMPLETED_SESSION \
  --edition-version 0.1.0
```

The first export must have an authoritative audio/session version: a registered
audio implementation version, explicit render `audition_version`, or deliberate
`--edition-version X.Y.Z`. There is no fallback to a narration-entry, function,
template, brand, repository or voice-model version. `0.1.0` above is an explicitly
chosen initial **private audition edition**, not a guessed production release.
The output `audition-edition.json` binds that version to the exact function,
locale, voice, master and original session-report hashes. Reuse it with
`--edition FILE`; conflicts and different source audio fail.

By default both formats are encoded directly from the completed master (MP3 at
320 kbps). For existing listening copies, pass `--flac-source FILE` and
`--mp3-source FILE`: the compressed packets are stream-copied, never transcoded
again. Their original tags (including track numbering) are retained except for
the authoritative title/album, narrator, OCF album artist, function/locale and
edition fields. Existing masters and narration/render manifests are verified
before and after export and remain unchanged. Packet and decoded-PCM hashes
verify stream-copy integrity; FLAC PCM must also match the master.

Cover precedence: `--artwork FILE`, then `--artwork-theme THEME_OR_FILE`, function
artwork preference, then configured artwork-surface default. Dark/light/custom
themes use the same supplied OCF assets and localized layout. `--no-artwork`
explicitly disables artwork and conflicts with cover/theme overrides. A custom
cover must be square, at least 320 pixels and already display the intended
edition; its text is operator-supplied rather than machine-certified.

New unique export directories stay under `.ocf-work/`; `--output DIRECTORY`
also refuses existing destinations. Outputs include `cover.png` when enabled,
FLAC native front-cover PICTURE / MP3 ID3v2.3 APIC, the edition record, artwork
provenance and verified metadata/audio hashes in `manifest.json`. Raw version
tags and manifest `version` match; `OCF_VERSION_LABEL` and manifest
`version_label` match the visible `vX.Y.Z` cover label. Candidate artwork and
private packaging do not grant listening or finished-release approval.

### Measured listener transcripts and native lyrics

Complete sessions, narration-only auditions and release packages include exact
plain TXT plus same-basename LRC/SRT/VTT and a timing receipt. They use measured
speech units where supplied, otherwise measured whole utterances; they are not
estimated word alignment. Repeated speech remains repeated. LRC uses truncated
centiseconds; SRT/VTT and MP3 synchronized lyrics use milliseconds.

Install `.[listener]` and explicitly request `--lyrics` on `audio export-audition`
or `audio release` to embed MP3 USLT/SYLT and FLAC LYRICS/UNSYNCEDLYRICS. Retained
export backfills require the original measured session report. Only staged copies
are tagged; packet and decoded-PCM checks preserve audio, existing covers and
unrelated metadata. Existing source masters and listening copies are not edited.

Tag readback and same-basename sidecars do not certify a player's lyric UI or
automatic subtitle discovery. SYLT and FLAC lyric-tag support vary by player;
select the matching SRT/VTT explicitly where supported, or read TXT/LRC in a
separate viewer. No player-specific UI compatibility or listening approval is
claimed here. See [listener and function guides](FUNCTION_GUIDES.md).

### Local OCF workspace

OCF scratch, caches, render staging, diagnostic logs, and default audition
outputs use `.ocf-work/` at the repository root. The root is gitignored and is
resolved from the repository layout, not the invoking shell's current
directory. Its standard areas are `tmp/`, `cache/`, `renders/`, and `logs/`.
Piper, Farfield, FFmpeg, and other OCF-launched subprocesses receive
`TMPDIR`, `TMP`, `TEMP`, and `XDG_CACHE_HOME` pointing into this workspace; OCF
does not change the parent process environment. Successful scratch directories
are removed by default; interrupted/failed render stages retain their context
and scratch, and subprocess failures retain captured diagnostics in `logs/`.
`OCF_KEEP_WORK=1` retains successful scratch for diagnosis. Complete and
narration-only auditions are published under the stable ignored `renders/`
area with collision-resistant run IDs; explicit output paths are never
overwritten.

Set `OCF_WORK_DIR` to select another dedicated workspace. Relative overrides
resolve from the repository root; the target must be a dedicated writable
directory. Stale scratch cleanup is scoped to marked OCF-created temporary
directories only:

```bash
python3 scripts/ocf.py workspace clean --older-than-hours 24 --dry-run
python3 scripts/ocf.py workspace clean --older-than-hours 24
```

Use `OCF_KEEP_WORK=1` to retain successful intermediates, or set
`OCF_WORK_DIR=/path/to/private-work` for a local override. Do not point the
workspace at a repository root, reference corpus, or directory containing
unrelated data.

For the narration-only workflow, which does not compose a complete session,
select it explicitly:

```bash
python3 scripts/ocf.py audio render OCF-SLP-005 --mode narration-only \
  --locale en-US --voice OCF-VOICE-0002 --pacing sleep --dry-run
```

This previews or renders the function's explicit
`function-content/bindings/<FUNCTION_ID>.yaml` narration plan and does not
require a complete-session template, audio implementation manifest, fixed
source timestamps, artwork, or release metadata. Remove `--dry-run` to render;
the default output is a unique retained audition under `.ocf-work/renders/`.

Declared [symbolic cues](SYMBOLIC_CUES.md) expand through LocaleCatalog before
paragraph/unit segmentation, pronunciation, recording text hashes or TTS cache
identity. Raw-template and resolved-text hashes remain separate; structural
conversion preserves existing approved speech and does not require new audio.

The binding lists source resource keys, their order and role, and explicit
repetition counts. The resolver uses the existing `LocaleCatalog`, requires the
function's existing `audio.script_status: approved` and reviewed/canonical
spoken resources for TTS readiness, and records function-level human review and
release readiness separately. It does not alter either approval state. Sleep
Easy's plan is opener → function body four times → closer. Its user-approved
successor consistently teaches `Plus Sleep Easy`, matching display cue
`PLUS-SLEEP EASY`. The former `Plus Quiet Sleep` wording remains historical
evidence, not an active compatibility lesson. The scoped
[migration record](../function-content/editorial/approved-title-cues-001.json)
preserves the old/new text fingerprints; breathing, repetitions and engineering
defaults are unchanged. New audition speech has not received listening approval.

Pacing presets are configuration only: NORMAL uses 0.8 s paragraph/2 s section
pauses, RELAXED uses 1.5 s/4 s, and SLEEP uses 2 s/6 s; SLEEP includes 2 s
leading and 6 s ending silence. Piper length scale is multiplied by 1.08 for
SLEEP and a fixed -3 dB TTS headroom gain is applied before assembly. These
documented defaults are engineering settings, not therapeutic claims. The
timeline chains each event to the preceding measured speech end plus its
configured pause. Duration derives from actual synthesized segment durations;
there is no target-duration stretch or arbitrary fixed anchor.

### Semantic narration pacing

The rushed delivery came from the unit boundary: each keyed locale entry was
synthesized as one TTS utterance, while the configured pause was scheduled only
after that whole event. Newlines inside a locale entry were not audio pauses;
Piper's small built-in sentence padding and the session's 1.08 sleep length
scale did not provide the intended instruction-level timing.

The H-Plus session pacing profile (`audio/templates/pacing/`) selects a named
narration pacing profile per stable resource key. Each resolved locale entry may
declare `timing.pacing_units`, one semantic role per sentence unit (for example
`count`, `instruction`, `phrase`, or `landing`). The sentence splitter uses
Unicode sentence-ending punctuation and blank paragraphs; it does not infer
English count words. A translation can declare its own unit roles when its
sentence boundaries differ. Dry-run fails if the locale's role list does not
match its resolved sentence units; count-sensitive profiles can also require
locale-specific unit roles rather than guessing count words from English.

Each selected unit is synthesized separately. OCF inserts real PCM silence
between units, fades each unit edge over 8 ms to avoid clicks, and records the
unit text, actual start/end, configured following pause, selected profile, and
rate scale. This backend-neutral path does not require SSML: Piper receives an
adjusted `length_scale` and zero built-in sentence padding so OCF owns the gap;
espeak/espeak-ng receive an adjusted WPM where available. Other backends still
receive the sentence units and real silence, and report when no rate control is
available. The current Piper and eSpeak adapters do not expose an OCF SSML
input path. No visible punctuation or markup is added to approved narration.

Tune named profiles under `narration_pacing.profiles` in the versioned session
pacing YAML; map resource keys to profiles under `narration_pacing.entries`.
Tune locale-specific sentence roles only in that locale resource's
`timing.pacing_units`. Sentence and paragraph pauses are profile values; count
and landing roles let the entry express its meaning without English-string
rules. The current H-Plus relaxation profile uses 3.5 s between guided
instructions, 6 s after each numbered stage, 1.25 s within “Relax. Let go.
Sleep.”, and a 5 s landing after “Sleep.” where the event continues. The
10-to-20 counter uses 5 s between every number; the waking counter uses 3 s
between counts, 4 s after “One.”, and a measured Piper rate scale that eases
from 0.90 to 0.97 for a gradually more alert cadence.

`audio render --dry-run` lists each resolved sentence unit, semantic role,
pause, and rate scale before TTS. Rendering inserts the pauses into the audio
track, so following speech-end anchors move naturally; it never compresses a
fixed stage to make room. Existing `maximum_duration` and fixed-anchor overlap
checks fail rather than silently shorten narration. Complete auditions include
`session-timing-report.json` plus configured short pacing WAVs and per-excerpt
JSON reports under `pacing-auditions/`. Use the complete-session `--dry-run`
first, then render the full session to obtain comparable excerpts.

The narration-only audition directory contains a WAV, UTF-8 transcript,
`tts-plan.json`, and `render-manifest.json`. The manifest records
function/script review state,
resource and locale provenance, voice profile/options, pacing values, segment
durations, duration/sample/channel measurements, peak/RMS/clipping, artifact
hashes, and release readiness. Existing audition directories are never
overwritten. The renderer verifies expected segment count and text, dynamic
non-overlap, WAV decoding/format, duration, silence boundaries, and clipping
before publication.

Sleep Easy's committed function record has `audio.script_status: approved` and
the selected narration resources are reviewed, so a local TTS audition is
permitted. Its function-content `human_review` remains `required`, and the
resources mark finished-session release as pending. The narration-first
workflow reports TTS readiness separately and does not make Sleep Easy
release-ready. A production package still requires the applicable human review,
release clearance, registered audio implementation, and explicitly approved
artwork.

Preparation stages such as optional affirmation and oHm/resonant tuning remain
specified but not shipped. Focus-state auditory cue sound design also remains
TBD. Do not insert those stages into the live pipeline because a design document
mentions them.

## Precedence and invariants

### Background and preset selection

- A missing preset means no background unless the selected workflow requires
  one.
- A manifest is found by ID/name before engine dispatch.
- Manifest engine selection wins when the CLI engine is the default auto value;
  an explicit non-default CLI engine overrides it.
- A literal existing preset path is accepted first.
- A Farfield preset name/stem is then searched in this order: directories in
  `OCF_FARFIELD_PRESETS_DIR`, committed
  `audio/background/presets/farfield/`, committed
  `audio/background/presets/`, then a discovered Farfield source checkout.
- `preset.file` is a committed repository path under
  `audio/background/presets/`; `presets/` is only upstream-contribution
  staging. SBaGenX sequences retain `-R 10`.

These rules are implemented in `audio_build.py` and `farfield.py`, with
regression coverage in `tests/test_audio_build.py` and
`tests/test_locale_render.py`.

### Sequencing

- Semantic state identity comes from structured events, never English text,
  filenames, frequencies, or subtitle `cue_id`.
- Measured anchors are authoritative for narration-dependent timing.
- A state directive must not be moved merely to make DSP audible; use an
  explicit approach when support-before-arrival is intended.
- Return/reorientation and ordinary waking remain separate semantic operations.
- Narration, DSP, cues, and TTS remain replaceable layers.
- TTS output is not byte-reproducible. A checksum identifies an artifact, not a
  recipe that will reproduce identical bytes.

See `docs/SEMANTIC_DSP.md`, `docs/SEMANTIC_SESSIONS.md`, and
`docs/AUDIO_STANDARD.md` for contracts and schemas.
