# Function content and provenance

Every function identity has exactly one canonical locale YAML resource at
`locales/<tag>/OCF-*.yaml`. The complete English catalog contains 58 such
resources. Identity, commands, lifecycle, narration, safety, editorial state,
provenance metadata, analysis and runtime references are embedded there.
`FunctionRecord` and rich CLI/API views are read-only projections.

Function-specific evidence, specification, decisions and bindings are embedded
under the canonical resource's `content` mapping. Their semantic distinctions
remain explicit, but there are no function-content sidecar files and narration
order is derived only from the canonical `narration.sequence`. The only remaining
shared function-content input is `function-content/command-procedures.yaml`.

`source-fact`, `structural-inference`, `function-specification-inference`,
`ocf-design-choice` and localized expression are distinct. Evidence claims are
about a document unless explicitly historical; historical assertions require
authenticated source records. Mockups cannot authenticate themselves. Runtime
bindings cannot inject historical facts. Cross-layer identities/references and
actual locale/template availability are checked by `validate --all`.

The 55 evidence-backed functions retain **complete available-evidence analytical
reviews** inside their canonical locale resources. Completion requires every analytical question, a full inspected source
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
Missing durations, requirements and compatibility remain null/unknown. Embedded
locale bindings indicate available draft resources, not approval or scientific evidence.

## Source-first working authoring (planned CLI)

[Source-first authoring](SOURCE_FIRST_AUTHORING.md) defines a separate local
workspace: immutable SOURCE → exact initial WORKING → HUMAN edits → explicit
RELEASE → measured timing. The content CLI described there is planned, not part
of the shipped sidecar validation/discovery described above. Its workspace review
and release statuses do not replace existing schema fields or analytical reviews.

Existing hash-addressed analytical locators seed **CANDIDATE** semantic block
boundaries only. A complete analytical review does not validate original section
order, approve narration, or authorize rewriting. Preserve exact selected text,
ranged source extents and originating locators for referenced shared blocks.
Shared source/working registry chunks remain local and are not packaged.

Claims, accessibility concerns, transcript uncertainty and proposed corrections
are separate review metadata. They never trigger automatic source rewriting;
human edits need no paraphrasing, distancing or automatic originality gate.
Release narration must satisfy the release claims/accessibility contract and
explicit text-hash approval with recorded rights clearance. Rights gate
release/package inclusion, not working edits; source availability is not clearance.

Preserve `previous_candidates` paths as review context, never automatic runtime
choices. This workflow does not change the 55 legacy mappings, the 16
source-unavailable planned reimplementations, Attention scripts, existing
candidates, RC1, frozen pilots or V2/V2.1 DSP/audition decisions. Draft preview is
untimed textual review, not final audio or a measured timing source.
