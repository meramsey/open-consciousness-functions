# Function content and provenance layers

Shipped validation/discovery for additive sidecars (OCFP-0002 draft). Existing
function YAML remains authoritative identity/display/purpose/activation/pronunciation
ownership metadata; no legacy format or command was changed.

| Layer | Authority |
| --- | --- |
| `function-content/evidence/` | SHA-addressed source class/authentication/completeness; documentary observations and categorical confidence |
| `function-content/specifications/` | Extracted operations, state/preparation requirements, block status and unresolved questions |
| `function-content/decisions/` | OCF design choices/claim transformations, material change and human review |
| `function-content/bindings/` | Runtime session/locale/voice references and known duration, never historical provenance |
| `locales/` | Localized expression and pronunciation, never source facts or semantic identity |

`source-fact`, `structural-inference`, `function-specification-inference`,
`ocf-design-choice` and localized expression are distinct. Evidence claims are
about a document unless explicitly historical; historical assertions require
authenticated source records. Mockups cannot authenticate themselves. Bindings
cannot inject historical fields. Cross-layer identities/references and actual
locale/template availability are checked by `validate --all`.

All55 initial sidecar sets are **partial research records**, not completed semantic
specifications. Keyword line candidates are low-confidence structural inference;
they do not establish a function's operations or runtime state. Unknown,
not-present, not-applicable and inferred are different statuses. The initializer
refuses to overwrite customized records. It authors no English narration and
changes no frozen pilot or RC1 content.

`functions list|describe --rich --json` exposes these capabilities using
`schemas/function-discovery.schema.json`. `build-index` adds the same capabilities
to generated JSON while retaining existing CSV and raw CLI output compatibility.
Missing durations, requirements and compatibility remain null/unknown. A locale
binding indicates available draft resources, not approval or scientific evidence.
