# Voice capabilities and portable profiles

OCF supports Piper/eSpeak and an optional local Chatterbox Nano reference-audio
adapter. Chatterbox Nano runs in a separate project-local Python environment;
Piper's existing environment/default is unchanged. F5-TTS remains unsupported.
Installing a package or importing profile metadata does not itself verify
inference or create a personalized voice.

The pack and audition commands use the shared `voice_engine_cli.add_commands`
and `dispatch` paths. Unit tests use synthetic signals; actual inference is an
explicit opt-in integration test and is not required by public CI.

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
`OCF_VOICE_ASSETS` overrides the asset root. Packs use `voice prepare-reference`,
`voice create-pack`, `voice inspect-pack`, `voice export-profile` and
`voice import-profile`; see [private packs](VOICE_PACKS.md). Test new text with
`voice audition-pack ID --text ...`, then route a single OCF voice smoke through
`voice smoke ID --locale en-US`. The `inference_verified` capability field is
conservative process-level status, so keep the individual audition receipt as
evidence of a real run. Do not infer personal identity or quality from a
synthetic test reference.
See [recording/training preparation](VOICE_TRAINING.md) and
[voice workflows](VOICE_WORKFLOWS.md) for the existing model-import path.
