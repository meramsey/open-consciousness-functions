# Media workflow verification and cache measurements

## Native OpenCode and original artwork

The native OpenCode 1.18.35 stdio workflow exercised brand inspection, independent
theme lookup, built-in/private voice discovery, honest unsupported training
planning, artwork job start/status/result, and verification of the completed
Recall audition. Artwork job `b8b990bcb3ca4b9687ff7a38e6f96df4` completed and
returned a 512-pixel candidate Sleep Easy cover, with no human approval.
Raw events remain in `.ocf-work/logs/opencode-media-native.jsonl`.
Native Claude Code/Codex interfaces were not exercised.

Original source geometry/palettes and eight candidate SVG variants are committed
under `brand/`. PNG/JPEG previews and the offline independently themed review
gallery stay in `.ocf-work/`. They are not the approved final public brand.

## Actual private-profile inference and comparisons

An existing operator-installed Piper model was imported into a private
OCF-VOICE-9001 profile and actually synthesized. This verifies model import
and inference; it is not cloning or training. The original built-in profiles
were preserved, and model weights/profile stay in the ignored workspace.

The same original test passages produced these speech-only comparison WAVs:

- OCF-VOICE-0001, eSpeak: 73.839 s.
- OCF-VOICE-0002, existing Piper: 70.816 s.
- OCF-VOICE-9001, privately imported Piper: 70.537 s.

All use 44.1 kHz, the same semantic unit/gap policy, no background, and -3 dBFS
peak normalization. Native rate controls and per-unit timing are recorded.
Different stochastic syntheses are not asserted to be byte-identical.
Directory: `.ocf-work/renders/voice-comparison-20261015T130236-9befe96b/`.
No human quality/listening approval or model redistribution permission is inferred.

## Measured DSP cache benefit

`python scripts/tools/benchmark_dsp_cache.py` explicitly rendered a bounded
40-second two-state program with a 25-second transition and ending fade.
It is an engineering cache probe, not a complete function session.

- Cold run: 48.0935 s, two state-cache misses, both stored after duration/RMS checks.
- Warm run: 6.6807 s, two verified state-cache hits.
- Observed local speedup: 7.20x for this probe.
- Both output SHA-256 values:
  `da848c3b6b088935ea29f8f7cbd35a02133fa1d2271c4938f5e24cb43940ed6e`.

The initial probe bypassed caching because this Farfield CLI does not report
`--version`. The corrected identity uses actual package/source content records
and the executable fingerprint; it never invents an engine version. An engine
without a defensible content identity still bypasses cache. Keys include exact
preset bytes, seed, duration and renderer/adapter identity. Cached stems are
rechecked and recalibrated; transition envelopes are applied per render.
TTS and DSP stores each have a 2 GiB bound and ownership-aware explicit cleanup.
`ocf dev ocf_cache_clean --arguments '{"kind":"dsp","dry_run":true}'` previews
DSP cleanup. Failed or historical auditions are not silently removed.

Raw measurements: `.ocf-work/logs/dsp-cache-benchmark-verified.json`.
These are local elapsed-time observations, not guaranteed cross-platform speedups.
