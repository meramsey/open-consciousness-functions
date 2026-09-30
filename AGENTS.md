# AGENTS.md — Guidance for AI coding agents

This file instructs future coding agents and LLM-assisted contributors working
in this repository.

## Mandatory rules

- **Inspect schemas first.** `schemas/*.schema.json` define the canonical data
  model. Never change the YAML function format without updating the schema.
- **Treat design docs as not-shipped.** `docs/PREPARATION_MODULE.md`,
  `docs/LOCALIZATION.md`, and the "Planned: focus-state auditory cue events"
  section of `docs/TIMED_TRANSCRIPTS.md` are forward-looking designs (v0.5).
  Never mark anything implemented that has no live `ocf` command; schema/data
  changes implied by those docs still require a proposal. The exact marker
  `TODO: Finalize focus-state auditory cue sound design.` must remain in
  `docs/TIMED_TRANSCRIPTS.md` until a cue design is accepted.
- **Preserve legacy mappings.** Historical commands, names, and source
  availability must never be deleted or rewritten; they are research and
  compatibility metadata.
- **Never fabricate source details.** If a field cannot be established from a
  cited source, leave it `pending-source-review`, `null`, or an empty list.
  Do not invent page locators, transcripts, or provenance.
- **Never hand-edit generated indexes.** Files under `function-index.*`,
  `FUNCTION_INDEX.md`, `legacy/hplus-command-map.*`, and generated matrices in
  `docs/` are produced by `scripts/ocf.py build-index`. Regenerate instead.
- **Run tests and validation** after any change: `make check`.
- **Preserve short-command policy.** Keep commands short; see
  `docs/COMMAND_GRAMMAR.md` and `docs/NAMING_GUIDELINES.md`.
- **Keep `PLUS-THINK`** as the canonical command for THINK FAST. Do not rename
  it (`PLUS-QUICKTHINK`, `PLUS-THINK-FAST`, etc. are prohibited vocab).
- **Keep `PLUS-FOCUS`** as the canonical command for ATTENTION.
- **Use MORE/LESS** for adjustable/sensory magnitude commands
  (`PLUS-SEE MORE` / `PLUS-SEE LESS`), not UP/DOWN or GREATER/LESSER for new
  canonical data.
- **Preserve all 55 initial functions.** The legacy map must always contain
  exactly the 55 documented functions in `legacy/README.md`.
- **Treat the 16 source-unavailable legacy functions as OCF reimplementation
  targets.** `ocf.reimplementation_status` must be `planned` (never delete
  them, never mark them dismissed). Use terminology "legacy source unavailable"
  and "OCF reimplementation planned", not "missing functions".
- **Keep Farfield integration optional.** It must degrade gracefully to a
  helpful message when `farfield` is not installed. Do not vendor Farfield
  source.
- **Do not vendor or reproduce copyrighted third-party audio.** Reference
  files are citation-only by default; see `docs/SOURCE_ATTRIBUTION.md`.
- **Route committable binaries through Git LFS; never `git add -f` an ignored
  file.** `.gitattributes` declares the LFS policy (`wav/flac/mp3/m4a/ogg/
  opus/aif/aiff`, `png/jpg/jpeg/gif/webp`); the file just gets added. Ignore
  rules are licensing decisions, so overriding them requires a proposal, not a
  large-file convenience. See `CONTRIBUTING.md` ("Large files and Git LFS").
- **Keep the timed-transcript toolchain status honest.** The `ocf transcript
  …` group (import/segment/analyze/review/export/extract-template) and the
  narration/audio-build toolchains (`ocf voice …` and `ocf audio
  render-speech|mix|build|inspect`) are **shipped**; the preparation toolchain
  (`ocf preparation …`) is **specified but not yet shipped** until its
  commands exist in `scripts/ocf_tools/cli.py`. Docs must not mark anything
  implemented that has no live command; the status matrix in
  `docs/TIMED_TRANSCRIPTS.md` and the normative spec in
  `OCF_OpenCode_Bootstrap_Prompt_v3_Transcript_Focus_Preparation.md` are the
  sources of truth.
- **Never relabel imported narration as OCF-authored.** Narration counts as
  OCF committable wording only when the document was composed from an
  `original-ocf` session template or declares `source.format: manual` with no
  import snapshot; otherwise it is citation-only. See
  `_doc_is_original` in `scripts/ocf_tools/audio_build.py`.
- **Keep `audio/scripts/attention.yaml` untouched.** It is the citation-only
  legacy import. The adapted script is `audio/scripts/attention-ocf.yaml`,
  composed from `audio/templates/sessions/OCF-TPL-SESSION-ATTENTION-001.yaml`
  (a `reference-derived` shell) plus `audio/slots/attention/focus11.txt`; its
  narration is adapted-from-legacy wording, so it is never relabelled as
  OCF-authored. Regenerate it with `ocf session compose` rather than
  hand-editing.
- **Manifests reference committed preset files.** `preset.file` is a repo path
  under `audio/background/presets/`; `presets/farfield` and `presets/sbagenx`
  are upstream-contribution staging copies only. SBaGenX sequences must keep
  `-R 10`; `-R 1000` makes `sbagenx` abort with an FPE.
- **Treat audio checksums as artifact identity, not a recipe.** TTS output is
  not bit-exact, so a rebuild of the same script yields a different
  `technical.checksum_sha256`. Never claim a rebuild reproduces the same bytes.
- **Never silently rewrite imported transcript wording.** Transcript imports
  preserve source text and timestamps exactly; the repository must never claim
  a tool rewrote narration.
- **Report unresolved ambiguity instead of guessing.** If data is unknown,
  record `pending-source-review` or raise it as an issue.

## Quick commands

```bash
python3 scripts/ocf.py validate --all   # schema + rule validation
python3 scripts/ocf.py build-index      # regenerate generated files
python3 scripts/ocf.py build-index --check  # fail if indexes are stale
python3 -m pytest                       # run tests
make check                              # validate + freshness in one step
```

## Generated files

Never edit these by hand; run `python3 scripts/ocf.py build-index`:

```
FUNCTION_INDEX.md
function-index.json
function-index.csv
legacy/hplus-command-map.json
legacy/hplus-command-map.csv
docs/COMMAND_REVIEW.md
docs/AVAILABILITY_MATRIX.md
docs/REIMPLEMENTATION_ROADMAP.md
docs/SAFETY_MATRIX.md
docs/AUDIO_IMPLEMENTATION_INDEX.md
docs/BACKGROUND_AUDIO_INDEX.md
```

## Testing

Run `python3 -m pytest` from the repository root. The suite covers the CLI,
wizards, schema and command validation, index generation, audio manifests, and
Farfield graceful degradation.