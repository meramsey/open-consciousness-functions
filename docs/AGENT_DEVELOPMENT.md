# Agent Development Guide

Use this document after the short repository contract in `AGENTS.md`. It is a
map for targeted investigation, not a replacement for schemas or tests.

## Repository map

- `functions/`: 55 canonical function records; YAML owns identity and command
  metadata.
- `function-content/`: evidence, extracted specifications, OCF decisions, and
  runtime bindings; provenance layers must not be merged.
- `schemas/`: canonical JSON Schemas. Inspect before changing YAML or a data
  contract.
- `locales/`: locale manifests, UI/function metadata, and spoken narration
  resources; `audio/voices/` contains voice profiles and metadata registries.
- `audio/templates/`, `audio/stages/`, `audio/slots/`, and `audio/scripts/`:
  session composition and timed narration inputs.
- `audio/background/`: committed background manifests and authoritative preset
  files; `audio/rendered/` is local generated output.
- `.ocf-work/`: gitignored runtime scratch, caches, audition renders, and logs;
  `OCF_WORK_DIR` is the validated workspace override.
- `scripts/ocf_tools/`: shipped library and CLI implementation.
- `scripts/tools/`: research, extraction, preservation, packaging, and local
  development drivers.
- `tests/`: audited unit contracts plus repository/external-tool integration.
- `.github/workflows/`: validation, generated-index, lint, and test jobs.
- `.opencode/`: repository-local read-only investigation agents and watcher
  settings; no MCP server is configured here.

## Investigation order

1. `git status --short --branch` and recent history.
2. Relevant schema and source YAML.
3. `scripts/ocf_tools/cli.py` registration and the owning module.
4. The nearest focused tests, then generated/index code if relevant.
5. `doctor`, focused CLI validation, and tests.

Use `@ocf-investigator` for a narrow flow question and
`@ocf-test-reviewer` for regression/test-taxonomy review. Ask for symbols,
precedence, and tests, not a repository-wide summary.

## Commands

```bash
python3 scripts/ocf.py capabilities --json
python3 scripts/ocf.py functions list --rich --json
python3 scripts/ocf.py functions describe OCF-FND-002 --rich --json
python3 scripts/ocf.py doctor --json
python3 scripts/ocf.py workspace clean --older-than-hours 24 --dry-run
python3 scripts/ocf.py validate --all
python3 scripts/ocf.py build-index --check
python3 -m pytest -m unit
python3 -m pytest -m integration
python3 -m pytest
make check
make lint
```

Use the supported Python environment for the repository rather than relying on
unverified system packages. `doctor --json --workflow NAME` distinguishes core,
selected-workflow, and optional tools. Native engines and ffmpeg are integration
dependencies, not unit-test dependencies.

## Code and data entry points

- CLI entry: `scripts/ocf.py` delegates to `ocf_tools.cli.main`.
- Function discovery: `indexes.py` -> `models.py`; explicit validation is in
  `validators.py`; derived views are produced by `generators.py`.
- Composition: `session.py` loads templates and resolves locale resources;
  `transcript.py` resolves timed events and measured dependencies.
- Voice: `voice.py` selects explicit recording, disabled narration, or TTS and
  returns measured cue/event timing; `narration_pacing.py` splits semantic
  sentence units and resolves locale/profile timing roles.
- Recorded/hybrid sources: `narration_cli.py` owns import/preflight commands;
  `narration_sources.py` owns deterministic event/resource/unit selection;
  `recording_audio.py` owns preparation/metrics/cache receipts; `narration_stems.py`
  owns complete all-event-marked stems. Inspect `narration-sources.schema.json`,
  `recording-processing.schema.json` and `narration-stem.schema.json` first. See
  [recorded](RECORDED_NARRATION.md) and [hybrid narration](HYBRID_NARRATION.md).
- Voice capabilities/portability/datasets: `voice_engine_cli.py` routes shared
  parser commands and the import-first `new voice-dataset MANIFEST` wizard to
  `voice_capabilities.py`, `custom_voices.py` and `voice_datasets.py`. See
  [voice workflows](VOICE_WORKFLOWS.md), [capabilities](VOICE_CLONING.md) and
  [dataset preparation](VOICE_TRAINING.md).
- Build: `audio_build.py` renders narration, selects background/DSP, mixes,
  encodes, and writes render metadata.
- Bulk sessions: `eligibility.py` migrates bindings explicitly and derives
  capability; `session_plans.py` generates compact declarations using the
  existing composer; `bulk_render.py` reuses complete rendering with verified
  receipts; `speech_cache.py` caches exact synthesis inputs. See
  [bulk workflows](BULK_SESSIONS.md).

Never infer semantic identity from a prose string, filename, carrier frequency,
or subtitle `cue_id`. Use event IDs, schemas, manifests, and measured ledgers.

## Localization

Stable `narration_key` identifiers are resolved at render time. UI text may use
the full BCP-47 fallback chain; spoken narration is strict by default and does
not silently fall back across languages. Regional parent fallback is allowed
within the same language. TTS backend/model compatibility is checked separately
from locale-resource availability. Translated speech gets measured timing and
its own provenance; English word timing is never reused.

Consult `docs/LOCALIZATION.md` for fallback and TTS details and
`locales/README.md` for pack authoring.

## Local render workspace

All default OCF scratch and audition outputs belong under `.ocf-work/`, resolved
from the repository root. Subprocesses receive `.ocf-work/tmp/` through
`TMPDIR`, `TMP`, and `TEMP`, and `.ocf-work/cache/` through `XDG_CACHE_HOME`;
the invoking process environment is not modified. Successful scratch is removed
unless `OCF_KEEP_WORK=1`; interrupted/failed stages retain context/scratch under
`tmp/`, and subprocess/render diagnostics are recorded under `logs/`. Default audition outputs are collision-resistant and
retained under `renders/`. Set `OCF_WORK_DIR` to a dedicated writable
directory; relative values resolve from the repository root. Inspect and remove
only stale marked scratch by running `ocf workspace clean --dry-run` before
`ocf workspace clean`. Never clean unmarked files or unrelated directories.

## Testing and verification

Unit tests are isolated deterministic contracts; the autouse process boundary
forbids real subprocess execution. Keep ffmpeg, Farfield, SBaGenX, filesystem
repository workflows, and multi-component CLI tests in integration unless an
individual test is audited as isolated. Use synthetic signal/noise fixtures for
research math. Coverage targets 100% lines and branches but the gate is not
enabled until the real unit denominator reaches it.

For architecture-sensitive changes, verify at least the relevant combination of:

- `tests/test_audio_build.py` and `tests/test_locale_render.py` for preset and
  localized build behavior;
- `tests/test_semantic_dsp.py` and `tests/test_dsp_approach.py` for state/DSP
  timing and approach invariants;
- `tests/test_voice_contracts.py`, `tests/test_complete_session.py`, and
  `tests/test_pacing_auditions.py` for sentence pacing, countdowns, and timing
  reports;
- `tests/test_locale.py` and `tests/test_locale_correctness.py` for fallback;
- `tests/test_transcript.py` and `tests/test_transcript_unit.py` for timed data;
- `tests/test_narration_sources.py`, `tests/test_narration_stems.py` and
  `tests/test_narration_jobs.py` for source coverage, marker ledgers and queued
  identities; `tests/test_narration_demo.py` for the synthetic verification driver;
- `tests/test_packaged_data.py`, `test_bootstrap.py`, and `test_container_config.py`
  for portability boundaries.

For documentation examples, parse arguments with the shared CLI parser without
dispatching placeholder imports/renders or authorization declarations. Distinguish
ordinary `narration validate` compatibility preflight from `narration inspect` or
queued technical validation. A complete stem preflight additionally prepares and
measures its source. Text hashes and declared speaker consistency are not ASR or
biometrics. The [recorded guide](RECORDED_NARRATION.md#cache-and-reproducible-technical-checks)
documents the real `verify_narration_engine2.py prepare`, `verify` and
`benchmark-recording` driver: synthetic tones are not human speech matching the
transcript. Report cold/warm timing scope and receipts, not an extrapolated speed
claim. Preserve existing caches and all frozen editorial/listening checkpoints.

## LSP, MCP, and search efficiency

OpenCode `1.18.34` supports project agents, watcher ignores, LSP, and MCP. This
repository supplies read-only narrow agents and ignores generated/build/cache
trees for watcher noise. No Python LSP server is installed in the audited
environment, so do not claim LSP diagnostics are active; when available, prefer
Pyright/Based Pyright or another Python server for definitions, references,
symbols, and diagnostics. Keep LSP configuration portable and optional.

The optional [OCF stdio MCP adapter](MCP.md) reuses application APIs for compact
discovery, targeted validation and persistent jobs. It is not automatically
configured in any client. Start with `dev ocf_project_overview`; the same
`ocf_*` operations work over MCP or `ocf dev OPERATION --arguments JSON`.
Current CLI discovery advertises 36 operations, including narration inspection,
queued recording validation/rendering and voice capabilities. Check the running
server's discovery after restarting it; a stale client tool list is not evidence
that the current CLI lacks an operation. Job boundaries are in [MCP](MCP.md).
Use external MCP/web tools only for authoritative information missing locally.
Never load reference corpora or entire generated indexes for routine discovery.

Long operations return job IDs. Poll status/results and request cancellation
rather than starting duplicates. Full-suite testing requires `full=true`;
focused selection is not a substitute for final gates. See `docs/workflows.json`
for canonical agent workflows and `documentation-index.json` for the
tracked surface inventory. Its machine findings are not human semantic review.

## Common pitfalls

- Generated indexes and matrix docs are outputs; regenerate, never hand-edit.
- `references/HumanPlusTranscripts/` is read-only research input and must remain
  untouched/uncommitted.
- `audio/rendered/` and audition artifacts are local/ignored; do not stage them.
- Imported narration is not automatically OCF-authored.
- Farfield integration is optional; missing tools must produce useful guidance.
- The preparation module and focus-state cue designs are not live commands.
- Do not propagate frozen V2.1, Hearing, or Sleep Easy editorial decisions.
