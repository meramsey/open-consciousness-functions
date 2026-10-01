# OCF Preparation Learning en-US RC1

Declared 2026-10-01 following approval of the Phase 8A–8C wording and semantic
composition. This release candidate covers **original en-US narration and
semantic session data**, not a production audio master.

## Identity and scope

- Session: `OCF-TPL-SESSION-PREP-LEARN-001`, version `0.3.0`, `content_status: reviewed`.
- Source locale: `en-US`; fixed RC1 resources are `reviewed`.
- Narration: `locales/en-US/preparation-learning.yaml`.
- Default: affirmation disabled, resonant tuning/oHm disabled; 1,896 spoken words.
- Full optional-stage review: 2,036 words, no mandatory/default affirmation.
- Provisional pauses: 572 seconds default; 618 seconds with both optional stages.
- User-provided affirmation wording is not covered by this fixed-wording approval.
- Routine Preparation/Function Installation final narration and translations
  remain outside this release candidate.

The reviewed words must not be modified to conceal TTS, timing, DSP or rendering
problems. Report those layers separately during development audition.

## Approved semantic coordination

An OPEN event may coordinate its auditory reference and “Eleven”; READY may
coordinate its auditory reference and Focus Eleven identification; CLOSE may
coordinate its auditory reference and “Ten”; Focus Ten READY may coordinate
its auditory reference and Focus Ten identification. These are intentional
shared coordination points, not missing semantic sub-events.

Exact within-event synchronization belongs to the **audio renderer**. A future
renderer may express cue onset at 0ms and a configurable speech offset without
changing semantic identity. Do not split semantic events merely to impose an
audible cue lead-in. Operational cue playback still means that its semantic
operation is actually occurring, never an illustrative replay during explanation.

## Development audition

The next render is explicitly **DEVELOPMENT AUDITION — NOT PRODUCTION MASTER**.
Use measured local-TTS durations and this RC's pauses. Disable operational
auditory cues unless temporary audition placeholders are explicitly identified.
DSP transitions must use the measured semantic ledger; static Attention timing
is not Preparation Learning timing. Record all preset, voice, timing and renderer
choices, especially any unsupported Focus-state DSP.

## Deferred decisions and technical debt

Final auditory sounds/frequencies, session-complete sound, visual identity,
default affirmation, resonant-tuning/oHm implementation, broader command
localization and production timing remain TBD.

The 15 repository-wide lint findings verified unchanged from `4093063` are
[pre-existing technical debt](../TECHNICAL_DEBT.md), explicitly **not a blocker
for this narration/semantic RC1**. All 354 tests passed at Phase 8C approval;
locale/semantic validation and generated-index freshness were clean apart from
the existing seven warnings.
