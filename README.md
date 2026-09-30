# Open Consciousness Functions (OCF)

An **open specification plus reference implementation framework** for
defining, reviewing, documenting, validating, and eventually producing
community-authored consciousness-function training exercises.

> **Independence notice.** OCF is an independent, community-maintained project
> inspired by the general idea of trainable "functions" used in Monroe
> Institute Human Plus material. It is **not affiliated with, endorsed by, or
> owned by** The Monroe Institute, Hemi-Sync, Interstate Industries, or any
> related entity.

## What OCF is

- An open, machine-readable **function specification** (canonical YAML + JSON
  Schema).
- A **legacy compatibility map** of 55 documented historical functions, kept
  as factual research/compatibility metadata.
- A **reimplementation program** — all 55 functions are OCF reimplementation
  targets, including the 16 whose legacy training source material is currently
  unavailable.
- **Interactive contributor tools** for non-programmers (wizards, validation,
  generated documentation).
- A **proposal/review workflow** (RFC/PEP style).
- An **audio implementation model** with optional generated background audio
  via the [Farfield](https://github.com/txus/farfield) and
  [SBaGenX](https://github.com/lm7137/SBaGenX) engines, or even-timbre beds
  composed from operator-supplied **reference masters** (`reference-master`
  engine, e.g. `F10`/`F11` bed + access excerpt).
- A **timed-transcript authoring pipeline** — timed lyrics (`.lrc`), SRT,
  WebVTT, text, and Markdown become canonical **OCF timed YAML** scripts
  (`ocf transcript import`); from there, sections/states, analysis, and
  buildable spoken audio — see `docs/TIMED_TRANSCRIPTS.md`.

## What OCF is not

- Not affiliated with The Monroe Institute, Hemi-Sync, or related entities.
- Not a medical, psychological, or therapeutic product.
- Not a guarantee of any psychological, physiological, medical, paranormal, or
  behavioral result.
- Not a replacement for emergency services, first aid, poison control, or
  professional treatment.
- Not a distributor of Monroe training audio.

## Maturity

**Early bootstrap.** The schema, CLI, validation, generated indexes, and all
55 legacy mappings are in place. Function records start at
`specification-only`; community scripts, audio implementations, and reviews
are welcome through the proposal workflow.

The **timed-transcript / audio toolchain** has two parts. The **transcript
pipeline** (`.lrc`/`.srt`/`.vtt`/`.txt`/`.md` → OCF timed YAML, sections,
state/focus levels, analysis, export, timing-only templates) is **shipped** as
`ocf transcript …`. The **voice/TTS and mixing/mastering** chain (`ocf voice
…` and `ocf audio build …`) is also **shipped**: optional TTS backends
(espeak-ng/espeak/piper) render narration per cue, mixing is pure stdlib PCM
(Farfield/SBaGenX beds) or ffmpeg `amix` (reference-master beds), and
FLAC/MP3 encode via ffmpeg/flac when available — otherwise everything
degrades gracefully with install guidance. Only the **preparation** module
(`ocf preparation …`) remains specified (v0.4+, not yet shipped).
`docs/TIMED_TRANSCRIPTS.md` marks each capability as *implemented*, *specified*,
or *planned*. Planned v0.5 work — localization/locale packs, composable
preparation stages (optional affirmation, oHm/resonant-tuning), and
focus-state auditory cue events — is designed (not shipped) in
`docs/PREPARATION_MODULE.md`, `docs/LOCALIZATION.md`, and `ROADMAP.md`.

## Quick start

```bash
# Requirements: Python 3.11+
pip install PyYAML jsonschema pytest ruff     # or: pip install -r requirements-dev.txt

python3 scripts/ocf.py doctor                  # environment health
python3 scripts/ocf.py validate --all         # validate every record
python3 -m pytest                             # run the test suite
```

## Contributor wizard

```bash
./scripts/ocf new function      # guided function record
./scripts/ocf new proposal      # guided proposal
./scripts/ocf new audio         # register an audio implementation
./scripts/ocf new background    # register a background preset
```

See `CONTRIBUTING.md` for the easy path, and `docs/USER_GUIDE.md` for the
full command reference.

## Adding a function from timed lyrics

A *timed-lyrics* file (LRC) is a lyric-style timed transcript whose lines are
timestamped, e.g. `[00:03:30.00]Let the body settle and relax.`. Many existing
timed meditation reads exist this way. OCF's transcript pipeline turns such a
file into a canonical script (live today) and, onward, into a function record
and a built audio implementation:

```text
timed lyrics (.lrc)  or  .srt / .vtt / .txt / .md / OCF timed YAML
        │  ocf transcript import FILE          (live)
        ▼
OCF timed YAML  (canonical editable script under audio/scripts/)
        │  ocf transcript segment/analyze/review FILE   (live)
        ▼
function record  (functions/<domain>/<slug>.yaml)
        │  ocf new audio  (implementation manifest)
        ▼
voice (TTS backend: espeak-ng · espeak · piper)     (live; profiles in audio/voices/)
        +  background (Farfield · SBaGenX · reference-master, optionally state-aware)
        │  ocf voice render / ocf audio build       (live)
        ▼
lossless master (WAV/FLAC) + render manifest + checksums
```

The step-by-step walkthrough — including sample LRC input, canonical OCF timed
YAML output, authoring modes, timing rules, and a `supported / specified`
status matrix — lives in **[`docs/TIMED_TRANSCRIPTS.md`](docs/TIMED_TRANSCRIPTS.md)**.
The normative specification is
`OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md`
(sections 32, 44–50).

## Example function record

`functions/foundation/attention.yaml` (abridged):

```yaml
id: "OCF-FND-002"
slug: "attention"
canonical:
  name: "Attention"
  command:
    primary: "PLUS-FOCUS"
legacy:
  source_system: "Monroe H-PLUS"
  name: "ATTENTION"
  commands: ["PLUS-FOCUS"]
  command_status: "unchanged"
  source_availability: "available"
ocf:
  reimplementation_status: "planned"
  command_review: "approved"
```

## Command philosophy

- **Preserve good commands.** `THINK FAST` is and stays `PLUS-THINK`;
  `ATTENTION` stays `PLUS-FOCUS`. No artificial uniformity.
- **Keep commands short.** One word after `PLUS` preferred, two acceptable,
  three exceptional. No filler (`NOW`, `SYSTEM`, `ACTIVATE`).
- **MORE/LESS, not UP/DOWN.** Adjustable magnitudes use
  `PLUS-SEE MORE` / `PLUS-SEE LESS`.
- Every changed command retains its legacy command as metadata/alias with a
  documented rationale.

See `docs/COMMAND_GRAMMAR.md`, `docs/NAMING_GUIDELINES.md`, and the generated
`docs/COMMAND_REVIEW.md`.

## The 55 legacy functions

All 55 documented functions are first-class OCF records:

| Source material          | Count | Status                          |
| ------------------------ | ----- | ------------------------------- |
| Available                | 39    | Legacy-mapped, reimplementation planned |
| Unavailable (documented) | 16    | Legacy-mapped, reimplementation planned |

The 16 source-unavailable legacy functions are **OCF reimplementation
targets**, eligible for original scripts, community proposals, review, and
future audio — never presented as reconstructed original Monroe audio.

- `FUNCTION_INDEX.md` / `function-index.json` / `function-index.csv`
- `legacy/hplus-command-map.json` / `.csv`
- `docs/AVAILABILITY_MATRIX.md` and `docs/REIMPLEMENTATION_ROADMAP.md`

## Audio architecture

Audio is modeled independently from functions. A spoken session is produced
by layered, independent artifacts:

```text
function capability
        │
        ▼
timed transcript (OCF timed YAML / audio/scripts/)
        │
        ├─────────────► spoken narration stem  (TTS backend per cue)
        └─────────────► background stem       (Farfield · SBaGenX · reference-master)
                            │
                            ▼ (mixer — pure stdlib PCM)
       mastered output (WAV/FLAC) + render manifest + checksums
```

A function is never tied to a single recording: one function may have several
audio implementations, several transcripts, and several background presets.
See `docs/AUDIO_STANDARD.md`, `docs/BACKGROUND_AUDIO.md`, and
`docs/TIMED_TRANSCRIPTS.md`.

## Transcript & audio pipeline — what is supported

| Artifact              | Formats / engines                                   | Status         |
| --------------------- | --------------------------------------------------- | -------------- |
| Function records      | canonical YAML (`schemas/function.schema.json`)     | implemented    |
| Proposals             | Markdown + YAML front matter                        | implemented    |
| Audio implementations | YAML manifests (`OCF-AUDIO-*`)                      | implemented    |
| Background presets    | YAML manifests (`OCF-BG-*`), engines: Farfield · SBaGenX · reference-master | implemented    |
| Timed transcripts     | import LRC/SRT/VTT/txt/md → **OCF timed YAML** (`audio/scripts/`) | implemented    |
| Sections / states     | role sections, state profiles, analysis, export, timing templates | implemented    |
| Voices / TTS          | optional backends: espeak-ng · espeak · piper, per-cue WAV render | implemented     |
| Mixing / mastering    | stdlib PCM mix, WAV/FLAC/MP3 via ffmpeg/flac, `OCF-RENDER-*` manifest | implemented     |
| Voice cloning         | OpenVoice · Kokoro · pre-recorded narration                        | specified       |

"Specified" means the format and CLI behavior are fully defined in
`OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md` and tracked
in `ROADMAP.md`; the corresponding `ocf preparation …` commands are not yet
shipped. "Implemented" rows have live, tested commands.
`ocf voice doctor` checks which optional TTS backends are installed.

**Audio binaries and Git LFS.** The repository vendors no rendered or
third-party audio: builds and citation-only material stay local
(`.gitignore`, licensing grounds). Genuinely committable binary assets
(OCF-owned or clearly licensed community audio, figures) are tracked as
**Git LFS** objects by `.gitattributes`, so a contributor just adds the file.
See `CONTRIBUTING.md` ("Large files and Git LFS").

## Farfield integration

Farfield is an **optional external synthesis engine**. OCF detects it on
PATH and calls only its public CLI (`farfield list|describe|render`).
If it is missing, commands degrade gracefully with install guidance:

```bash
./scripts/ocf audio check-engine
./scripts/ocf audio render-background OCF-BG-0001
```

## Validation

```json
python3 scripts/ocf.py validate --all
```

covers JSON-Schema conformance, duplicate IDs, duplicate commands,
command-design rules, the 55-function invariants, and 39/16 availability
counts.

## Testing

`python3 -m pytest` covers the CLI, wizards, schemas, command rules, indexes,
audio manifests, and Farfield graceful degradation. `make check` runs
validation plus index freshness in one step.

## Contribution path

1. Draft (`proposals/draft/`) → 2. Review (`proposals/review/`) →
3. Experimental → 4. Accepted. Legacy compatibility is always preserved.
See `CONTRIBUTING.md`, `docs/SUBMISSION_GUIDELINES.md`,
`docs/FUNCTION_LIFECYCLE.md`.

## Safety

Functions carry safety levels, and health/emergency functions carry explicit
statements. OCF makes **no effect guarantees** — see
`docs/SAFETY_POLICY.md` and `docs/EVIDENCE_AND_CLAIMS.md`.

## Licensing

- OCF code, docs, and field formats: Apache-2.0.
- Community scripts/audio: license recorded per item.
- Legacy factual metadata: Apache-2.0 (facts, not expressions).
- Third-party source material: **not redistributed**.

See `LICENSE`, `NOTICE.md`, and `docs/SOURCE_ATTRIBUTION.md`.

## Roadmap

See `ROADMAP.md`.