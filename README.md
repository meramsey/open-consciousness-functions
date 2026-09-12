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
  via the [Farfield](https://github.com/txus/farfield) engine.

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

Audio is modeled independently from functions:

```
function capability  ->  training script  ->  audio implementation
                                          ->  optional background preset
```

see `docs/AUDIO_STANDARD.md`, `docs/BACKGROUND_AUDIO.md`.

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