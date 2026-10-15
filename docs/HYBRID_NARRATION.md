# Hybrid narration

Hybrid mode selects recorded takes and local TTS explicitly within one semantic
session. It reuses the complete-session renderer, measured ledger and independent
DSP pipeline. Start with [recorded narration](RECORDED_NARRATION.md) for import,
segment cuts, processing, stereo, cache receipts and technical verification.

## Create and preview a source plan

```bash
python scripts/ocf.py narration init OCF-SLP-005 \
  --output .ocf-work/my-hybrid/sources.json --mode hybrid --fallback tts \
  --voice OCF-VOICE-0002
python scripts/ocf.py narration import OCF-SLP-005 \
  --sources .ocf-work/my-hybrid/sources.json --file recordings/opener.wav \
  --id opener-v1 --event function-opener.block --speaker my-speaker
python scripts/ocf.py narration preview OCF-SLP-005 \
  --sources .ocf-work/my-hybrid/sources.json
python scripts/ocf.py audio render OCF-SLP-005 \
  --narration-sources .ocf-work/my-hybrid/sources.json \
  --narration-source hybrid --dry-run
python scripts/ocf.py audio render OCF-SLP-005 \
  --narration-sources .ocf-work/my-hybrid/sources.json
```

Use actual recording paths and an installed compatible TTS profile. The manifest
already selects hybrid mode, so `--narration-source hybrid` is optional. An
explicit `--voice PROFILE` supplies the default TTS voice; otherwise use the
manifest's `default_voice`, then the document's `voice_profile`. Scoped voice
choices still take precedence. `--voice` is optional, but every selected TTS path
must resolve to an available locale-compatible backend at render time. Source
preview alone does not establish successful inference.

## Source precedence

[`narration-sources.schema.json`](../schemas/narration-sources.schema.json) defines
the version 2.0 manifest. For each spoken event the resolver chooses the first
applicable explicit source choice:

1. Manifest `events[EVENT_ID]`.
2. The event's own `voice.profile` (selects TTS).
3. Manifest `resources[NARRATION_KEY]`.
4. Manifest `stages[STAGE_ID]`.
5. Manifest `functions[FUNCTION_ID]`.
6. Automatic catalog matching under the manifest mode and default voice.

Choices declare `source: recording|tts|silence`, with optional `recording_id`,
voice/speaker, gain, rate and processing controls. `recording_id` requires
`source: recording`. Silence cannot suppress required spoken text. Nonspoken
events remain intentionally nonspoken and retain their structured timing.

Without an explicit choice, recordings match declared selectors, never filenames.
Selectors may constrain event ID, function ID, narration key, stage ID and 1-based
unit index. Specificity scores are respectively 16, 8, 4, 2 and 32; equal-best
matches fail as ambiguous. Resolve ties with an explicit `recording_id`.

### Whole takes and sentence units

- Automatic unit selection applies only where the event already has a semantic
  pacing plan and no explicit scoped choice overrides it.
- A complete matching unit collection wins over an automatic whole-event take.
- A partial collection does not displace an available whole-event take.
- With no whole take, partial units require coverage for each remaining unit:
  recorded-only mode fails; hybrid uses its declared fallback policy.
- A whole-event recording keeps its natural interior cadence: OCF adds no
  sentence-unit pauses inside it. Only the authored outer event pause remains.
- Unit recordings keep their own cadence within each unit; the existing pacing
  plan supplies inter-unit gaps and short edge fades. TTS units use the same
  semantic role/gap plan with backend-aware rate controls. Do not include the
  same inter-unit pause twice in your recordings and pacing configuration.

A complete marked `session_stem` is a separate recorded-only path. It cannot
combine with hybrid/per-cue source selection; see the
[all-event marker contract](RECORDED_NARRATION.md#complete-marked-session-stem).

## Explicit fallback and declared speakers

`mode: recording` never substitutes TTS. Hybrid requires an explicit
`fallback: error` or `fallback: tts`. The latter permits automatic TTS only for
uncovered narration; an explicit TTS choice is intentional even with
`fallback: error`. Missing files, bad checksums, stale text, invalid locale or
ambiguous recordings are errors, not reasons to fall back. Catalog checksums are
checked even for unselected takes. Narration-language fallback remains separately
strict under [localization](LOCALIZATION.md).

Reports identify source, selection scope, recording/voice/speaker, expected text
hash, fallback reason and measured timing. `speaker_consistency: report` is the
default; `require-single` rejects more than one **declared** selected speaker
and requires an explicit speaker identity for every spoken source.
This compares metadata, not voice biometrics, acoustic similarity or identity.
Use honest speaker declarations when mixing a recording with a TTS profile.

## Gain, processing and timing

Source manifests and processing profiles require finite JSON-compatible values;
YAML NaN/infinity is rejected. Combined source gain is the sum of choice,
speaker, stage, recording-entry and event `voice.gain_db`, bounded to -60..24 dB.
Selected TTS also applies its profile gain. The complete-session mix's linear
narration gain is a separate control.

Recording preparation merges `speaker_processing`, recording-entry processing,
then choice processing (later keys win). TTS processing starts from supported
profile defaults, then resolved source processing. Explicit processing gain and
source/mix gains are distinct stages; inspect receipts to avoid doubling a gain.
Supported TTS defaults include processing gain, peak normalization and optional
silence trim; `denoise` is unsupported, and a processing sample rate conflicting
with the session working rate fails. Speaker choice, pronunciation, model identity
and effective rate are retained in TTS receipts and synthesis cache inputs.
Choice `rate_scale`, then event `voice.rate`, then 1.0 supplies the event TTS
rate; declared controls are bounded to 0.5..2. Semantic-unit/session TTS pacing
also contributes its configured rate. Recorded speech is not speed/pitch adjusted.

Measured prepared durations drive speech-end/event-end dependencies and DSP
anchors. Replacing TTS with a recording may change total duration and transition
times while preserving semantic identity, configured waits and selected DSP
presets. OCF does not guess new boundaries, align arbitrary audio automatically,
or compress waits to fit. Processing and narration-channel choices never process
or downmix the independent stereo binaural bed. Review the source coverage,
preparation receipts and complete session/timing reports before listening review;
text compatibility and technical decoding do not verify spoken content or approve
a release.
