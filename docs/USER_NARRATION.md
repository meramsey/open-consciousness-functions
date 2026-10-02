# User-provided prerecorded narration

Shipped: `voice render --recordings`, `audio render-speech --recordings`,
`audio build --recordings`. TTS is optional; these paths do not select a TTS
backend. The narration package schema is `schemas/narration-package.schema.json`.
One recording maps to each **spoken event occurrence ID**, never English text.
Repeated identical sentences can have separate files and different durations.

```yaml
schema_version: "1.0"
id: my-voice
source_type: prerecorded-user
locale: en-US
author: me
license: private use only
redistribution_permission: false
recordings:
  purpose.purpose:
    file: purpose.wav
    sha256: REPLACE_WITH_THE_FILE_SHA256
  # Add every other spoken event ID from the composed/resolved session.
```

This explanatory snippet requires real64hex checksums and all required event
entries before it validates. Paths are relative inside the package directory.
No source file is renamed, resampled, normalized or overwritten. The renderer
checks schema, exact locale, missing/extra event mappings, paths, file existence
and original checksums before decoding. User declarations are provenance, not
proof of spoken text accuracy, pronunciation, consent or redistribution rights.

```bash
python scripts/ocf.py voice render session.yaml --recordings package.yaml \
  --locale en-US --output narration.wav
python scripts/ocf.py audio build OCF-AUDIO-0001 --recordings package.yaml \
  --locale en-US --output output-directory
```

PCM16 mono/stereo WAV works without a TTS engine or ffmpeg. Other audio formats
need ffmpeg for nondestructive in-memory decode to PCM16 mono; actual decoded
duration is measured. Sample-rate conversion/downmix occurs in build output,
without speech time-stretch or automatic loudness normalization. Original hashes,
author/license/permission, package identity, measured duration and decoder use
are recorded under `narration_source` in voice/build metadata.

Existing end-relative anchors, explicit pauses and opt-in `timing.policy: reflow`
follow **actual recording duration**. Fixed overlaps still fail. `--fit`, `--flow`,
`--even-counts`, a TTS voice and a recording package cannot be combined. Missing
recordings never fall back to TTS. Export subtitles using canonical localized text
and the measured render manifest, not timestamps borrowed from another voice.
Semantic DSP consumes this same measured ledger independently.

Current limitations: no directory-to-manifest import wizard, narration-key alias
mapping, speech-recognition/content verification, normalization controls or GUI
recorder. Disabled narration and community voice-pack distribution remain planned.
Do not relabel reference-derived wording as original OCF because a user recorded it.
