# Explicit function session variants

Current bindings, not category names, govern endings and repetitions. Recall,
Circulation, Think Fast and Sleep Easy currently explicitly select the complete
locked HPlus template, including two programming/two sleep passes and waking
return. These are engineering bindings, not a claim that every future function
should use that ending or that human review is complete.

The canonical locale function resource may declare embedded
`content.bindings.session_overrides`, validated
against `schemas/session-overrides.schema.json`. Precedence is explicit CLI
arguments/override file, then function overrides, then selected template, then
its inherited locked defaults. Mappings merge recursively; no locked file is
rewritten. Plans report the resolved override settings and their source.

Example configuration (illustrative; not applied to any approved function):

```json
{
  "ending": "waking",
  "sleep_continuation": false,
  "repetitions": {"programming": 1},
  "background_gain": 0.7,
  "narration_gain": 1.0,
  "pacing": {"pauses": {"focus10_hold_s": 30}},
  "stage_maximum_seconds": {"focus11-body": 240}
}
```

Preview an operator-authored file with `audio plan FUNCTION_ID --expand
--overrides FILE.json`; render with the same `--overrides` on `audio render`.
Persist an intentionally reviewed function variant in its binding before
regenerating committed plans. Ephemeral CLI overrides never overwrite source plans.

Supported settings include registered voice/pacing/DSP profile selection,
programming/sleep repetition counts, sleep continuation, waking return,
Focus 10 induction/Focus 11 programming selection, linear background/narration
gains, semantic pacing/transition values and measured per-stage duration caps.
Hold durations use the selected pacing profile's named pause values. A measured
stage exceeding its explicit cap fails before publication; narration is never
compressed to fit. At least one function-body pass is required.

`ending: sleep` removes the waking-return stage. It retains the approved closer
verbatim; review the closer's meaning before using such a variant. Conflicting
ending/waking settings fail. No runtime paraphrase or automatic editorial
approval occurs. DSP ignores/continuity probes and excerpt selection follow the
explicit resolved stages; default Focus 10/11 settings stay locked.

## Connected preparation and relaxation

Explicitly select `OCF-PACING-CONNECTED-SESSION-001` through `pacing_profile`
for routine sessions, or `OCF-PACING-CONNECTED-LEARNING-001` for standalone
Learning. The Learning API and private configuration accept `pacing_profile`.
These successors synthesize connected prose within authored paragraphs together
without changing words, count pauses, event holds or semantic transitions.
Learning retains its 510-second practice allocation. Existing policies and
public defaults remain unchanged. Timing reports measure the combined utterance;
individual sentence timestamps are not inferred. Grouping is incompatible with
existing hybrid unit bindings. Listening approval remains separate.

## Automatic Nano and Farfield defaults

New complete sessions using Chatterbox Nano with Farfield state backgrounds now
select `OCF-BACKEND-NANO-FARFIELD-001` version 1.0.0. The policy uses the approved
A6 balance: fixed F10 −3 dB and F11 −14 dB relative to the original −18 dBFS
state-normalization baseline. These gains apply once throughout each state's
speech, gaps and closure envelope; narration gain is unchanged.

`OCF-PACING-NANO-FARFIELD-SESSION-001` and its `LEARNING` counterpart inherit the
connected preparation/relaxation wording and pauses, with native 1.00x rate
controls. Learning retains three Eleven visits and 510 seconds of practice.
The selected policy and effective mix appear in dry-run plans and render identity.
Voice-independent source plans and immutable predecessor locks remain unchanged.
The lower-level `audio build` command replays an authored transcript with its
explicit timing/mix settings; automatic selection occurs when composing a new
complete session or standalone Learning session.
The policy checks declared backend metadata, not private voice IDs or filenames.
Other voice engines, non-Farfield backgrounds, recorded/hybrid narration and
custom state normalization retain their explicit configuration.

An explicit `--mix-profile FILE` wins, including a file containing `{}` to use
unattenuated legacy mixing. A `pacing_profile` in the function or CLI overrides
wins independently; individual `pacing` overrides still apply afterward.
To disable both automatic choices, pass a JSON overrides file containing:

```json
{"backend_defaults": false}
```

Both `audio render` and `audio render-many` accept `--overrides FILE.json` and
`--mix-profile FILE`. Standalone Learning accepts `backend_defaults=False` in
its API, or `"backend_defaults": false` in private configuration. Its mix profile
may now be omitted; an explicit private profile remains authoritative. Existing
completed editions are never rewritten or relabeled by default selection.
