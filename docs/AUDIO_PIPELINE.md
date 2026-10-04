# OCF Audio Pipeline

This document describes the current shipped pipeline. It is an implementation
map, not a promise that every designed preparation feature is shipped.

## Layers

Function records declare capability and identity. Session templates and timed
YAML declare operations, event identity, ordering, narration references, and
semantic state directives. Locale resources supply spoken text. Voice profiles
select a backend. Background manifests and semantic DSP profiles select audio
programs. Render manifests record measured timing, provenance, commands,
checksums, and output identity.

The main implementation modules are:

- `scripts/ocf_tools/cli.py`: command parsing and dispatch;
- `scripts/ocf_tools/session.py`: template composition and semantic document
  binding;
- `scripts/ocf_tools/transcript.py`: timed-YAML parsing, timeline resolution,
  analysis, and subtitle export;
- `scripts/ocf_tools/locale.py`: locale resolution and provenance;
- `scripts/ocf_tools/voice.py`: recording, disabled narration, or TTS rendering;
- `scripts/ocf_tools/semantic_dsp.py`: measured-ledger state dispatch;
- `scripts/ocf_tools/audio_build.py`: background selection, mixing, encoding,
  tags, and render manifests;
- `scripts/ocf_tools/farfield.py` and `sbagenx.py`: optional external adapters.

## Current sequence

1. Compose or load a semantic session and validate its template/schema
   references.
2. Resolve keyed narration for the requested locale. Spoken fallback is strict
   by default; an explicit draft fallback is recorded in provenance.
3. Select one narration source: TTS, an explicitly event-mapped recording
   package, or explicitly disabled narration for a speech-free document.
4. Resolve event timing, including measured speech-end/event-end dependencies,
   and render a narration stem. Localized speech gets its own measured ledger;
   English timing is never copied into another locale.
5. Select a static background or semantic DSP profile. Semantic DSP consumes the
   measured ledger independently of TTS. A state approach may begin before the
   semantic state directive, but the semantic state event remains the arrival
   boundary and must not replay a second ramp.
6. Apply section narration gain windows and mix narration/background. Background
   paths use the configured engine or reference-master path; no unrelated preset
   or silent source-loop substitution is allowed.
7. Encode requested outputs and emit the render manifest with timing, source
   provenance, preset/engine information, tags, and artifact checksums.

Preparation stages such as optional affirmation and oHm/resonant tuning remain
specified but not shipped. Focus-state auditory cue sound design also remains
TBD. Do not insert those stages into the live pipeline because a design document
mentions them.

## Precedence and invariants

### Background and preset selection

- A missing preset means no background unless the selected workflow requires
  one.
- A manifest is found by ID/name before engine dispatch.
- Manifest engine selection wins when the CLI engine is the default auto value;
  an explicit non-default CLI engine overrides it.
- A literal existing preset path is accepted first.
- A Farfield preset name/stem is then searched in this order: directories in
  `OCF_FARFIELD_PRESETS_DIR`, committed
  `audio/background/presets/farfield/`, committed
  `audio/background/presets/`, then a discovered Farfield source checkout.
- `preset.file` is a committed repository path under
  `audio/background/presets/`; `presets/` is only upstream-contribution
  staging. SBaGenX sequences retain `-R 10`.

These rules are implemented in `audio_build.py` and `farfield.py`, with
regression coverage in `tests/test_audio_build.py` and
`tests/test_locale_render.py`.

### Sequencing

- Semantic state identity comes from structured events, never English text,
  filenames, frequencies, or subtitle `cue_id`.
- Measured anchors are authoritative for narration-dependent timing.
- A state directive must not be moved merely to make DSP audible; use an
  explicit approach when support-before-arrival is intended.
- Return/reorientation and ordinary waking remain separate semantic operations.
- Narration, DSP, cues, and TTS remain replaceable layers.
- TTS output is not byte-reproducible. A checksum identifies an artifact, not a
  recipe that will reproduce identical bytes.

See `docs/SEMANTIC_DSP.md`, `docs/SEMANTIC_SESSIONS.md`, and
`docs/AUDIO_STANDARD.md` for contracts and schemas.
