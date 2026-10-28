# Private zero-shot voice packs (MVP)

OCF reference packs are private OCF voice profiles, not trained models. They keep
the reference WAV and consent declaration under `.ocf-work/cache/voices/models/`
and register metadata in `.ocf-work/cache/voices/profiles/`. Model weights are
external dependencies and are not copied into each pack. Piper remains the
default narrator.

Prepare a local WAV, FLAC or MP3. FFmpeg/ffprobe are needed for compressed input
and rate conversion; no network service is used. Automatic selection picks the
longest energetic region and is only a candidate detector, not ASR or proof that
the region contains clean speech. Use exact manual bounds if needed:

```bash
python scripts/ocf.py voice prepare-reference ~/voice.wav
python scripts/ocf.py voice prepare-reference ~/voice.flac --start 12.0 --duration 18.0
```

The result includes the prepared file path and a JSON receipt with source and
prepared SHA-256 values, source measurements, selected clip range, sample peak,
and clipping-sample count. Input is never modified. Inspect the clip and confirm
the exact spoken words yourself; OCF does not invent or automatically verify a
transcript.

Create a private profile-backed pack with an explicit ownership/authorization
declaration. The declaration is recorded locally but does not verify legal
ownership or consent:

```bash
python scripts/ocf.py voice create-pack \
  --reference .ocf-work/cache/voices/prepared/REPLACE.wav \
  --id OCF-VOICE-9100 --name "My private voice" --locale en-US \
  --transcript "Exact words spoken in the selected reference clip." \
  --consent-declaration "I own this voice recording and authorize its private use."
python scripts/ocf.py voice inspect-pack OCF-VOICE-9100
python scripts/ocf.py voice export-profile OCF-VOICE-9100 \
  --output /private/path/my-voice.json --include-assets
```

The export contains the selected reference asset only when `--include-assets` is
explicit. Consent records are never transferred; importing a cloned profile
requires a new local consent-record attachment:

```bash
python scripts/ocf.py voice import-profile /private/path/my-voice.json \
  --include-assets --id OCF-VOICE-9101 --consent-record OCF-VOICE-9101/consent.txt
```

Pack creation and preparation are implemented; Chatterbox Nano inference is not
yet enabled by this MVP. Do not select a pack for synthesis until OCF reports a
verified inference adapter. A Chatterbox Nano reference must exceed five seconds
according to its upstream implementation; shorter clips are not suitable.
Never commit reference audio, consent records, embeddings or cloned narration.
