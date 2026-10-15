# Import-first recording and training preparation

OCF prepares private datasets and reports readiness. Training remains
`unsupported-until-verified`: no OCF adapter has produced and tested a model.
There is no OCF `train` or `clone` command. Upstream support and GPU memory do
not establish working OCF training or reference-audio inference.

Shared CLI integration registers `voice dataset-guide` / `dataset-record`
through `voice_engine_cli.add_commands`, and `new voice-dataset` through
`add_new_commands(new_subparsers)`, then routes execution through `dispatch`.
The examples below require that wiring. Regression tests exercise the real
shared parser, main-to-service forwarding with mocks, and synthetic-WAV wizard
imports. The existing `new voice` profile wizard and `voice training-plan` stay
separate.

## Prepare and import

```bash
python scripts/ocf.py voice dataset-init .ocf-work/my-dataset --id my-voice --rate 22050
python scripts/ocf.py voice dataset-guide .ocf-work/my-dataset/dataset.json --json
python scripts/ocf.py new voice-dataset .ocf-work/my-dataset/dataset.json
```

Initialization creates original OCF script slots, exact transcripts and stable
train/validation/test assignments. The wizard opens an existing manifest,
presents setup guidance, asks for room/microphone/gain notes, then displays each
script slot and accepts an external WAV path plus per-prompt session/speaker IDs.
Blank file paths skip slots; `:quit`, EOF or keyboard interruption retains prior
imports. Failed imports can be retried. Notes are saved with imported sessions,
not treated as acoustic measurements. Reuse a session ID only with the same
speaker and setup; use a new session ID when either changes.

Record externally using a recorder/DAW. Use a quiet, soft-furnished room, consistent
microphone position (roughly 15–25 cm, slightly off-axis), and conservative gain
with speech peaks around -12 to -6 dBFS. Inspect separate room tone manually.
OCF does not capture hardware audio, measure room noise from speech RMS, denoise,
resample or rewrite transcripts during import. Keep unprocessed originals.

For a noninteractive import, replace the source with your actual recording and
select the exact slot shown by `dataset-guide`:

```bash
python scripts/ocf.py voice dataset-record .ocf-work/my-dataset/dataset.json normal-001 --audio recordings/normal-001.wav --session day-one --speaker my-speaker
python scripts/ocf.py voice validate-dataset .ocf-work/my-dataset/dataset.json
```

Audio must be mono PCM16 WAV at the manifest sample rate, nonempty and at most
120 seconds per take. Imports retain source bytes and checksums, exact text
fingerprints, session/speaker identities and the prompt's original split.
Another session can add a take; all takes of a prompt keep the same split.
Duplicate destinations are refused. Validation reports duplicate PCM, split
leakage, changed text/checksums, format, clipping, level and silence findings.
Synthetic test WAVs verify import behavior, not voice quality or model inference.

## Inspect the training plan

```bash
python scripts/ocf.py voice training-plan --dataset .ocf-work/my-dataset/dataset.json --backend piper
python scripts/ocf.py voice training-plan --dataset .ocf-work/my-dataset/dataset.json --backend f5-tts
```

The existing command accepts `--dataset` and `--backend`; GPU probing is exposed
by `voice capabilities --gpu`. Plans report dataset readiness, local resources,
unsupported adapters, upstream guides and license notes while leaving `ready`
and `model_produced` false. The Python `voice_datasets.training_plan` service also
accepts `probe_gpu=True`; that does not add an option to the existing CLI command.

Complete audio/provenance, independent held-out data, explicit speaker
authorization metadata and a local consent record are dataset preparation
requirements. Initialization leaves consent/license unknown; the wizard never
changes those declarations automatically. Validation does not independently
verify authorization or grant rights to distribute datasets, weights or voices.

Upstream training requires a separately pinned engine/configuration and its
documented hardware/OS/export workflow. OCF does not install training stacks or
claim native training verification. A genuinely trained compatible Piper ONNX
model can follow the existing `voice import-model` / audition workflow. See
[portable profiles and capabilities](VOICE_CLONING.md) and
[voice workflows](VOICE_WORKFLOWS.md).
