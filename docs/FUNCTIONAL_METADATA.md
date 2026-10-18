# Functional metadata and lifecycle scopes

The [current review](releases/OCF_FUNCTIONAL_METADATA_CURRENT.md) implements
18 explicitly approved decisions across 16 functions, after collection and final
confirmation. Five purposes, ten persistence/scope decisions, two conditional
responses and Nutricia's alternative command role are recorded in the
[metadata-only ledger](../function-content/editorial/functional-metadata-001.json).
Approved naming remains unchanged.

## Source authority and scope

Function YAML remains the authority for identity, purpose, lifecycle, commands,
procedures and narration bindings. Existing `lifecycle.persistence` remains the
function-level summary. Optional `lifecycle.scopes` separates:

- `capability`: lasting learned availability or readiness;
- `baseline`: ongoing development, adaptive maintenance or retained effects;
- `application`: one consciously invoked action or reinforcement;
- `episode`: a conditional, temporary response to an injury or exposure.

Each scope has a persistence value, canonical English `description`, stable
`description_key`, and optional descriptive activation value. Episode conditions
reference `lifecycle.trigger_conditions` rather than duplicating trigger text.
These declarations never evaluate a trigger, schedule an action, detect injury or
exposure, execute a cue, or control physiology.

`commands[].effect_scope_ref` accepts only the legacy `lifecycle.persistence`
or one of the four explicit scoped persistence paths. Missing and unknown
references fail validation. `invocation_scope_ref` may reference only
`lifecycle.scopes.application`, which must explicitly be manual. Command views
resolve the effect separately from invocation, so a lasting effect does not
imply a continuously running command.

Imprint's primary command retains the permanent storage effect; Plus Recall has
a temporary retrieval effect. Both invocations are manual and temporary. Habit
Freedom retains lasting selected-habit change, with a discrete intervention.
Other adaptive-baseline functions use temporary manual reinforcement. Options
and Information Access retain temporary selected applications alongside lasting
capability and background development.

Injury Response and Toxic Exposure Response use conditional function activation,
explicit descriptive trigger conditions, permanent readiness, temporary episodes,
and optional manual reinforcement. Their existing narration is unchanged.

Nutricia retains both Food More/Food Less cues and IDs. Food Less is a `mode`,
paired with Food More, rather than a decrement modifying a primary intensity.
Its role/usage descriptions and current compatibility explanation reflect that
distinction; historical mappings remain intact.

## Interfaces and localization

Rich CLI discovery exposes `lifecycle` independently of the historical
`activation` command-list field. Shared command views expose `effect_scope`,
optional `effect_scope_details` and `invocation_scope`. Compact MCP function
lookup additionally supports `purpose`, `lifecycle` and `command_metadata`.
These are additive response fields; no service restart or configuration change
is required by the repository migration itself.

The schemas and shared validators also supply LSP property completion and
diagnostics, including unsaved malformed references. English scope descriptions
must agree with function YAML. Command documentation resolves their stable locale
keys with explicit UI fallback provenance. Other languages may use their own
reviewed terminology; spoken cues retain the existing strict fallback and
symbolic-reference rules. No PLUS translation or production translation is added.

## Integrity and reproducibility

No narration changes are authorized: all 177 protected resolved entries and raw
narration resources remain unchanged. The existing text fixture 005 and defaults
lock 006 stay current; there is no new audio baseline. The metadata successor
pins the confirmed decision set, exact predecessor/current files, all engineering
dependencies and all 55 generated source plans. Historical naming verifiers use
the authenticated predecessor view, without rewriting older ledgers.

Speech cache inputs and recording fingerprints remain unchanged. Existing stale
recordings still fail their normal checks; this migration does not relabel audio
or change hybrid fallback policy. DSP, measured anchors, pacing, gains and body
repetitions remain unchanged.

```bash
python scripts/tools/current_functional_metadata.py --check
python scripts/tools/check_hplus_narration_integrity.py
python scripts/ocf.py functions describe OCF-COG-004 --rich --json
python scripts/ocf.py commands describe OCF-CMD-COG-004-RECALL --json
```
