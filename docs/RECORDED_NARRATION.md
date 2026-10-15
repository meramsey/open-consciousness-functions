# Recorded narration

Use your own local recordings as narration in the existing complete-session
renderer. OCF binds audio to stable event/resource IDs and measures its duration;
the semantic timeline still owns state and DSP boundaries. For mixed recording
and TTS selection, see [hybrid narration](HYBRID_NARRATION.md). Training datasets
are a separate [voice workflow](VOICE_WORKFLOWS.md).

## Discover, initialize and import

Run from the checkout root with Python 3.11+. Substitute actual local files and
IDs from `narration sources`; example paths are placeholders. Record externally
with a recorder/DAW and keep unprocessed originals.

```bash
python scripts/ocf.py narration sources OCF-SLP-005 --locale en-US
python scripts/ocf.py narration init OCF-SLP-005 \
  --output .ocf-work/my-narration/sources.json --mode recording --fallback error
python scripts/ocf.py narration inspect recordings/opener.wav
python scripts/ocf.py narration import OCF-SLP-005 \
  --sources .ocf-work/my-narration/sources.json --file recordings/opener.wav \
  --id opener-v1 --event function-opener.block --speaker my-speaker \
  --session day-one --version 1
```

Initialization creates a source manifest, not audio. Import technically inspects
the input and copies its original bytes into a checksum-named `assets/` file
beside the manifest. It records the source checksum, exact resolved text
fingerprint, locale, speaker, session/version and explicit target. Import leaves
approval pending, consent/license unknown and redistribution permission false.
Supply `--consent self-recorded` or `authorized-contributor` only when that is your
actual declaration. Import does not independently verify consent or speech.

Use `--resource RESOURCE_KEY` instead of `--event EVENT_ID` to reuse an exact
resource take in the selected function. `--unit N` selects a 1-based semantic
sentence unit from the existing pacing plan. New IDs/versions preserve earlier
takes; duplicate recording IDs are refused. In recorded-only mode every spoken
event or selected unit needs coverage before preview/render can succeed.

### Explicit cuts from a stage file

```bash
python scripts/ocf.py narration import OCF-SLP-005 \
  --sources .ocf-work/my-narration/sources.json --file recordings/stage.wav \
  --id opener-cut-v1 --event function-opener.block --speaker my-speaker \
  --start 1.25 --end 8.5
```

Both markers are required; `0 <= start < end` must fit the audio. A segment is
selected **after whole-file preparation**, at rounded frame positions in the
prepared working-rate WAV. If you explicitly trim the file during preparation,
these offsets refer to that prepared file. Inspect the preparation receipt and
selected segment duration/checksum. OCF does not automatically align a stage
recording, identify sentence boundaries, or verify transcript fidelity.

## Preflight and render

After importing complete spoken coverage:

```bash
python scripts/ocf.py narration preview OCF-SLP-005 \
  --sources .ocf-work/my-narration/sources.json
python scripts/ocf.py narration validate OCF-SLP-005 \
  --sources .ocf-work/my-narration/sources.json
python scripts/ocf.py audio render OCF-SLP-005 \
  --narration-sources .ocf-work/my-narration/sources.json \
  --narration-source recording --dry-run
python scripts/ocf.py audio render OCF-SLP-005 \
  --narration-sources .ocf-work/my-narration/sources.json
```

`--narration-source recording` is optional when the manifest already selects
`mode: recording`. `--voice` is optional; fully recorded narration needs no TTS
backend. Missing/stale/corrupt recordings fail, without TTS fallback. These flags
belong to the default complete-session mode, not `--mode narration-only`.

For ordinary per-cue manifests, `sources --sources FILE`, `preview` and
`validate` use the same source-compatibility preflight: schema, finite values,
contained paths, locale, catalog checksums, coverage and selected text bindings.
CLI `narration validate` is **not a full technical decode of the catalog**.
Use `narration inspect FILE` for original-audio decode/metrics, or the explicit
queued `ocf_validate_recordings` operation for selected originals. Complete
marked stems also undergo preparation/measurement during preflight. See
[MCP jobs](MCP.md) for workspace containment, polling and queued-input identities.

Text hashes bind the declared expected text. They do not establish that a human
actually spoke it, perform speech recognition, or grant listening/release
approval. The emitted transcript follows declared resolved text, not ASR.

## Complete marked session stem

For one opaque whole-session narration file, declare `session_stem` in the
version 2.0 sources manifest, using
[`narration-stem.schema.json`](../schemas/narration-stem.schema.json). This is a
manual manifest path; `narration import` imports event/resource takes, not a
complete marker ledger. The stem requires `mode: recording`; it cannot combine
with a recording catalog, per-cue source choices, speaker processing, or
speaker/stage gain overrides.

- Supply a contained relative `file`, original `sha256`, locale, declared speaker,
  version and `markers`. An optional session fingerprint binds the session version.
- Mark **all composed event IDs**, including nonspoken semantic/DSP events, with
  `at` and `speech_duration`. Extra/missing markers fail. Spoken markers require
  positive measured speech duration and exact `text_sha256`; nonspoken markers
  require zero speech duration.
- Times refer to the original untrimmed recording. Markers must reproduce the
  composed scheduler's anchors within one frame (capped at 20 ms), fit the audio,
  and preserve speech/pause non-overlap. Optional `end` is the structural event
  end: `at + max(speech_duration, DSP transition_s) + pause_after`, not just speech
  end. Truncated files or stale text/session/checksum bindings fail.
- Declare every DSP boundary explicitly. OCF never guesses it from audio,
  transcript wording, filename, silence or tone frequency.
- The stem adapter preserves interior cadence and adds no semantic pauses, tail
  silence, speed/pitch change or implicit effects. Trimming is forbidden. Explicit
  permitted processing and output-format conversion retain the timeline. The
  complete-session mix envelope and renderer tail remain separate pipeline behavior.

The same `audio render FUNCTION --narration-sources FILE` path produces a complete
audition with a source/marker/preparation report. Successful technical checks
leave speech-content review and listening/release approval pending.

## Non-destructive preparation and stereo

```bash
python scripts/ocf.py narration preprocess recordings/stage.wav \
  --rate 44100 --channels 2 --output .ocf-work/stage-prepared.wav
python scripts/ocf.py narration preprocess recordings/stage.wav \
  --processing private/processing.json --rate 44100 --channels 1 \
  --output .ocf-work/stage-processed.wav
```

Choose unused WAV and `.processing.json` sidecar paths. The optional processing
file follows [`recording-processing.schema.json`](../schemas/recording-processing.schema.json).
Defaults apply no DC removal, trimming, gain change, fades, high-pass,
compression, peak normalization or loudness normalization. There is no automatic
aggressive denoising/effect chain. Original files are preserved. Explicit effects
are reported in order: channel conversion, resampling, DC removal, trimming,
high-pass, gain, compression, loudness, peak target, fades, PCM16 quantization.

WAV/FLAC/MP3/M4A are accepted, mono/stereo at 8–192 kHz. Native integer PCM WAV
inspection and same-rate PCM16/channel conversion need no external codec tools;
compressed/float decoding, resampling and selected filters require FFmpeg and
ffprobe. Input and decoded floating PCM each have a 256 MiB ceiling; unsupported,
nonfinite or excessively large samples and nonfinite settings fail explicitly.

Preparation defaults to mono. Set sources `output_channels: 2` for stereo
narration: L/R order is preserved and mono is duplicated. Mono conversion averages
L/R without hidden loudness compensation. The binaural/background bed and final
complete-session master remain stereo. Narration processing never runs on the bed.

Reports include frames/duration/rate/channels, source/processed hashes, sample
peak, per-channel RMS/DC/clipping, silence fraction, stereo correlation/imbalance,
explicit trims/filters/gain and cache identity/hit status. Loudness is optional.
Sample peak is not true peak; rail counts do not prove original waveform clipping.
The 10th-percentile 50 ms RMS estimate is a signal-level proxy, not measured room
noise, SNR, transcript accuracy or voice quality. Undefined measurements are null.

## Cache and reproducible technical checks

Prepared recordings use a private content-addressed cache under
`.ocf-work/cache/recordings/`. Identity includes original bytes/suffix, normalized
finite settings, rate/channels, code/schema hashes, Python/platform and any used
tool executable hashes/versions. Atomic receipts bind immutable WAV/report
generations; reuse verifies both hashes, PCM format and reported measurements.
Segment selection follows cached whole-file preparation and has its own receipt.

The real technical driver is
[`scripts/tools/verify_narration_engine2.py`](../scripts/tools/verify_narration_engine2.py):

```bash
python scripts/tools/verify_narration_engine2.py prepare \
  --output .ocf-work/my-narration-demo --function OCF-SLP-005 --voice OCF-VOICE-0002
python scripts/tools/verify_narration_engine2.py verify \
  --prepared .ocf-work/my-narration-demo RECORDED_REPORT_DIR GAIN_REPORT_DIR HYBRID_REPORT_DIR
python scripts/tools/verify_narration_engine2.py benchmark-recording \
  --output .ocf-work/my-recording-benchmark --repeats 3 --warm-runs 2
```

`prepare` creates new private synthetic-tone fixtures and manifests, not renders;
its JSON provides exact queue CLI arguments. It requires an existing Piper profile
for the hybrid variant. Start the returned jobs explicitly, poll them, then pass
their actual completed report directories to `verify`. All three variants are
needed for complete comparisons; fewer produce a partial result. Checks include
source/gain receipts, hashes, measured timeline/state anchors, stereo decoding,
background continuity and an intentionally stale text fingerprint rejection.

Fixtures are **synthetic tones, not human narration, and do not match the declared
transcript**. They test technical plumbing only. `benchmark-recording` measures
wall time for a local 10-second stereo fixture using isolated cold caches and
verified warm reads, preserving existing caches. It checks byte equality and
reports trials/medians; timings depend on the local runtime and are not a speed,
training, perceptual or production-throughput claim.
