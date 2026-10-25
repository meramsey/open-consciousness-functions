# User Guide

Get things done with OCF tooling.

## Current checkpoint

The catalog contains 58 functions, preserves 55 historical mappings, and has
102 structured command records, 58 generated en-US session plans and all 177
protected narration entries.
Historical source availability remains 39 available / 16 unavailable; it is not
modern TTS eligibility or release approval. Canonical `PLUS-THINK`, `PLUS-FOCUS`
and `PLUS-SEE BETTER` remain unchanged. Source wording, review status and measured
timing are separate contracts; see [source-first authoring](SOURCE_FIRST_AUTHORING.md).

The supplied Cosmic Path brand kit 0.3.0 remains a human-review candidate with
an offline comparison gallery and pinned import provenance, not an automatically
approved identity. See [branding](BRANDING.md). Engineering locks, RC1/V2/V2.1
auditions and frozen editorial/listening decisions retain their existing status.

## Entry points

For listener-facing instructions, use the
[function guide workflow](FUNCTION_GUIDES.md). Guides show current display/spoken
cues, ordered documented activation steps, secondary controls, and declared
persistence/mode/reset behavior. Optional related practices are approved
directional suggestions, never required sequences or evidence of combined effects.
Food More/Food Less belong to Nutricia; Appetite Choice uses Plus Satisfied.
The Focus function is distinct from Focus 10/11 audio stages.

Inside a private listener package, open `guides/index.html` (or its PDF/Markdown
counterpart) to find the included guides, audio, transcripts and edition manifest.
Related guides may be included without their recordings. Keep older package
variants intact when documentation changes; new guide bytes require a new output
directory/receipt, not an overwritten audition edition.
Some readers restrict local-file launching. If a link cannot open an audio file,
use the file manager and keep its matching transcript/lyrics sidecars together;
working relative links do not establish native player or PDF-reader UI support.

Use Python 3.11 or newer in the environment where OCF is installed. See the
[README installation steps](../README.md#get-started) for platform-specific activation.
The [interface example library](../examples/README.md) inventories every shipped
CLI leaf, MCP tool/resource/prompt, schema and OCF LSP method, distinguishing
executed read-only workflows from parser-only and operator-dependent examples.

```bash
./scripts/ocf
python3 scripts/ocf.py
ocf                      # if installed: pip install .
```

## Everyday commands

For current complete-session workflows, see [bulk sessions](BULK_SESSIONS.md):
`audio eligibility`, `audio plan`, `audio defaults`, `audio render-many` and
`new session-plan`. The [documentation map](README.md) is the shortest route to
focused guides. Optional [local MCP](MCP.md) and `ocf dev` expose compact
discovery and persistent jobs while delegating to these same APIs.

For machine/agent discovery, start with `ocf capabilities --json`,
`ocf functions list --json`, and `ocf functions describe OCF-FND-002 --json`.
These expose live commands and canonical metadata, not inferred semantic identities.
`ocf corpus inventory` fingerprints citation-only research with explicit evidence
classes. Measured speech can drive independent DSP with
[`ocf audio render-state-program`](SEMANTIC_DSP.md).
The three [function pilots](research/PILOT_FUNCTIONAL_SPECIFICATIONS.md) are
draft rehearsals, not approved production installations.

Phase2B workflows: [`functions ... --rich --json`](FUNCTION_CONTENT.md),
[`plan FILE --json`](AUTHORING_PLANS.md),
[`doctor --json --workflow ...`](DOCTOR.md),
[`native setup`](SETUP.md), [`wheel data`](INSTALLED_DATA.md),
[`optional containers`](CONTAINERS.md), and
[`community voice metadata`](COMMUNITY_VOICES.md). These deterministic interfaces
support agents/GUI clients while keeping reasoning and editorial approval external.

Use [`--recordings package.yaml`](USER_NARRATION.md) on voice rendering or audio
build for user-provided narration without TTS. Timings come from the recordings;
missing files or mismatched locales fail before output.
For current complete sessions, use
[`--narration-sources FILE`](RECORDED_NARRATION.md) for recorded-only or
[explicit hybrid](HYBRID_NARRATION.md) narration instead.

| Command                                  | Purpose                                   |
| ---------------------------------------- | ----------------------------------------- |
| `ocf help`                               | command reference                         |
| `ocf doctor`                             | environment health                        |
| `ocf validate`                           | validate all records + rules              |
| `ocf validate --all`                     | same, full report                         |
| `ocf validate path/to/function.yaml`     | validate one file                         |
| `ocf build-index`                        | regenerate all derived files              |
| `ocf build-index --check`                | fail if derived files are stale           |
| `ocf review commands`                    | regenerate the command review report      |
| `ocf edit function attention`            | edit a record in `$EDITOR`                |

## Wizards

```bash
ocf new function       # function record
ocf new proposal       # marked-down proposal
ocf new audio          # audio-implementation manifest
ocf new background     # background preset manifest
ocf new test-report    # anecdotal report
ocf new voice          # private model/profile import
ocf new voice-dataset .ocf-work/voice-dataset/dataset.json  # external recording imports
ocf import source      # fingerprint / optionally copy a source file
```

The general authoring wizards support `?` (help), `skip`, `back`, and `quit`, show
a final review screen, write atomically, and validate what they wrote. The
import-first voice-dataset wizard instead uses blank paths to skip slots and
`:quit` to finish while retaining earlier imports; it never opens a microphone.

## Audio

```bash
ocf audio check-engine
ocf audio list-background
ocf audio describe-background OCF-BG-0001
ocf audio render-background OCF-BG-0001 --output .ocf-work/examples/out.wav
ocf audio render-background OCF-BG-0002 --engine sbagenx --output .ocf-work/examples/bed.wav
ocf audio render-background OCF-BG-0004 --engine reference-master --output .ocf-work/examples/reference-bed.wav
```

Background engines are optional and degrade gracefully. Supported engines:
Farfield (synthesis, default), SBaGenX (synthesis), and `reference-master`
(even-timbre beds assembled from operator-supplied reference files
`F10 V4 Volume Adjusted.flac` / `F11 V4.flac`, which stay local and
citation-only). A preset's manifest `engine` is used automatically when no
`--engine` flag is given; when an engine is missing you get install guidance,
not a traceback. `reference-master` needs ffmpeg.

## Recorded and hybrid complete sessions

First inspect exact composed event/resource IDs, then initialize and import your
local recordings using [recorded narration](RECORDED_NARRATION.md):

```bash
python scripts/ocf.py narration sources OCF-SLP-005 --locale en-US
python scripts/ocf.py narration init OCF-SLP-005 \
  --output .ocf-work/my-narration/sources.json --mode recording --fallback error
python scripts/ocf.py narration import OCF-SLP-005 \
  --sources .ocf-work/my-narration/sources.json --file recordings/opener.wav \
  --id opener-v1 --event function-opener.block --speaker my-speaker
```

Use actual file paths and declared speakers. Import each required spoken take
before preview/render; the single example above is not complete coverage.

```bash
python scripts/ocf.py narration preview OCF-SLP-005 \
  --sources .ocf-work/my-narration/sources.json
python scripts/ocf.py narration validate OCF-SLP-005 \
  --sources .ocf-work/my-narration/sources.json
python scripts/ocf.py narration inspect recordings/opener.wav
python scripts/ocf.py narration preprocess recordings/opener.wav \
  --rate 44100 --channels 2 --output .ocf-work/opener-prepared.wav
python scripts/ocf.py audio render OCF-SLP-005 \
  --narration-sources .ocf-work/my-narration/sources.json \
  --narration-source recording --dry-run
```

Remove `--dry-run` for an explicit render. The manifest supplies the source mode;
`--narration-source recording|hybrid` is optional. Recorded-only needs no TTS voice
and never falls back. Hybrid requires a declared fallback policy and a compatible
installed voice for selected TTS; `--voice PROFILE` can supply its default.
Ordinary CLI `narration validate` checks source compatibility, not full technical
audio decode; use `inspect` or queued recording validation for that. Text hashes
do not verify words spoken or grant listening approval.

Import supports `--resource`, 1-based `--unit`, or paired `--start`/`--end` cuts
after whole-file preparation. There is no automatic speech alignment. A complete
`session_stem` must manually mark **every composed event**, including nonspoken
DSP boundaries; OCF never guesses them or inserts extra semantic silence inside
the stem. Default processing preserves originals without aggressive effects;
mono/stereo narration output never changes the independent stereo binaural bed.
The [recorded guide](RECORDED_NARRATION.md) explains reports, cache hashes/tool
versions, metric proxy limits and the synthetic-tone prepare/verify/benchmark
driver. Tones are not human narration and do not match the declared transcript.

## Private voice profiles and datasets

```bash
python scripts/ocf.py voice capabilities --json
python scripts/ocf.py voice export-profile OCF-VOICE-9001 --output .ocf-work/portable-voice.json
python scripts/ocf.py voice import-profile .ocf-work/portable-voice.json --id OCF-VOICE-9002
python scripts/ocf.py voice dataset-init .ocf-work/voice-dataset --id my-voice --rate 22050
python scripts/ocf.py voice dataset-guide .ocf-work/voice-dataset/dataset.json --json
python scripts/ocf.py new voice-dataset .ocf-work/voice-dataset/dataset.json
```

Export assumes an existing private profile and unused destinations. Metadata-only
is the default; `--include-assets` on both export/import deliberately copies a
private asset bundle. Profile metadata does not grant redistribution rights or
verify inference. The local `OCF-VOICE-9001` Lessac example is an ordinary imported
Piper model, not cloning. The dataset wizard imports externally recorded exact
prompt WAVs and preserves originals/splits. See [voice workflows](VOICE_WORKFLOWS.md),
[capability/portability boundaries](VOICE_CLONING.md) and
[training preparation](VOICE_TRAINING.md). F5/Torch are absent in the observed
environment; OCF cloning/training remains unsupported until verified. Local GPU
memory observations do not establish future training readiness.

## Transcript & audio pipeline

The **transcript group is shipped**:

```bash
# Timed transcripts (LRC/SRT/VTT/txt/md → OCF timed YAML)
ocf transcript import FILE [--format auto|lrc|srt|vtt|txt|md|yaml] [--output] [--title] [--force]
ocf transcript segment FILE [--apply] [--output]
ocf transcript analyze FILE [--interactive]
ocf transcript review FILE [--state-profile NAME] [--write] [--output]
ocf transcript export FILE.yaml --format srt|vtt|lrc [--output] [--force]
ocf transcript extract-template FILE --timing-only [--output] [--force]
```

The **voice/TTS and audio build groups are shipped** (v0.4). Backends are
optional external binaries (espeak-ng/espeak/piper) detected on PATH; without
one the toolchain degrades gracefully with install guidance. The
**preparation group remains specified but not yet shipped** (see `ROADMAP.md`
and `OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md`). They
are listed here because the workflow for adding a function from timed lyrics
relies on them; full walkthrough:
[`docs/TIMED_TRANSCRIPTS.md`](TIMED_TRANSCRIPTS.md).

```bash
# Voices / TTS
ocf voice list-backends
ocf voice doctor
ocf voice list
ocf voice render SCRIPT [--voice PROFILE] [--output WAV] [--fit] [--flow] [--even-counts] [--force]

# Full audio build
ocf audio render-speech SCRIPT [--voice PROFILE] [--output WAV] [--force]
ocf audio mix --speech narration.wav [--background background.wav] --output final.wav [--background-gain 0.25]
ocf audio build OCF-AUDIO-0001 [--format wav|flac|mp3]... [--tag KEY=VALUE]... [--voice PROFILE] [--output DIR]
                [--fit] [--flow] [--even-counts] [--background-gain 0.25] [--force]
ocf audio inspect FILE

# Session composition templates (declared slots → full timed script)
ocf session list-templates
ocf session compose --slot NAME=FILE ... [--template ID|LOCAL] [--title TITLE] [--id SLUG] [--output YAML] [--force]

# Preparation module (specified — not yet shipped)
ocf new preparation
ocf preparation import-reference FILE
ocf preparation edit|validate|build OCF-PREP-0001
```

The preparation design (composable stages, optional affirmation, optional
oHm/resonant-tuning chant) is in
[`docs/PREPARATION_MODULE.md`](PREPARATION_MODULE.md) and is deliberately not
presented as usable commands yet.

Localization *is* shipped:

```bash
ocf locale list                       # installed packs and their provenance
ocf locale validate                   # contracts, coverage, stale versions
ocf locale resolve --file DOC --locale es   # resolve narration keys
ocf voice render DOC --locale es       # language-aware render
ocf transcript export DOC --format srt --locale es
```

Spoken narration fails loudly when a translation is missing rather than
dropping English into a translated session; `--allow-fallback` is the explicit
override. See [`docs/LOCALIZATION.md`](LOCALIZATION.md) and
[`locales/README.md`](../locales/README.md).

Narration pacing flags on `ocf voice render` / `ocf audio build`:

- `--fit` — adaptive per-cue pacing (`timing_mode fit-soft`): trim TTS trailing
  pads, stretch short flow slots up to a cap, preserve deliberate pauses.
- `--flow` — flow-merge consecutive whisper sentence fragments into single
  utterances (`timing_mode natural`).
- `--even-counts` — re-time pure-count runs onto even grids anchored by each
  run's first/last count (`timing_mode …+even-counts`). Runs of bare counts
  (e.g. the attention exercise count ups and downs) gain even spacing; counts
  embedded inside full phrase lines keep their authored times. The transcript
  wording is never rewritten.

Build outputs and tags: `ocf audio build` writes the WAV master **and** FLAC +
MP3 derivatives by default (`--format` is repeatable). FLAC/MP3 files are
tagged with metadata derived from the manifests (title, artist, album, track,
comment, and `OCF_*` tags including the session template id when the script
was composed via `ocf session compose`); override any tag with repeated
`--tag KEY=VALUE`. The `OCF-RENDER-*` manifest records every output file,
encoder, checksum, and the tag set used. WAV is never tagged (plain PCM).

Session composition (`ocf session compose`): each template declares the slot
names it needs in `slots.required` / `slots.optional`, and the composer accepts
**only** slots the template declares. The default `OCF-TPL-SESSION-LEARN-001`
shell (original OCF placeholder wording) requires four function-specific
pieces: the **opener**, the **focus-11 function material** (`--focus11`: the
function intro / installation / cue rehearsal spoken while in the focus-11
state), the **sleep-20 function reinforcement** (`--sleep20`: function wording
spoken while in the twentieth/sleep state), and the **closer**. The template
provides the bridge: opening the access channel, closing access,
consolidation, the count to the twentieth state, the sleep hold, and the count
back. Slot files are one spoken line per line; a `[MM:SS.xx]` prefix is
honoured as an absolute track time, otherwise lines are paced every
`--line-seconds N` seconds (default 3). A section may declare `repeat` to run
its slot wording once per band across the section window, and `from_slot` to
reuse another slot's wording without declaring it (the Attention template's
`sleep20` reuses `focus11` this way). The composed YAML records `template`
provenance plus the exact slot wording (`slots`) and passes schema validation.
A citation-only, reference-derived shell can be used locally via
`--template /path/to/file.yaml` and is never committed.

A second committed template, `OCF-TPL-SESSION-ATTENTION-001`, is a working
reference: it adapts the Attention (PLUS-FOCUS) legacy arc — wording and
timing recovered from the citation-only Monroe H-PLUS transcript, with OCF
function terminology — and needs only the function material:

```bash
ocf session compose --template OCF-TPL-SESSION-ATTENTION-001 \
    --focus11 audio/slots/attention/focus11.txt \
    --title "Attention (PLUS-FOCUS) — adapted legacy-arc session" \
    --id OCF-SCRIPT-ATTENTION-001 --output audio/scripts/attention-ocf.yaml --force
```

Its single required slot, `audio/slots/attention/focus11.txt`, supplies the
five-line PLUS-FOCUS instruction; all boilerplate (opening, access channel,
close, induction, count, return, closer) is authored in the template from the
converted legacy wording. A section can declare `gain_db` to sit far below the
rest of the narration — the template's `sleep20` section uses `-24` and
repeats the focus-11 wording across the twentieth-state hold, so the
reinforcement is a faint underlay rather than a silent hold. `ocf audio build`
applies the window and records it as `narration_gain_windows` in the render
manifest.

## Finding things

| What                       | Where                          |
| -------------------------- | ------------------------------ |
| All functions              | `FUNCTION_INDEX.md`            |
| Machine-readable index     | `function-index.json/.csv`     |
| Legacy↔OCF commands        | `legacy/hplus-command-map.*`   |
| Availability 39/16         | `docs/AVAILABILITY_MATRIX.md`  |
| Reimplementation roadmap   | `docs/REIMPLEMENTATION_ROADMAP.md` |
| Command review             | `docs/COMMAND_REVIEW.md`       |
| Safety                     | `docs/SAFETY_MATRIX.md`        |
| Audio implementations      | `docs/AUDIO_IMPLEMENTATION_INDEX.md` |
| Background presets         | `docs/BACKGROUND_AUDIO_INDEX.md` |

## Troubleshooting

- **`jsonschema` not found** → `pip install PyYAML jsonschema`
- **`farfield` not available** → it's optional; everything else still works,
  and `ocf audio check-engine` prints install guidance.
- **Stale indexes** → `ocf build-index` (CI blocks stale merges).
- **Wizard wrote a bad file** → `ocf edit function <slug>` or delete and
  re-run; validation reports errors immediately.

## After any contribution

```bash
python3 scripts/ocf.py validate --all
python3 scripts/ocf.py build-index
python3 -m pytest
```
