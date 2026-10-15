# Open Consciousness Functions (OCF)

OCF is a declarative function/session authoring and audio toolchain. Canonical
YAML, schemas and reviewed locale resources define functions; Python tools
validate, compose, synthesize and package them. It is an independent community
project, unaffiliated with The Monroe Institute, Hemi-Sync or related entities.
It distributes no historical source recordings and makes no medical or
therapeutic efficacy claim.

## Current capabilities

- 55 canonical functions, with preserved commands and provenance. Historical
  sources are available for 39 and unavailable for 16; this is distinct from
  modern narration availability.
- All 55 have complete English TTS session bindings and deterministic generated
  plans. Technical eligibility is not editorial approval or release clearance.
- Interactive function/proposal/audio wizards; strict spoken localization;
  timed-transcript import/export; semantic sentence/count pacing.
- Optional Piper/eSpeak narration, Farfield/SBaGenX backgrounds, verified
  auditions and artwork/metadata/transcript/checksum release packaging.
- Resumable explicit bulk auditions, content-addressed speech cache, local jobs,
  and an optional provider-neutral stdio MCP adapter.

The shared LOCKED configuration is an engineering baseline, not human listening
approval. Human review remains required. Preparation-module designs and final
focus-state auditory cue sound design remain planned; see
[status and architecture](docs/AGENT_DEVELOPMENT.md).

## Install

Python **3.11+**; Linux, macOS and Windows. Run commands from the checkout root.
Use your platform's Python executable (`python3` on many POSIX systems,
`py -3` on Windows) to create the environment:

```bash
python -m venv .venv
# Activate .venv with your shell's standard activation command.
python -m pip install -e .
python scripts/ocf.py doctor --json
python scripts/ocf.py --help
```

Without activation, use `.venv/bin/python` on Linux/macOS or
`.venv\Scripts\python.exe` on Windows. Native engines, codecs and voice models
are separate optional installations; `doctor` and `voice doctor` report them.
See [native setup](docs/USER_GUIDE.md) and [voices](docs/COMMUNITY_VOICES.md).

## Find, author and localize

```bash
python scripts/ocf.py functions list --json
python scripts/ocf.py functions describe OCF-FND-002 --rich --json
python scripts/ocf.py new function
python scripts/ocf.py validate --all
python scripts/ocf.py review commands
python scripts/ocf.py build-index
```

Start with [function lifecycle](docs/FUNCTION_LIFECYCLE.md) and
[source-first authoring](docs/SOURCE_FIRST_AUTHORING.md). Immutable source,
working edits, human review and explicit release approval are separate stages.
Never silently rewrite approved narration or canonical activation phrases.
`PLUS-THINK`, `PLUS-FOCUS` and `PLUS-SEE BETTER` remain canonical.

Translations use stable resource IDs, not constructed English. Follow
[localization](docs/LOCALIZATION.md) and [locale packs](locales/README.md).
Spoken fallback is strict; missing Spanish resources are reported rather than
silently spoken in English. Measured timing is locale- and voice-specific.

## Plan without audio engines

```bash
python scripts/ocf.py audio eligibility --all --locale en-US
python scripts/ocf.py audio plan OCF-FND-002 --locale en-US --dry-run
python scripts/ocf.py audio plan --all --locale en-US
python scripts/ocf.py audio plan --all --locale en-US --check
python scripts/ocf.py audio plan OCF-SLP-005 --locale en-US --expand
python scripts/ocf.py new session-plan
```

[Bulk sessions](docs/BULK_SESSIONS.md) explains bindings, template inheritance,
generation and review. Generated declarations live in `audio/session-plans/`;
never hand-edit them or the generated function/command indexes.

## Audition with your selected voice

```bash
python scripts/ocf.py voice doctor
python scripts/ocf.py audio render OCF-SLP-005 --locale en-US \
  --voice OCF-VOICE-0002 --pacing sleep --dry-run
python scripts/ocf.py audio render-many OCF-SLP-005 --locale en-US \
  --voice OCF-VOICE-0002 --resume
```

The example voice requires its configured Piper model. Full-session rendering
uses Focus 10 from the start (OCF-BG-0012, approximate V4-derived candidate),
Focus 11 during access/programming (OCF-BG-0006, canonical newer pure SAM),
25-second equal-power transitions, a continuous bed through pauses and sleep,
and a 10-second ending fade. No automatic Focus 20 DSP substitution occurs.
There are two programming and two -24 dB sleep body repetitions.

Semantic pacing synthesizes sentence/count units separately and inserts real
silence with backend-aware rate controls. Inspect the timing reports and short
pacing excerpts, then perform a listening review. `--mode narration-only` on
`audio render` explicitly selects the separate narration-only workflow.

Outputs, cache, logs and scratch stay in ignored `.ocf-work/`; auditions use
unique paths. Bulk rendering all functions requires explicit `--all` and never
happens during planning. See [audio pipeline](docs/AUDIO_PIPELINE.md),
[semantic DSP](docs/SEMANTIC_DSP.md) and [backgrounds](audio/background/README.md).

## Package an approved release

Use `python scripts/ocf.py audio release --help`. Select a registered audio
implementation/function, explicit approved PNG/JPEG artwork, locale and formats;
preview with `--dry-run`. Packaging verifies decode, metadata, embedded artwork,
transcript and checksums. It does not itself establish rights or human approval.
See [release packaging](docs/AUDIO_PIPELINE.md#final-release-packages).

## Develop and contribute

```bash
python -m pip install -r requirements-dev.txt
python -m pytest                         # comprehensive serial suite
python -m pytest -n 2 --dist loadfile    # same suite, bounded workers
make check                             # schemas, indexes and all source plans
make lint                              # Ruff, formatting and internal links
```

On Windows without make, run the commands listed in `Makefile` individually.
Markdownlint runs in CI; local absence is reported as a skip. Use focused tests
while editing and the full gates before completion. See
[testing](docs/TEST_COVERAGE.md), [measured performance](docs/releases/OCF_BULK_TEST_PERFORMANCE.md)
and [contributing](CONTRIBUTING.md).

## Coding agents and optional MCP

[AGENTS.md](AGENTS.md) is the provider-neutral entry point. Start with a compact
query instead of loading large indexes or narration files:

```bash
python scripts/ocf.py dev ocf_project_overview
python scripts/ocf.py dev ocf_get_function --arguments '{"function_id":"OCF-FND-002"}'
python -m pip install -e '.[mcp]'       # optional official SDK
python scripts/ocf.py mcp             # local stdio; connect an MCP client
```

The same adapters work through CLI without MCP. Long jobs return persistent IDs
for polling/cancellation and bounded result summaries. Read
[MCP setup and job boundaries](docs/MCP.md) for OpenCode, Claude Code and Codex
configuration. No provider credentials or paid services are required.

## Documentation

The [documentation map](docs/README.md) routes to canonical guides in two steps.
`python scripts/ocf.py docs-inventory` generates the tracked documentation
inventory; historical research/checkpoint pages remain explicitly historical.
See [governance](GOVERNANCE.md), [licensing](LICENSE) and
[source attribution](docs/SOURCE_ATTRIBUTION.md).
