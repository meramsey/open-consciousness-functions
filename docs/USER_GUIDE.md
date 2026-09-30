# User Guide

Get things done with OCF tooling.

## Entry points

```bash
./scripts/ocf
python3 scripts/ocf.py
ocf                      # if installed: pip install .
```

## Everyday commands

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
ocf import source      # fingerprint / optionally copy a source file
```

Every wizard supports `?` (help), `skip`, `back`, and `quit`, shows a final
review screen, writes atomically, and validates what it wrote.

## Audio

```bash
ocf audio check-engine
ocf audio list-background
ocf audio describe-background OCF-BG-0001
ocf audio render-background OCF-BG-0001 --output out.wav
ocf audio render-background OCF-BG-0002 --engine sbagenx --output bed.wav
ocf audio render-background OCF-BG-0004 --engine reference-master --output bed.wav
```

Background engines are optional and degrade gracefully. Supported engines:
Farfield (synthesis, default), SBaGenX (synthesis), and `reference-master`
(even-timbre beds assembled from operator-supplied reference files
`F10 V4 Volume Adjusted.flac` / `F11 V4.flac`, which stay local and
citation-only). A preset's manifest `engine` is used automatically when no
`--engine` flag is given; when an engine is missing you get install guidance,
not a traceback. `reference-master` needs ffmpeg.

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
[`docs/PREPARATION_MODULE.md`](PREPARATION_MODULE.md); planned localization of
the whole pipeline is in [`docs/LOCALIZATION.md`](LOCALIZATION.md). Both are
forward-looking design (v0.5) and are deliberately not presented as usable
commands yet.

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