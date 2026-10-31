# Private zero-shot voice packs (MVP)

OCF reference packs are private OCF voice profiles, not trained models. They keep
the reference WAV and consent declaration under `.ocf-work/cache/voices/models/`
and register metadata in `.ocf-work/cache/voices/profiles/`. Model weights are
external dependencies and are not copied into each pack. Piper remains the
default narrator. On POSIX, pack directories are mode 0700 and reference,
consent, cache and audition files are mode 0600; Windows uses its normal account
ACLs and was not platform-tested in this MVP.

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
declaration. Chatterbox Nano does not require reference transcription; when the
words are not confirmed, omit `--transcript` and OCF records `not-provided`
instead of inventing a transcript. A supplied transcript is provenance only,
not sent as conditioning text. The declaration is recorded locally but does
not independently verify legal ownership or consent:

```bash
python scripts/ocf.py voice create-pack \
  --reference .ocf-work/cache/voices/prepared/REPLACE.wav \
  --id OCF-VOICE-9100 --name "My private voice" --locale en-US \
  --consent-declaration "I own this voice recording and authorize its private use."
python scripts/ocf.py voice inspect-pack OCF-VOICE-9100
python scripts/ocf.py voice export-profile OCF-VOICE-9100 \
  --output /private/path/my-voice.json --include-assets
```

The export contains the selected reference asset only when `--include-assets` is
explicit. Consent records are never transferred; importing a cloned profile
requires a new local consent-record attachment. Create that local declaration
file under the private voice asset root before import; its contents are not
exported:

```bash
mkdir -p .ocf-work/cache/voices/models/OCF-VOICE-9101
printf '%s\n' "I authorize private use of this voice pack on this computer." \
  > .ocf-work/cache/voices/models/OCF-VOICE-9101/consent.txt
python scripts/ocf.py voice import-profile /private/path/my-voice.json \
  --include-assets --id OCF-VOICE-9101 --consent-record OCF-VOICE-9101/consent.txt
```

Install the optional backend into a project-local environment without modifying
OCF's Piper environment. Install dependencies explicitly; the pretrained Nano
model is then fetched on first inference and cached in the OCF workspace:

```bash
python -m venv .ocf-work/voice-envs/chatterbox && \
  .ocf-work/voice-envs/chatterbox/bin/python -m pip install "chatterbox-tts==0.1.7" && \
  .ocf-work/voice-envs/chatterbox/bin/python -m pip install --no-deps --upgrade \
    "git+https://github.com/resemble-ai/chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2" && \
  .ocf-work/voice-envs/chatterbox/bin/python -m pip install 'setuptools<81'
```

For Windows PowerShell, use the equivalent interpreter path in each pip step:

```powershell
python -m venv .ocf-work\voice-envs\chatterbox
& .ocf-work\voice-envs\chatterbox\Scripts\python.exe -m pip install "chatterbox-tts==0.1.7"
& .ocf-work\voice-envs\chatterbox\Scripts\python.exe -m pip install --no-deps --upgrade "git+https://github.com/resemble-ai/chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2"
& .ocf-work\voice-envs\chatterbox\Scripts\python.exe -m pip install 'setuptools<81'
```

If `OCF_WORK_DIR` is set, replace `.ocf-work` in these paths with that workspace.
The pinned upstream source adds the Nano API absent from the published PyPI
wheel; the setuptools pin keeps `pkg_resources` available for the upstream
`resemble-perth` watermarker. Then synthesize previously unseen text:

```bash
python scripts/ocf.py voice audition-pack OCF-VOICE-9100 \
  --text "A short original sentence for a private voice audition." --device auto
```

Set `OCF_CHATTERBOX_PYTHON` to another compatible optional-environment Python
executable if desired. Keep a virtual environment's `bin/python` (or
`Scripts/python.exe`) path as written: resolving its symlink can select the base
Python and lose the optional environment's PyTorch packages. Chatterbox Nano's
upstream implementation requires a reference longer than five seconds. The local audio is retained under
`.ocf-work/renders/voice-pack-auditions/`; inference is not claimed successful
until that command produces and verifies a WAV. A successful run writes a private
receipt under `.ocf-work/logs/voice-inference/VOICE-ID/`; inspect the pack to
review receipts and its measured readiness. The exact model weights and
transitive dependency licenses must be reviewed before redistribution.
This adapter currently accepts English locales only; it does not infer a locale
from reference audio. Output receives downward-only scalar gain if needed to keep
sample peaks below full scale; it is not clipped, stretched or pitch-shifted.
Nano has no OCF speaking-rate control yet; OCF measures the generated duration
instead of stretching audio to a target.

## Select the narrator and reuse speech across sessions

After a successful audition, explicitly select the private voice by stable ID
for one complete session:

```bash
python scripts/ocf.py audio render OCF-FUNCTION-ID --mode session \
  --voice OCF-VOICE-9100 --locale en-US --pacing sleep \
  --output .ocf-work/renders/my-voice-smoke
```

For a deliberately selected batch, OCF's content-addressed dry-speech cache
reuses matching narration across functions and repeated function-body passes.
Background audio and DSP mixes remain per-session; -24 dB reinforcement gain is
applied during assembly, after shared narration clips are read. Cache keys
include exact post-pronunciation text, voice/profile and model fingerprints,
reference and transcript hashes, locale, rate/style settings, and processing /
chunk-context versions. Reused WAV bytes are independently hash/decode checked.

```bash
python scripts/ocf.py audio render-many OCF-SEN-001 OCF-SEN-002 OCF-BOD-006 \
  --voice OCF-VOICE-9100 --locale en-US --pacing sleep --workers 1 \
  --speech-cache auto --dry-run
python scripts/ocf.py audio render-many OCF-SEN-001 OCF-SEN-002 OCF-BOD-006 \
  --voice OCF-VOICE-9100 --locale en-US --pacing sleep --workers 1 \
  --speech-cache auto
```

`auto` is the default and reuses only verified compatible dry speech; `off`
regenerates every unit for a fresh comparison; `refresh` regenerates each
compatible unit once in that batch and preserves prior cache generations. The
legacy `--fresh-synthesis` option aliases `--speech-cache off`. Cache summaries
record requests, unique units, hits/misses, reused hashes, inference time and
estimated saved generation time. Chatterbox uses one private worker/model per
render batch and reuses speaker conditioning only for an identical reference
hash; failures reset the worker. Stochastic regenerated speech may differ, so
the first verified cached WAV remains the artifact for its fingerprint until
an explicit refresh.

These commands render only the selected functions; do not add `--all` unless a
58-function render is separately requested. A full session still requires its
configured background/DSP engine and is never replaced by narration-only audio.
The command in [`BULK_SESSIONS.md`](BULK_SESSIONS.md) reports verified complete-
session cache receipts and the content-based candidate speech plan before it
starts synthesis.
The same guide documents the opt-in three-function actual-narration cache
benchmark; it intentionally does not mix a full session or alter approved DSP.

Never commit reference audio, consent records, embeddings or cloned narration.
