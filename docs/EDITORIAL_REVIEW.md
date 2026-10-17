# Title–cue decisions and historical audit review

## Current implemented decisions

The approved vocabulary now has a structural successor using
[function-owned spoken cues and strict narration references](SYMBOLIC_CUES.md).
This changes raw templates, not approved resolved speech. Source-pinned historical
reports and approval ledgers remain evidence of their original revisions.
The local interactive queue records one explicit decision at a time; context
requests and silence never authorize edits.

The [current decision sheet](releases/OCF_TITLE_CUE_CURRENT.md),
[machine-readable current view](releases/OCF_TITLE_CUE_CURRENT.json),
[current teaching status](releases/OCF_TEACHING_CURRENT.md),
[source-English terminology sheet](releases/OCF_EN_US_TERMINOLOGY.md) and
[historical lookup guide](releases/OCF_HISTORICAL_LOOKUP_CURRENT.md) reflect
`OCF-EDITORIAL-TITLE-CUES-001`. Nine selected pairs, Detox and the requested
heart cue are implemented. Heart Flow remains tentative; Heart Renewal and the
Body Cleansing/Body Cleanse proposals are rejected/superseded. All other unselected
vocabulary remains pending. No HPLUS identity migration is implemented.

```bash
python scripts/tools/approved_cue_migration.py --check
python scripts/tools/current_title_cues.py --check
python scripts/ocf.py functions lookup "Mobius West" --locale en-US --json
```

The [approval and exact-change manifest](../function-content/editorial/approved-title-cues-001.json)
contains previous/current values, each allowed resource diff and old/new hashes.
The 177-entry predecessor fixture and defaults lock 001 remain immutable;
successor fixture 002 and defaults lock 002 select the approved content with
identical engineering profiles. Only 21 protected entries change. Existing audio
is never relabeled or overwritten. Listening and release approval are separate.
The canonical-command review now records the approved source-English primary
vocabulary. Specification review, other-language terminology review, listening
and release states remain separate and are not promoted by that field.

## Historical proposal checkpoint

The [complete decision sheet](releases/OCF_TITLE_CUE_REVIEW.md),
[machine-readable recommendations](releases/OCF_TITLE_CUE_REVIEW.json),
[exact teaching report](releases/OCF_EXACT_TEACHING_REVIEW.md),
[identifier successor proposal](releases/OCF_IDENTIFIER_SUCCESSOR_PROPOSAL.md) and
[locale readiness proposal](releases/OCF_LOCALE_TITLE_CUE_READINESS.md) form one
historical proposal checkpoint. Their vocabulary recommendations were
**PROPOSED — NOT IMPLEMENTED** at that source revision. They do not override the
current decisions above. Earlier audit drafts and pending user edits are preserved.

## Reproduce and inspect

From a checkout with the declared source commit available in Git history:

```bash
python scripts/tools/title_cue_review.py --check
python -m pytest tests/test_title_cue_review_companion.py
```

Without `--check`, the tool regenerates only its four named companion report
files. `--output` selects an alternate report directory. It has no apply/rename
operation, translation, synthesis or release action. Canonical function,
specification, binding, narration and relevant profile inputs must match the
declared source commit. A dirty canonical input fails with an actionable error;
use an isolated committed checkout rather than overwriting the user's work.

The source SHA is deliberate: after canonical inputs evolve, an editor must
review the corresponding contextual findings before selecting a new checkpoint.
The tool does not automatically stamp current HEAD onto old recommendations.

Run the historical generator in a matching historical checkout. The approved
successor deliberately triggers its old source-drift guard; use
`current_title_cues.py` for current-tree freshness. Tests verify historical saved
evidence against historical Git blobs rather than restamping it as current data.

## What the evidence means

Exact excerpts, code-point offsets, YAML scalar line locations and text hashes
support review of complete declared phrases. Source-English screening permits
case and whitespace/comma/hyphen differences for discovery. It does not change
word order, repetitions, digits, wording or pronunciation. Explicitly recorded
spoken realization explains Bloodpressure/Blood Pressure; Breath/Breathe remains
a lexical difference. Shorter phrases nested in complete longer phrases are not
independent teaching.

The curated per-function context distinguishes activation, optional reinforcement,
target selection, controls, automatic baseline and duration of a selected
application. Automated occurrence detection alone does not establish that role,
authenticate historical material or verify recorded speech. Nonspoken composed
events remain mandatory markers for whole-session stems. Separately referenced
control narration is reported separately from composed events.

The machine report inventories all current structured commands and preserves
their roles, procedures, relationships, review status, historical lookup and
localization bindings. Per-resource teaching differences remain visible even
when a proposed title change is straightforward. No existing approval is created
or revoked by an audit classification.

Identifier totals count textual mentions in the pinned source, including earlier
reports and generated references; they are not counts of unique active IDs.
The protected-identity category follows a narration key wherever it is mentioned.
Use the per-file inventory and mapping locators to distinguish an active consumer
from a historical report before planning migration. User-owned references and
immutable brand imports are excluded without opening them.

## Approval sequence

Review source-language pairs first, then purposes/modes and shared controls.
Approve exact teaching edits separately, preserving each procedure and repetitions
unless explicitly decided otherwise. Establish per-locale terminology using the
existing resolver, review complete spoken collisions and only then translate
teaching. Historical lookup, active aliases and identifier successor migration
are independent decisions. See the linked proposals for affected recordings,
fingerprints, caches, immutable locks and generated-reference dependencies.
