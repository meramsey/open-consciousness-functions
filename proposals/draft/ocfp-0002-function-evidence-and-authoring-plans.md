# OCFP-0002: Separate function evidence, specifications and runtime bindings

- Status: draft (additive implementation; content review remains pending)
- Date: 2026-10-02

Existing function YAML remains the authority for identity, command ownership,
display/purpose metadata, safety and historical compatibility. Add independent
documents under `function-content/{evidence,specifications,decisions,bindings}/`.
Evidence addresses local sources by SHA256 and records documentary observations;
specifications contain operations and explicit unknown/not-present/inferred states;
decisions record OCF choices/claim transformations; bindings reference existing
session templates and locale resources without redefining provenance. None
duplicates or replaces locale wording. No canonical command or state identity changes.

Schemas reject mockup authentication, undeclared provenance fields and invalid
cross-document references. Historical assertions cannot cite only a reconstruction
or an OCF decision. Categorical confidence replaces invented numeric precision.
Machine extraction is visibly partial/candidate until source review establishes
operations. Equivalent-format content hashes identify shared representations,
not independently authenticated evidence or semantic equality.

Discovery exposes unknown values honestly. A separate authoring-plan schema lets
agents validate deterministic template/locale/voice/DSP choices without pretending
to understand natural language, invent new wording or promote frozen draft content.
Existing raw `functions --json` output stays compatible; richer discovery is opt-in.
Research/schema status is independent of listener approval and implementation quality.
