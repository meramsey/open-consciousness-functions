# Per-locale function authority (Option A)

## Migration contract

The en-US manifest establishes stable function identities. Each complete locale
function resource owns its words, cues, command controls, lifecycle, classification
and narration sequence. Filenames are not translated identity contracts.
Translations do not inherit English spoken cues or narration. Shared session
preparation remains a separate reusable resource.

The existing `FunctionRecord` interface remains a read-only compatibility view,
not an additional editable registry. Historical provenance is immutable and may
be read separately; active behavior comes from the locale resource. Structural
contracts are generated from canonical en-US resources, not a hand-edited index.

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
| legacy/aliases/historical_lookup/compatibility | historical identity | immutable history reference; no second active word authority |
| status/ocf/sources/claims/attribution/history | historical/editorial | exact immutable source, separately exposed in audit views |
| documentation keys | derived compatibility | generated from stable function/command IDs and existing local metadata keys |
| empty applications/chains/incompatible_functions/contributor | obsolete scaffolding | archival preservation; no empty editable boilerplate in active locale files |

The before inventory includes all 58 records and 147 observed leaf paths. The
private continuity audit retains the complete field-by-function matrix and exact
predecessor hashes. Historical files and locks must not be rewritten to make a
new source appear equivalent.

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
