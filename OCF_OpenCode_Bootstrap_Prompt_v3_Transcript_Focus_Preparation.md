# OpenCode Agent Bootstrap Prompt — Open Consciousness Functions (OCF)

You are the principal implementation agent for a new open-source project:

**Open Consciousness Functions (OCF)**

Repository name suggestion:

```text
open-consciousness-functions
```

Your job is to build a complete, polished, production-quality GitHub starter repository — not merely describe one.

The repository is an independent community project inspired by the general idea of trainable “functions” used in Monroe Institute Human Plus material, but it must not imply affiliation with, endorsement by, or ownership by The Monroe Institute, Hemi-Sync, Interstate Industries, or any related entity.

The project should preserve legacy mapping information for research and compatibility while defining an original, open, community-maintained function specification, command grammar, contribution workflow, validation system, and future audio-generation toolchain.

## Version note

This **v3** prompt extends `OCF_OpenCode_Bootstrap_Prompt.md` (the base
specification). Sections 1–26 remain normative for the core repository.
Sections 27–61 add the timed-transcript / timed-lyrics authoring pipeline,
state/focus timeline modeling, voice and TTS backend layer, mixing and
mastering, and the dedicated Preparation Module. Where a later section changes
a base requirement, the later section wins.

Generated documentation must explain, in plain language, how a contributor
adds a function **from timed lyrics** (e.g. an `.lrc` file) and must state
explicitly **what is supported** for each artifact: input formats, authoring
modes, backends, and output formats. No documentation may claim a tool exists
unless this specification actually requires it.

---

# 1. PRIMARY GOALS

Build OCF as an **open specification plus reference implementation framework** for defining, reviewing, documenting, validating, and eventually producing community-authored consciousness-function training exercises.

OCF must support:

1. Legacy-compatible function mappings.
2. Original community-authored functions.
3. Reimplementation of all known legacy functions, including those whose original training audio/source material is currently unavailable.
4. Structured machine-readable function definitions.
5. Human-readable generated documentation and indexes.
6. Interactive contribution tools for non-programmers.
7. Formal proposal/review workflows.
8. Audio-script metadata and implementation manifests.
9. Optional generated background audio using the `farfield` project.
10. Clear provenance, licensing, safety, claims, and compatibility policies.
11. Automated validation, tests, generated-index checks, and CI.

---

# 2. AUTHORITATIVE LEGACY SOURCE MATERIAL

If these files are present locally, use them as the initial authoritative legacy-reference sources:

```text
references/HPLUS_Field_Guide_Print.pdf
references/HPLUS_Function_Index.pdf
```

Extract only information actually supported by those sources.

Preserve page locators where possible.

Do not invent missing data.

When a field cannot be established from the source:

```text
pending-source-review
```

or `null` / empty list as appropriate.

Do not reproduce large copyrighted passages from legacy pamphlets.

The repository should contain concise factual mappings, short summaries, metadata, source citations, and original OCF descriptions.

---

# 3. LEGACY COLLECTION SCOPE

The initial OCF legacy map includes **55 documented functions**:

- 39 whose original/reference training material is currently available.
- 16 documented functions whose original/reference training material is currently unavailable.

IMPORTANT:

The 16 unavailable legacy functions MUST still be included as full OCF reimplementation targets.

Do **not** treat them as excluded from the OCF project.

Instead distinguish:

```yaml
legacy:
  source_availability: unavailable

ocf:
  reimplementation_status: planned
```

They should be eligible for:

- new original OCF training scripts;
- community reimplementation proposals;
- review;
- experimentation;
- future audio implementations;
- compatibility mapping based on documented legacy information.

They must not be falsely represented as reconstructed original Monroe audio.

---

# 4. CORE DESIGN PRINCIPLES

## 4.1 Preserve good commands

Do not rename a legacy command merely to make the vocabulary look uniform.

If a command is already short, intuitive, memorable, and clearly associated with the function, retain it.

Examples that should remain canonical unless a maintainer explicitly changes them later:

```text
ATTENTION              -> PLUS-FOCUS
THINK FAST             -> PLUS-THINK
RECALL                 -> PLUS-RECALL
IMPRINT                -> PLUS-IMPRINT
ACCESS TO ENERGY       -> PLUS-ENERGIZE
ACCESS TO INFORMATION  -> PLUS-RETRIEVE
RECHARGE               -> PLUS-RECHARGE
RELAX                  -> PLUS-RELAX
RESET                  -> PLUS-RESET
SPEAK UP               -> PLUS-SPEAK UP
RELEASE                -> PLUS-RELEASE
SEE-BE                 -> PLUS-AUTOMATE
```

Especially:

```text
THINK FAST -> PLUS-THINK
```

Do not replace this with `PLUS-QUICKTHINK`, `PLUS-THINK-FAST`, `PLUS-THINK-ACCELERATE`, or anything longer.

## 4.2 Change only commands that benefit from change

A replacement should be considered only if a legacy command is:

- cryptic;
- arbitrary;
- needlessly repetitive;
- hard to connect to its function;
- inconsistent with a useful reusable pattern;
- awkward to remember.

Every changed command requires:

- legacy command;
- proposed OCF command;
- reason;
- old spoken-word count;
- new spoken-word count;
- compatibility strategy;
- review state.

## 4.3 Command length is a first-class design constraint

Rules:

- Prefer one meaningful word after `PLUS`.
- Two words are acceptable when needed.
- Three post-prefix words are an exceptional maximum.
- A canonical command should normally be the same length or shorter than the legacy command.
- Do not add domain names unnecessarily.
- Do not add filler words such as `NOW`, `SYSTEM`, `FUNCTION`, or `ACTIVATE`.
- Do not invent awkward compounds.

## 4.4 MORE / LESS is the standard directional grammar

Use `MORE` / `LESS` for adjustable magnitude functions.

Examples:

```text
PLUS-SEE MORE
PLUS-SEE LESS

PLUS-HEAR MORE
PLUS-HEAR LESS

PLUS-SMELL MORE
PLUS-SMELL LESS

PLUS-TASTE MORE
PLUS-TASTE LESS

PLUS-TOUCH MORE
PLUS-TOUCH LESS

PLUS-SEX MORE
PLUS-SEX LESS

PLUS-FOOD MORE
PLUS-FOOD LESS
```

Prefer MORE/LESS over UP/DOWN.

## 4.5 Separate function, command, and implementation

The repository must model these independently:

- function capability;
- canonical name;
- canonical command;
- legacy name;
- legacy command;
- command aliases;
- intended purpose;
- training script;
- audio implementation;
- background-audio preset;
- release/cancel behavior;
- activation mode;
- persistence/lifecycle;
- evidence/claim status;
- provenance.

This is critical: a function is not the same thing as its audio recording.

---

# 5. PROJECT IDENTIFIERS

Use:

```text
Open Consciousness Functions
OCF
```

Function ID format:

```text
OCF-<DOMAIN>-<NUMBER>
```

Examples:

```text
OCF-FND-001
OCF-COG-004
OCF-SLP-002
```

Proposal IDs:

```text
OCFP-0001
```

Audio implementation IDs:

```text
OCF-AUDIO-0001
```

Background audio preset/implementation IDs:

```text
OCF-BG-0001
```

Voice profile IDs (see §28):

```text
OCF-VOICE-0001
```

Render / build manifest IDs (see §37):

```text
OCF-RENDER-0001
```

Preparation module IDs (see §51):

```text
OCF-PREP-0001
```

State profile IDs (see §47):

```text
OCF-STATEPROFILE-<SLUG>-<NNN>
```

Reusable audio-section template IDs (see §46):

```text
OCF-TPL-<GROUP>-<NNN>
```

Session composition template IDs (see §55):

```text
OCF-SESSION-<SLUG>-<NNN>
```

IDs must remain stable across renames.

---

# 6. REPOSITORY STRUCTURE

Create at least:

```text
open-consciousness-functions/
├── .editorconfig
├── .gitattributes
├── .gitignore
├── .markdownlint.json
├── .pre-commit-config.yaml
├── AGENTS.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── GOVERNANCE.md
├── LICENSE
├── NOTICE.md
├── README.md
├── ROADMAP.md
├── SECURITY.md
├── pyproject.toml
├── requirements-dev.txt
├── Makefile
├── function-index.json
├── function-index.csv
├── FUNCTION_INDEX.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── AUDIO_SECTIONS.md               (v3)
│   ├── AUDIO_STANDARD.md
│   ├── BACKGROUND_AUDIO.md
│   ├── COMMAND_GRAMMAR.md
│   ├── COMPATIBILITY_POLICY.md
│   ├── DESIGN_SPEC.md
│   ├── EVIDENCE_AND_CLAIMS.md
│   ├── FUNCTION_LIFECYCLE.md
│   ├── MIXING_AND_MASTERING.md         (v3)
│   ├── NAMING_GUIDELINES.md
│   ├── PREPARATION_MODULE.md           (v3)
│   ├── PROJECT_TERMINOLOGY.md
│   ├── SAFETY_POLICY.md
│   ├── STATE_AND_FOCUS_LEVELS.md       (v3)
│   ├── SUBMISSION_GUIDELINES.md
│   ├── SOURCE_ATTRIBUTION.md
│   ├── TIMED_TRANSCRIPTS.md            (v3)
│   ├── USER_GUIDE.md
│   ├── VOICE_BACKENDS.md               (v3)
│   └── VOICE_RECORDING_GUIDE.md        (v3)
├── schemas/
│   ├── function.schema.json
│   ├── proposal.schema.json
│   ├── audio-implementation.schema.json
│   ├── background-audio.schema.json
│   ├── timed-transcript.schema.json    (v3)
│   ├── voice-profile.schema.json       (v3)
│   ├── render-manifest.schema.json     (v3)
│   ├── audio-section.schema.json       (v3)
│   ├── state-profile.schema.json       (v3)
│   ├── state-segment.schema.json       (v3)
│   └── preparation-module.schema.json  (v3)
├── functions/
│   ├── foundation/
│   ├── cognition/
│   ├── emotion/
│   ├── communication/
│   ├── body/
│   ├── performance/
│   ├── sensory/
│   ├── sleep/
│   ├── lifestyle/
│   ├── emergency/
│   ├── automation/
│   └── experimental/
├── legacy/
│   ├── README.md
│   ├── hplus-command-map.json
│   ├── hplus-command-map.csv
│   └── source-notes/
├── proposals/
│   ├── README.md
│   ├── draft/
│   ├── review/
│   ├── accepted/
│   ├── rejected/
│   └── withdrawn/
├── audio/
│   ├── README.md
│   ├── scripts/
│   ├── implementations/
│   ├── manifests/
│   ├── rendered/                       (v3: lossless masters + derivatives)
│   ├── states/
│   │   └── profiles/                   (v3)
│   ├── templates/                      (v3, see §46)
│   │   ├── preparation/
│   │   ├── induction/
│   │   ├── access-open/
│   │   ├── function-intro/
│   │   ├── installation/
│   │   ├── rehearsal/
│   │   ├── integration/
│   │   ├── access-close/
│   │   ├── consolidation/
│   │   ├── sleep/
│   │   ├── return/
│   │   └── outro/
│   ├── voices/                         (v3, see §28)
│   │   ├── README.md
│   │   ├── profiles/
│   │   ├── manifests/
│   │   └── samples/
│   ├── background/
│   │   ├── README.md
│   │   ├── presets/
│   │   ├── manifests/
│   │   └── rendered/
│   └── tools/
├── preparation/                        (v3, see §51)
│   ├── README.md
│   ├── modules/
│   ├── templates/
│   └── manifests/
├── references/
│   └── README.md
├── templates/
│   ├── function.yaml
│   ├── proposal.md
│   ├── audio-script.md
│   ├── audio-manifest.yaml
│   ├── background-audio.yaml
│   ├── testing-report.md
│   ├── source-review.md
│   ├── timed-transcript.yaml           (v3)
│   ├── voice-profile.yaml              (v3)
│   ├── state-profile.yaml              (v3)
│   ├── audio-section.yaml              (v3)
│   └── preparation-module.yaml         (v3)
├── scripts/
│   ├── ocf
│   ├── ocf.py
│   └── ocf_tools/
│       ├── __init__.py
│       ├── cli.py
│       ├── prompts.py
│       ├── validators.py
│       ├── generators.py
│       ├── indexes.py
│       ├── audio.py
│       ├── farfield.py
│       ├── transcript.py              (v3, see §44/§56/§57)
│       ├── speech.py                  (v3 TTS backend registry, see §34)
│       ├── mixer.py                   (v3 FFmpeg mixing, see §35)
│       ├── preparation.py             (v3, see §52–§53)
│       ├── paths.py
│       ├── models.py
│       └── utils.py
├── tests/
│   ├── test_cli.py
│   ├── test_validation.py
│   ├── test_index_generation.py
│   ├── test_command_rules.py
│   ├── test_audio_manifest.py
│   ├── test_farfield_integration.py
│   └── fixtures/
└── .github/
    ├── CODEOWNERS
    ├── pull_request_template.md
    ├── ISSUE_TEMPLATE/
    │   ├── config.yml
    │   ├── bug_report.yml
    │   ├── function_proposal.yml
    │   ├── command_change.yml
    │   ├── audio_submission.yml
    │   ├── documentation.yml
    │   └── safety_concern.yml
    └── workflows/
        ├── validate.yml
        ├── test.yml
        ├── lint.yml
        └── generated-index-check.yml
```

You may add useful files, but do not omit required ones.

---

# 7. CANONICAL FUNCTION FORMAT

Use YAML as the canonical editable function format.

Example:

```yaml
schema_version: "1.0"

id: "OCF-FND-001"
slug: "attention"

canonical:
  name: "Attention"
  command:
    primary: "PLUS-FOCUS"
    modes: []

legacy:
  source_system: "Monroe H-PLUS"
  name: "ATTENTION"
  commands:
    - "PLUS-FOCUS"
  command_status: "unchanged"
  source_availability: "available"

ocf:
  reimplementation_status: "planned"
  command_review: "approved"

aliases:
  names:
    - "Focus"
  commands: []

classification:
  primary_domain: "foundation"
  secondary_domains:
    - "cognition"

status:
  maturity: "legacy-mapped"
  implementation: "specification-only"
  evidence: "source-described"

lifecycle:
  persistence: "temporary"
  activation: "manual"
  release:
    required: false
    command: null

purpose:
  summary: ""
  source_description: ""
  community_description: ""

applications: []
companions: []
chains: []

safety:
  level: "general"
  notes: []

claims:
  intended_effects: []
  prohibited_claims: []

audio:
  script_status: "not-started"
  implementation_status: "not-started"
  background_audio:
    strategy: "optional"
    engine: "farfield"
    preset: null

sources:
  - type: "legacy-reference"
    title: ""
    locator: ""
    url: null

attribution:
  original_authors: []
  ocf_contributors: []

version:
  current: "0.1.0"
  created: "YYYY-MM-DD"
  updated: "YYYY-MM-DD"

history: []
```

Use JSON Schema validation.

---

# 8. INITIAL LEGACY MAP — ALL 55 FUNCTIONS

Create records for all functions below.

## Available legacy/reference material

1. ACCESS TO ENERGY — `PLUS-ENERGIZE`
2. ACCESS TO INFORMATION — `PLUS-RETRIEVE`
3. ATTENTION — `PLUS-FOCUS`
4. BRAIN: REPAIRS & MAINTENANCE — `PLUS-FLOW BETTER` — permanent
5. BUY THE NUMBERS — `PLUS-CALCULATE` — permanent
6. CIRCULATION — `PLUS-FLOW SMOOTH` — permanent
7. CONTEMPLATION — `PLUS-OPEN`; `PLUS-CLOSED`
8. DE-DISCOMFORT — `PLUS-55515`
9. DE-HAB — `PLUS-NO MORE, NO MORE`
10. DE-TOX: BODY — `PLUS-CLEAN, CLEAR` — permanent
11. DO THIS NOW — `PLUS-DO-THIS-NOW`
12. EAT/NO EAT — `PLUS-SATISFIED, SUPPLIED`
13. EIGHT-GREAT — `PLUS-EIGHT, GREAT` — permanent
14. HEART: REPAIRS & MAINTENANCE — `PLUS-HEART, BETTER, BETTER` — permanent
15. HYPERTENSION — `PLUS-BALANCE-BLOODPRESSURE`
16. IMMUNIZING — `PLUS-ALERT, DESTROY` — permanent
17. IMPRINT — `PLUS-IMPRINT, IMPRINT`; `PLUS-RECALL`
18. LET GO — `PLUS-LET GO`
19. LUNGS: REPAIRS & MAINTENANCE — `PLUS-BREATH BETTER` — permanent
20. MOBIUS WEST — `PLUS-CHANGE, CHANGE`
21. NUTRICIA — `PLUS-FOOD MORE`; `PLUS-FOOD LESS`
22. OFF-LOADING — `PLUS-FADE, FADE`
23. OPTIONS — `PLUS-OPTIONS, CHOICES`
24. PASSAGES — `PLUS-EQUALIZE-HARMONIZE`
25. RECALL — `PLUS-RECALL`
26. RECHARGE — `PLUS-RECHARGE`
27. RELAX — `PLUS-RELAX, RELAX`
28. RESET — `PLUS-RESET, RESET`
29. RESTORATIVE SLEEP — `PLUS-HEAL, HEAL`
30. SENSORY: HEARING — `PLUS-HEAR MORE`; `PLUS-HEAR LESS`
31. SENSORY: SEEING — `PLUS-SEE BETTER` — permanent
32. SEX DRIVE — `PLUS-SEX GREATER`; `PLUS-SEX LESSER`
33. SLEEP — `PLUS-20-20`
34. SPEAK UP — `PLUS-SPEAK UP` — permanent
35. SWEET DREAMS — `PLUS-THEME, DREAM, SLEEP`
36. SYNCHRONIZING — `PLUS-SMOOTH, FAST` — permanent
37. THINK FAST — `PLUS-THINK` — permanent
38. TUNE-UP — `PLUS-BALANCE, HEAL`
39. WAKE/KNOW — `PLUS-SLEEP, HELP`

## Documented legacy/reference material unavailable — OCF reimplementation targets

40. EMERGENCY: INJURY — `PLUS-CONTROL, BALANCE, RESTORE`
41. EMERGENCY: TOXIC — `PLUS-CLEAR, REMOVE`
42. EMPATHIZING — `PLUS-PROFILE, PROFILE`
43. LIGHT FOOT — `PLUS-LIGHTER, LIGHTER`
44. MAKE YOUR DAY — `PLUS-THIS DAY`
45. REGENERATE — `PLUS-BUILD, LIVE` — permanent
46. RELEASE — `PLUS-RELEASE`
47. SEE-BE — `PLUS-AUTOMATE`
48. SENSORY: SMELL — `PLUS-SMELL GREATER`; `PLUS-SMELL LESSER`
49. SENSORY: TASTE — `PLUS-TASTE GREATER`; `PLUS-TASTE LESSER`
50. SENSORY: TOUCH — `PLUS-TOUCH GREATER`; `PLUS-TOUCH LESSER`
51. SHORT FIX — `PLUS-GO NUMB, GO NUMB`; `PLUS-RELEASE`
52. SLEEP EASY — `PLUS-QUIET, SLEEP`
53. STAY AWAKE — `PLUS-ONE, AWAKE, ALERT, ONE, ONE`
54. STRONG-QUICK — `PLUS-STRONG-QUICK`
55. ZONING — `PLUS-INSULATE, INSULATE`; `PLUS-CANCEL`

For these 16 records:

```yaml
legacy:
  source_availability: unavailable

ocf:
  reimplementation_status: planned
```

They MUST appear in the main OCF index and reimplementation roadmap.

---

# 9. INITIAL COMMAND DECISIONS

## Keep unchanged

At minimum:

```text
ACCESS TO ENERGY      -> PLUS-ENERGIZE
ACCESS TO INFORMATION -> PLUS-RETRIEVE
ATTENTION              -> PLUS-FOCUS
BUY THE NUMBERS        -> PLUS-CALCULATE
DO THIS NOW            -> PLUS-DO-THIS-NOW
IMPRINT                -> PLUS-IMPRINT
LET GO                 -> PLUS-LET GO
OPTIONS                -> PLUS-OPTIONS
RECALL                 -> PLUS-RECALL
RECHARGE               -> PLUS-RECHARGE
RELAX                  -> PLUS-RELAX
RESET                  -> PLUS-RESET
SPEAK UP               -> PLUS-SPEAK UP
THINK FAST             -> PLUS-THINK
RELEASE                -> PLUS-RELEASE
SEE-BE                 -> PLUS-AUTOMATE
```

For `REGENERATE`, evaluate whether the obvious concise OCF canonical command should be:

```text
PLUS-REGENERATE
```

but mark it for review rather than assuming approval.

## Normalize adjustable modes

Use proposed canonical mode vocabulary:

```text
SENSORY: SEEING
  PLUS-SEE MORE
  PLUS-SEE LESS

SENSORY: HEARING
  PLUS-HEAR MORE
  PLUS-HEAR LESS

SENSORY: SMELL
  PLUS-SMELL MORE
  PLUS-SMELL LESS

SENSORY: TASTE
  PLUS-TASTE MORE
  PLUS-TASTE LESS

SENSORY: TOUCH
  PLUS-TOUCH MORE
  PLUS-TOUCH LESS

SEX DRIVE
  PLUS-SEX MORE
  PLUS-SEX LESS

NUTRICIA
  PLUS-FOOD MORE
  PLUS-FOOD LESS
```

## Mark questionable replacements as review-required

Potential concise candidates include:

```text
DE-DISCOMFORT     -> PLUS-COMFORT
DE-HAB            -> needs-review
DE-TOX: BODY      -> PLUS-DETOX
EIGHT-GREAT       -> PLUS-STRONG
MOBIUS WEST       -> PLUS-PROGRAM
OFF-LOADING       -> PLUS-CLEAR
RESTORATIVE SLEEP -> PLUS-RESTORE
SLEEP             -> PLUS-SLEEP
SWEET DREAMS      -> PLUS-DREAM
WAKE/KNOW         -> PLUS-KNOW
LIGHT FOOT        -> PLUS-LIGHT
SHORT FIX         -> PLUS-NUMB
SLEEP EASY        -> PLUS-SLEEP EASY
STAY AWAKE        -> PLUS-AWAKE
STRONG-QUICK      -> PLUS-STRONG QUICK
ZONING            -> PLUS-ZONE
ZONING cancel     -> PLUS-CANCEL
```

Do not mark these approved automatically.

Generate a command-review report.

---

# 10. LEGACY COMPATIBILITY

Create `docs/COMPATIBILITY_POLICY.md`.

Compatibility states:

```text
unchanged
alias-listed
bridge-trainable
canonical-first
legacy-first
none
```

Every changed command must retain its historical command metadata.

Do not silently delete legacy aliases.

Document that OCF can train an association between legacy and canonical cues, but must not claim automatic transfer as a proven fact.

A future bridge-training script may use an original OCF phrase such as:

```text
The familiar cue is [legacy command].
The concise OCF cue is [canonical command].
During this training exercise, either cue may be practiced with the same intended function.
```

Label this as a training design, not established science.

---

# 11. INTERACTIVE CONTRIBUTOR CLI

This is mandatory.

Build a Python CLI usable by non-programmers.

Entry points:

```text
./scripts/ocf
python3 scripts/ocf.py
ocf
```

Shebangs:

```bash
#!/usr/bin/env bash
```

and:

```python
#!/usr/bin/env python3
```

Commands:

```text
ocf new function
ocf new proposal
ocf new audio
ocf new background
ocf new test-report
ocf import source
ocf edit function
ocf validate
ocf validate --all
ocf build-index
ocf review commands
ocf audio check-engine
ocf audio list-background
ocf audio describe-background <preset>
ocf audio render-background <preset>
ocf doctor
ocf help
```

### v3 command additions

These groups must also be implemented and listed in `docs/USER_GUIDE.md` and
the CLI help text. They are specified in the sections noted:

Timed transcripts (§44, §56, §57):

```text
ocf transcript import FILE [--format auto] [--output FILE.yaml]
ocf transcript segment FILE
ocf transcript analyze FILE [--interactive]
ocf transcript review FILE
ocf transcript export FILE.yaml --format srt
ocf transcript export FILE.yaml --format vtt
ocf transcript export FILE.yaml --format lrc
ocf transcript extract-template FILE --timing-only
```

Voices (§30):

```text
ocf voice list-backends
ocf voice doctor
ocf voice list
ocf voice new
ocf voice import
ocf voice record
ocf voice validate
ocf voice preview <voice-id>
ocf voice render <voice-id> --text "..."
```

Audio build pipeline (§38):

```text
ocf audio doctor
ocf audio render-speech SCRIPT [--voice OCF-VOICE-0001]
ocf audio render-background PRESET
ocf audio mix --speech narration.wav --background background.wav --output final.wav
ocf audio build OCF-AUDIO-0001 [--master] [--format flac|mp3]
ocf audio inspect FILE
```

Preparation module (§52–§53):

```text
ocf new preparation
ocf preparation import-reference FILE
ocf preparation edit OCF-PREP-0001
ocf preparation validate OCF-PREP-0001
ocf preparation build OCF-PREP-0001
```

## Function wizard prompts

Prompt for:

- contributor name;
- optional contact handle/email;
- function name;
- short descriptive name;
- slug;
- primary domain;
- secondary domains;
- purpose;
- use cases;
- intended behavior;
- canonical command;
- optional modes;
- legacy name;
- legacy commands;
- aliases;
- unchanged / normalized / proposed command status;
- change rationale;
- source availability;
- OCF reimplementation status;
- permanent / temporary / persistent / conditional;
- manual / automatic / conditional / continuous activation;
- trigger conditions;
- release/cancel behavior;
- companion functions;
- incompatible functions;
- chains;
- safety notes;
- medical relevance;
- claims/evidence state;
- source files;
- source URLs;
- references;
- testing status;
- audio status;
- background audio status;
- notes.

Wizard requirements:

- defaults;
- help for every field;
- `back`;
- `skip`;
- `quit`;
- final review screen;
- atomic writes;
- overwrite confirmation;
- validation immediately after writing;
- exact next-step instructions.

---

# 12. SOURCE FILE ASSISTANCE

When contributors provide a local source file:

- accept pasted paths;
- support spaces in paths;
- validate existence;
- compute SHA-256;
- preserve source filename;
- do not alter source file;
- permit citation-only mode without copying;
- explicitly warn before copying third-party copyrighted material;
- store only allowed files in a clearly documented references area;
- do not automatically redistribute third-party PDFs/audio.

---

# 13. AUDIO IMPLEMENTATION MODEL

A function may have multiple audio implementations.

Create an audio implementation schema with fields for:

- implementation ID;
- function ID;
- title;
- version;
- contributor;
- narrator;
- language;
- license;
- training type;
- duration;
- induction approach;
- command rehearsal;
- legacy bridge mode;
- mode rehearsal;
- release rehearsal;
- safety intro;
- transcript;
- background audio;
- technical metadata;
- testing notes;
- review state.

Audio types may include:

```text
training
reinforcement
quick
sleep
extended
voice-only
background-only
experimental
```

Do not assume any one audio style is required.

---

# 14. FARFIELD BACKGROUND AUDIO INTEGRATION

Integrate support for:

```text
https://github.com/txus/farfield
```

Treat Farfield as an **optional external synthesis engine**, not vendored OCF code by default.

Do not copy Farfield source into the repository unless there is a documented reason.

Prefer one of these approaches:

1. external executable detected on PATH;
2. optional Python dependency;
3. git submodule only if maintainers explicitly choose that later.

Create:

```text
docs/BACKGROUND_AUDIO.md
scripts/ocf_tools/farfield.py
audio/background/presets/
audio/background/manifests/
templates/background-audio.yaml
schemas/background-audio.schema.json
```

## Farfield integration goals

OCF should be able to define background synthesis separately from the spoken training script.

Example conceptual manifest:

```yaml
schema_version: "1.0"

id: "OCF-BG-0001"
name: "Neutral focus bed"
engine: "farfield"

engine_source:
  repository: "https://github.com/txus/farfield"
  version: null

preset:
  file: "audio/background/presets/example.yaml"

render:
  output: "audio/background/rendered/example.wav"
  seed: 12345
  deterministic: true

usage:
  functions: []
  audio_implementations: []

provenance:
  design: "original-ocf"
  notes: ""

safety:
  headphone_notice: true
  driving_warning: true
```

## CLI support

Implement:

```text
ocf audio check-engine
ocf audio list-background
ocf audio describe-background <preset>
ocf audio render-background <preset>
ocf audio render-background <preset> --output FILE
```

The wrapper should detect whether `farfield` exists and provide installation guidance rather than crashing.

Do not hardcode undocumented internal Farfield APIs.

Prefer invoking the public CLI unless stable Python APIs are clearly documented.

The OCF wrapper should support the public command model:

```text
farfield list
farfield describe <preset>
farfield render <preset>
```

Where supported, expose reproducible seeds and JSON sidecars.

Do not promise psychoacoustic or health effects.

## Separation requirement

A background preset is not a function.

A background preset is not a training script.

A training script is not an audio render.

Model them independently so one OCF function can use several different backgrounds and one background can be reused by several functions.

---

# 15. AUDIO CONTRIBUTION WIZARD

`ocf new audio` must prompt for:

- function ID;
- implementation title;
- author;
- narrator;
- language;
- license;
- training type;
- duration;
- transcript/script path;
- induction method;
- background-audio strategy;
- background preset ID;
- canonical command rehearsal;
- legacy command rehearsal;
- compatibility mode;
- release sequence;
- safety language;
- sample rate;
- channels;
- format;
- loudness notes;
- checksum;
- accessibility transcript;
- test notes.

`ocf new background` must prompt for:

- background ID;
- title;
- author;
- engine;
- Farfield preset file;
- provenance;
- intended use;
- function associations;
- deterministic seed;
- output format;
- render notes;
- headphone note;
- safety notes;
- license/attribution.

---

# 16. CONTRIBUTION PROCESS

Use an RFC/PEP-style proposal model.

Statuses:

```text
draft
review
experimental
accepted
deprecated
superseded
rejected
withdrawn
```

Every new function proposal should address:

- problem;
- purpose;
- proposed name;
- command;
- command-length rationale;
- activation;
- release;
- persistence;
- safety;
- compatibility;
- evidence state;
- alternatives;
- implementation;
- testing;
- sources;
- licensing.

All 16 unavailable legacy functions should have a pathway to community reimplementation proposals.

Do not call these “missing functions” in the data model.

Use terminology such as:

```text
legacy source unavailable
OCF reimplementation planned
```

---

# 17. COMMAND QUALITY VALIDATION

Lint command design.

Flag:

- replacement longer than legacy command;
- more than three post-prefix spoken words;
- duplicate canonical commands;
- ambiguous collisions;
- missing PLUS prefix;
- inconsistent MORE/LESS pair;
- changed command without rationale;
- changed command without compatibility metadata;
- awkward punctuation;
- awkward invented compounds;
- mode asymmetry.

Required tests:

- THINK FAST remains `PLUS-THINK`;
- ATTENTION remains `PLUS-FOCUS`;
- directional sensory controls use MORE/LESS;
- longer replacement triggers a warning;
- duplicate canonical command triggers an error;
- all 55 legacy functions exist;
- 39 are marked source-available;
- 16 are marked source-unavailable;
- all 16 source-unavailable functions remain valid OCF reimplementation targets.

---

# 18. GENERATED INDEXES

Generate from YAML:

```text
FUNCTION_INDEX.md
function-index.csv
function-index.json
legacy/hplus-command-map.csv
legacy/hplus-command-map.json
docs/COMMAND_REVIEW.md
docs/AVAILABILITY_MATRIX.md
docs/REIMPLEMENTATION_ROADMAP.md
docs/SAFETY_MATRIX.md
docs/AUDIO_IMPLEMENTATION_INDEX.md
docs/BACKGROUND_AUDIO_INDEX.md
```

Indexes should show:

- OCF ID;
- canonical name;
- legacy name;
- canonical command;
- legacy command;
- domain;
- permanent/persistence state;
- legacy source availability;
- OCF reimplementation status;
- command review state;
- compatibility state;
- function file link;
- audio implementation count;
- background preset count.

Generated files must say:

```text
GENERATED FILE — DO NOT EDIT DIRECTLY
```

CI must fail when indexes are stale.

---

# 19. SAFETY AND CLAIMS

OCF should distinguish:

```text
source-described
community-hypothesis
anecdotal
experimental
externally-supported
unverified
```

Do not claim that:

- suggestion;
- meditation;
- binaural beats;
- Farfield presets;
- hypnosis;
- audio entrainment;
- any OCF function

guarantees a psychological, physiological, medical, paranormal, or behavioral result.

Health-oriented functions need a clear safety statement.

Emergency-oriented functions must explicitly say they do not replace:

- emergency services;
- first aid;
- poison control;
- medical evaluation;
- professional treatment.

---

# 20. DOCUMENTATION

Create polished:

## README.md

Include:

- project overview;
- independence disclaimer;
- current maturity;
- what OCF is;
- what OCF is not;
- legacy mapping concept;
- all 55 reimplementation targets;
- quick start;
- contributor wizard;
- function example;
- command philosophy;
- audio architecture;
- Farfield integration;
- **adding a function from timed lyrics** (§61 requires this walkthrough);
- **what is supported** (formats, authoring modes, backends, outputs);
- validation;
- testing;
- contribution path;
- safety;
- licensing;
- roadmap.

### v3 documentation additions

The following documents are created by the v3 sections and must appear in
README and `docs/USER_GUIDE.md`:

- `docs/TIMED_TRANSCRIPTS.md` — timed-lyrics/LRC import, canonical OCF timed
  YAML, sections, timing modes, exports (§32, §44–§46).
- `docs/STATE_AND_FOCUS_LEVELS.md` — state profiles and state-aware
  background programs (§47–§50).
- `docs/VOICE_BACKENDS.md` and `docs/VOICE_RECORDING_GUIDE.md` — TTS
  backends, stock vs reference voices, consent policy, recording guidance
  (§28–§31).
- `docs/AUDIO_SECTIONS.md` — reusable section templates (§46).
- `docs/MIXING_AND_MASTERING.md` — FFmpeg pipeline, ducking, formats (§35–§37).
- `docs/PREPARATION_MODULE.md` — the dedicated Preparation Module (§51–§54).

`README.md` must contain a plain-language walkthrough titled around "adding a
function from timed lyrics" and a "what is supported" summary table covering
every supported input format, authoring mode, speech/background backend, and
output format, plus each tool's status (implemented vs specified).

## CONTRIBUTING.md

Two workflows:

### Easy contributor path

```text
ocf new function
ocf new proposal
ocf new audio
ocf new background
```

### Advanced contributor path

Manual YAML, schema validation, tests, generated indexes, PR process.

## AGENTS.md

Future agents must:

- inspect schemas first;
- preserve legacy mappings;
- never fabricate source details;
- never hand-edit generated indexes;
- run tests;
- run validation;
- preserve short-command policy;
- keep PLUS-THINK;
- keep PLUS-FOCUS;
- use MORE/LESS for adjustable sensory modes;
- preserve all 55 initial functions;
- treat the 16 source-unavailable legacy functions as OCF reimplementation targets;
- keep Farfield integration optional;
- not vendor or reproduce copyrighted third-party audio;
- report unresolved ambiguity instead of guessing.

---

# 21. GITHUB AUTOMATION

Create workflows for:

- tests;
- Python linting;
- Markdown linting;
- schema validation;
- all-function validation;
- duplicate IDs;
- duplicate commands;
- generated index freshness;
- internal link checking where practical.

Use minimal permissions.

Do not require secrets.

---

# 22. IMPLEMENTATION QUALITY

Use:

- Python 3.11+;
- pathlib;
- type hints;
- docstrings;
- dataclasses where useful;
- clear exceptions;
- atomic file writes;
- deterministic output;
- UTF-8;
- modular code;
- minimal dependencies.

Core functionality should work on:

- Linux;
- macOS;
- Windows.

Bash is only a convenience wrapper.

Do not leave executable placeholders or TODO-only stubs.

---

# 23. TESTS

Use pytest.

At minimum test:

- CLI help;
- function wizard;
- proposal wizard;
- audio wizard;
- background wizard;
- schema validation;
- command validation;
- duplicate IDs;
- duplicate commands;
- generated indexes;
- source paths containing spaces;
- atomic writes;
- overwrite protection;
- doctor command;
- Farfield-not-installed behavior;
- Farfield command construction;
- deterministic background manifest generation.

Commands:

```text
python3 -m pytest
make test
make validate
make indexes
make check
```

---

# 24. LICENSING

Use a permissive license for original OCF code, preferably Apache-2.0 unless repository circumstances suggest otherwise.

Clearly distinguish:

- OCF code;
- OCF documentation;
- community-authored training scripts;
- community-authored audio;
- legacy factual metadata;
- third-party source material;
- Farfield dependency/license/provenance.

Do not redistribute copyrighted Monroe audio.

Do not reproduce full proprietary pamphlet text.

Keep attribution and NOTICE documentation clear.

---

# 25. EXECUTION ORDER

Do the work; do not merely plan it.

Proceed in this order:

1. Inspect the current directory.
2. Preserve existing files.
3. Detect provided references.
4. Create a concise internal implementation plan.
5. Scaffold repository.
6. Create schemas.
7. Implement models.
8. Implement validation.
9. Implement CLI.
10. Implement interactive wizards.
11. Implement Farfield wrapper.
12. Create all 55 legacy map records.
13. Create generated-index system.
14. Generate indexes.
15. Write docs.
16. Add GitHub templates.
17. Add CI.
18. Add tests.
19. Run tests.
20. Run validation.
21. Regenerate indexes.
22. Verify generated files are current.
23. Verify exactly 55 initial mappings.
24. Verify 39 source-available and 16 source-unavailable.
25. Verify all 16 source-unavailable entries are marked OCF reimplementation targets.
26. Verify PLUS-THINK.
27. Verify PLUS-FOCUS.
28. Verify MORE/LESS sensory grammar.
29. Verify Farfield integration degrades gracefully when Farfield is absent.
30. Produce a completion report.

Do not stop after creating the directory tree.

Do not ask for approval between routine steps.

Ask only when continuing could destroy existing work or when a decision truly cannot be represented as a draft/review-required state.

---

# 26. FINAL REPORT

When finished, report:

1. Summary.
2. Repository tree.
3. Number of mapped functions.
4. Count source-available.
5. Count source-unavailable.
6. Count planned for OCF reimplementation.
7. Commands retained unchanged.
8. Commands normalized.
9. Commands still requiring review.
10. Contributor wizard examples.
11. Farfield integration status.
12. How to install dependencies.
13. How to run tests.
14. How to validate.
15. How to regenerate indexes.
16. Test results.
17. Validation results.
18. Any unresolved design questions.

Do not claim success unless tests and validation actually pass.

---

# 27. SPOKEN-AUDIO BACKENDS, VOICE PROFILES, TIMED TRANSCRIPTS, AND FINAL MIXING

OCF must support a pluggable spoken-audio synthesis layer in addition to the Farfield background-audio layer.

The required architecture is:

```text
Function definition
        |
        +--> Training transcript / timed script
        |          |
        |          +--> Spoken-audio backend
        |                  |
        |                  +--> Voice / voice profile
        |                  +--> Rendered narration stem
        |
        +--> Background-audio backend
                   |
                   +--> Farfield preset
                   +--> Rendered background stem

Narration stem + background stem
        |
        +--> Mixer/mastering backend
                   |
                   +--> final WAV / FLAC / MP3 / M4A
                   +--> render manifest
                   +--> checksums
```

Do not couple OCF to one TTS engine.

Implement a backend interface so future engines can be added without changing function definitions or audio manifests.

Required initial spoken-audio backend types:

```text
openvoice
kokoro
piper
external-command
pre-recorded
```

## 27.1 Recommended backend roles

### OpenVoice V2

Support OpenVoice V2 as the initial OCF reference-voice / voice-cloning backend.

Upstream:

```text
https://github.com/myshell-ai/OpenVoice
```

Design assumptions:

- OpenVoice V1/V2 are MIT licensed upstream.
- It supports reference/tone-color voice cloning.
- It does not require OCF to train a brand-new speech model for every contributor.
- It should only be used for a contributor's own voice, a voice they have explicit permission/license to use, or another clearly authorized source.
- Treat it as optional and externally installed.
- Do not vendor model files automatically.

### Kokoro

Support Kokoro as an initial prebuilt selectable-voice backend.

Upstream:

```text
https://github.com/hexgrad/kokoro
```

Use it for contributors who want a high-quality stock/open voice without cloning.

The wrapper should:

- list locally available voices;
- display language/voice metadata;
- display available license/model information;
- optionally synthesize a short neutral preview;
- allow selecting a voice by stable backend-specific identifier;
- record backend and model version in the manifest.

### Piper

Support Piper as a lightweight/offline selectable-voice backend.

Use a maintained Piper distribution rather than hard-coding one historical repository URL forever.

The adapter must make executable/package location configurable.

Piper is especially useful for:

- CPU-only rendering;
- lightweight systems;
- multiple languages and voices;
- reproducible offline builds.

Every Piper voice must preserve its own model-card/license metadata because individual voice-model licenses may differ.

### Other engines

Other engines may be added through the generic backend API.

Do not make F5-TTS the default. Its code may be permissively licensed while commonly distributed pretrained weights can have non-commercial restrictions.

---

# 28. VOICE PROFILE MODEL

Create:

```text
audio/voices/
├── README.md
├── profiles/
├── manifests/
└── samples/
```

Add:

```text
schemas/voice-profile.schema.json
templates/voice-profile.yaml
docs/VOICE_BACKENDS.md
docs/VOICE_RECORDING_GUIDE.md
```

A voice profile is independent from a function and from an audio implementation.

Example reference/cloned voice profile:

```yaml
schema_version: "1.0"

id: "OCF-VOICE-0001"
name: "Example Contributor Voice"
backend: "openvoice"

owner:
  name: ""
  contributor_id: null

rights:
  source: "self-recorded"
  consent_confirmed: true
  permission_notes: ""
  redistribution_allowed: false

language:
  primary: "en-US"
  supported: []

reference:
  audio_file: "audio/voices/samples/OCF-VOICE-0001/reference.wav"
  transcript_file: "audio/voices/samples/OCF-VOICE-0001/reference.txt"
  sha256: ""
  duration_seconds: null

recording:
  sample_rate_hz: 48000
  channels: 1
  bit_depth: 24
  environment: "quiet room"
  microphone: null

backend_config:
  model: null
  model_version: null
  speaker_id: null
  options: {}

review:
  status: "draft"
  quality_notes: []
```

The same schema must support stock/selectable voices, for example:

```yaml
backend: "kokoro"
reference: null
backend_config:
  voice_id: "..."
```

---

# 29. VOICE CONSENT AND PROVENANCE POLICY

Voice cloning must be consent-based.

The contributor wizard MUST ask:

```text
Whose voice is this?

[1] My own voice
[2] A voice I have explicit permission/license to use
[3] A stock/open voice supplied by the selected TTS backend
```

Do not provide a workflow intended to clone a person without permission.

For option 2, require a permission/provenance note.

Do not require private consent documents to be committed publicly. Permit maintainers to record a private or externally verified provenance reference while the public manifest records that permission was verified.

Generated narration must not be falsely described as a live recording by a real person.

Where practical, generated output metadata should indicate that narration was synthesized.

---

# 30. INTERACTIVE VOICE WIZARD

Add commands:

```text
ocf voice list-backends
ocf voice doctor
ocf voice list
ocf voice new
ocf voice import
ocf voice record
ocf voice validate
ocf voice preview <voice-id>
ocf voice render <voice-id> --text "..."
```

Also make `ocf new audio` invoke voice selection automatically.

The wizard should ask:

```text
How should spoken narration be produced?

1. Select a built-in/open voice
2. Create a voice profile from my own recording
3. Import a voice profile I have permission to use
4. Use a pre-recorded narration file
5. Configure an external/custom TTS command
```

For a built-in/open voice:

- choose backend;
- detect installation;
- list voices;
- show language and license/model metadata;
- optionally render a short preview;
- save backend and voice ID.

For a personal/reference voice:

- explain recording requirements;
- allow recording directly when practical;
- otherwise accept WAV paths;
- validate audio;
- normalize only a working copy;
- preserve original sample;
- create transcript metadata;
- create checksums;
- create voice profile;
- run a test synthesis;
- let the contributor approve or retry.

---

# 31. VOICE SAMPLE RECORDING ASSISTANT

Create an interactive guided recording workflow.

The goal is to produce a clean reference sample for a backend such as OpenVoice, not to imitate another speaker.

Guide contributors toward:

- a quiet room;
- minimal echo/reverb;
- no music;
- no TV/fans/background speech;
- stable microphone distance;
- a natural, neutral speaking style;
- no clipping;
- lossless WAV preferred;
- mono working derivative permitted while preserving the original.

Do not hard-code a voice-reference duration unsupported by the selected backend. Store backend-specific recommendations in the backend adapter/documentation and show them dynamically.

Provide an original OCF recording passage, for example:

```text
Today I am recording a clear reference sample for Open Consciousness Functions.
My speaking pace is comfortable and steady. Some sentences are short, while
others are a little longer. I can speak softly, normally, and with clear
emphasis when needed. Numbers such as twelve, forty-seven, and one hundred
help capture different sounds. Questions change my intonation, don't they?
This sample is recorded with my permission for the voice profile I am creating.
```

Do not use copyrighted text as the default recording passage.

The recorder/validator should calculate where practical:

- duration;
- peak level;
- clipping warning/count;
- sample rate;
- channel count;
- SHA-256.

Use FFmpeg/ffprobe for inspection when installed.

If direct recording is not practical on the platform, provide clear instructions and accept a local file path.

---

# 32. TIMED TRANSCRIPT / SCRIPT FORMAT

OCF must support ordinary transcripts and precisely timed narration.

Supported inputs:

```text
plain Markdown          (import-only, see §44)
plain text              (import-only, see §44)
LRC timed lyrics        (import-only, see §44)
SRT                     (interoperability)
WebVTT                  (interoperability)
OCF timed YAML           (canonical editable format)
```

Use **OCF timed YAML** as the canonical editable timed format.

SRT/WebVTT are interoperability formats. LRC ("timed lyrics") is a widely
available lyric-style timestamp format used by many existing meditation
transcriptions; it is a first-class **import** source (§44) but never the
canonical editable format.

Do not use LRC as the primary format because OCF narration needs segment
duration, pause, gain, voice, and timing instructions beyond simple lyric
timestamps. Importers preserve the exact source text and timestamps and never
silently rewrite wording (§44).

A timed document may be a flat top-level `timeline` list (as in the example
below) or grouped into `sections`, each carrying its own `timeline`, for
preparation/installation/rehearsal/close roles (§45–§46, §48). The same
`schemas/timed-transcript.schema.json` must accept both shapes.

Create:

```text
schemas/timed-transcript.schema.json
templates/timed-transcript.yaml
docs/TIMED_TRANSCRIPTS.md
```

Example:

```yaml
schema_version: "1.0"

title: "Attention Training"

timeline:
  - id: "intro-001"
    at: "00:00:08.000"
    text: "Allow your breathing to become easy and natural."
    voice:
      profile: "OCF-VOICE-0001"
      rate: 0.94
      gain_db: 0
    timing:
      preferred_duration: 4.8
      maximum_duration: 6.0
      pause_after: 3.0

  - id: "install-001"
    at: "00:01:42.000"
    text: "The command is PLUS-FOCUS."
    voice:
      profile: "OCF-VOICE-0001"
      rate: 0.90
      gain_db: 0
    timing:
      pause_after: 5.0

  - id: "practice-001"
    after: "install-001"
    offset: 8.0
    text: "PLUS-FOCUS."
    timing:
      pause_after: 10.0
```

Support absolute `at` or relative `after` + `offset` placement.

Reject circular references.

---

# 33. TIMING BEHAVIOR FOR SYNTHESIZED SPEECH

Do not blindly accelerate speech to force every sentence into an arbitrary window.

Implement configurable modes:

```text
natural
fit-soft
fit-strict
timeline-shift
```

`natural`: render at normal backend speed and allow timeline growth.

`fit-soft`: default. Permit modest speed adjustment or high-quality time stretching within configured safe bounds. If still too long, report a conflict instead of producing unintelligible speech.

`fit-strict`: attempt to fit the interval and emit warnings when adjustment exceeds recommended bounds.

`timeline-shift`: preserve natural speech and shift subsequent relative events while retaining absolute anchors.

Store timing decisions in the render manifest.

---

# 34. TTS BACKEND INTERFACE

Implement an internal interface conceptually similar to:

```python
class SpeechBackend:
    def doctor(self) -> BackendStatus: ...
    def list_voices(self) -> list[VoiceInfo]: ...
    def synthesize(
        self,
        text: str,
        voice: VoiceProfile,
        output_path: Path,
        options: SpeechOptions,
    ) -> SpeechRenderResult: ...
```

Implement adapters for:

```text
OpenVoiceBackend
KokoroBackend
PiperBackend
ExternalCommandBackend
PreRecordedBackend
```

Core repository logic must not require heavyweight ML imports.

Backend-specific dependencies should remain optional and may be isolated through subprocesses.

If a backend is absent:

- explain that it is optional;
- show install/configuration guidance;
- keep all unrelated OCF commands functional.

---

# 35. AUDIO MIXING / MASTERING BACKEND

Use **FFmpeg** as the initial mixing/mastering backend.

Treat FFmpeg as an external dependency detected by `ocf doctor`.

Add:

```text
scripts/ocf_tools/mixer.py
docs/MIXING_AND_MASTERING.md
```

The pipeline must be able to:

1. render narration segments;
2. position them on a timeline;
3. generate or load Farfield background;
4. pad/trim stems safely;
5. optionally duck background beneath narration;
6. mix stems;
7. prevent obvious clipping;
8. produce a lossless master;
9. optionally produce distribution formats;
10. record render provenance.

Required final formats:

```text
WAV
FLAC
```

Optional when supported:

```text
MP3
M4A/AAC
Opus
```

Always support a lossless master.

---

# 36. BACKGROUND DUCKING

Support optional narration-aware background ducking.

Example:

```yaml
mix:
  narration_gain_db: 0
  background_gain_db: -9

  ducking:
    enabled: true
    reduction_db: 5
    attack_ms: 250
    release_ms: 1200
```

Do not alter intentional Farfield left/right relationships unless a preset explicitly permits it.

Do not collapse a stereo binaural background to mono during mixing.

---

# 37. FULL AUDIO BUILD MANIFEST

Create:

```text
schemas/render-manifest.schema.json
```

Example:

```yaml
schema_version: "1.0"

id: "OCF-RENDER-0001"
function: "OCF-FND-001"
audio_implementation: "OCF-AUDIO-0001"

script:
  file: "audio/scripts/attention-training.yaml"
  sha256: ""

speech:
  backend: "openvoice"
  backend_version: ""
  voice_profile: "OCF-VOICE-0001"

background:
  backend: "farfield"
  preset: "OCF-BG-0001"
  seed: 12345

mixer:
  backend: "ffmpeg"
  version: ""
  timing_mode: "fit-soft"
  ducking: true

output:
  master:
    file: "audio/rendered/attention-training-master.wav"
    sample_rate_hz: 48000
    channels: 2
    sha256: ""
  derivatives: []

reproducibility:
  created_utc: ""
  platform: ""
  command: ""
```

---

# 38. FULL AUDIO PIPELINE CLI

Add:

```text
ocf audio doctor
ocf audio render-speech SCRIPT
ocf audio render-speech SCRIPT --voice OCF-VOICE-0001
ocf audio render-background PRESET
ocf audio mix --speech narration.wav --background background.wav --output final.wav
ocf audio build OCF-AUDIO-0001
ocf audio build OCF-AUDIO-0001 --master
ocf audio build OCF-AUDIO-0001 --format flac
ocf audio build OCF-AUDIO-0001 --format mp3
ocf audio inspect FILE
```

`ocf audio build` is the high-level operation and should:

1. validate function;
2. validate script;
3. resolve voice;
4. render narration;
5. resolve/render background;
6. align narration;
7. mix/master;
8. compute checksums;
9. create render manifest;
10. print output paths.

---

# 39. AUDIO BUILD WIZARD

Extend `ocf new audio` so a nontechnical contributor can build an implementation interactively:

```text
Select function
    ↓
Select training-script template
    ↓
Write/import transcript
    ↓
Choose timed or natural narration
    ↓
Choose speech backend
    ↓
Choose/create voice
    ↓
Preview voice
    ↓
Choose background backend
    ↓
Choose/create Farfield preset
    ↓
Preview background
    ↓
Configure narration/background levels
    ↓
Render short preview
    ↓
Approve or adjust
    ↓
Render full lossless master
    ↓
Optionally render distribution formats
    ↓
Create manifest/checksums
```

A contributor should not need to know YAML or FFmpeg syntax.

Advanced users may edit manifests directly.

---

# 40. REPRODUCIBLE AUDIO BUILDS

Record where practical:

- transcript hash;
- speech backend/version;
- voice ID/profile hash;
- voice reference hash;
- Farfield preset hash;
- Farfield seed;
- FFmpeg version;
- mix parameters;
- output checksum.

Do not claim bit-for-bit reproducibility when a speech backend is nondeterministic.

Record backend determinism as:

```text
deterministic
best-effort
non-deterministic
```

---

# 41. AUDIO QUALITY REVIEW

Create a generated/reusable review checklist including:

- narration intelligible;
- no clipping;
- no missing words;
- no unexpected voice changes;
- command pronunciation checked;
- pauses appropriate;
- stereo background preserved;
- narration centered unless intentionally different;
- background does not mask spoken commands;
- no abrupt edits;
- fades intentional;
- transcript matches speech;
- timed anchors respected;
- legacy/canonical commands spoken correctly;
- output metadata/checksums generated.

---

# 42. TESTS FOR SPOKEN AUDIO ARCHITECTURE

Add tests for:

- backend registry;
- missing backend graceful failure;
- mocked OpenVoice synthesis;
- mocked Kokoro synthesis;
- mocked Piper synthesis;
- stock voice selection;
- reference voice profile validation;
- consent/provenance field validation;
- absent reference files;
- timed transcript parsing;
- SRT import;
- WebVTT import;
- relative timeline resolution;
- circular dependency rejection;
- timing conflict warnings;
- FFmpeg command construction;
- stereo-preserving mixing;
- ducking configuration;
- narration-only render;
- background-only render;
- complete build manifest;
- checksum generation;
- paths containing spaces;
- final lossless master using generated test tones/silence.

CI tests must not download multi-gigabyte ML models.

Mock heavyweight speech engines in CI.

When FFmpeg is unavailable, explicitly skip FFmpeg-dependent tests with a clear reason while keeping core tests passing.

---

# 43. UPDATED FINAL VERIFICATION

In addition to all previous verification requirements, verify:

- speech backends are pluggable;
- OpenVoice is represented as a consent-based reference/cloning option;
- Kokoro and Piper are represented as selectable stock/open voice options;
- pre-recorded narration is supported;
- external/custom TTS command backends are supported;
- voice profiles are independent objects;
- consent/provenance metadata exists for reference voices;
- timed OCF YAML works;
- SRT/WebVTT import works;
- Farfield backgrounds remain independent from narration;
- FFmpeg combines narration and background into a single output;
- lossless masters are supported;
- stereo is preserved;
- ducking is optional;
- render manifests record provenance;
- the CLI walks a nontechnical contributor through the complete build;
- missing optional ML backends do not break unrelated repository functionality.

---

# 44. TRANSCRIPT IMPORT: LRC, SRT, WEBVTT, AND TIMED TEXT

OCF must be able to bootstrap its canonical timed YAML from common timed-transcript formats.

Add first-class import support for:

```text
.lrc
.srt
.vtt
.txt
.md
```

Also permit importing an already-authored OCF timed YAML file.

Required commands:

```text
ocf transcript import FILE
ocf transcript import FILE --format auto
ocf transcript import FILE --output FILE.yaml
ocf transcript segment FILE
ocf transcript review FILE
ocf transcript export FILE.yaml --format srt
ocf transcript export FILE.yaml --format vtt
ocf transcript export FILE.yaml --format lrc
```

The importer should:

1. detect format by extension/content;
2. preserve source timestamps exactly in import metadata;
3. normalize timestamps into OCF's canonical timeline representation;
4. preserve the original source filename and SHA-256;
5. retain source text exactly in an import snapshot unless the user edits it;
6. never silently rewrite transcript wording;
7. create editable OCF YAML;
8. validate the result;
9. offer section assignment immediately after import.

LRC is especially important because many existing timed meditation transcripts are available in lyric-style timestamp form.

Support standard LRC metadata such as:

```text
[ti:...]
[ar:...]
[al:...]
[length:...]
[re:...]
```

Ignore unknown metadata safely while preserving it under `source_metadata`.

The importer must handle:

- centisecond timestamps;
- millisecond timestamps where present;
- repeated timestamps;
- blank lines;
- very long pauses;
- metadata before the first timed line;
- lines containing only numbers/counts;
- imperfect ASR transcripts.

Do not interpret transcription mistakes as authoritative content.

---

# 45. THREE AUTHORING MODES

OCF must support three authoring paths.

## 45.1 Import + review

Best for an existing timed transcript.

Flow:

```text
ocf transcript import Attention.lrc
    ↓
parse timestamps
    ↓
generate OCF timed YAML
    ↓
suggest section boundaries
    ↓
user reviews/edits boundaries
    ↓
assign focus/state metadata
    ↓
select reusable templates where appropriate
    ↓
retain function-specific material as editable/freeform
```

## 45.2 Guided template wizard

Best for nontechnical contributors creating an original OCF implementation.

Walk the contributor through standard section roles such as:

```text
Preparation / settling
Transition to learning state
Access / learning-channel opener
Function introduction
Function installation
Command teaching
Command rehearsal
Integration / reinforcement
Access close
Optional consolidation / sleep
Return / wake
Optional reminder / outro
```

These are semantic roles, not mandatory fixed wording.

Every section may be:

```text
template
custom
freeform
omitted
```

## 45.3 Advanced/freeform

Advanced contributors may directly edit the canonical timed YAML and create arbitrary sections, timing, voices, background states, and transitions.

The validator should enforce schema correctness and safety metadata but must not force every session into the standard template.

---

# 46. SECTION MODEL AND REUSABLE COMPONENTS

Add reusable section/component support.

Create:

```text
audio/templates/
├── preparation/
├── induction/
├── access-open/
├── function-intro/
├── installation/
├── rehearsal/
├── integration/
├── access-close/
├── consolidation/
├── sleep/
├── return/
└── outro/
```

Also create:

```text
schemas/audio-section.schema.json
templates/audio-section.yaml
docs/AUDIO_SECTIONS.md
```

A session can reference a reusable component:

```yaml
- id: prep-001
  type: preparation
  source:
    mode: template
    template_id: OCF-TPL-PREP-001
```

or use custom/freeform content:

```yaml
- id: install-001
  type: installation
  source:
    mode: freeform
  timeline:
    - at: "00:07:40.000"
      text: "..."
```

Reusable templates must be original OCF-authored material.

Do not place copied proprietary Monroe wording into reusable OCF templates.

Imported legacy/reference transcripts may be used locally by a contributor for structural analysis and source citation, but the repository should store only material that is lawful to redistribute.

---

# 47. FOCUS / STATE TIMELINE MODEL

OCF must explicitly model the mental/focus/state level associated with each timeline segment so the background-audio engine can generate state-appropriate audio for that period.

Do not hardcode the architecture to only one historical system.

Create a generic state system with named profiles.

Add:

```text
schemas/state-profile.schema.json
schemas/state-segment.schema.json
templates/state-profile.yaml
docs/STATE_AND_FOCUS_LEVELS.md
audio/states/profiles/
```

A state profile should define states such as:

```yaml
id: "OCF-STATEPROFILE-HPLUS-LEGACY-001"
name: "Legacy H-PLUS reference state map"
source_status: "reference-derived"

states:
  - id: waking
    label: "Waking"
    numeric_level: 1

  - id: focus-10
    label: "Focus 10"
    numeric_level: 10

  - id: access-11
    label: "Access / 11"
    numeric_level: 11

  - id: instruction-12
    label: "Instruction / 12"
    numeric_level: 12
```

IMPORTANT:

The exact names/meaning of legacy levels must be grounded in source material and marked `pending-source-review` where uncertain.

The software architecture should support the levels even before every semantic label is finalized.

A completely original OCF profile may use different state names while maintaining mappings where desired.

---

# 48. STATE-ANNOTATED TIMED YAML

Extend the timed transcript schema so every section/event may specify its state/focus level.

Example:

```yaml
schema_version: "1.0"

title: "Attention Training"
state_profile: "OCF-STATEPROFILE-HPLUS-LEGACY-001"

sections:
  - id: preparation
    type: preparation
    state:
      from: waking
      to: focus-10
    background:
      follow_state_profile: true

    timeline:
      - at: "00:00:20.000"
        text: "Original OCF preparation wording..."
        state: waking

      - at: "00:03:30.000"
        cue:
          type: state-transition
          target: focus-10

  - id: access-open
    type: access-open
    state:
      from: focus-10
      to: access-11

  - id: function-install
    type: installation
    state:
      from: access-11
      to: instruction-12

    timeline:
      - at: "00:07:45.000"
        text: "Function-specific installation text..."
        state: instruction-12
```

Allow state assignment at:

- session level;
- section level;
- individual timeline event level.

The most specific assignment wins.

---

# 49. STATE-DRIVEN BACKGROUND AUDIO

Farfield/background generation should be able to react to the state timeline.

Do not simply generate one static background file for the whole session unless requested.

Support a state-to-background mapping such as:

```yaml
background_program:
  backend: farfield
  state_profile: OCF-STATEPROFILE-HPLUS-LEGACY-001

  mappings:
    waking:
      preset: OCF-BG-WAKING-001

    focus-10:
      preset: OCF-BG-F10-001

    access-11:
      preset: OCF-BG-F11-001

    instruction-12:
      preset: OCF-BG-F12-001

  transitions:
    default_crossfade_seconds: 8.0
```

The renderer must be able to:

1. read the state timeline;
2. render or load the appropriate background for each state segment;
3. crossfade between state backgrounds;
4. preserve stereo/binaural relationships;
5. line up state transitions with narration cues;
6. generate a single continuous background stem;
7. mix narration only after the state-aware background stem is complete.

Where a Farfield preset encodes binaural parameters, OCF should preserve those parameters exactly rather than trying to reinterpret them.

Do not claim that a given state-specific audio preset causes a focus state as established fact.

Treat it as an implementation convention/design target.

---

# 50. IMPORT WIZARD STATE ASSIGNMENT

After importing LRC/SRT/VTT, the wizard must offer:

```text
How should focus/state levels be assigned?

1. Detect likely transitions and let me review
2. Walk me through each section
3. Apply a known state profile template
4. Leave states unassigned for now
5. Advanced/manual editing
```

For heuristic detection, the importer may look for obvious cues such as:

- numeric countdowns;
- explicit references to a numbered state;
- access-channel opening/closing language;
- sleep/return countdowns;
- long silence boundaries.

But all auto-detected assignments must be presented as suggestions requiring confirmation.

Never silently infer authoritative state semantics.

---

# 51. PREPARATION TRACK AS A FIRST-CLASS OCF ARTIFACT

OCF needs a dedicated Preparation training module because the preparation procedure is conceptually learned once and then reused before learning/using other functions.

Create a separate artifact type:

```text
Preparation Module
```

Add:

```text
preparation/
├── README.md
├── modules/
├── templates/
└── manifests/

schemas/preparation-module.schema.json
templates/preparation-module.yaml
docs/PREPARATION_MODULE.md
```

Assign stable IDs such as:

```text
OCF-PREP-0001
```

The preparation module must be separate from ordinary function records.

It may establish/rehearse reusable skills such as:

- settling physically;
- relaxation;
- setting distractions aside;
- entering the standard learning state;
- opening the function-learning/access state;
- recognizing state transitions;
- learning the general command-learning procedure;
- closing the learning/access state;
- returning to ordinary waking awareness.

The exact content should be based on original OCF wording.

Do not copy a proprietary preparation track into the repository.

---

# 52. PREPARATION MODULE SOURCE-REFERENCE WORKFLOW

The user/maintainer may later supply a timed transcription of an official preparation track as a **baseline research reference**.

OCF must provide an import workflow specifically for this use case:

```text
ocf preparation import-reference preparation.lrc
```

or:

```text
ocf preparation import-reference preparation.srt
```

This should:

1. import timestamps and text into a private/local reference object;
2. compute SHA-256;
3. preserve source metadata;
4. allow section segmentation;
5. allow focus/state annotation;
6. generate a structural analysis;
7. identify repeated structural components;
8. create an EMPTY/ORIGINAL OCF preparation-template scaffold based on roles/timing, not copied prose;
9. require a contributor to author or approve original OCF wording;
10. preserve citation/provenance of the structural reference.

The generated public OCF template should contain original text or placeholders, not copied source wording unless that wording is clearly lawful to redistribute.

---

# 53. PREPARATION MODULE WIZARD

Add:

```text
ocf new preparation
ocf preparation import-reference FILE
ocf preparation edit OCF-PREP-0001
ocf preparation validate OCF-PREP-0001
ocf preparation build OCF-PREP-0001
```

The guided wizard should ask:

```text
Preparation module title
Purpose
State profile
Starting state
Target learning/access state
Relaxation approach
Distraction-set-aside approach
State transition method
Access/opening wording
General command-learning explanation
Closing procedure
Return procedure
Optional sleep/consolidation section
Voice
Background program
Timing style
Safety notes
```

Then walk through each section separately.

Each section can be:

```text
use default OCF wording
edit default wording
write custom wording
import timed reference for timing only
advanced/freeform
omit optional section
```

The wizard must make it easy to create one high-quality default OCF preparation track while still allowing advanced authors full freedom.

---

# 54. PREPARATION INSTALLATION / DEPENDENCY MODEL

Functions may declare a preparation prerequisite.

Extend function metadata:

```yaml
training_requirements:
  preparation:
    required: true
    module: OCF-PREP-0001
    completion_model: learn-once
```

Support:

```text
learn-once
recommended-refresh
per-session
none
```

The initial H-PLUS-compatible OCF model should support `learn-once` as the default concept for the standard preparation module, while allowing maintainers to revise this based on source review.

An OCF audio implementation should be able to declare:

```yaml
assumes_preparation_installed: true
```

or:

```yaml
includes_preparation_refresh: true
```

This lets later function sessions remain shorter instead of repeating an entire preparation curriculum every time.

---

# 55. SESSION COMPOSITION TEMPLATES

Create reusable high-level session templates.

Examples:

```text
OCF-SESSION-FUNCTION-LEARN-001
OCF-SESSION-FUNCTION-REFRESH-001
OCF-SESSION-PREPARATION-001
OCF-SESSION-FREEFORM-001
```

A standard learn-function template might be conceptually:

```yaml
sections:
  - role: settle
  - role: transition-to-focus-10
  - role: open-access
  - role: transition-to-instruction-state
  - role: function-install
  - role: command-rehearsal
  - role: integration
  - role: close-access
  - role: return-to-focus-10
  - role: optional-consolidation
  - role: wake-return
  - role: optional-command-reminder
```

These roles must remain editable.

Do not force every future OCF function to use the historical H-PLUS sequence.

---

# 56. REFERENCE TRANSCRIPT ANALYZER

Add a structural analyzer for imported timed transcripts.

Command:

```text
ocf transcript analyze FILE
```

Output should include, where detectable:

- total duration;
- number of timed entries;
- longest silences/gaps;
- possible countdowns;
- possible state transitions;
- repeated passages;
- likely installation/rehearsal blocks;
- likely close/return blocks;
- possible command occurrences;
- candidate section boundaries.

This is a contributor aid, not an authoritative semantic classifier.

All findings must be labeled as suggestions.

A useful option:

```text
ocf transcript analyze FILE --interactive
```

should walk the user through accepting/rejecting each proposed boundary.

---

# 57. TIMING TEMPLATE EXTRACTION

Allow a contributor to create a reusable **timing-only template** from an imported reference transcript.

Command:

```text
ocf transcript extract-template FILE --timing-only
```

The generated template should contain:

- section roles;
- start/end times;
- state transitions;
- silence durations;
- placeholder slots;
- no copied transcript text by default.

Example:

```yaml
sections:
  - type: preparation
    start: "00:00:00.000"
    end: "00:03:18.000"
    text: null

  - type: state-transition
    target: focus-10
    start: "00:03:18.000"
    end: "00:06:31.000"

  - type: access-open
    start: "00:06:31.000"
    end: "00:07:40.000"

  - type: installation
    start: "00:07:40.000"
    end: "00:11:30.000"

  - type: integration-close
    start: "00:11:30.000"
    end: "00:12:50.000"
```

The exact boundaries must remain reviewable/editable.

---

# 58. FUNCTION-SPECIFIC AUDIO DIFFERENCES

The framework should explicitly recognize that most learned-function sessions may share a common structural shell while differing mainly in:

- function introduction;
- installation wording;
- command phrase;
- command activation procedure;
- rehearsal wording;
- function-specific safety notes;
- optional specialized state/background segments.

Model those differences as slots rather than requiring contributors to duplicate an entire session manually.

For example:

```yaml
session_template: OCF-SESSION-FUNCTION-LEARN-001

slots:
  function_intro: function-intro.md
  installation: install.md
  command_rehearsal: rehearsal.md
  closing_reminder: reminder.md
```

Advanced/freeform mode must still allow replacing any or all shared sections.

---

# 59. UPDATED CONTRIBUTOR EXPERIENCE

The ideal nontechnical workflow should look roughly like:

```text
$ ocf new audio

Select function:
> Attention

Preparation module:
> OCF standard preparation already assumed / learned once

How do you want to author this session?
  1. Guided standard function template
  2. Import LRC/SRT/VTT transcript
  3. Start from an existing OCF template
  4. Advanced/freeform
> 2

Transcript file:
> Attention.lrc

Detected format: LRC
Entries: ...
Duration: ...

Analyze possible sections? [Y/n]
> y

Review suggested boundaries...

Assign state/focus profile:
> Legacy-compatible H-PLUS reference profile

Review proposed state transitions...

Choose narration backend:
> OpenVoice / Kokoro / Piper / prerecorded / custom

Choose voice...

Choose background strategy:
> State-aware Farfield program

Generate preview? [Y/n]
> y

Build full session? [Y/n]
> y
```

---

# 60. UPDATED VALIDATION AND TESTS

Add tests for:

- LRC parsing;
- LRC metadata preservation;
- SRT import;
- WebVTT import;
- transcript-to-YAML conversion;
- timed YAML export back to LRC/SRT/VTT;
- section assignment;
- state profile validation;
- event-level state override;
- state transition ordering;
- background mapping by state;
- state-background crossfade planning;
- preparation-module schema;
- learn-once prerequisite metadata;
- timing-only template extraction;
- freeform sections;
- standard template sections;
- transcript analyzer heuristic output being explicitly marked suggestions;
- imported proprietary/reference text not automatically copied into public reusable templates.

Tests must not depend on proprietary source files.

Use synthetic fixtures.

---

# 61. UPDATED FINAL VERIFICATION

In addition to all previous final checks, verify:

- `.lrc` import works;
- `.srt` import works;
- `.vtt` import works;
- imported timing can generate canonical OCF timed YAML;
- contributors can choose guided, import/review, or advanced/freeform authoring;
- reusable session sections exist;
- sections may be overridden freely;
- state/focus levels are timeline-aware;
- background audio may change according to focus/state segments;
- state transitions align with narration timing;
- a dedicated Preparation Module exists as a first-class artifact;
- Preparation may be modeled as learned once;
- functions can declare preparation prerequisites;
- official/reference preparation transcripts can be imported locally for timing/structure research;
- timing-only structural templates can be generated without copying source prose;
- original OCF preparation wording can be authored through a wizard;
- standard function-learning sessions can reuse a common shell while keeping function-specific installation/rehearsal sections editable;
- advanced contributors can bypass all templates and author the full timeline manually;
- `README.md` contains a plain-language walkthrough for adding a function from timed lyrics (`.lrc`) and explains what each import format, authoring mode, backend, and output format supports;
- `docs/TIMED_TRANSCRIPTS.md` exists, is accurate, and contains a supported-formats/status matrix;
- no documentation claims a feature exists unless this specification requires it — the docs distinguish *implemented* from *specified / planned*;
