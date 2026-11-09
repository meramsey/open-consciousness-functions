# Use your own voice with a private reference pack

Create a reference pack, audition new text, then select that voice for an OCF
session. The optional Chatterbox Nano adapter conditions a pretrained model on
an authorized recording; it does not train a new model. Piper remains the
default narrator. Installing a package alone does not verify speech generation.

## 1. Keep your voice assets durable and private

Keep original recordings, consent records, reusable profiles and model weights
outside the checkout and disposable workspace. Without overrides, OCF uses
`.ocf-work/cache/voices/{profiles,models}/`, which workspace cleaning can remove.
A checkout-local `audio/voices/private-packs/` is ignored by Git and excluded from
`workspace clean`, but removing the checkout can still remove it.

For example, on Linux select owner-owned user-data directories before creating
or importing a pack:

```bash
export OCF_VOICE_PROFILE_DIR="$HOME/.local/share/ocf/voices/profiles"
export OCF_VOICE_ASSETS="$HOME/.local/share/ocf/voices/assets"
export HF_HOME="$HOME/.local/share/ocf/models/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub"
```

Use equivalent private user-data paths on other platforms. These variables apply
to the invoking process and its children; retain them in your private launcher
or service configuration for future sessions. Keep an independent backup and
verify copied bytes before changing storage locations. Models are external
dependencies, not copied into each pack. See [durable private delivery](PRIVATE_LISTENING_DELIVERY.md).

On POSIX, OCF pack directories use mode 0700 and reference, consent, cache and
audition files use mode 0600. Windows uses account ACLs; these permission settings
do not establish Windows inference or security verification.

## 2. Prepare and inspect a reference

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

## 3. Create and inspect the pack

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

Keep the prepared reference and a verified export in durable storage; audition
WAVs and inference receipts below use disposable workspace paths by default.

The export contains the selected reference asset only when `--include-assets` is
explicit. Consent records are never transferred; importing a cloned profile
requires a new local consent-record attachment. Create that local declaration
file under the private voice asset root before import; its contents are not
exported:

```bash
mkdir -p "$OCF_VOICE_ASSETS/OCF-VOICE-9101"
printf '%s\n' "I authorize private use of this voice pack on this computer." \
  > "$OCF_VOICE_ASSETS/OCF-VOICE-9101/consent.txt"
python scripts/ocf.py voice import-profile /private/path/my-voice.json \
  --include-assets --id OCF-VOICE-9101 --consent-record OCF-VOICE-9101/consent.txt
```

The supported `voice import-profile` API writes metadata to
`OCF_VOICE_PROFILE_DIR` (or the disposable workspace cache when unset), and
reference/model assets to `OCF_VOICE_ASSETS` (or the disposable workspace cache
when unset). Set both when importing for durable reuse; provide a local consent
record explicitly. Profile inspection reports inference readiness separately.

## 4. Provision the optional runtime and audition

First inspect `voice doctor` and `voice capabilities --json`; preserve an existing
working runtime. Select it with `OCF_CHATTERBOX_PYTHON`. For a new installation,
keep the runtime under your durable private data directory, separate from OCF's
development environment: on Python 3.12, the Nano adapter requires NumPy <2,
while the project development extra requires NumPy >=2.

The Nano API is supplied by the pinned upstream Chatterbox source revision
`5de7a54aa4e5e2baadb0182dde554908b48b85c2`, not by the published 0.1.7 wheel alone.
The verified Linux runtime uses Python 3.12, torch/torchaudio 2.6.0,
transformers 5.2.0, NumPy 1.26.4 and setuptools 80.10.2. Those direct versions
are not a complete dependency lock or a claim of native inference on other
platforms. Preserve and replay the complete compatible lock, including pinned
VCS dependencies, as described in [runtime provisioning](PRIVATE_LISTENING_DELIVERY.md#durable-private-storage).
Run `pip check`, compare the installed lock and verify fresh CLI synthesis before
using a replacement runtime. Do not install conflicting backend dependencies into
the project development environment.

For an already provisioned Linux runtime, select its virtual-environment
entrypoint explicitly (adapt the path to your installation):

```bash
export OCF_CHATTERBOX_PYTHON="$HOME/.local/share/ocf/voices/runtime/chatterbox/bin/python"
python scripts/ocf.py voice capabilities --json
```

On Windows, select the corresponding `Scripts/python.exe` using
`$env:OCF_CHATTERBOX_PYTHON`. Do not resolve the interpreter symlink: doing so can
select the base Python and lose the backend's packages. Set durable `HF_HOME`
and `HF_HUB_CACHE` before the first inference, which may download model weights.
Keep a verified copy of complete model blobs and their targets; a snapshot of
symlinks alone is not a model backup.

Then synthesize previously unseen text:

```bash
python scripts/ocf.py voice audition-pack OCF-VOICE-9100 \
  --text "A short original sentence for a private voice audition." --device auto
```

Chatterbox Nano's upstream implementation requires a reference longer than five seconds. The local audio is retained under
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

## 5. Select the narrator for a session

After a successful audition, explicitly select the private voice by stable ID
for one complete session:

```bash
python scripts/ocf.py audio render OCF-FUNCTION-ID --mode session \
  --voice OCF-VOICE-9100 --locale en-US --pacing sleep \
  --output .ocf-work/renders/my-voice-smoke
```

## Reuse speech across selected sessions

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
