# Narration review drafts

The **OCF Preparation Learning en-US RC1** views are generated from the reviewed
en-US source resources and approved semantic composition. See the
[RC1 declaration](../releases/OCF_PREPARATION_LEARNING_en-US_RC1.md). Edit those sources,
then regenerate; these views are not alternative sources of narration.

```bash
python3 scripts/tools/preview_preparation_learning.py
python3 scripts/tools/preview_preparation_learning.py --check
```

- [Complete listener transcript](preparation-learning.en-US.listener.md): both
  optional stages included for review, with no default affirmation or tone.
- [Developer view](preparation-learning.en-US.developer.md): semantic events,
  localization keys, cue references, explicit pauses, and estimated clock times.

The generator never calls TTS, DSP engines, or cue generators. Estimates use
140 words/minute and are not measured speech or final production timing.
`--without-optional` previews the default composition; `--affirmation TEXT`
explicitly configures review wording through the existing variable mechanism.

Actual cue sounds/frequencies, session-complete sound, artwork, default
affirmation, resonant-tuning/oHm implementation, broader command localization,
and final production timing remain TBD. Routine Preparation and Function
Installation final narration and real translations require separate approval.

## Phase 8B editorial revision

At the Phase 8B review checkpoint the narration was still draft and uncommitted;
it is now approved as RC1. Semantic IDs, event ordering, DSP directives,
cue identities, schemas, and localization behavior retain the approved model.
The only composition binding changes select learning-specific count resources;
shared bare-number resources remain available for other contexts.

| Default composition, estimate at 140 words/minute | Phase 8A | Phase 8B |
| --- | --- | --- |
| Spoken words | 2,326 | 1,895 |
| Estimated speech | 16m 37s | 13m 32s |
| Explicit quiet/practice pauses | 6m 24s | 9m 32s |
| Estimated total | 23m 01s | 23m 04s |

Both optional stages included: 2,035 words, about 14m 32s speech plus
10m 18s explicit pauses, about 24m 50s total. No default affirmation is inserted.

Condensed the introductory explanations, repeated sensory-accessibility
reminders, repeated failure-prevention language, and pre-opening lecture.
Scientific qualification remains in the writing standard rather than the
spoken induction. The count now carries progressive relaxation through
support, face, shoulders, arms, breathing, torso, legs, feet and whole-body
rest, culminating in Ten and Focus Ten. A neutral hypothetical task-settling
example makes deliberate learning/rehearsal/association/use more concrete,
without assigning an activation command. Additional silence supports container
practice, recognition, the working state, rehearsal and closing.

## Phase 8C verification

Only three micro-edits change narration: the Access Channel introduction,
the first activation-command sentence, and the return identification. The
wording was subsequently approved and RC1 declared. The Phase 8B
table above records that editorial revision's baseline, not a production clock.

See [operational cue meaning and exact event grammar](../SEMANTIC_SESSIONS.md#operational-cue-meaning).
Operational signals may only announce their own semantic occurrence, including
when currently disabled. Explanation/review does not replay them. Future
sound-recognition training requires an explicitly designed cue-rehearsal
operation; it is not shipped.

The composed OPEN/Eleven, READY/identification and CLOSE/Ten each share a single
coordination event, explicitly approved for RC1. There is no separately scheduled audible cue lead-in.
Actual cue playback and state-aware DSP synthesis are not shipped, so the
developer view verifies logical event data, not physical audio order. Strict
within-event sound/speech alignment belongs to the audio renderer, not new
semantic events. Future renderer settings can express 0ms cue onset and a
configurable speech offset without changing event identity.

The closing preview's separate “Ten.” paragraph is intentional: it is the
resolved `focus.anchor.ten` resource on `close.close`, after `close.prepare`
and its 3-second pause. The transition guide then has a 25-second settling
pause before identification/recognition. It is not a missing or empty event.

Current word counts: **1,896 default**, **2,036 with both optional stages**.
At the review rate of 140 words/minute, the default is about 13m 33s of
speech plus 9m 32s of explicit pauses, about 23m 05s total. Both optional
stages give about 14m 33s speech plus 10m 18s pauses, about 24m 51s total.
These estimates do not finalize production timing.

| Major quiet period | Composed event | Provisional pause after |
| --- | --- | --- |
| Focus Container practice | `setting-aside.place` | 40s |
| Post-body-scan rest | `relaxation.whole` | 30s |
| Post-count Focus Ten rest | `focus-ten.ready` | 40s |
| Initial Focus Ten recognition | `recognize-ten.recognize` | 30s |
| Focus Eleven transition, after its guide | `open.transition` | 25s |
| Focus Eleven breath practice | `recognize-eleven.recognize` | 20s |
| Focus Eleven attention practice | `recognize-eleven.practice` | 60s |
| Working-state recognition/reinforcement | `recognize-eleven.complete` | 15s |
| Hypothetical function's first experience | `function-concept.concept` | 10s |
| Hypothetical function rehearsal | `command-learning.rehearse` | 40s |
| F11-to-F10 settling, after its guide | `close.transition` | 25s |
| Returned Focus Ten recognition | `recognize-return.recognize` | 30s |
| Waking return | `return.begin` through `return.complete` | 31s total: 4 + 5 + 5 + 4 + 5 + 5 + 3 |

RC1 review scope is **en-US narration and semantic data**, not completed audio.
Fixed RC1 words are now marked `reviewed`. Cue assets,
cue-before-speech alignment, cue playback, state-aware DSP production, tuning,
default affirmation, artwork and final production timing remain pending.
The shared-event contract is approved. Do not split those semantic events to
force a particular audio alignment.

Validation: 354 tests pass; localization/semantic validation and index freshness
pass. Targeted Phase 8C lint and whitespace checks pass. Repository-wide lint
still has 15 inherited findings in `voice.py`, `audio_build.py`, `sbagenx.py`
and two audio/SBaGenX test files, confirmed unchanged from `4093063`. They are
[tracked technical debt](../TECHNICAL_DEBT.md), explicitly not a blocker for RC1.
