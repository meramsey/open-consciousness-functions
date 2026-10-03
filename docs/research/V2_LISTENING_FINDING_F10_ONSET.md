# V2 listening finding: induction support must precede state arrival

Human listening feedback (Phase2C addendum): approximately the first eight minutes
of V2 are narration/silence without F10 DSP, followed by a late F10 introduction.
This is a **scheduling/architecture finding**, not subjective production approval
or a claim that the measured F10 components need changing.

Inspection of the unchanged measured RC1 ledger confirms:

| Anchor | Semantic identity | Actual seconds |
| --- | --- | ---: |
| `relaxation.begin` | `preparation.relaxation.begin` |179.127891 |
| `focus-ten.learn` | `focus.ten.learning` |372.038005 |
| `focus-ten.count-one` | `focus.ten.count` |394.779138 |
| `focus-ten.enter` (spoken Ten/arrival identification) | `focus.ten.enter` |487.570884 |
| `focus-ten.transition` (state-program directive after arrival speech) | `focus.ten.transition` |494.645533 |
| `focus-ten.ready` | `focus.ten.ready` |494.645533 |

V2 first F10 gain window is494.645533–499.645533s: explicit directive plus5s
profile fallback. The progressive-relaxation stage is already declared an
**induction** stage; its first event179.127891s is the earliest relevant semantic
approach anchor. The explicitly named F10 learning/count begins later, as shown.
None of these times is a hard-coded eight-minute engine threshold.

Existing transition gain code starts only at state directives. Moving that state
directive earlier would wrongly conflate supporting DSP with arrival. Add an
explicit approach envelope binding measured semantic occurrence IDs, independent
of the active state. For the scoped V2.1 profile: begin at progressive relaxation,
reach sustained level by the **start of spoken Ten**, hold through the arrival
utterance, then hand off without a second fade when the existing state directive
commits. F10→F11/return/exit retain their measured anchors and existing curve.

Initial deterministic choice: raised-cosine amplitude emergence from0to1, with
zero endpoint slopes. This is a disclosed OCF scheduling choice, not a recovered
source morph or claim that a specific loudness curve is optimal for listeners.
Reuse the same selected candidate/stems and existing sustained/mix calibration.
No carrier/beat/modulation parameters, RC1 words, event identities or cue assets
change. `OCF-BG-0012` remains approximate V4-derived candidate; F11 selection
remains pure-SAM`0006`, with`0007` preserved as theta alternate.

V2 is retained under`audio/rendered/auditions/preparation-learning-v2/`.
V2.1 will be a separate non-production artifact with exact reused speech and
ledger; objective rendering checks and listener comparison remain distinct.
