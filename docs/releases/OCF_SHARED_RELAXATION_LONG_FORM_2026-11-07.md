# Approved original long-form shared relaxation successor

## Baseline checkpoint

Task branch: `engineering/shared-relaxation-long-form-20261107`, starting at
`b7fefd129df18d44516f27c5ecc9bb3bef49f418` (clean checkout). All 58 function
bindings select `OCF-TPL-SESSION-HPLUS-LOCKED-005`; its relaxation section uses
`OCF-TPL-STAGE-HPLUS-RELAXATION-001`, six entries in
`locales/en-US/hplus-relaxation.yaml`, and a silent whole-body hold.
Separate Focus Ten resources follow that stage. They are not body-scan counts.

The user approved the exact original long-form hypnotic v2 wording beginning
“Make yourself comfortable, and take a moment to settle.” and its selection as
the active routine successor. This is OCF-authored wording, not an authenticated
Hemi-Sync transcript. It does not authorize listening approval, audio release,
publication, or edits to frozen editions.

Before edits, the existing integrity tool captured protected parsed texts/hashes;
LocaleCatalog captured the complete en-US entry map. Bindings, effective pacing,
representative normal/historical resolved sessions, session-template previews,
and frozen file hashes are retained privately at
`.ocf-work/agent-continuity/RELAXATION-LONG-20261107/baseline.json`.
Private reference material and audio are excluded from Git and this report.

Baseline interpreter: repository `.venv/bin/python` (supported isolated environment).
Baseline focused command:
`python -m pytest tests/test_hplus_narration_integrity.py tests/test_shared_session_successor.py tests/test_session_pacing_successor.py tests/test_narration_revisions.py -q`:
49 collected tests passed. No production render or test worker was visible.
Existing native116 supervision units and historical worktrees were left untouched.

## Narration and selection checkpoint

The single new editable speech authority is
`locales/en-US/relaxation-long-002.yaml`, selected by narration revision
`OCF-RELAXATION-LONG-002`. Its eleven ordered keys share prefix
`hplus.shared.relaxation.`:
`begin`, `support`, `face`, `jaw-neck`, `shoulders`, `hands`, `chest-breathing`,
`abdomen-lower-back`, `hips-thighs`, `lower-legs-feet`, `whole-body-awareness`.
The last entry includes the entire integration/handoff paragraph. The isolated
spoken count sequence is exactly One, Two, Three, Four, Five, Six, Seven, Eight,
Nine, Ten. Neither legacy `torso` nor legacy `legs` participates in this stage.

The exact assembled 688-word passage (two LF characters between resources,
unchanged internal lines/paragraphs, no leading/trailing LF) has SHA-256:
`2c5ece916a8dc35f0c99b8843244093040cd8670df5fbbdeccf552ac0dd75421`.
The locale resource file SHA-256 is
`9536f63e6e5b7741480bca8f9073d2a05348f08d256609ad5317527adce6ba42`.
Per-entry successor hashes, explicit additions/removals, predecessor hashes,
1,112 unchanged canonical entry hashes and frozen-file receipts are in
`function-content/editorial/relaxation-long-002.json`. This ledger stores hashes,
not a second copy of the new narration or a retired source-authority file.

All 58 canonical function bindings deliberately select
`OCF-TPL-SESSION-HPLUS-LOCKED-005` → `OCF-TPL-SESSION-HPLUS-LOCKED-006` (6.0.0).
Their explicit historical selections remain allowed. The migration changes only
the default-selection line and the allowed-template addition in each resource;
complete parsed resources were compared before retaining their original formatting.
New relaxation stage `OCF-TPL-STAGE-HPLUS-RELAXATION-002` is version 2.0.0;
pacing `OCF-PACING-HPLUS-LOCKED-006` is 6.0.0. Defaults lock
`OCF-AUDIO-DEFAULTS-HPLUS-016` (16.0.0) retains all predecessor dependencies and
adds the new text, manifest and current binding inputs. Its SHA-256 is
`8677dbaefde4111ffdb8fb92a876c15e5d7d5b73d4cbbd3048a1e05cf0553bf4`.
The inherited DSP remains `OCF-DSP-HPLUS-LOCKED-003`, not a new DSP edition.

The CLI complete-session route selects the binding, composes the selected
template/stage, then resolves the revision through strict LocaleCatalog before
segmentation/synthesis. Compact plan generation and session-library validation
now consult that same selected revision. No prose is hardcoded in Python.
Content-addressed PCM identities include exact speech; changed entries therefore
receive different identities without deleting any cache. Complete render identity
also changes through the selected template/revision. Identical unaffected speech
remains reusable.

Locale semantic version is deliberately 2.0.0 for substantive meaning/segmentation
changes; entries are reviewed 2.0.0. No translation was authored or promoted.
Spanish remains partial/stale, and requesting this unavailable spoken revision
in Spanish fails instead of silently selecting English.

Historical LOCKED-001 through -005 and STANDARD-001 through -004 previews and
the independently approved Preparation Learning RC1 are checked transitively by
resolved event-text hashes. Canonical shared predecessor resources and all prior
approval/lock files remain byte-identical. Separate Focus Ten entry/count/ready/
return resources, Focus Eleven, Focus Twenty, waking counts, function words,
commands, four body passes, -24 dB underlay, DSP, fades and ending policy are not
rewritten. No short relaxation variant is authored or activated.

## Pacing and duration

Timing decision: retain existing relaxation rate scale 0.88 and existing pause
values, assigning sentence roles (2 seconds) and existing brief phrase roles
(1.25 seconds) within the conversational passage. Existing paragraph policy
supplies 4 seconds; numbered count units retain 6 seconds. Line wraps never
create pauses. Introduction event gap stays 5 seconds; each completed step uses
the existing 6-second event gap. The last unit uses that event gap, not an added
landing pause. The separate silent whole-body hold remains 30 seconds.

No preferred speech duration is copied from the old text. Speech-end/event-end
anchors allow the entire new narration to finish. Transmutation Box placement
and separate breathing-practice hold remain 20 seconds each; unrelated transition,
rest, repetition, voice, gain and DSP policies are unchanged.

Planning estimates only, using the inherited 160 words/minute and effective
unit rate scales (not measured synthesis):

| Quantity | Before | After |
| --- | ---: | ---: |
| Relaxation speech | 216.051 s | 293.182 s |
| Internal semantic pauses | 260.500 s | 179.500 s |
| External event gaps/whole-body hold | 65.000 s | 95.000 s |
| Complete relaxation stage | 541.551 s | 567.682 s |
| Focus (OCF-FND-002) session | 1794.313 s | 1820.444 s |
| Hearing (OCF-SEN-001) session | 1865.488 s | 1891.619 s |

The speech grows by 181 words. Internal pause totals reflect the new sentence/
phrase structure and removal of old repeated relaxation/sleep fragments, not
shortened external holds. Ten step gaps replace five prior body-part gaps.
The net session increase is 26.131 seconds in these estimates. A 58-function
advisory projection found none above 45 minutes; longest is OCF-BOD-006 at
2582.194 seconds (43:02). Actual synthesis can exceed this estimate/soft target;
the existing duration audit flags that without cutting or accelerating speech.

## Private previews and optional local audition

Under `.ocf-work/agent-continuity/RELAXATION-LONG-20261107/`:

- `baseline.json`: pre-edit capture.
- `OCF-FND-002-resolved.txt` / `OCF-SEN-001-resolved.txt`: full resolved session speech.
- Corresponding `*-resolved.json`: complete resolved documents.
- `relaxation-approved-resolved.txt`: exact joined approved passage.
- `estimated-timelines.json` / `timing-summary.json`: before/after complete timelines and accounting.
- `catalog-duration-estimates.json`: all 58 advisory duration projections.
- `relaxation-only.yaml`: validated, key-bound, revision-selected local audition input.
- `*-cli-dry-run-local-voice.json`: actual CLI normal-template dry-runs with the available local voice override.
- `generation/`: independent source-pinned generation receipts and logs.
- `generation-r2/`: refreshed 58-plan receipts after the affirmation-policy preservation.

No new relaxation or complete-session audition was synthesized, listened to,
uploaded or published. The unchanged
default OCF-VOICE-0003 Lessac model path is unavailable here, so its no-override
CLI render preflight is blocked. `voice doctor` verified an already installed
local OCF-VOICE-9003 model; both representative CLI dry-runs succeeded with that
explicit temporary voice selection. No default voice/profile was modified.

Optional exact local command from the repository root (not executed):

```bash
.venv/bin/python scripts/ocf.py audio render-speech \
  .ocf-work/agent-continuity/RELAXATION-LONG-20261107/relaxation-only.yaml \
  --locale en-US --voice OCF-VOICE-9003 \
  --output .ocf-work/agent-continuity/RELAXATION-LONG-20261107/relaxation-long-002-private.wav
```

Run any extended synthesis through independent monitored supervision, not an
unattended tool child. This command does not confer listening/release approval.

## Verification status

Baseline focused suite: 49 passed. Narration/selection focused checkpoint:
57 passed in 129.72 seconds. The existing 177-key integrity tool passes without
replacing an old baseline. Generation of all 58 source plans and generated indexes
completed successfully under an independent bounded systemd engineering worker.
Expanded focused regression: 136 passed, 1 skipped in 316.62 seconds using two
workers. The skip is the existing opt-in complete Piper/Farfield render requiring
`OCF_RUN_COMPLETE_SESSION_SMOKE=1`; it was not run or claimed passing. Its exact
tested worktree fingerprint is
`e240ce547f41e11800606465889534acde6bbf16004472fa8288b8bf0eaf5672`.
An additional validator-adapter check exposed an unnecessary revision-method call
for unrevisioned templates. The fix limits that call to selected revisions;
all 12 adapter tests then passed, preserving their existing coverage. Ruff check
and format checks pass across all 315 Python files.
Final scope review also found that selecting a narration revision normally opts
into a separate preparation/affirmation default policy. This relaxation-only
revision is explicitly excluded from that unrelated policy: legacy explicit
affirmation enable behavior, all existing choices and defaults are preserved.
Six added selector/enable regressions plus the narration-revision and adapter
checks passed: 67 tests in 121.69 seconds. No wording, narration/resource hash,
locked profile or previous revision policy changed in this correction. The
in-progress first final-gate job was stopped before editing its pinned inputs
and marked superseded, not passing; full pytest had not started there.
All 58 compact source plans were then regenerated successfully against the
corrected composition metadata, without changing spoken text or the new lock.
Final full-suite, coverage and repository-gate results are recorded in the
subsequent verification checkpoint; not claimed here yet.

`make check PY=.venv/bin/python` passed against clean HEAD
`5e36eb66e09e754c048f6b9267a478eaf1c1e765`, worktree fingerprint
`d8d7ae41c179cf788f3a4530b8803e219c6d761ff35ee5403565e53410ab2547`:
all-function validation (0 errors, 9 warnings), generated indexes, all 58 source
plan freshness checks, Farfield inventory, cue headers and editorial review.
The warnings are partial/stale Spanish and existing legacy/editorial metadata
warnings; no translations or unrelated editorial decisions were changed.
Locale en-US validation also passed (0 errors, 0 warnings).

That job's subsequent lint phase found two stale generated interface-example
fingerprints: the changed locale manifest and Focus source plan. The supported
`python -m ocf_tools.examples` generator refreshed only those two hashes in
`examples/interfaces.json`. No runtime input changed. The first full pytest has
not yet run; the resumed final gate starts with lint and then the complete suite.

Scoped non-narration integration changes are limited to the 58 binding selections,
their two generated capability/field-source indexes and 59 compact source-plan
files, selectors/explicit migration support, revision-aware generation/validation,
the scoped affirmation-policy preservation, the existing measured-session audit's
successor-ID allowance, regression tests,
approval hashes and this report/documentation inventory. No unrelated content
or configuration profile is changed. The interface-example fingerprint refresh
is the corresponding generated-data integration change, not a new example or
an executed operator action.

One early oversized new parametrized focused run timed out; it was not a pass.
The permanent tests use two full representative compositions, all 58 explicit
binding checks, and generated plans for all consumers. A diagnostic check of
historical lock 009 exposed older function-resource hash differences; that old
lock is untouched. Current predecessor 015 and successor 016 both validate.

## Rollback

Select the still-bound approved predecessor `OCF-TPL-SESSION-HPLUS-LOCKED-005`
explicitly for a session, or apply a scoped revert of this task's selection/
integration commits on an appropriate branch. Never reset over other work,
regenerate a predecessor approval baseline, delete caches wholesale or overwrite
historical audio editions. No push, merge, release or production-service change
is authorized by this implementation.
