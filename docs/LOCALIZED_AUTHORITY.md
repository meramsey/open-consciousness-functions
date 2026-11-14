# Per-locale function authority — completed migration

The approved single-source migration is implemented. Each supported locale has
at most one complete function YAML per stable function ID; the current en-US
catalog has 58. Canonical resources are manifest-listed under
`locales/<tag>/OCF-*.yaml`.

Each resource owns its localized function words, stable command identifiers,
command controls and procedures, lifecycle, narration text/order/repetitions,
classification, safety, tags/uses, relationships, editorial state, provenance
metadata and function-specific content metadata. `FunctionRecord`, discovery,
CLI/API/MCP/LSP views, plans and reader guides are derived read-only projections.

The `content` object preserves evidence, analysis, decisions and binding semantics
without maintaining a second file for each function. Evidence retains hashes,
authentication labels, locators and review notes; it does not copy referenced
source or transcript text. Narration order is read only from `narration.sequence`;
an API compatibility view may expose a derived binding `narration_plan`, but it
is not stored independently. Shared procedures and reusable session/audio
templates remain separate only when they serve multiple functions.

## Completeness and speech

Locale completeness is `complete`, `partial`, `missing` or `needs-review`.
Missing translations are reported, never fabricated. Spanish remains partial;
there is no English spoken-cue or narration inheritance. Cue-template raw and
resolved-text hashes remain distinct.

## Reader outputs

Command and function indexes link to the canonical en-US YAML resource. Detailed
function sheets are available on demand through `ocf commands describe`; they
are not tracked as 58 generated copies. Portable listener-guide editions are
generated as self-contained release artifacts in new output paths and are not
overwritten. Guide generation is not listening approval or release approval.

## History and recovery

Previous versions are recoverable from ordinary Git history. Current runtime
function loading does not consult prior function YAML or archived locale copies.
Old versioned migration/review ledgers are historical records, not current
authoring sources. Historical verification that requires a prior revision must
read the exact Git object and verify its recorded hash; it must not recreate an
alternate source tree in the current checkout.
