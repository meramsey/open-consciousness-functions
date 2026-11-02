# Explicit narration revisions and affirmation selection

A session template may select a `narration_revision`. Composition carries that
identity into the timed document, and strict locale resolution selects only
resources registered for that revision in the requested spoken language. Repeated
resolution retains the selection. Templates without a revision keep their
existing resources and behavior.

The locale manifest registers a revision using the existing resource list:

```yaml
resources:
  - file: routine-successor.yaml
    domain: narration
    revision: EXAMPLE-ROUTINE-002
```

Revision files use the ordinary locale-resource schema. A selected file must
contain nonempty narration entries; missing, empty, wrong-domain or unavailable
language resources fail before synthesis. Unselected resources do not override
the canonical pack. Old wording can therefore remain available to frozen
templates without duplicating a current authority.

## Affirmation choices

`session compose --affirmation` accepts `none`, `Gateway`, `SyncCreation`,
`OCF` or `custom`. Named choices reference localized narration keys; this core
change does not distribute supplied preset speech or activate a new preparation
template. A locale must provide the selected, appropriately authorized words.
No choice silently selects the OCF preset or falls back to English.

For revisioned routines, omitted selection with no custom input means none:
the whole optional stage, its wrappers and its practice interval are absent.
Explicit none also removes the stage. Older templates retain their existing
explicitly enabled-stage behavior, including strict missing-resource errors.
Legacy explicitly enabled custom slots remain supported.

A selected named preset speaks introduction, exactly one preset and conclusion.
Custom requires explicit nonempty text; `--slot affirmation=FILE` supplies it.
`--custom-affirmation-locale` must match the requested session locale. Custom text
is literal data, not executable template syntax. Conflicting preset/custom input,
unknown selections and non-strict fallback requests fail before synthesis.

The structured authoring API exposes the same selection. Complete-session APIs
accept `affirmation`, `custom_affirmation` and `custom_affirmation_locale`
overrides while retaining explicit function/template binding checks. The only
custom inline exception is the selected affirmation practice event.

Private recordings, private profiles, supplied preset wording and private audio
are not included. No public voice, pacing, DSP or template default is changed.
Wording availability does not establish rights, source authenticity, listening
approval or release authorization.
