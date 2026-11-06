# Per-locale function authority (Option A)

## Migration contract

The en-US manifest establishes stable function identities. Each complete locale
function resource owns its words, cues, command controls, lifecycle, classification
and narration sequence. Filenames are not translated identity contracts.
Translations do not inherit English spoken cues or narration. Shared session
preparation remains a separate reusable resource.

The existing `FunctionRecord` interface remains a read-only compatibility view,
not an additional editable registry. Historical identity and approved provenance
are embedded as non-authoritative metadata in each locale resource. Runtime
resolution never reads historical function YAML or separate function content
files. Structural contracts are generated from canonical en-US resources.

## Field migration map

| Existing structural field | Classification | New authority / treatment |
| --- | --- | --- |
| id | invariant | existing function_id |
| slug | invariant lookup | locale slug |
| canonical.name, purpose.summary | localized | existing title, description; no copied editable value |
| canonical.command | localized command identity | activation/secondary display cues; stable command IDs retained |
| commands.id/function_id | invariant | existing command_id plus enclosing function_id |
| commands.role/designation/availability/documentation | active behavior | per-command control |
| commands.procedure/effect_scope_ref/invocation_scope_ref/relationships | active behavior | per-command control, with local ordered instruction wording |
| commands.localization | derived | stable projected UI keys; literal local command values remain authority |
| commands.spoken/spoken_review | localized | existing spoken_cue text/status, never inherited |
| commands.observed_phrase, command_phrases | historical evidence | immutable predecessor records, keyed by stable command identity |
| lifecycle | active behavior | locale lifecycle, including scopes, trigger and release semantics |
| classification | invariant IDs/localized labels | locale classification; IDs compared across locales |
| tags/use_cases | localized discovery | existing tags/common_uses; semantic tag IDs added without changing labels/status |
| companions | reviewed relationships | derived from existing approved related_functions |
| narration.sequence | active behavior | locale narration sequence; keys/order/repetition/variables unchanged |
| safety | active guidance | locale safety; original classifications and wording preserved |
| audio | active engineering configuration | locale audio; no audio generation or status promotion |
| version | identity history | locale function_version; original values retained |
| legacy/aliases/historical_lookup/compatibility | historical identity | embedded non-active metadata; no predecessor source lookup |
| status/ocf/sources/claims/attribution/history | historical/editorial | embedded metadata, distinct from runtime behavior and approval |
| documentation keys | derived compatibility | generated from stable function/command IDs and existing local metadata keys |
| empty applications/chains/incompatible_functions/contributor | obsolete scaffolding | omitted; no empty editable boilerplate or duplicate archive |

The before inventory includes all 58 records and 147 observed leaf paths. Git
history remains the recovery mechanism for predecessors; no archived function
definition participates in current resolution.

### Immutable audio-default provenance

The immutable `audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-001.json` through
`...-015.json` locks are preserved byte-for-byte. Their 825 historical
`locales/en-US/hplus-OCF-*.yaml` dependency keys are hash-bound provenance, not
function definitions and not paths that runtime resolves or reads. When a
historical key's file is absent, audio-default verification may match its
stable function ID to the canonical resource's recorded predecessor digest;
it does not open or restore a retired YAML file. Do not edit these historical
locks or create successor locks as part of the single-source migration. The
active function catalog, authoring, validation, and session-plan paths use the
locale manifest and canonical locale resources only.

## Locale completeness

Completeness is explicit: complete, partial, missing or needs-review. Missing
translations are reported rather than synthesized. Existing Spanish shared
templates remain partial; absence of complete Spanish function definitions is
not permission to copy English speech. Structural drift identifies affected
locale resources without modifying translated text.

## Reader and audit editions

Listener guides contain exact useful cues, procedures, function-specific safety,
tags/uses, clearly labeled relationships and complete readable narration. Internal
keys, source paths, repeated status/version/provenance and implementation labels
belong in a separate generated developer audit document, not every reader PDF.
