# Preparation Learning RC1 — Development Audition V2

Status: **rendered and objectively checked; listener review pending**.
Not a production master or a faithful full V4 reconstruction.
RC1 baseline: `061b2989ef13aca213112965d640fa43a036ec4a`.

## Artifacts

Local directory:
`/tmp/opencode/OCF-Preparation-Learning-en-US-RC1-dev-audition-V2/`.
Listening files start with
`DEVELOPMENT-AUDITION-V2-OCF-Preparation-Learning-en-US-RC1`:
`-listening.flac`, `-listening.mp3`, `-master.wav`, `-narration.wav`,
`-DSP-bed.wav`, `.srt`, `.lrc`.

The directory also contains `render-manifest.yaml`, `semantic-dsp-render.yaml`,
`verification.json`, frozen V1 semantic/resolved sessions and measured ledger,
V1 speech metadata/timing report, and engine logs. Reference recordings and
large audition binaries are not committed. Manifest hashes identify the exact
working-tree implementation and selected presets in addition to the base commit.
TTS is not invoked: copied speech is **byte-identical to V1**, as are subtitles.
Affirmation, resonant tuning and operational cue assets remain disabled.

Reproduce the procedure with `scripts/tools/render_development_v2.py --v1 DIR
--output NEW_DIR`; objective checks use `scripts/tools/verify_development_v2.py
NEW_DIR` (numpy/scipy/soundfile research dependencies). Checksums identify this
render, not a promise that arbitrary future engine versions reproduce its bytes.

## State dispatch

Profile: `OCF-DSP-DEVELOPMENT-V4-001`, seed0, equal-power envelopes, state RMS
target−18dBFS, master bed gain0.15. F10 candidate=`OCF-BG-0012`;
newer pure-SAM F11=`OCF-BG-0006`; ordinary waking explicitly has no DSP.

| Transition | Start seconds | End seconds | Timing origin |
| --- | --- | --- | --- |
| ordinary → F10 | 494.645533 | 499.645533 | explicit state event; configured5s fallback |
| F10 → F11 | 643.657052 | 676.150748 | measured opening transition → ready |
| F11 → F10 | 1009.000635 | 1043.542948 | measured closing transition → ready |
| F10 → ordinary | 1218.547574 | 1237.265306 | measured return directive → signal |

The waking-return narration starts1135.301134s; the DSP directive is later,
1218.547574s. The renderer follows that semantic ledger rather than interpreting
English narration as a DSP command. No Focus Three or inferred induction onset.
Cross-generation morphs, equal-power curve and RMS targets are OCF design choices.

## Actual audio verification

- Length1238.265261s (**20:38.265**),54,607,498frames, stereo44100Hz PCM24.
- Master peak−2.4773dBFS; RMS−22.1954L/−22.1953R dBFS; zero clipped samples.
- DSP bed peak−5.7945dBFS; full-session RMS−20.3115L/−20.3044R dBFS;
  zero clipped samples. State calibration uses ffmpeg's0.1dB mean-volume estimate.
- WAV and lossless FLAC decode identically:
  float64 PCM SHA256`7465bbb26e9852d2536e505a445a363e79201c0e2224e3c86c051e363aa91116`.
- Silent bed verified0–490s and1237.4–1237.9s.
- F10 checked510–570s and1060–1120s: five rounded right-high pairs,
  relative levels within0.6dB of intended+3.9/0/−4.8/−8.2/−10.9.
  Nominal carriers exceed selected+0.15Hz-offset probes by at least20dB.
- F11 checked720–840s: three shared carriers,±40Hz sidebands,
  interaural sideband phases within1.2° of180°.
 175/179Hz probes are >50dB below the323.625Hz carrier: no persistent
  theta alternate accidentally selected.
- All eight envelope boundaries checked for sample-step spikes relative to
  surrounding audio. A separate synthetic-state integration test checks actual
  per-sample midpoint gains and deterministic repeated PCM output.

## Limitations and review decisions

See [direct-source measurements](../research/V4_SHORT_MEASUREMENTS.md).
F10 common-mode~2Hz PM and staggered30s AM are omitted because the selected
engine cannot express their topology exactly. The bed is a constrained main-band
fit, not exact source texture. Equal ears remove a measured narrowband R bias.
These are disclosed candidate decisions, not established canonical F10 behavior.

No subjective listening review was performed; acoustic checks do not establish
perceptual seamlessness, speech naturalness or efficacy. Final cue sound design,
within-event audible cue alignment and production mastering remain pending.
The original52utterances,572s authored pauses and measured timing are preserved.

Validation checkpoint:366 tests passed; `make check` passed with0errors and
7 inherited warnings; Markdown links and `git diff --check` passed.
Repository-wide ruff retains the15 documented TD-001 findings, with no new
rule findings in this phase. Research verification initially lacked an application
dependency in its separate Python environment; removing unnecessary application
imports kept the standalone verifier's documented dependency scope honest.
