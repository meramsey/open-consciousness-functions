# Approved editorial batch: 14 November 2026

Status: source-only implementation under review. Not merged, published, rendered, or approved for listening/release.

Authority: the owner's complete “OCF overnight editorial batch” attachment. Exact wording and paragraph breaks are captured in the conformance fixture; its source SHA-256 binds the supplied attachment. Source checkpoint: `704440da8e0379cee8dfd332203bc0001c0a5f27`.

## Approval-to-implementation traceability

| Function | Approved text | Description | Activation alignment |
| --- | --- | --- | --- |
| Brain Flow, BOD-001 | Exact opener/body/closer | Retained | No target focus; close eyes, inhale, hold, mental cue, mouth exhale, open eyes |
| Heart Flow, BOD-006 | Exact opener/body/closer | Replaced | No target focus; no added eye opening |
| Comfort, BOD-003 | Exact opener/body/closer | Replaced | One selected-area step before inhalation; temporary application retained |
| Sleep, SLP-002 | Exact opener/body/closer | Replaced | Close eyes, inhale, hold, mental cue, slow exhale, normal breathing; both redundant purpose steps removed |
| Detox, BOD-004 | Exact opener/body/closer | Retained | No organ/target pre-focus or added eye opening |
| Circulation, BOD-002 | Exact opener/body/closer | Replaced | No target focus; eye opening only in approved closer, not body |
| Blood Pressure Balance, BOD-007 | Exact opener/body/closer | Replaced | Comfortable inhalation; no target focus; adaptive baseline and temporary reinforcement retained |
| Restorative Sleep, SLP-001 | Exact opener/body/closer | Replaced | Whole-body default; optional area; eyes closed; temporary sleep application retained |
| Breathe Better, BOD-009 | Exact opener/body/closer | Retained | No target or eyes requirement; mouth exhale without candle simile |
| Immune Readiness, BOD-008 | Exact closer only | Retained | Existing activation retained; opener/body untouched |

All sequence repetitions remain one opener, four body passes, one closer. Spoken cues resolve through existing `cue.primary` bindings. Function/command IDs, cue wording, lifecycle, safety, relationship approvals, historical lookup, templates, DSP, pacing, published audio and historical receipts remain unchanged. Shared procedure definitions are unchanged; Sleep selects an existing compatible hold-cue sequence rather than changing its old shared exhale-only definition.

## Deliberate production boundary

The isolated review branch deliberately advances the source configuration to `OCF-AUDIO-DEFAULTS-HPLUS-021`. Historical 020 remains byte-for-byte immutable and correctly fails against changed current source. Only the ten approved canonical file digests change; dependency membership, template/pacing/DSP IDs and versions remain identical, listening approval stays null and release-ready stays false. No merge, render, publication or production deployment occurred.

The new shared source-plan fingerprint propagates to all 58 current source plans, including unaffected functions. This is an identity/cache ripple, not an editorial change to those functions. Regression checks preserve unaffected plan semantics and bindings. This configuration permits future preflight against the approved source but does not authorize executing renders or release; those actions remain outside this batch.

The historical metadata-only review's “177 unchanged entries” statement describes that earlier decision, not this subsequent explicitly approved editorial change. Hash-only editorial successor checks must preserve prior baselines and reject unrelated drift.

## Remaining scope

Immune Readiness opener/body simplification, other function editorial proposals, listening approval, audio generation, publication and merging remain excluded. Exact test commands/results and CI state will be recorded in the review handoff; source conformance is not a physical listening test.

## Verified local checks (Linux)

- Exact approved-content and activation regression suite: 20 passed.
- Editorial-successor, canonical-semantic-baseline and narration-integrity suites: 33 passed after final integrity optimization.
- Independent source review: all 28 replacements exact; six descriptions replaced/four retained; Immune opener/body untouched; generated instructions preserve local step wording.
- `validate --all`: 0 errors, 9 existing warnings (partial/stale Spanish and existing legacy/compatibility notes).
- `locale validate --locale en-US`: 0 errors, 0 warnings.
- `build-index --check`: fresh.
- Initial plan-only checks correctly failed the unchanged 020 exact-source lock. The initial full suite was stopped after 2,189 passes, three lock failures and one skip before the authorized branch-only 021 consistency update; it is not the final full-suite result. No validator or threshold was weakened.
- `make lint` with repository virtualenv Ruff 0.17.0: PASS; optional markdownlint unavailable. An initial run accidentally used global Ruff 0.16.7 and reported an unchanged-file import style issue; the supported virtualenv run passes.
- Independent hash-successor review: PASS; no baseline weakening or runtime source fallback.
- Final exact-content/configuration/plan regression suite: 23 passed, including all 48 untouched complete plans and all 58 binding payloads.
- Source-plan generation for all 58 functions: PASS with 021; no audio rendered.
- Final instrumented local suite: 3,379 passed, 4 failed, 5 skipped in 3,614.14 seconds. All four failures were current cue-report or documentation-inventory freshness; official generators refreshed those artifacts afterward. This is not represented as a green full-suite result.
- Coverage metrics met unchanged floors: combined statements 90.192%, branches 84.796%; unit-context statements 60.466%, branches 65.280%; integration-context statements 55.632%, branches 57.439%. The overall gate failed solely because pytest had the four freshness failures.
- Skips require explicitly enabled full Piper/Farfield synthesis, private/authorized Chatterbox voice packs, or a built container image. Those optional/private operations were not enabled.
- Aggregate `make check`, final worktree-local `make lint`, and en-US validation passed; optional markdownlint is unavailable. One derived interface-example fingerprint was regenerated after the 021 source-plan update.
- Post-regeneration targeted tests and exact-head CI remain pending at this checkpoint.

No native Windows/macOS, physical-device, listening or audio-render verification is claimed.

### Derived canonical contract fingerprints

The approved activation changes require refreshing `localization.contract_sha256` for Brain Flow, Circulation, Detox, Heart Flow, Blood Pressure Balance, Restorative Sleep and Sleep. Each new fingerprint is computed from that same canonical function's structural contract. No localization/review status is promoted. Without this consistency update the source planner correctly marks those seven changed contracts as needing review. The explicit approved wording/procedure batch supplies the authority; the fingerprint itself is not listening or release approval.
