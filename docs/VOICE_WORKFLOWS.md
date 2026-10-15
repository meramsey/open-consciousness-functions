# Private voices, recording datasets and short comparisons

OCF keeps portable profile metadata, model weights, recordings, training
configuration and consent records separate. Existing OCF-VOICE-0002 and the
default voice are preserved. Built-in profiles remain under
`audio/voices/profiles/`; imported private profiles/models use
`.ocf-work/cache/voices/{profiles,models}/`. Set `OCF_VOICE_ASSETS` to a dedicated
model directory; relative values resolve from the repository root.

## Supported operations

```bash
python scripts/ocf.py voice list
python scripts/ocf.py voice inspect OCF-VOICE-0002
python scripts/ocf.py new voice
python scripts/ocf.py voice import-model /path/to/model.onnx --id OCF-VOICE-9001 --name "My private voice"
python scripts/ocf.py voice validate-profile .ocf-work/cache/voices/profiles/OCF-VOICE-9001.yaml
python scripts/ocf.py voice audition OCF-VOICE-0002 OCF-VOICE-9001
python scripts/ocf.py audio render OCF-FND-002 --voice OCF-VOICE-9001 --dry-run
```

The import example requires your actual local ONNX file plus its adjacent
`.onnx.json`; it is not an automatic model download. Import checks metadata
and hashes, then an audition tests actual inference. Duplicate IDs/assets are
never silently replaced. Profiles describe version, locale, backend, model and
configuration checksums, speaker ID, sample rate, rate/pronunciation settings,
attribution, license, distribution permission, privacy and consent status.
Existing legacy `piper_model` references still work. Future engines remain
explicit backend adapters; configuration cannot execute arbitrary commands.

Use `--kind cloned --consent self-recorded --consent-record RECORD_REFERENCE`
only for your genuinely authorized model; authorized contributor voices use
`authorized-contributor`. These are user declarations, not independently
verified permission. Unknown consent blocks cloned-profile validation.
Inference access never implies permission to redistribute recordings or weights.

The short comparison uses original versioned prompts in
`audio/voices/recording-script.json`, not protected or historical narration.
It covers ordinary speech, relaxation, counting, focus terminology and command
pronunciation. Every voice receives the same text/pacing, silence-only background,
44.1 kHz output and -3 dBFS peak target. This is peak normalization, not a claim
of equal perceived loudness. Reports record actual timing, synthesis controls
and hashes; listening approval remains unset. Current original prompts are en-US.

## Record a dataset

```bash
python scripts/ocf.py voice dataset-init .ocf-work/voice-dataset --id my-voice --rate 22050
python scripts/ocf.py voice validate-dataset .ocf-work/voice-dataset/dataset.json
python scripts/ocf.py voice training-plan --dataset .ocf-work/voice-dataset/dataset.json --backend piper
```

Initialization creates prompts and named-file slots; it does not activate a
microphone or fabricate recordings. Use a local recorder/DAW to record each
prompt into its named mono PCM16 WAV. Maintain unprocessed originals separately.
The deterministic manifest records exact transcripts and train/validation/test
splits. Do not put duplicate takes into different splits.

- Use a consistent microphone; a cardioid USB/XLR microphone with a pop filter
  is practical, but room noise and positioning matter more than price.
- Choose a quiet, soft-furnished room. Disable noisy fans where feasible;
  record a few seconds of room tone for manual noise-floor inspection.
- Keep the microphone approximately 15–25 cm away, slightly off-axis, with the
  same posture and distance between takes. Avoid touching the stand.
- Set gain conservatively, typically with speech peaks near -12 to -6 dBFS.
  Re-record clipping instead of trying to recover flattened peaks.
- Use the manifest's sample rate consistently (22,050 Hz for the initial Piper
  workflow; 24/44.1/48 kHz are also validated). Never merely relabel a sample rate.
- Keep breaths natural and pronunciation consistent; include vowels, sibilants,
  plosives, consonant clusters, numbers and varied sentence lengths/prosody.
- Align one exact transcript to each recording. Mark corrections in the
  transcript or re-record; do not silently align a different utterance.
- Keep held-out validation/test phrases and voices private. Record speaker
  authorization, attribution, permitted uses and redistribution decisions.

Validation checks decode, PCM width/channels/rate, bounded duration, clipping,
level, excessive near-silence, missing transcripts/audio, duplicate PCM and
split coverage. RMS/silence metrics are not an independent room-noise measurement
or a voice-quality score. No automatic denoising or source rewriting occurs.

## Training/adaptation status: unsupported until verified

No OCF training adapter has produced and tested a model in this milestone.
`training-plan` reports this explicitly; there is no fake `train` command or
successful-cloning claim. No authorized speaker dataset was supplied. The local
environment has 6 GiB VRAM and no Torch training installation.

Evaluated upstream paths:

- [Piper training](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/TRAINING.md):
  separate PyTorch Lightning/Cython training stack, dataset preparation and
  ONNX export. This is not a simple inference-side cloning API. Upstream reports
  most training on 24/48 GiB GPUs and user success from 8 GiB; that is not a
  guarantee for this 6 GiB host. The current repository also requests maintainers.
  Engine, checkpoint and dataset licenses must be checked independently.
- [F5-TTS](https://github.com/SWivid/F5-TTS): local reference-conditioned inference
  and fine-tuning are documented upstream, including Apple Silicon inference
  setup. Code is MIT; the README identifies pretrained models as CC-BY-NC.
  OCF has not verified this engine's inference/training on any platform and
  does not silently install it or assert redistribution permission.

Use a separate pinned upstream environment only after supplying a validated,
authorized dataset and checking the specific engine/model license. Follow its
current authoritative training/export guide; imported trained ONNX models can
then use OCF's verified profile/audition path. Training memory, quality and native
OS compatibility remain unverified until an actual model is produced and tested.

Share portable metadata only deliberately. Large weights belong in separately
authorized model packages/release assets. Private recordings and consent details
are not published by any OCF command.
