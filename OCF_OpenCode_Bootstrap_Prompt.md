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
│   ├── AUDIO_STANDARD.md
│   ├── BACKGROUND_AUDIO.md
│   ├── COMMAND_GRAMMAR.md
│   ├── COMPATIBILITY_POLICY.md
│   ├── DESIGN_SPEC.md
│   ├── EVIDENCE_AND_CLAIMS.md
│   ├── FUNCTION_LIFECYCLE.md
│   ├── NAMING_GUIDELINES.md
│   ├── PROJECT_TERMINOLOGY.md
│   ├── SAFETY_POLICY.md
│   ├── SUBMISSION_GUIDELINES.md
│   ├── SOURCE_ATTRIBUTION.md
│   └── USER_GUIDE.md
├── schemas/
│   ├── function.schema.json
│   ├── proposal.schema.json
│   ├── audio-implementation.schema.json
│   └── background-audio.schema.json
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
│   ├── background/
│   │   ├── README.md
│   │   ├── presets/
│   │   ├── manifests/
│   │   └── rendered/
│   └── tools/
├── references/
│   └── README.md
├── templates/
│   ├── function.yaml
│   ├── proposal.md
│   ├── audio-script.md
│   ├── audio-manifest.yaml
│   ├── background-audio.yaml
│   ├── testing-report.md
│   └── source-review.md
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
- validation;
- testing;
- contribution path;
- safety;
- licensing;
- roadmap.

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
