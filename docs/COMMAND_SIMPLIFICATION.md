# Confirmed command presentation decisions

The reviewed command and title decisions are part of the canonical locale
function resources under `record_metadata.editorial_decisions`. Current titles,
display cues, spoken cues, procedures, lifecycle semantics, and narration are
read from the same per-locale resources used at runtime. Decision hashes retain
approval provenance without keeping predecessor YAML or narration copies.

The implemented presentation includes:

- Circulation: `PLUS-CIRCULATE` / Plus Circulate.
- Appetite Choice: `PLUS-SATISFIED` / Plus Satisfied.
- Heart Flow: `PLUS-HEART-FLOW` / Plus Heart Flow.
- Body Tune-Up: `PLUS-TUNE-UP` / Plus Tune Up.
- Injury Response: `PLUS-INJURY-RESPONSE` / Plus Injury Response.
- Toxic Exposure Response: `PLUS-TOXIC-CLEAR` / Plus Toxic Clear.
- Focus is titled Focus; `PLUS-FOCUS` / Plus Focus remains.
- Coordination: `PLUS-COORDINATE` / Plus Coordinate.

Manifest, Dissolve, Intuition, and Clear Zone retain reviewed artwork copy in
their canonical locale resources. These decisions do not imply listening,
rights, or release approval. Approved narration integrity and semantic
equivalence are checked by the path-free fixtures and canonical validators;
there is no predecessor replay at runtime.

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
