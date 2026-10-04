# Source-first authoring migration checkpoint — 2026-10-03

Starting commit: `96f48aea6e697d7ceade5163d110756e04ecdacb`.
The cancelled Treasure Hunt task produced no changes and was not resumed.

## Recovery commits

| Commit | Change |
| --- | --- |
| `123a374` | Exact-source editorial workspaces, schemas, diff/review/release CLI, package safeguards and tests |
| `161b394` | Source-first human-editing policy, contributor guide, source-distribution resources and exclusions |
| `1d2e53e` | Preserve shared transcript uncertainty; test a complete synthetic 39/16 batch |

This report's own commit is discoverable with
`git log -1 --format=%H -- docs/releases/OCF_SOURCE_FIRST_CHECKPOINT_2026-10-03.md`.
No push, reset, restoration, reference rewrite, candidate promotion or final audio
generation occurred. Only intended implementation/policy files were staged.

## Policy and architecture

**Immutable SOURCE → exact initial WORKING → HUMAN edits → explicit RELEASE →
measured timing.** Mandatory paraphrasing, stylistic distancing and originality
review were removed as working-authoring prerequisites. No phrase-distance
validator or automatic paraphrasing engine was found to remove. Human release
review, provenance, claims/accessibility standards and distribution-rights
attestations remain separate requirements. Source claims and visualization
instructions are retained, with flags rather than automatic rewriting.

`schemas/editorial-function.schema.json` and `editorial-block.schema.json` are
additive local contracts. Existing function/evidence/specification/decision/binding,
session/stage/locale/timing/cue/DSP schemas were not replaced. Exact UTF-8 source
text, including line endings, is snapshotted and fingerprinted. Candidate snippets
cover the full available transcript contiguously, without duplication or omitted
lines. Changes to snapshot text, block source text, ranges or block semantic
identity fail validation.

The private `.ocf-authoring/` workspace contains `sources/`, `blocks/` and
`functions/`, plus generated local review views. Shared blocks have one working
text file, with originating function/hash/range locators on each occurrence.
All text is local and ignored, not committed or packaged. Clean checkouts can
rebuild it from explicitly supplied local reference files and committed metadata;
runtime discovery does not depend on the reference corpus.

`ocf content` now provides skeletonize, diff, dashboard, variants, review, approve,
preview and explicit human insertion. Diffs distinguish unchanged, modified,
removed, correction-associated, OCF-only inserted and template-substituted text.
Corrections remain separate records; tools never apply them automatically. Review
records the human and text hash. Release approval also records rights/evidence and
its own hash. Later changes invalidate review/approval. Shared substitutions retain
both consuming and replacement provenance; cycles and semantic changes fail.

No exact wording is fabricated for unavailable sources. Existing previous
candidates are referenced for comparison, not selected at runtime. Rights statuses
are human attestations, not automated legal determinations.

## Corpus result

Representative real cases were Relax (straightforward), Attention (adapted prior
candidate and shared language), Information (unusual/incomplete return structure)
and Sleep Easy (source unavailable). Synthetic tests additionally exercise exact
variants, partial sources, substitutions, corrections, releases and all 55 targets.
Then all 55 real targets were processed.

- **39 source-bearing functions skeletonized:** 34 unverified source-designated
  transcripts and 5 explicitly partial source transcripts.
- **16 source-unavailable records:** zero historical text blocks; semantic/mockup
  research remains in the existing sidecars.
- **388 occurrences / 373 unique block files**, all unchanged from SOURCE.
- **213 reusable-section candidates / 175 function-specific occurrences.**
- **333 inherited / 55 transcript-uncertain occurrences**, corresponding to 324
  inherited / 49 uncertain unique files. Shared exact wording conservatively
  retains uncertainty from any partial-source occurrence instead of dropping it.
- **0 reviewed / 388 unreviewed; 0 approved / 388 pending release occurrences.**
- **Rights unknown: 388 occurrences / 373 unique files.** All other rights
  statuses are zero. No correction was applied and no OCF-only text was inserted
  into the real corpus.
- All 388 occurrences carry authentication, candidate-boundary and accessibility
  review flags, plus existing function-level claim categories. These categories
  describe the source/function context, not proof of a particular claim in every
  sentence. No release or scientific validation is implied.
- All **277** original reference inventory SHA-256 values were rechecked and
  match. Local source inputs were not modified.

### Exact 55-target snapshot

`unverified` means transcript availability, not authenticated original wording.
All nonzero rows are candidate skeletons; unavailable rows have explicit empty
skeletons. Every block remains unreviewed and rights-unknown.

| Function | Source | Blocks | Reusable | Specific | Uncertain |
| --- | --- | ---: | ---: | ---: | ---: |
| OCF-AUT-001 | unavailable | 0 | 0 | 0 | 0 |
| OCF-BOD-001 | unverified | 11 | 5 | 6 | 0 |
| OCF-BOD-002 | partial | 10 | 5 | 5 | 10 |
| OCF-BOD-003 | unverified | 9 | 6 | 3 | 0 |
| OCF-BOD-004 | partial | 12 | 5 | 7 | 12 |
| OCF-BOD-005 | unverified | 7 | 5 | 2 | 0 |
| OCF-BOD-006 | unverified | 9 | 5 | 4 | 0 |
| OCF-BOD-007 | unverified | 12 | 6 | 6 | 0 |
| OCF-BOD-008 | unverified | 10 | 6 | 4 | 1 |
| OCF-BOD-009 | partial | 8 | 4 | 4 | 8 |
| OCF-BOD-010 | unverified | 9 | 6 | 3 | 0 |
| OCF-BOD-011 | unverified | 10 | 6 | 4 | 0 |
| OCF-BOD-012 | unverified | 10 | 6 | 4 | 0 |
| OCF-BOD-013 | unverified | 9 | 6 | 3 | 1 |
| OCF-BOD-014 | unavailable | 0 | 0 | 0 | 0 |
| OCF-BOD-015 | unavailable | 0 | 0 | 0 | 0 |
| OCF-COG-001 | unverified | 8 | 2 | 6 | 0 |
| OCF-COG-002 | unverified | 12 | 6 | 6 | 0 |
| OCF-COG-003 | unverified | 11 | 6 | 5 | 1 |
| OCF-COG-004 | unverified | 11 | 6 | 5 | 1 |
| OCF-COG-005 | partial | 9 | 5 | 4 | 9 |
| OCF-COG-006 | partial | 10 | 5 | 5 | 10 |
| OCF-COG-007 | unverified | 9 | 5 | 4 | 1 |
| OCF-COM-001 | unverified | 9 | 6 | 3 | 0 |
| OCF-EMG-001 | unavailable | 0 | 0 | 0 | 0 |
| OCF-EMG-002 | unavailable | 0 | 0 | 0 | 0 |
| OCF-EMO-001 | unverified | 11 | 6 | 5 | 0 |
| OCF-EMO-002 | unverified | 12 | 6 | 6 | 0 |
| OCF-EMO-003 | unavailable | 0 | 0 | 0 | 0 |
| OCF-EXP-001 | unverified | 9 | 5 | 4 | 0 |
| OCF-EXP-002 | unavailable | 0 | 0 | 0 | 0 |
| OCF-FND-001 | unverified | 12 | 3 | 9 | 0 |
| OCF-FND-002 | unverified | 9 | 6 | 3 | 1 |
| OCF-FND-003 | unverified | 11 | 6 | 5 | 0 |
| OCF-FND-004 | unverified | 9 | 6 | 3 | 0 |
| OCF-FND-005 | unverified | 10 | 6 | 4 | 0 |
| OCF-FND-006 | unavailable | 0 | 0 | 0 | 0 |
| OCF-LIF-001 | unverified | 10 | 6 | 4 | 0 |
| OCF-PRF-001 | unverified | 10 | 5 | 5 | 0 |
| OCF-PRF-002 | unverified | 10 | 6 | 4 | 0 |
| OCF-PRF-003 | unverified | 10 | 6 | 4 | 0 |
| OCF-PRF-004 | unavailable | 0 | 0 | 0 | 0 |
| OCF-PRF-005 | unavailable | 0 | 0 | 0 | 0 |
| OCF-PRF-006 | unavailable | 0 | 0 | 0 | 0 |
| OCF-SEN-001 | unverified | 9 | 6 | 3 | 0 |
| OCF-SEN-002 | unverified | 10 | 5 | 5 | 0 |
| OCF-SEN-003 | unavailable | 0 | 0 | 0 | 0 |
| OCF-SEN-004 | unavailable | 0 | 0 | 0 | 0 |
| OCF-SEN-005 | unavailable | 0 | 0 | 0 | 0 |
| OCF-SLP-001 | unverified | 9 | 6 | 3 | 0 |
| OCF-SLP-002 | unverified | 11 | 6 | 5 | 0 |
| OCF-SLP-003 | unverified | 12 | 6 | 6 | 0 |
| OCF-SLP-004 | unverified | 9 | 5 | 4 | 0 |
| OCF-SLP-005 | unavailable | 0 | 0 | 0 | 0 |
| OCF-SLP-006 | unavailable | 0 | 0 | 0 | 0 |

## Reusable variants and limits

Candidate analytical locators, not keyword detectors, seed the partitions. Their
overlaps are split without changing source text. Narrower reviewed ranges take
precedence; full-source investigative ranges do not prove a section's boundaries.
**The boundary/semantic partition remains a human-review candidate**, not a claim
that every historical installation passage has been definitively classified.
No source phrase can introduce a runtime DSP directive.

| Candidate semantic family | Occurrences | Exact-text groups | Minor candidates | Material candidates |
| --- | ---: | ---: | ---: | ---: |
| focus.eleven.close | 66 | 53 | 24 | 28 |
| function.consolidation | 38 | 38 | 0 | 37 |
| function.learning.attend | 40 | 38 | 28 | 9 |
| preparation.orientation.begin | 39 | 39 | 18 | 20 |
| session.return.begin | 30 | 30 | 0 | 29 |

Minor/material labels compare each variant against the first exact group and are
informational only. Similarity is not originality, semantic equivalence, evidence
authentication or permission to pick a preferred variant. Human source-context
review remains necessary. The 198 reusable exact-text groups reduce 213 repeated
occurrences without copying shared paragraphs into each function.

Existing stage identities/localization architecture remain available for the
English core. No IEC terminology migration or automatic choice of Transmutation
Box, Energy Ball, Inner Doorway or other English wording occurred in this task.
Advanced operations remain separate from basic preparation. Reviewed selection
can later bind existing reusable stages rather than changing stable semantic IDs.

Local artifacts:

- `.ocf-authoring/dashboard-2026-10-03.json`: current final counts and filters.
- `.ocf-authoring/variants.json`: source-occurrence provenance and exact diffs.
- `.ocf-authoring/previews/attention.working.yaml` and `relax.working.yaml`:
  textual development export views only; no measured speech or final audio.
- The earlier `.ocf-authoring/dashboard.json` is a pre-uncertainty-propagation
  snapshot. Use the dated final report or regenerate the live dashboard.

## Tests, coverage and validation

Actual Linux/Python 3.12 results:

- Final focused editorial suite: **60 passed**. Total new selection: 58 isolated
  unit cases and 2 explicitly integration-marked CLI/timing workflows.
- Final unit run: **229 passed**, 286 integration cases deselected.
- Integration run: **286 passed**. Total **515 tests** across separate runs.
- Existing V2.1 approach/envelope and localized timing regressions passed; no
  curve, level, signal definition, cue, speech or preset was changed.
- Unit coverage: **4229/7316 lines = 57.80481137233461%**;
  **1441/2908 branches = 49.55295735900963%**; **3087 missing lines / 1467 missing
  branches**, 0 excluded statements. Full denominator includes library and tools.
  Exact per-file missing lines/branches:
  `audio/rendered/source-first-unit-2026-10-03.json` (ignored).
- New editorial module coverage is not 100%; no unit gate was enabled or scope
  reduced. Largest remaining gaps: prompts 324/68, validators 316/196, CLI
  292/136, audio_build 236/131, transcript 200/86, voice 199/125, session 160/104,
  development verifier 140/26 (lines/branches).
- Schema/library validation and `make check`: **0 errors / 7 existing warnings**.
- `locale validate`: **0 errors / 1 existing partial-Spanish warning** (89 missing
  keys). No locale wording was changed or translated.
- `build-index` regeneration and freshness pass; no generated view diff remained.
- Ruff checks and format pass (89 files), internal Markdown links and whitespace
  pass. `markdownlint` is absent and the repository target skipped it.

Packaging was actually exercised: source wheel, source distribution, wheel rebuild
from source distribution, install and validation outside the checkout, and final
source wheel/install after the uncertainty fix. Private corpus and reference
artifacts are absent from inspected archives. Final source-wheel SHA-256:
`be2a43e02206dfea1a9cd991e92d0711a33834ada3755edd4b3aa6464dc948ba`.
Earlier rebuilt sdist-wheel SHA-256:
`c060aedec667502c9a5f6417eb216b815f9a111cf9d49d4598c8dc6530b958dd`.
The latter packaging roundtrip predates the final shared-uncertainty metadata fix;
it is not represented as the final source bytes. Installed final-wheel validation
preserves all 55 functions and validates the new schemas. Core doctor passed in
the earlier packaged roundtrip.

Resolved failures: first export event used an invalid speech-end anchor; stale
excluded resources survived incremental staging; symlinks could reach private
sources; template targets lacked full origin checking; stale review filtering
disagreed with release gating; shared uncertainty/claim flags could be lost during
deduplication. Failure-path tests cover these. Build warnings remain for inherited
setuptools license-table/classifier deprecations and the intentionally empty
community voice registry. No source authentication or legal outcome is claimed.

No native macOS/Windows, container rebuild, real speech preview, production audio,
community voice download or MCP execution occurred for this migration.

## Preserved working-tree boundary

All prior work remains intact. The pre-existing agent-infrastructure refactor to
AGENTS and ARCHITECTURE and its untracked `.opencode/`, AGENT_DEVELOPMENT and
AUDIO_PIPELINE documents remain pending. Only a source-first policy insertion
was staged in AGENTS, independently of its pending refactor. The existing
untracked Attention wording draft remains a previous candidate, not a release.
`ReusablePrompts/` and `references/HumanPlusTranscripts/` remain untouched and
unstaged. Locale data, pilot/session/stage YAML, function-content specifications,
F10/F11 manifests/profiles and listening artifacts were not changed.

## Exact next human workflow

1. Run `python3 scripts/ocf.py content diff OCF-FND-002 --filter function-specific`.
2. Inspect block provenance and candidate boundaries. Edit only the indicated
   `working.text` file; retain SOURCE and flag/correction metadata.
3. Inspect shared preparation variants before editing a shared file; choose a
   preferred wording intentionally rather than by a similarity score.
4. Mark each block `reviewed_unchanged` or `reviewed_modified` with a named reviewer.
5. Resolve claims/accessibility/uncertainty and any pending correction proposals
   through human review, without silently changing source wording.
6. Record rights evidence and explicitly approve each block for release. Do not
   approve a whole corpus based merely on its exact wording or source presence.
7. Export `content preview ID --release --output FILE`, bind reusable semantic
   stages/state transitions in a reviewed session, and use existing measured
   narration/recording, subtitle and DSP generation. Reflow is downstream of text.
8. Maintain frozen pilot/RC1/V2/V2.1 comparisons and pending listening review. No
   bulk final audio generation until human text/release decisions are complete.
