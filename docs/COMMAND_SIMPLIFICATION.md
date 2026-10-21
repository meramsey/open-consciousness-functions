# Confirmed command simplification

The twelve decisions were reviewed individually and authorized with **Confirm
implementation**. The [pinned successor](../function-content/editorial/command-simplification-001.json)
preserves exact predecessor files and resolved speech. It implements:

- Circulation: `PLUS-CIRCULATE` / Plus Circulate.
- Appetite Choice: `PLUS-SATISFIED` / Plus Satisfied.
- Heart Flow: `PLUS-HEART-FLOW` / Plus Heart Flow.
- Body Tune-Up: `PLUS-TUNE-UP` / Plus Tune Up.
- Injury Response: `PLUS-INJURY-RESPONSE` / Plus Injury Response.
- Toxic Exposure Response: `PLUS-TOXIC-CLEAR` / Plus Toxic Clear.
- Focus: title replaces Attention; `PLUS-FOCUS` / Plus Focus remains. Only the
  title-specific closing sentence changes in its narration.
- Coordination: `PLUS-COORDINATE` / Plus Coordinate.

Manifest, Dissolve and Intuition artwork descriptions retain their exact text
with reviewed status. Clear Zone uses the reviewed description “Set an intention
to discourage unwanted insects”. These four approvals concern artwork copy.

Baseline 008 accounts for exactly 15 changed entries and 162 unchanged entries
in the protected 177-entry cohort. Defaults lock 011 updates only the eight
narration dependencies; all DSP, pacing, template and background parameters and
previous lock revisions remain immutable. All function/command IDs, historical
legacy mappings, procedures, modes, lifecycle scopes and triggers are preserved.
Nutricia's separate Food More/Food Less commands are retained.

Earlier editorial verifiers first check and project this successor backward.
Changed resolved speech gets new normal synthesis/recording fingerprints;
original recordings are retained and are never relabelled as matching speech.
Editorial approval does not establish listening, rights or release approval.

## Private reference background overrides

Semantic DSP state selections accept an explicit local background manifest path
in addition to a registered ID/name. Local manifests use the existing background
schema; they do not register or replace global presets. A reference manifest may
declare `reference.preserve_precision: true` with no fixed splices to decode its
independent stereo state directly to 24-bit PCM. A declared
`provenance.reference_sha256` is checked before rendering. Originals are read-only.

`audio render-many ... --dsp-profile LOCAL_PROFILE.yaml --dry-run` validates the
complete-session override. Bulk resume binds the profile, complete manifests and
actual source hashes; changed beds cannot reuse an old completed render. Speech
cache identity remains independent. Required state stems must span the complete
measured session; short sources fail rather than silently looping or padding.

Explicit complete-session DSP overrides retain their profile identity as the
private edition's `background_variant` and `OCF_BACKGROUND_VARIANT` export tag.
Use a new private edition/output directory for a new background variant. Existing
audition editions and retained exports remain immutable.
