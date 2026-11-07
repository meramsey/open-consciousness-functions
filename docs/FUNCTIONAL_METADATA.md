# Functional metadata and lifecycle scopes

The [current review](releases/OCF_FUNCTIONAL_METADATA_CURRENT.md) is a derived
reader view of 18 explicitly approved decisions across 16 canonical locale
function resources. Decision notes, review-source hashes, current-value hashes,
and function-specific purpose/lifecycle changes are embedded in the matching
resource under `record_metadata.editorial_decisions`. There is no metadata
sidecar registry.

Each `locales/<tag>/OCF-*.yaml` resource remains the sole function authority for
that identity and locale. The shared schema and validators preserve the
distinctions among:

- `capability`: lasting learned availability or readiness;
- `baseline`: ongoing development, adaptive maintenance, or retained effects;
- `application`: one consciously invoked action or reinforcement;
- `episode`: a conditional, temporary response to an injury or exposure.

Each scope declares persistence, a stable localized description, and optional
descriptive activation. Episode conditions refer to
`lifecycle.trigger_conditions` rather than duplicating trigger text. These
declarations never evaluate triggers, schedule actions, detect injury or
exposure, execute cues, or control physiology.

Command controls use canonical `activation` and `secondary_commands` entries.
They distinguish effect scope from invocation scope: a lasting effect does not
imply a continuously running command. Injury Response and Toxic Exposure
Response retain conditional descriptive triggers, permanent readiness, temporary
episodes, and optional manual reinforcement. Their approved narration is
unchanged.

Nutricia retains Food More/Food Less identities and cues. Food Less is a mode
paired with Food More, not a decrement of primary intensity. Options and
Information Access retain temporary selected applications alongside lasting
capability and background development.

## Interfaces, localization, and integrity

CLI, API, MCP, LSP, command views, and guides expose read-only projections from
canonical locale resources. Missing translations remain explicit; English speech
is never inherited silently. Locale validation checks cue and scope descriptions
against stable keys.

All 177 protected resolved narration entries remain covered by the path-free
text-hash fixture. The canonical semantic baseline separately covers the 58
functions' structure, narration entries, commands, lifecycle, and localized
presentation. No audio was rendered; DSP, measured anchors, pacing, gains, and
body repetitions were not changed.

```bash
python scripts/tools/current_functional_metadata.py --check
python scripts/tools/check_hplus_narration_integrity.py
python scripts/ocf.py functions describe OCF-COG-004 --rich --json
python scripts/ocf.py commands describe OCF-CMD-COG-004-RECALL --json
```
