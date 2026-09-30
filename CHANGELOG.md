# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial repository scaffold for **Open Consciousness Functions (OCF)**.
- Canonical YAML function format and JSON Schema validation.
- All 55 documented legacy H-PLUS function mappings as OCF reimplementation
  targets (39 with source material available, 16 with source material
  unavailable but fully valid OCF targets).
- Interactive contributor CLI (`./scripts/ocf`), including wizards for
  functions, proposals, audio implementations, and background presets.
- Command-design linting (`ocf review commands`) and command-review reports.
- Generated indexes (`FUNCTION_INDEX.md`, `function-index.json/.csv`,
  `legacy/hplus-command-map.json/.csv`, and docs matrices).
- Optional Farfield background-audio integration with graceful degradation.
- GitHub automation: validation, tests, linting, and index-freshness checks.
- Documentation suite under `docs/`.
- Timed-transcript toolchain (`ocf transcript import|analyze|segment|review|export|extract-template`):
  LRC/SRT/VTT/txt/md → canonical OCF timed YAML, section roles, state profiles,
  exports, and timing-only templates; transcript wording is never rewritten.
- Narration/TTS toolchain (`ocf voice list-backends|doctor|list|render`) with
  optional espeak-ng/espeak/piper backends.
- Audio-building toolchain (`ocf audio render-speech|mix|build|inspect`) with
  WAV/FLAC/MP3 mastering, checksums, and `OCF-RENDER-*` manifests.
- Narration pacing modes on `voice render`/`audio build`: `--fit`
  (adaptive per-cue pacing), `--flow` (sentence-fragment merging), and
  `--even-counts` (even-spaced count runs anchored by their first/last count).
- Background engines: **SBaGenX** (binaural `.sbg` beds) and
  **reference-master** (beds composed from operator-supplied, citation-only
  reference masters, e.g. `OCF-BG-0004` F10 bed + F11 access excerpt),
  alongside the existing Farfield engine.
- Session-composition templates (`ocf session list-templates|compose`):
  a four-part contributor contract — opener, focus-11 function material
  (`--focus11`), twentieth/sleep-state function reinforcement (`--sleep20`),
  and closer — resolved against an original-OCF shell template
  (`OCF-TPL-SESSION-LEARN-001`) into canonical timed YAML, with `template`
  provenance and the exact slot wording recorded (`schemas/session-template.schema.json`,
  `audio/templates/`). The sleep-20 slot is paced across the whole sleep hold
  (`pace: even-span`), so sleep-state reinforcement no longer echoes
  access-channel wording.
- Multi-format tagged outputs on `ocf audio build`: WAV + FLAC + MP3 by
  default (`--format` repeatable), with FLAC Vorbis / ID3v2 metadata derived
  from the manifests (title, artist, album, track, comment, `OCF_*` tags
  including `OCF_SESSION_TEMPLATE`), per-tag `--tag KEY=VALUE` overrides, and
  all outputs + tags recorded in the `OCF-RENDER-*` manifest.
- Section-level `gain_db` for timed transcripts and session templates, applied
  by `ocf audio build` in both mixing paths and recorded as
  `narration_gain_windows` in the render manifest. It makes a sleep-state
  reinforcement *present but barely audible* instead of a silent hold.
- Optional narration `source` provenance on session templates, copied into
  composed documents; narration is reported as OCF-authored only with explicit
  `original-ocf` or `source.format: manual` provenance, otherwise
  citation-only.
- Session-composition slot reuse: sections may declare `repeat` to run their
  slot wording once per band across the section window, and `from_slot` to
  reuse another declared slot's wording without declaring a new one —
  templates declare the slots they actually need, and compose rejects any
  undeclared slot.
- **Attention (PLUS-FOCUS) reference implementation, adapted from the legacy
  arc:** dedicated session template `OCF-TPL-SESSION-ATTENTION-001` carrying
  converted legacy wording for the whole arc (tenth state, access state,
  instruction, close, sleep to the twentieth state, return, close) with a
  single required slot, `audio/slots/attention/focus11.txt` (the five-line
  PLUS-FOCUS instruction; the stray legacy `12` at 07:19.60 is dropped). The
  composed script `audio/scripts/attention-ocf.yaml` (77 cues) repeats the
  focus-11 wording through the twentieth-state hold (`from_slot` + `repeat`,
  mixed at -24 dB, ~17:41-26:22), and `OCF-AUDIO-0001` is rebuilt as tagged
  WAV/FLAC/MP3. Its narration is adapted-from-legacy and citation-only — never
  labelled OCF-authored. The legacy import `audio/scripts/attention.yaml` is
  retained unchanged as a citation-only reference.
- OCF-owned Focus-11 preset mirrors committed under
  `audio/background/presets/` (Farfield + SBaGenX, `focus-11-a|b|c`) and
  registered as `OCF-BG-0005`–`OCF-BG-0010`; `preset.file` now resolves
  through manifests, so `describe-background`/`render-background` render the
  committed preset instead of an engine-side name. SBaGenX sequences use
  `-R 10`; `-R 1000` makes `sbagenx` abort with a floating-point exception.
- OCF-authored composite bed `OCF-BG-0011`: a 10-16 Hz binaural arc with the
  OCF-authored gamma+theta+pink Focus-11 access state spliced into the
  6:31-12:50 access window, replacing the operator reference excerpt. No
  third-party audio is vendored or redistributed.

### Changed

- `technical.checksum_sha256` is documented as identifying the artifact that
  was built, not a reproducible recipe: TTS backends are not bit-exact (three
  renders of one identical Piper line produced three different digests).