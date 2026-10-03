# Preparation Learning RC1 — Development Audition V2.1 (F10 induction support)

Status: **rendered and objectively checked; listener review pending**.
Not a production master and not a faithful full V4 reconstruction.
RC1 baseline speech/ledger: `061b2989ef13aca213112965d640fa43a036ec4a` (V1, reused
byte-for-byte). V2 remains preserved and unmodified as the comparison reference.

## Why this render exists

Human listening feedback on V2: roughly the first eight minutes were
narration without F10 DSP, so the program appeared as a late introduction rather
than as support for the relaxation that precedes it. See the
[listening finding](../research/V2_LISTENING_FINDING_F10_ONSET.md). This is a
scheduling/architecture finding about DSP onset versus semantic arrival. It is not
approval of V2's sound, and it changes no wording, cue, carrier, beat or
modulation parameter.

V2's first F10 gain window was `494.645533–499.645533s`, i.e. after the spoken
"T en" arrival line. V2.1 introduces a **semantic approach** concept: the selected
F10 program becomes audible during the progressive-relaxation stage, reaches its
intended sustained level by the start of the spoken arrival, and holds while the
arrival utterance plays. The state directive itself is unmoved.

## Architecture change

`schemas/semantic-dsp-profile.schema.json` gains an optional `approaches` array.
Each entry binds a target state to three existing measured event occurrences —
`begin_event`, `established_event`, `state_event` — and a `raised-cosine` curve.
`scripts/ocf_tools/semantic_dsp.py` resolves those occurrences from the same
measured ledger used for every other window, so timing follows each locale and
recording instead of English wording or a fixed minute count.

| Anchor | Semantic identity | Seconds | Meaning |
| --- | --- | ---: | --- |
| begin | `preparation.relaxation.begin` | 179.127891 | induction support starts from zero |
| established | `focus.ten.enter` (spoken Ten starts) | 487.570884 | full sustained F10 level |
| arrival directive | `focus.ten.transition` | 494.645533 | state commits; no second ramp |

The relaxation and Focus Ten stages are already declared `type: induction`; the
explicitly named F10 learning/count begins later, at `focus-ten.learn`
372.038005s and `focus-ten.count-one` 394.779138s. Those identities are template
facts, not narration interpretation.

Existing windows are unchanged:

| Transition | Start seconds | End seconds | Timing origin |
| --- | --- | --- | --- |
| F10 → F11 | 643.657052 | 676.150748 | measured opening transition → ready |
| F11 → F10 | 1009.000635 | 1043.542948 | measured closing transition → ready |
| F10 → ordinary | 1218.547574 | 1237.265306 | measured return directive → signal |

Profile: `OCF-DSP-DEVELOPMENT-V4-INDUCTION-001`. It reuses `OCF-DSP-DEVELOPMENT-V4-001`
exactly — same states, seed0, equal-power curves, fallback5s, −18dBFS state RMS
target, F10 candidate `OCF-BG-0012`, pure-SAM F11 `OCF-BG-0006`, disabled ordinary
waking — and adds only the approach entry. The raised-cosine curve is a disclosed
OCF scheduling choice, not a recovered V4 morph and not a claim that this level or
curve is perceptually ideal.

## Artifacts

Local directory: `audio/rendered/auditions/preparation-learning-v2.1/`, gitignored
under the local audition policy. Listening files start with
`DEVELOPMENT-AUDITION-V2.1-OCF-Preparation-Learning-en-US-RC1`: `-listening.flac`,
`-listening.mp3`, `-master.wav`, `-narration.wav`, `-DSP-bed.wav`, `.srt`, `.lrc`.
The directory also holds `render-manifest.yaml`, `semantic-dsp-render.yaml`,
`verification.json`, the frozen V1 semantic/resolved sessions and measured ledger,
V1 speech metadata/timing report, and engine logs. No reference recordings or
audition binaries are committed.

Reproduce with
`scripts/tools/render_development_v2.py --v1 DIR --output NEW_DIR --label V2.1
--profile OCF-DSP-DEVELOPMENT-V4-INDUCTION-001`, then
`scripts/tools/verify_development_v2.py NEW_DIR`. The same verifier also accepts
V2 (no `approaches`), and re-running it on a copy of V2 reproduces its checks
without touching the preserved directory. Manifest hashes identify this render's
working-tree implementation and presets; TTS is not invoked.

## Actual audio verification

- Length 1238.265261s (**20:38.265**), 54,607,498 frames, stereo 44100Hz PCM24 —
  identical duration to V2 because the speech stem is reused.
- Master peak −2.4773dBFS; RMS −22.1696L/−22.1696R dBFS; zero clipped samples.
- DSP bed peak −5.7945dBFS; full-session RMS −19.6288L/−19.6224R dBFS; zero
  clipped samples. The higher bed RMS versus V2 is the expected consequence of
  the program now being present for most of the session.
- WAV and lossless FLAC decode identically: float64 PCM SHA256
  `5b5dfa31d2c5eec753fdcbe3bd418dca92f7637a048016dd7cb51cc9f6c6c69c`.
- Bed verified exactly silent 0–178.627891s and 1237.4–1237.9s.
- Approach probes measured relative to the sustained level
  (−15.0074dBFS bed RMS), each within 0.65dB of the declared raised-cosine curve:

  | Approach fraction | Offset seconds | Measured | Declared |
  | --- | ---: | ---: | ---: |
  | 0.125 | 38.555374 | −27.749dB | −28.391dB |
  | 0.25 | 77.110748 | −16.352dB | −16.686dB |
  | 0.5 | 154.221497 | −5.919dB | −6.021dB |
  | 0.75 | 231.332245 | −1.351dB | −1.375dB |

- Full sustained level already present at the established anchor and unchanged
  across arrival: within 0.5dB at the established anchor, 4s before arrival, and
  0.5s after it. There is no second ramp and no level jump at the directive.
- At 12.5% of the approach window the first F10 pair is 27.7dB below its
  sustained level in each intended ear (39.75Hz left, 40.25Hz right), confirming
  the quiet material is the selected program rather than unrelated audio.
- F10 checked 510–570s and 1060–1120s: five rounded right-high pairs, relative
  levels within 0.6dB of intended +3.9/0/−4.8/−8.2/−10.9; nominal carriers exceed
  selected +0.15Hz-offset probes by at least 20dB. Sustained F10 texture is
  therefore unchanged from V2.
- F11 checked 720–840s: three shared carriers, ±40Hz sidebands, interaural
  sideband phases within 1.2° of 180°; 175/179Hz probes are more than 50dB below
  the 323.625Hz carrier, so the theta alternate was not selected.
- Nine envelope boundaries (including approach begin and established) show no
  sample-step spike relative to surrounding audio. Unit tests check the planned
  gain curve, locale/duration independence, non-English insensitivity and every
  rejection path; an ffmpeg integration test compares rendered PCM against the
  planned gain at fifteen times.

## Limitations and review decisions

F10 common-mode ~2Hz PM and staggered 30s AM remain omitted because the selected
engine cannot express their topology exactly, and equal ears still remove a
measured narrowband right bias. Both are inherited candidate decisions from
[direct-source measurements](../research/V4_SHORT_MEASUREMENTS.md), not new
findings; scheduling F10 earlier does not change them.

Envelope and boundary checks confirm the declared design and arrival hold. They do
not establish perceived appropriateness, perceptual seamlessness, speech
naturalness or efficacy. No subjective listening review of V2.1 was performed;
the human comparison between V2 and V2.1 is the next step. Within-event audible
cue alignment, final cue sound design and production mastering remain pending,
and RC1 narration plus the editorial freeze are untouched.