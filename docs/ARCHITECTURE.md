# Architecture

OCF separates the **specification** (schemas + YAML records) from the
**tooling** (validation, generation, wizards, audio) and the **provenance**
(legacy metadata, attribution, evidence).

```
┌─────────────────────────── SPECIFICATION ───────────────────────────┐
│ schemas/*.schema.json          canonical data model                │
│ functions/<domain>/*.yaml      canonical editable records          │
│ templates/*                    starting points for new records     │
└─────────────────────────────────────────────────────────────────────┘
                     │ parsed by
                     ▼
┌─────────────────────────── TOOLING ─────────────────────────────────┐
│ scripts/ocf_tools/                                                   │
│   paths.py      repository-aware path resolution                    │
│   models.py     typed accessors over YAML records                   │
│   indexes.py    discovery + loading + audio lookups                 │
│   validators.py JSON-Schema + rule checks + collection invariants   │
│   generators.py deterministic derived files                          │
│   prompts.py    wizards and interactive helpers                     │
│   audio.py      `ocf audio ...` handlers                            │
│   farfield.py   optional external engine wrapper                    │
│   cli.py        argument routing                                    │
└─────────────────────────────────────────────────────────────────────┘
                     │ produce / verify
                     ▼
┌─────────────────────────── DERIVED DATA ────────────────────────────┐
│ FUNCTION_INDEX.md · function-index.json/.csv                        │
│ legacy/hplus-command-map.json/.csv                                  │
│ docs/COMMAND_REVIEW.md, docs/*_MATRIX.md, docs/*_INDEX.md           │
│ (GENERATED — never hand-edited; refresh via build-index)            │
└─────────────────────────────────────────────────────────────────────┘
```

## Design decisions

- **YAML is the source of truth.** Human-friendly editing, machine-readable
  parsing. JSON Schemas constrain it.
- **Deterministic generation.** Every derived file is produced by one command
  (`build-index`) and fails freshness checks on drift.
- **Zero side effects in validators.** Validation only reads; generation only
  writes derived files.
- **Atomic writes.** Wizard and generator output uses temp-file + rename so a
  crash never leaves half-written records.
- **Model separation.** A function, its command, its training script, its
  audio implementation, and its background preset are distinct objects — this
  is what allows one function to reuse several backgrounds and vice versa.
- **Minimal dependencies.** `PyYAML` + `jsonschema` at runtime;
  `pytest`/`ruff` for development. Python 3.11+. Linux/macOS/Windows.

## Module responsibilities

| Module       | Reads                | Writes                    |
| ------------ | -------------------- | ------------------------- |
| `validators` | all records, schemas | none                      |
| `generators` | parsed records       | index files (atomic)      |
| `indexes`    | all records          | none                      |
| `prompts`    | user input           | new records (atomic)      |
| `farfield`   | PATH detection       | engine output / guidance  |
| `cli`        | argv                 | stdout, exit codes        |

## Data flow for a contribution

1. Wizard or manual YAML creates/edits a function record.
2. `ocf validate` runs schema + rule + collection checks immediately.
3. `ocf build-index` regenerates every derived file.
4. CI (`generated-index-check`) re-runs validation + freshness so nothing
   stale merges.

## Extensions

The shipped audio pipeline uses `audio/scripts/` timed documents and audio
implementation manifests (not function records) to produce local rendered
artifacts. `ocf voice` renders narration with measured timing; `ocf audio build`
selects static background or semantic DSP, mixes/encodes outputs, and writes a
render manifest with provenance and checksums. Farfield and SBaGenX are optional
adapters invoked through their public CLIs. See [`AUDIO_PIPELINE.md`](AUDIO_PIPELINE.md)
for the actual sequence and precedence rules.

Shipped:

- **Localization layer** — semantic `narration_key`s resolve through locale
  packs with a BCP-47 fallback chain (es-MX → es → en-US); spoken narration
  fails loudly instead of falling back to English. Language-aware TTS
  selection, pronunciation hints, and measured localized subtitle export.
  Text is resolved at render time; DSP, session structure, and timing stay
  language-independent. See `docs/LOCALIZATION.md` and
  `proposals/draft/ocfp-0001-semantic-narration-keys-and-locale-packs.md`.

Planned (designed, not shipped — see `ROADMAP.md` v0.5):

- **Preparation stage composer** — optional, composable preparation stages
  (relaxation · Energy Conversion Box · affirmation · oHm · focus
  transitions) built on the shipped session-composition mechanics. See
  `docs/PREPARATION_MODULE.md`.
- **Focus-state cue registry** — semantic transition events
  (`focus11_open/ready/close`, `session_complete`) mapped to configurable
  sound cues, resolved independently of narration and DSP. See
  `docs/TIMED_TRANSCRIPTS.md`.
- **Voice registry awareness** — backends advertise supported languages and
  voices so wizard/CLI prompts match the requested locale (additive to the
  existing `audio/voices/profiles/` + `ocf voice` contract).

Each planned layer is optional and backward compatible: new fields/roles
default to no behavior change, and data-model additions go through the
proposal process (`docs/DESIGN_SPEC.md`).
