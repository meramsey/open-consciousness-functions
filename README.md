# Open Consciousness Functions

**Choose a practice. Make it your own. Listen locally.**

OCF helps you create and use guided audio practices for intentions such as
relaxation, attention, learning and sleep. Each *function* is a named practice
with its own description, cues and documented instructions. Choose a function,
read its guide, then use an available listening edition or create one with a
voice you choose—including a private reference-based version of your own voice.

You control the voice, optional session choices and listening experience. Keep
your recordings, voice references and review notes on your own computer. The
catalog includes both available and planned work; a listed function is not
necessarily a finished recording or a promise of an effect.

[Quickstart](docs/QUICKSTART.md) · [Use your own voice](docs/VOICE_PACKS.md) ·
[Browse functions](FUNCTION_INDEX.md) · [Listening guide](docs/LISTENING_GUIDE.md)

[Listen & Download OCF Audio](https://meramsey.github.io/open-consciousness-functions-audio/)
is the public distribution companion. The library is preparing its first approved
release; local candidate recordings are awaiting listening, rights and publication review.

<p align="center">
  <img src="brand/versions/0.3.0/presentation/readme-hero.png" alt="Open Consciousness Functions — Cosmic Path and Resonance Rings" width="100%">
</p>

## Get started

1. **Choose one intention.** Browse the function catalog and read that function's
   instructions, cues and precautions. Tags help discovery; optional companion
   links help you compare separate practices.
2. **Choose how to listen.** Open a completed edition in your private listening
   portal or listener package. To create audio, choose an installed narrator,
   your own authorized voice reference, or existing recordings.
3. **Preview, then create.** Inspect the session plan and required tools before
   rendering. Planning does not need an audio engine. Rendering writes a new
   edition, leaving earlier editions available for comparison.
4. **Listen and review.** Start at a comfortable volume, use the matching
   transcript, and save your notes. Technical verification and your listening
   judgment are separate.

Follow the [step-by-step quickstart](docs/QUICKSTART.md) for these paths. If you
already have a listener package, open its `guides/index.html`; a guide can be
included without a matching recording. A private listening portal lists only
completed, verified editions.

<details>
<summary>Install from source and try your first plan</summary>

Clone this repository, install Git LFS for its supplied visual assets, and run
commands from the checkout root. Use Python 3.11 or newer.

### Linux / macOS

```bash
git lfs pull
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: --upgrade pip==26.2.0
python -m pip install -e ".[artwork,mcp]"
python scripts/ocf.py doctor --json
```

### Windows PowerShell

```powershell
git lfs pull
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --only-binary=:all: --upgrade pip==26.2.0
python -m pip install -e ".[artwork,mcp]"
python scripts/ocf.py doctor --json
```

Activation is optional: use `.venv/bin/python` or
`.venv\Scripts\python.exe` directly. Artwork, MCP and LSP are optional extras; core
discovery, authoring and planning also work with `python -m pip install -e .`.
Piper/eSpeak, voice models, Farfield/SBaGenX and FFmpeg are separate optional
installations. [Setup](docs/SETUP.md) and [the user guide](docs/USER_GUIDE.md)
explain the supported paths.

### Your first plan — no audio engines required

```bash
python scripts/ocf.py functions list --json
python scripts/ocf.py functions describe OCF-FND-002 --rich --json
python scripts/ocf.py audio plan OCF-SLP-005 --locale en-US --expand
python scripts/ocf.py audio eligibility --all --locale en-US
```

A plan is a declaration, not a render. It reports the bound narration,
template, pacing and background policy without synthesizing speech.

</details>

<details>
<summary>Advanced workflows and developer reference</summary>

Python 3.11+ · Linux · macOS · Windows · Apache-2.0

[![Validation](https://github.com/meramsey/open-consciousness-functions/actions/workflows/validate.yml/badge.svg)](https://github.com/meramsey/open-consciousness-functions/actions/workflows/validate.yml)
[![Tests](https://github.com/meramsey/open-consciousness-functions/actions/workflows/test.yml/badge.svg)](https://github.com/meramsey/open-consciousness-functions/actions/workflows/test.yml)
[![Lint](https://github.com/meramsey/open-consciousness-functions/actions/workflows/lint.yml/badge.svg)](https://github.com/meramsey/open-consciousness-functions/actions/workflows/lint.yml)
[![Generated files](https://github.com/meramsey/open-consciousness-functions/actions/workflows/generated-index-check.yml/badge.svg)](https://github.com/meramsey/open-consciousness-functions/actions/workflows/generated-index-check.yml)

## Explore the functions

The current catalog contains **58 OCF function records**, **102 structured
command records** and **58 generated English session plans**. It comprises 55
legacy-mapped functions (39 with historical source available and 16 without)
plus 3 OCF-original functions. Historical source availability is not OCF
implementation status. Plan validity, audio rendering/verification, human
listening approval and publication authorization are tracked separately; a
valid plan or rendered file does not imply listening or publication approval.

| Area | Functions | Explore |
| --- | --- | --- |
| Foundation and cognition | 13 | Focus, Relax, Recall, Imprint, Options |
| Body and senses | 20 | Comfort, circulation, breathing and sensory practices |
| Emotion and communication | 4 | Let Go, Off-Loading, Empathizing, Speak Up |
| Performance and automation | 7 | Do This Now, Synchronizing, See-Be |
| Sleep | 6 | Sleep, Sleep Easy, Sweet Dreams, Stay Awake |
| Lifestyle, experimental and emergency | 8 | Habit patterns and specialized practices |

[Browse the generated catalog](FUNCTION_INDEX.md) or use
`python scripts/ocf.py commands describe OCF-SLP-005` for command roles and
procedures. A function, its activation phrase, its narration and its audio are
separate identities. Current title/cue status is derived from canonical locale
resources; see the [current title/cue view](docs/releases/OCF_TITLE_CUE_CURRENT.md).

## From intention to audio

**Author → validate → plan → audition → review → explicitly package.**

| Workflow | Start here |
| --- | --- |
| Create a function or translate a resource | [Function lifecycle](docs/FUNCTION_LIFECYCLE.md) · [Localization](docs/LOCALIZATION.md) |
| Compose templates, pacing and function variants | [Bulk sessions](docs/BULK_SESSIONS.md) · [Session overrides](docs/SESSION_OVERRIDES.md) |
| Use your recorded voice | [Recorded narration](docs/RECORDED_NARRATION.md) |
| Mix recordings and synthesis cue by cue | [Hybrid narration](docs/HYBRID_NARRATION.md) |
| Import a private voice or prepare a dataset | [Voice workflows](docs/VOICE_WORKFLOWS.md) |
| Inspect timing, gains and Focus backgrounds | [Audio pipeline](docs/AUDIO_PIPELINE.md) · [Semantic DSP](docs/SEMANTIC_DSP.md) |
| Build private reference-V4 listening editions | [Private workflow](docs/PRIVATE_REFERENCE_V4.md) |

### Audition a complete session

With the configured Piper model and audio tools installed:

```bash
python scripts/ocf.py voice doctor
python scripts/ocf.py audio render OCF-SLP-005 --voice OCF-VOICE-0002 --pacing sleep --dry-run
python scripts/ocf.py audio render OCF-SLP-005 --voice OCF-VOICE-0002 --pacing sleep
```

The locked engineering baseline keeps Focus 10 from the opening, Focus 11 during
access/programming, 25-second equal-power transitions and a 10-second ending fade.
Logical sleep stages do not substitute a Focus 20 background. Timing is measured
from the selected narration. Outputs, logs and caches stay in `.ocf-work/`;
existing auditions are never overwritten. [Bulk generation](docs/BULK_SESSIONS.md)
adds explicit multi-function selection and verified resume.

### Recordings, hybrid speech and portable voices

```bash
python scripts/ocf.py narration sources OCF-SLP-005
python scripts/ocf.py voice capabilities --json
python scripts/ocf.py voice dataset-init .ocf-work/my-dataset --id my-voice
```

Use explicit event/resource/unit mappings or a complete all-event-marked stem.
Recorded-only mode never silently falls back; hybrid mode requires a declared
policy. Original files are preserved, and narration processing never touches
the independent binaural bed. Text hashes do not verify speech content.
Private reference-voice packs are supported through the optional local
Chatterbox Nano adapter; see the [voice-pack quick start](docs/VOICE_PACKS.md)
and [voice privacy and capability notes](docs/VOICE_CLONING.md). Model training
is not provided by this workflow.

## Artwork with a cosmic identity

<p align="center">
  <img src="brand/imports/ocf-cosmic-path-brand-kit-v1/png/ocf-app-icon-128.png" alt="Supplied OCF Cosmic Path application icon" width="64">
</p>

New generated covers default to **imported cosmic dark**. Light, minimal,
custom themes and explicit custom covers remain available; the application/UI
and documentation themes are independent.

```bash
python scripts/ocf.py artwork generate OCF-SLP-005 --resolution 1200
python scripts/ocf.py artwork generate OCF-FND-002 --theme ocf-cosmic-light --format jpeg --resolution 1200
python scripts/ocf.py artwork theme --surface ui
```

[Review the versioned gallery](brand/versions/0.3.0/gallery/index.html) locally
and read [branding and theme precedence](docs/BRANDING.md). Brand 0.3.0 remains a
candidate. The cinematic reference hero and editable companions are distinct;
the vectors are not exact copies of the cinematic artwork. Originals are intact.
[Social-preview image and GitHub setup](brand/versions/0.3.0/presentation/README.md).

## Local agent workflows

The optional MCP server exposes **36 tools** for compact discovery, validation,
planning, explicit jobs and cancellation over local stdio. It reuses the same
application services as the CLI and needs no HTTP listener.

```bash
python scripts/ocf.py dev ocf_project_overview
python scripts/ocf.py dev ocf_get_function --arguments '{"function_id":"OCF-FND-002"}'
python scripts/ocf.py mcp
```

[Connect an MCP client](docs/MCP.md) or use the CLI adapters directly.
[Configure the optional OCF language server](docs/LSP.md) for YAML/JSON diagnostics,
completion, navigation and read-only migration previews in an editor.
[AGENTS.md](AGENTS.md) and [the developer guide](docs/AGENT_DEVELOPMENT.md)
describe bounded jobs, targeted validation and protected-data rules.

## Documentation, contribution and provenance

- **New here?** Follow [the user guide](docs/USER_GUIDE.md) and [documentation map](docs/README.md).
- **Need examples?** Use the [checked interface library](examples/README.md) for
  CLI, MCP, schemas, workflows and editor integration.
- **Contributing?** Start with [CONTRIBUTING.md](CONTRIBUTING.md); run focused tests,
  `make check`, `make lint` and the comprehensive suite before submitting changes.
- **Packaging?** Select a registered implementation and approved/custom artwork;
  [preview the release](docs/AUDIO_PIPELINE.md#final-release-packages) before any
  deliberate packaging. Successful encoding is not publication approval.
- **Editorial review?** Read [editorial review boundaries](docs/EDITORIAL_REVIEW.md)
  and the generated [current title/cue view](docs/releases/OCF_TITLE_CUE_CURRENT.md).

</details>

OCF is independent and unaffiliated with The Monroe Institute, Hemi-Sync or
related entities. Historical source recordings and private voices/models are
not distributed. Intended practice outcomes, documentary provenance, technical
renderability and human/release approval are separate. See [Apache-2.0](LICENSE),
[source attribution](docs/SOURCE_ATTRIBUTION.md) and [governance](GOVERNANCE.md).
