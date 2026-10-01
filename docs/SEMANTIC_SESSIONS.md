# Semantic sessions, reusable stages and auditory bindings

Status: additive architecture supported by **`ocf session compose`**. The new
Routine Preparation and Function Installation records remain **architecture
drafts**. Preparation Learning is now **OCF Preparation Learning en-US RC1**,
approved through Phase 8C, with provisional pauses and disabled cue sounds; it is not a
final production exercise. Its [listener/developer views](drafts/README.md)
are text-only. Routine/function wording and final production timing await
separate approval. The separate
`ocf preparation …` toolchain remains specified but not shipped.

## Semantic coordination

```yaml
- id: open.transition
  semantic: focus.eleven.transition.open
  after: open.open
  offset: 0
  timing: {anchor: speech-end}
  dsp: {state: {from: focus-10, to: focus-11}}
- id: open.ready
  semantic: focus.eleven.ready
  after: open.transition
  offset: 0
  timing: {anchor: event-end}
  auditory_cue: focus.eleven.ready
```

An event's `id` identifies this occurrence. Its extensible dotted `semantic`
identifies the intent. `narration_key` resolves words, `dsp` records a separate
state/program directive, and `auditory_cue` references a learned nonverbal
identity. None defines the other. `cue_id` retains its subtitle/import meaning.
State labels are subjective practice conventions, not neurological claims.

Existing inline text, slots, absolute anchors, and start-relative `after`
references remain supported. `timing.anchor` distinguishes `start`,
`speech-end`, and `event-end` dependencies. End-dependent anchors are finalized
from measured speech and declared DSP transition duration, not English words.
Binding architecture does not yet synthesize state-aware DSP or play cues.

The speech renderer implements end-relative scheduling. It first synthesizes
the localized utterances, measures their durations, then resolves dependencies.
`event-end` includes declared `dsp.transition_s`; `speech-end` uses speech only.
Both include the referenced event's numeric `pause_after`. Fixed overlapping
speech fails before the output file is written; `timing.policy: reflow` can
delay eligible speech and dependent events, without moving unrelated fixed
anchors. `--flow` and English-number heuristics cannot retime semantic events.

## Reusable stages

`audio/templates/stages/OCF-TPL-STAGE-*.yaml` stores versioned original-OCF
semantic stages. Each has unique local event IDs. Composition namespaces them
by stage instance, and records stage identity/version/instance as provenance.
Repeated use of a stage is supported through distinct instance IDs.

Stage includes may supply `narration` overrides keyed by local event ID:
`{purpose: {narration_key: function.intro.name, variables: {function_name: Attention}}}`.
Overrides accept only narration/variables/inline-locale fields; they cannot
change semantics, DSP, cues or timing. This is how a function supplies specific
purpose/practice/examples instead of inheriting universal wording. Inline
contributor content remains supported and is not automatically rewritten.
`--function OCF-FND-002` binds function identity and supplies missing metadata
variables from its record; explicit conflicting commands fail validation.

```yaml
sections:
  - {id: orientation, stage: OCF-TPL-STAGE-ORIENTATION-001, start: 0}
  - {id: setting-aside, stage: OCF-TPL-STAGE-SETTING-ASIDE-001, after: "$previous"}
  - {id: affirmation, stage: OCF-TPL-STAGE-AFFIRMATION-001, after: "$previous", enabled_by: affirmation}
  - {id: tuning, stage: OCF-TPL-STAGE-TUNING-001, after: "$previous", enabled_by: tuning}
  - {id: focus-ten, stage: OCF-TPL-STAGE-FOCUS-TEN-001, after: "$previous"}
```

`$previous` binds to the preceding **included** stage's last event, so skipping
optional stages does not leave dangling anchors. Optional stages default off;
`--enable-stage affirmation --enable-stage tuning` enables them. Unknown
feature names fail. Required stage narration is marked `narration_required`;
missing approved wording is not silently replaced by an English placeholder.

Three compositions reuse the library:

- `OCF-TPL-SESSION-PREP-LEARN-001`: teaches the concepts and cue associations.
- `OCF-TPL-SESSION-PREP-ROUTINE-001`: concise recall for an experienced listener.
- `OCF-TPL-SESSION-FUNCTION-INSTALL-001`: function-specific purpose/practice,
  optional examples, shared command learning and future use; `--enable-stage
  return` includes close/return, otherwise continuation remains possible.

Setting-aside and working-state concepts avoid permanent coupling to “Energy
Conversion Box” / “Access Channel” wording. Those terms remain under review.
Existing compatible identifiers are retained.

## Cue profiles

`audio/cues/profiles/OCF-CUE-PROFILE-DEFAULT.yaml` explicitly disables every
current cue. Sound design remains TBD. A configured profile can bind a cue to
`disabled`, a licensed `asset` path, or a named `generator` plus parameters.
`bind_document_cues` checks references without generating or playing audio.
There are no baked-in prototype frequencies. Active bindings are a future audio
playback contract, not an implemented player.

Changing profile assets does not change semantic sessions or translations.
Activation commands stay function metadata and are never cue-profile bindings.

### Operational cue meaning

**Playback of an operational state cue means its semantic event is actually
occurring.** OPEN, READY, CLOSE, Focus-Ten and session-complete signals are not
illustrative sound effects. Explanation, priming and verbal review do not
replay them. This is a statement about the session's operation, not a claim
that a listener has reached a scientifically measured internal state.

The current operational identities (`focus.ten.enter`, `focus.ten.ready`,
`focus.eleven.open`, `focus.eleven.ready`, `focus.eleven.close`,
`session.complete`) require the same `semantic` identity on their owning event.
The binder and narration validation enforce this even while bindings are
disabled. Neither `intentional_repeat` nor a casual rehearsal label bypasses
the contract. Future community cue identities remain extensible.

If sound-recognition training is needed later, it must be a deliberately
specified **cue-rehearsal semantic operation** with an explicit training
context and validation policy. That workflow is not shipped. Do not alias an
operational sound under another name merely to evade the operational rule.
Actual playback remains unshipped; a future player must emit a binding only
when it dispatches the owning semantic event.

### Preparation Learning event grammar

The composed event data, rather than the prose, gives this order:

```text
learn-working-state.prime → open.prepare
→ open.open [focus.eleven.open cue reference + spoken Eleven, one event]
→ open.transition [F10→F11 DSP directive + transition guide]
→ 25s pause after the guide
→ open.ready [focus.eleven.ready cue reference + Focus Eleven identification]
→ recognize-eleven recognition/practice

close.prepare
→ close.close [focus.eleven.close cue reference + spoken Ten, one event]
→ close.transition [F11→F10 DSP directive + settling guide]
→ 25s pause after the guide
→ close.ready [focus.ten.ready cue reference + Focus Ten identification]
→ recognize-return recognition
```

Cue references and their words/identification share a coordination event.
There is no separate authored sound-before-word sub-event or guaranteed cue
lead-in. Binding metadata is not evidence of physical playback. Whether the
future audio player emits a cue before its event's narration is a production
alignment decision still to be made; changing the text composition is not
needed for RC1. The shared coordination model is approved. Exact within-event
cue/speech synchronization is an audio-rendering decision: cue onset can be
0ms with configurable speech onset, without changing semantic identity or
introducing separate semantic events.

## Draft inspection

```bash
ocf session compose --template OCF-TPL-SESSION-PREP-LEARN-001 \
  --enable-stage affirmation --output /tmp/preparation-architecture.yaml
ocf locale resolve --file /tmp/preparation-architecture.yaml --locale en-US
```

These commands compose and resolve the en-US text draft, not production audio.
The complete review transcript and developer event/pause view can be regenerated
with `python3 scripts/tools/preview_preparation_learning.py`. Follow the
[narration standard](NARRATION_STANDARD.md) and [migration inventory](NARRATION_MIGRATION.md)
when reviewing or changing resources.

## Validation and compatibility

`make check` now validates stage/profile schemas and composes library templates
structurally. Architecture drafts report pending original narration; runtime
render preflight rejects their missing required resources. Imported/adapted
templates are checked without inventing contributor-slot text.

Resources can declare `requires_events` (semantic identities they depend on)
and `required_pronunciation` (tokens, or variable names resolving to tokens).
Translations must preserve those contracts. Required pronunciation must be
available for the chosen backend; unsupported hints do not silently satisfy it.
Non-required hints continue to be optional. Pronunciation replaces TTS tokens,
never repeats them and never changes visible command spelling/subtitles.

The render ledger records original event IDs, generated utterance IDs, actual
starts/ends, localized text provenance and resolved auditory bindings. Binding
records are not played audio. Static Farfield/reference-master beds retain
their explicit preset timelines: the semantic DSP ledger is available to a
future state-aware synthesizer, not an automatic rewrite of those presets.

Compatibility change: sessions which relied on silent speech truncation must
fix their timing or explicitly opt eligible narration into reflow. Valid
non-overlapping inline/imported sessions retain wording and fixed starts.
Unknown command ownership is now an error for command-bearing canonical keyed
narration; an audio build supplies its manifest's function identity.
