# Semantic DSP state programs

Shipped: `ocf audio render-state-program` and `ocf audio build --dsp-profile`.
Narration and semantic state directives do not name an audio engine.
Profiles under `audio/background/state-profiles/` bind states to background
manifest IDs, or explicitly disable a state. Schema:
`schemas/semantic-dsp-profile.schema.json`.

```bash
python3 scripts/ocf.py audio render-state-program session.yaml \
  --render-manifest measured-speech.yaml \
  --dsp-profile OCF-DSP-DEVELOPMENT-V4-001 --output state-bed.wav
python3 scripts/ocf.py audio build OCF-AUDIO-0001 \
  --dsp-profile OCF-DSP-DEVELOPMENT-V4-001 --output output-directory
```

The first command reuses `event_timing` and `total_duration_s` (or `duration`)
from a measured narration ledger without calling TTS. The second integrates
state dispatch into the existing build. A manifest may use
`background_audio.semantic_profile`; an explicit CLI profile overrides a static
background selection. Missing required state bindings, missing engines, short
stems, contradictory from-states and overlapping transitions fail clearly.
There is no unrelated-preset fallback or silent source-loop substitution.

For each state directive, explicit `dsp.transition_s` takes precedence;
otherwise the earliest measured end-dependent child defines the end. Without
such an anchor, `transitions.fallback_seconds` is a documented rendering choice.
Linear/equal-power curves operate on continuous session-time state oscillators.
Repeated same-state directives leave gain unchanged. Disabled states produce
silence; they remain explicit selections in the render metadata.

## Supporting a state before arrival

A profile may add an `approaches` entry so a selected program becomes audible
before the listener's semantic state is declared. The entry names three existing
measured event occurrences — `begin_event`, `established_event` and the owning
`state_event` — and a `raised-cosine` `curve`. The program then rises from zero at
the begin anchor, reaches sustained level at the established anchor, and the
owning directive commits the state without replaying a ramp. The previous state
recedes across the same window using the profile's normal curve. Semantic state,
narration and cue identity are unchanged: support is not arrival.

All three anchors must exist in both the session and the measured ledger, stay in
order inside the session duration, avoid other transitions and approaches, and
name a directive that actually selects the declared target from a different
state. A disabled state, an unknown or non-numeric anchor, a duplicate arrival
directive, or a second nonzero ramp at arrival is an error, never a silent
substitution. Profiles without `approaches` keep their previous behavior exactly.

```yaml
approaches:
  - state: focus-10
    begin_event: relaxation.begin
    established_event: focus-ten.enter
    state_event: focus-ten.transition
    curve: raised-cosine
```

Anchor identity is declarative: times come from each locale/recording's measured
ledger, so the same profile follows different narration durations and languages.
See [the V2 listening finding](research/V2_LISTENING_FINDING_F10_ONSET.md) and the
[V2.1 report](releases/OCF_PREPARATION_LEARNING_DEV_V2_1.md).

The default profile selects **newer pure-SAM F11** but deliberately has no
universal F10 binding. A session requiring F10 must choose a profile with an
appropriate F10 binding or explicitly disable it. The development V4 profile
selects a visibly labelled approximation candidate: see
[measurements](research/V4_SHORT_MEASUREMENTS.md) and
[V2 report](releases/OCF_PREPARATION_LEARNING_DEV_V2.md).

Render metadata records profile/version, seed, selections, backend, preset
checksum/provenance, state-stem hashes, RMS calibration, transition windows and
their timing origin, engine commands and output identity. This records an
artifact and recipe; different engine versions/platforms need not be byte-exact.
The dispatcher does not read English strings to infer state identity or cue
operations, and does not change canonical narration or timing to fit a bed.
