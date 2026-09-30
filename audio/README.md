# Audio

Tooling and records for audio implementations of OCF functions.

## Layout

| Path                 | Purpose                                              |
| -------------------- | ---------------------------------------------------- |
| `scripts/`           | Canonical **OCF timed YAML** transcript/script files (`<slug>.yaml`) |
| `implementations/`   | Rendered audio files (optional, contributed)         |
| `manifests/`         | `OCF-AUDIO-*` implementation manifests (YAML)        |
| `templates/`         | Reusable section templates (preparation, installation, rehearsal, …) |
| `states/profiles/`   | State/focus profiles for state-aware backgrounds (planned) |
| `voices/profiles/`   | `OCF-VOICE-*` voice profiles (`voice-profile.schema.json`) |
| `rendered/`          | Masters + `OCF-RENDER-*` manifests from `ocf audio build` |
| `background/`        | Background presets (see `background/README.md`)      |
| `tools/`             | Helper scripts                                       |
| `testing-reports/`   | Results from `ocf new test-report`                   |

## Model

A **function** is not the same thing as its **audio recording**:

- a function capability is defined in `functions/`;
- an audio implementation (`manifest`) is one concrete recording of a script
  for that function;
- a function may have **several** audio implementations;
- a background preset is independent of both (see `BACKGROUND_AUDIO.md`).

## Registering audio

```bash
./scripts/ocf new audio        # wizard writes audio/manifests/OCF-AUDIO-*.yaml
./scripts/ocf validate --all
./scripts/ocf build-index
```

Audio types allowed: `training`, `reinforcement`, `quick`, `sleep`,
`extended`, `voice-only`, `background-only`, `experimental`. No single style
is required.

## Timed transcripts and scripts

Scripts live here as **OCF timed YAML** (`audio/scripts/<slug>.yaml`), the
canonical editable timed format. Timed lyrics (`.lrc`) and `.srt`/`.vtt`/
`.txt`/`.md` are **import sources**:

```bash
./scripts/ocf transcript import sample.lrc --output audio/scripts/sample.yaml
./scripts/ocf transcript segment audio/scripts/sample.yaml --apply
./scripts/ocf transcript analyze audio/scripts/sample.yaml
./scripts/ocf transcript review audio/scripts/sample.yaml
./scripts/ocf transcript export audio/scripts/sample.yaml --format vtt
```

Wording is never rewritten automatically: imports keep the source text
verbatim in `source.snapshot`. The full walkthrough and a supported-status
matrix are in [`docs/TIMED_TRANSCRIPTS.md`](../docs/TIMED_TRANSCRIPTS.md).
Local generation from a lawfully held file is permitted; only committing the
transcript wording to this repo is restricted.

## Rendering narration and masters

```bash
./scripts/ocf voice list-backends          # espeak-ng / espeak / piper
./scripts/ocf voice doctor
./scripts/ocf voice render audio/scripts/<slug>.yaml \
    --voice espeak-en --output audio/rendered/<slug>-narration.wav
./scripts/ocf audio build OCF-AUDIO-0001 [--format wav|flac|mp3]
./scripts/ocf audio inspect audio/rendered/OCF-AUDIO-0001-master.wav
```

TTS backends and FLAC/MP3 encoders (ffmpeg/flac) are optional; when missing,
the toolchain degrades gracefully with install guidance.

## Licensing

Community-authored audio carries its own license recorded in its manifest.
Never upload or redistribute Monroe training audio or other third-party
copyrighted audio; reference files are citation-only by default.