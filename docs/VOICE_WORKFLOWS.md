# Private voices, recording datasets and short comparisons

OCF keeps portable profile metadata, model weights, recordings, training
configuration and consent records separate. Existing OCF-VOICE-0002 and the
default voice are preserved. Built-in profiles remain under
`audio/voices/profiles/`; imported private profiles/models use
`.ocf-work/cache/voices/{profiles,models}/`. Set `OCF_VOICE_ASSETS` to a dedicated
model directory; relative values resolve from the repository root.

## Supported operations

The shared CLI ships capability discovery, profile export/import and import-first
dataset commands. Use [capabilities/profile portability](VOICE_CLONING.md) and
[training preparation](VOICE_TRAINING.md) for their detailed contracts.

```bash
python scripts/ocf.py voice capabilities --json
python scripts/ocf.py voice capabilities --gpu --json
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

Profiles and Piper configuration must contain finite JSON-compatible values;
NaN/infinity is rejected. Profile gain, processing defaults, speed and speaker
selection are explicit controls, not evidence of a trained or cloned identity.
In this checkout, private `OCF-VOICE-9001` is an ordinary imported Lessac Piper
installed-model profile used for inference/audition checks. It is not a cloned
voice or evidence of training.

### Portable metadata and private assets

These examples require an existing private profile and unused destinations:

```bash
python scripts/ocf.py voice export-profile OCF-VOICE-9001 \
  --output .ocf-work/portable-voice.json
python scripts/ocf.py voice import-profile .ocf-work/portable-voice.json --id OCF-VOICE-9002
python scripts/ocf.py voice export-profile OCF-VOICE-9001 \
  --output .ocf-work/private-voice-bundle.json --include-assets
python scripts/ocf.py voice import-profile .ocf-work/private-voice-bundle.json \
  --include-assets --id OCF-VOICE-9003
```

Default export is metadata only: machine paths and private consent references
are redacted, model/reference-audio files are not copied, and exact reference
transcripts are not rewritten. `--include-assets` exports an adjacent `*-assets`
directory; keep it with the JSON. Import also requires `--include-assets` to opt
into checksum-verified private asset copying. Existing IDs/conflicting assets
are refused; a metadata-only import may remain unavailable until assets exist.
For profiles requiring authorization metadata, reattach a real local
`--consent-record` relative to the voice asset root. Portable metadata grants no
rights to publish weights, reference audio or consent records. Import does not
verify inference; follow it with profile validation, doctor and an explicit audition.

### Short comparisons

The short comparison uses original versioned prompts in
`audio/voices/recording-script.json`, not protected or historical narration.
It covers ordinary speech, relaxation, counting, focus terminology and command
pronunciation. Every voice receives the same text and semantic unit/gap policy
(native profile rate controls are recorded), silence-only background,
44.1 kHz output and -3 dBFS peak target. This is peak normalization, not a claim
of equal perceived loudness. Reports record actual timing, synthesis controls
and hashes; listening approval remains unset. Current original prompts are en-US.

## Record a dataset

```bash
python scripts/ocf.py voice dataset-init .ocf-work/voice-dataset --id my-voice --rate 22050
python scripts/ocf.py voice dataset-guide .ocf-work/voice-dataset/dataset.json --json
python scripts/ocf.py new voice-dataset .ocf-work/voice-dataset/dataset.json
python scripts/ocf.py voice dataset-record .ocf-work/voice-dataset/dataset.json normal-001 \
  --audio recordings/normal-001.wav --session day-one --speaker my-speaker
python scripts/ocf.py voice validate-dataset .ocf-work/voice-dataset/dataset.json
python scripts/ocf.py voice training-plan --dataset .ocf-work/voice-dataset/dataset.json --backend piper
```

Initialization creates prompts and named-file slots; it does not activate a
microphone or fabricate recordings. Use a local recorder/DAW to record each
prompt into its named mono PCM16 WAV. Maintain unprocessed originals separately.
The deterministic manifest records exact transcripts and train/validation/test
splits. Do not put duplicate takes into different splits.

`new voice-dataset MANIFEST` opens an existing manifest and guides external-file
imports, displaying exact script slots and asking for speaker/session/setup
notes. It never captures a microphone. Blank paths skip; `:quit` or interrupted
input retains successful imports. `dataset-record` is the noninteractive path:
choose the actual prompt ID shown by `dataset-guide` and an existing mono PCM16
WAV at the manifest rate (at most 120 seconds per take). Imports preserve source
bytes, text fingerprints and split assignments; another session adds a take.
Use a new session ID if speaker or setup changes. The wizard does not manufacture
authorization metadata, resample recordings or rewrite exact transcripts.

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

## Use recordings in a session

Training datasets and rendered session narration are separate. For event/resource
and semantic-unit takes, stage-file segment cuts or a whole complete marked stem,
use [recorded narration](RECORDED_NARRATION.md). For mixed TTS/recordings and
explicit fallback/speaker policy, use [hybrid narration](HYBRID_NARRATION.md).
Render via `audio render FUNCTION --narration-sources FILE`; recorded-only needs
no TTS voice. Preserve originals and the independent stereo bed. Source text
fingerprints and declared speaker checks do not verify speech content or identity.

## Training/adaptation status: unsupported until verified

No OCF training adapter has produced and tested a model in this milestone.
`training-plan` reports this explicitly; there is no fake `train` command or
successful-cloning claim. No authorized speaker dataset was supplied. The local
environment observed on 2026-10-15 has neither F5-TTS nor Torch installed; the
explicit GPU probe reported about 6 GiB total VRAM and about 1 GiB free. These are
local observations, not future hardware availability or training-memory promises.
`voice capabilities` distinguishes upstream features, shipped adapters, installed
packages and unverified inference. Only explicit `--gpu` requests the bounded GPU
probe; capability discovery itself does not run inference or training.

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
