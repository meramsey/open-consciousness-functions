# Canonical narration cue references

Each `locales/<tag>/OCF-*.yaml` resource owns that function's exact local cue
wording and narration entries. Its `narration.sequence` declares authorized
resource keys, order, roles, and repetitions. Command controls and lifecycle
semantics are in the same resource. No legacy function YAML, cue preview file,
or replay ledger is loaded as a fallback.

## Strict template contract

An entry may use explicitly approved symbolic references instead of copying a
cue into narration:

```yaml
entries:
  hplus.function.ocf-slp-005.closer:
    status: reviewed
    version: 1.2.1
    cue_template:
      function_id: OCF-SLP-005
      allowed: [cue.primary]
    text: |-
      Think or say in your mind, "{{ cue.primary }}."
```

The key must occur in the owning function's narration sequence. `allowed` must
list exactly the distinct symbols used, with no duplicates. Supported selectors
include `cue.primary`, role-specific mode/release/cancel/close/retrieval cues,
`cue.id.OCF-CMD-…` for an explicit active command owned by the same function,
and `function.title` for localized title text. A reviewed `.variant.NAME` suffix
selects only a declared variant. Labels and explanations are never spoken cue
fallbacks.

Malformed, unresolved, inactive, ambiguous, cross-function, or unreviewed cue
references fail validation. Literal braces use `\{` or `\}`; final speech may not
contain unexpanded template markers. Templates cannot evaluate code, access
environment/filesystem/network state, or accept caller-supplied ICU variables.

## Resolution and integrity

`LocaleCatalog.resource` returns effective text plus provenance. Raw template
hashes and resolved-text hashes are distinct. Resolution happens before
segmentation, pronunciation, TTS/cache identity, and recording fingerprints.
Final rendering, recording selection, and transcripts reject unresolved tokens.
Cue pronunciation hints follow the selected canonical command; conflicting hints
require an explicit reviewed variant.

All 58 canonical function structures, narration entries, commands, lifecycle
values, and English title/cue presentation are covered by the path-free semantic
baseline. The 177 protected spoken entries have a separate resolved-text
baseline. These checks verify current canonical bytes; no predecessor content is
reconstructed at runtime. Audio defaults locks and prior recording files remain
immutable, and technical validation is not listening or release approval.

Spanish remains explicitly partial; missing speech is never silently inherited.
Edit the owning locale resource and validate the locale rather than generating
comment banners or copying another locale's narration.

```bash
python scripts/ocf.py functions describe OCF-SLP-005 --rich --json
python scripts/ocf.py narration validate OCF-SLP-005 --locale en-US
python scripts/tools/check_hplus_narration_integrity.py
```
