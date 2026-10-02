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
