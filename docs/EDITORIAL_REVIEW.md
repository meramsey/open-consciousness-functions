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
`OCF-EDITORIAL-TITLE-CUES-001` and its approved successors through
`OCF-EDITORIAL-TITLE-CUES-004`. The completed 32-function review includes
Comfort and Regenerate, followed by 28 batch approvals and two explicit
keep-current decisions: Options and Nutricia. Heart Flow is now finalized;
its already-approved **Plus Heart Better** cue is unchanged. Heart Renewal
and Body Cleansing/Body Cleanse remain rejected/superseded.
No HPLUS identity migration is implemented.

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

## Comfort: first individual follow-up review

The user's explicit selection of option 1 approves OCF-BOD-003 as **Comfort**,
with display cue **PLUS-COMFORT** and complete spoken cue **Plus Comfort**.
The [successor ledger](../function-content/editorial/approved-title-cues-002.json)
records the exact authorization, predecessor files, substitutions and hashes.
Function YAML owns the spoken phrase; the body and closer reference
`{{ cue.primary }}`. Three body mentions, one closer mention and the exercise
sign-off are aligned. Only these two protected entries change; the other 175
resolved entries are byte-identical to the preceding revision.

Target selection, closing the eyes, inhaling/holding, internal cue and candle-like
exhalation remain intact. Persistence stays temporary; no mode or release is
introduced. `PLUS-55515` and its spoken numeric realization remain historical
lookup, and the legacy command identity is historical-only. Stable IDs and
source provenance are retained.

Fixture 003 and engineering defaults lock 004 record the Comfort revision.
Earlier fixtures, approval/structural ledgers and locks 001–003 remain immutable.
Lock 004 updates affected narration dependencies with the same engineering
profiles. The verifier checks the bounded decision before projecting predecessor
content for historical checks. Old text fingerprints remain stale for recorded
and hybrid sources; historical lookup does not select activation. Existing audio
does not acquire new wording or listening approval from this decision.

## Regenerate: second individual follow-up review

The user's explicit selection of option 1 approves **Regenerate** /
**PLUS-REGENERATE** / **Plus Regenerate** for OCF-BOD-014. The
[successor ledger](../function-content/editorial/approved-title-cues-003.json)
records exactly two body substitutions and one closer substitution from
`Plus Build Live`. Function-owned `{{ cue.primary }}` references resolve the
new phrase. The title and exercise sign-off remain Regenerate.

The lasting automatic repair/reconstruction suggestions and optional conscious
targeting retain their existing wording and procedures: close eyes, picture
healthy form and function, inhale/hold, internal cue, exhale and open eyes.
Persistence remains permanent, with no separate mode or release. Reconstruction
provenance and historical source-unavailable status are retained. `PLUS-BUILD,
LIVE` and `Plus Build Live` remain historical lookup; the old command identity
is historical-only.

The Regenerate revision uses fixture 004 and engineering defaults lock 005.
Exactly two protected entries change relative to Comfort's revision; 175 are
unchanged. Earlier ledgers, fixtures and locks remain immutable. Engineering
profiles stay identical. Both approved successors are verified before their
predecessor views are used by historical checks. Old recording text fingerprints
remain stale in recorded and hybrid modes. This decision adds no listening or
finished-session release approval.

## Collected naming batch: reviews 3–32

At the user's request, decisions were collected one function at a time before
implementation. The [batch approval ledger](../function-content/editorial/approved-title-cues-004.json)
records each selected title, display cue, complete spoken phrase, exact response,
scope and separately flagged metadata issue. The entire authorization is pinned;
editing its old wording or substitutions cannot silently enlarge the approval.

Twenty-eight approvals change 41 protected body/closer entries; the other 136
entries are byte-identical to the preceding revision. Titles and/or primary cues
change only as selected. Current totals are 55 functions, 97 stable command
identities, 79 active records, 18 historical-only records and 40 implemented
approved primary pairs. Nine superseded primary aliases become historical-only.
Retrieval, release and sensory LESS controls retain their exact data and speech.

Options retains **Plus Options Choices**, and Nutricia retains **Plus Food More**
and **Plus Food Less**. Their function YAML and narration remain unchanged.
The completed queue does not reopen these keep-current decisions or Heart Flow.
The remaining Options display/teaching difference is intentional and visible.

Fixture 005 and engineering defaults lock 006 are the current successors.
All previous ledgers, fixtures and locks remain immutable. The lock updates only
approved narration dependencies; profiles, stages, DSP and mixing remain intact.
After completing the naming reviews, the user explicitly released the draft-pilot
freeze: “I don't need to keep those frozen pilots.” Pilot composition therefore
uses the current approved titles and spoken cues through the ordinary resolver;
no historical pilot-binding compatibility layer is retained. Draft content and
listening/release review remain separate from naming approval.

Purpose, persistence, trigger and role discrepancies identified during review
remain separate pending questions, recorded per decision. No naming approval
rewrites those mechanisms, resolves those discrepancies, creates a control,
changes a breathing sequence or grants listening/release approval. Old recorded
text fingerprints remain stale even when only a title/sign-off changes; hybrid
fallback cannot bypass that mismatch.

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
