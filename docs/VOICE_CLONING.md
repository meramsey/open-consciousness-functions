# Voice capabilities and portable profiles

OCF supports local basic TTS through Piper and eSpeak adapters. Upstream
reference-conditioned speech (for example F5-TTS) is distinct from a working OCF
adapter: its OCF inference and training remain unsupported. Installing a package
or importing profile metadata does not verify inference or create a cloned voice.

Once wired into the shared CLI, the commands below use
`voice_engine_cli.add_commands` and `dispatch`. Regression tests exercise the real
shared parser and main-to-service forwarding with mocked capability/profile
services; they do not run model inference.

```bash
python scripts/ocf.py voice capabilities --json
python scripts/ocf.py voice capabilities --gpu --json
```

Reports distinguish upstream features, OCF adapter support, local installation,
availability and unverified inference. Unsupported paths include blockers,
next actions and upstream guide/license notes. `--gpu` explicitly requests a
bounded local NVIDIA query; discovery otherwise performs no GPU query. Reported
memory does not establish training readiness.

## Move a profile

Select an existing profile by unambiguous ID, slug or name. These examples assume
an existing private `OCF-VOICE-9001` and unused destination paths/IDs:

```bash
python scripts/ocf.py voice export-profile OCF-VOICE-9001 --output .ocf-work/portable-voice.json
python scripts/ocf.py voice import-profile .ocf-work/portable-voice.json --id OCF-VOICE-9002
python scripts/ocf.py voice export-profile OCF-VOICE-9001 --output .ocf-work/voice-bundle.json --include-assets
python scripts/ocf.py voice import-profile .ocf-work/voice-bundle.json --include-assets --id OCF-VOICE-9003 --consent-record private/consent.txt
```

Default export contains portable JSON metadata without copying model/reference
audio assets. Private consent references and machine paths are redacted; exact
reference transcripts are never rewritten. `--include-assets` on export creates
an adjacent `*-assets` directory; keep it with the JSON bundle. On import the
flag opts into checksum-verified copying into the private asset store. Existing
IDs and conflicting assets are refused. Metadata-only import may be unavailable
until the declared assets are installed.

Cloned, reference-audio and trained profiles require explicit authorization
metadata and a local consent reference; reattach the reference on import with
`--consent-record`. It is relative to the local voice asset root, not the bundle
directory. A consent declaration is not independent authorization verification,
and portable metadata grants no redistribution rights.

Private profiles/models use `.ocf-work/cache/voices/{profiles,models}/`;
`OCF_VOICE_ASSETS` overrides the asset root. Import validates metadata and asset
identity, leaving `inference_verified: false`. Use existing `voice doctor`,
`voice validate-profile` and `voice audition` for the supported adapter workflow.
See [recording/training preparation](VOICE_TRAINING.md) and
[voice workflows](VOICE_WORKFLOWS.md) for the existing model-import path.
