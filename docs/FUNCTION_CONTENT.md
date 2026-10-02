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

The initial55 partial sidecars now have **complete available-evidence analytical
reviews**. Completion requires every analytical question, a full inspected source
extent, substantive answers (including investigated unknowns) and hash-addressed
line/page locators. It does not authenticate historical recordings, bind runtime
states or approve narration. Keyword candidates are preserved separately and do
not establish absence. Unknown/not-present/not-applicable/inferred remain distinct.
The initializer refuses customized-record overwrite; the review applicator consumes
manually authored analysis, never keyword-derived semantics. No final narration or
frozen pilot/RC1 wording changes. See[review matrix](FUNCTION_EXTRACTION_REVIEW.md).

`functions list|describe --rich --json` exposes these capabilities using
`schemas/function-discovery.schema.json`. `build-index` adds the same capabilities
to generated JSON while retaining existing CSV and raw CLI output compatibility.
Missing durations, requirements and compatibility remain null/unknown. A locale
binding indicates available draft resources, not approval or scientific evidence.
