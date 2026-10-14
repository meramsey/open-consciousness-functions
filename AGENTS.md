# OCF Agent Contract

OCF is a declarative function/session authoring and audio toolchain. The
repository, schemas, committed YAML, tests, and cited evidence are
authoritative. The agent reasons; OCF validates and executes.

## Start here

1. Preserve unrelated working-tree changes; inspect `git status` first.
2. Read the relevant schema before changing data or a data contract.
3. Use LSP symbols/definitions/references when available, then targeted
   `Glob`/`Grep`/file reads. Do not recursively read generated output, audio,
   caches, or reference corpora to discover ordinary code relationships.
4. For a subsystem, consult `docs/AGENT_DEVELOPMENT.md` and then the narrower
   architecture/audio/localization/testing document it points to.
5. Validate assumptions with focused tests before broad tests. Run `make check`
   before claiming repository validation.

## Durable rules

- Keep clean-checkout reproducibility: no absolute machine paths, hidden local
  assets, network-only behavior, vendored optional engines, or undocumented
  dependencies.
- Preserve the 55 legacy mappings and the 16 source-unavailable records as OCF
  reimplementation targets with `reimplementation_status: planned`.
- Preserve canonical commands `PLUS-THINK` and `PLUS-FOCUS`; use MORE/LESS for
  new adjustable magnitude commands. Never rewrite historical mappings.
- Never fabricate evidence, provenance, source wording, locators, translations,
  licensing, consent, authentication, efficacy, or historical mechanisms.
  Record unknowns explicitly and keep mockups/reconstructions separate from
  source facts.
- Never hand-edit generated indexes or matrices. Regenerate with
  `python3 scripts/ocf.py build-index`; use `--check` to verify freshness.
- Follow `docs/SOURCE_FIRST_AUTHORING.md`: immutable SOURCE → exact initial
  WORKING → HUMAN edits → explicit RELEASE approval → measured timing. Do not
  require paraphrasing, distancing or automatic originality checks to edit.
  Never automatically rewrite source claims; record flags and corrections in
  separate metadata. Provenance and source availability remain explicit.
- Keep source/working chunks local and out of packages. Rights clearance gates
  release/package inclusion, not working edits; it is not an automated legal
  conclusion. Approved release narration follows `docs/NARRATION_STANDARD.md`.
  Do not mass-generate final narration or promote previous candidates at runtime.
- Keep narration, semantic state, DSP, cues, TTS, and metadata separate.
  Semantic state is not DSP onset. Audio sequencing must preserve measured
  anchors, state transitions, return/reorientation, and no duplicate ramp at
  state arrival. See `docs/AUDIO_PIPELINE.md` and `docs/SEMANTIC_DSP.md`.
- Treat localization as data, not English string construction. Preserve stable
  semantic IDs, strict spoken fallback, measured localized timing, Unicode, and
  representation-neutral/autonomy-aware wording. Support aphantasia and varied
  sensory experience without asserting outcomes; see
  `docs/LOCALIZATION.md` and `docs/NARRATION_STANDARD.md`.
- Keep Farfield/SBaGenX/TTS optional and degrade clearly. Resolve committed
  presets deterministically; never infer identity from filenames or frequencies.
- Respect security and licensing: do not expose secrets, execute arbitrary
  downloaded code, upload reference material, or commit ignored/private audio.
- Debug root causes rather than weakening validators, shrinking coverage, or
  reclassifying integration tests as unit tests. Add meaningful failure-path
  regression coverage for reachable behavior.
- Use MCP only for authoritative external information that local code, schemas,
  tests, and LSP cannot provide. Do not add services or downloads by default.
- Use `.opencode/agents/` for narrow read-only investigations; do not delegate
  broad repository rereads. The specialized agents return symbols, precedence,
  evidence, and tests, not speculative edits.

## Frozen boundaries

- `docs/PREPARATION_MODULE.md` and the planned cue section of
  `docs/TIMED_TRANSCRIPTS.md` are designs, not shipped commands. Keep the exact
  marker `TODO: Finalize focus-state auditory cue sound design.`.
- RC1 narration, V2/V2.1 development auditions, and Relax/Hearing/Sleep Easy
  pilot editorial decisions remain frozen pending human review. Do not alter
  V2.1 induction curve or level before the V2/V2.1 listening comparison.
- `OCF-BG-0012` is an approximate V4-derived F10 candidate, `OCF-BG-0006` is
  canonical newer F11 pure SAM, and `OCF-BG-0007` is its theta-enhanced
  alternate. Do not relabel these evidence boundaries.
- Keep `audio/scripts/attention.yaml` untouched; regenerate the adapted script
  only through session composition. Do not touch
  `references/HumanPlusTranscripts/` or commit listening audio.

## Completion report

Report changed files, focused/full tests, validation warnings/failures,
platforms actually run, unresolved uncertainty, and remaining follow-up work.
Do not claim native OS, package, audio, or MCP verification unless it ran.

## Task workflows

Use the built-in CLI and wizards as the authoritative workflows. Do not create
agent-specific scripts that duplicate their decisions. Python 3.11+ and the
project dependencies are required; optional audio engines/codecs are detected
by `doctor` and `voice doctor`. Run commands from the repository root.

### Add a function

Prerequisites: review `docs/FUNCTION_LIFECYCLE.md`, `docs/NAMING_GUIDELINES.md`,
and `schemas/function.schema.json`; determine a unique function identity and
provide source/evidence or explicitly record unknown provenance. Run
`python3 scripts/ocf.py new function`, complete the prompts, then
`python3 scripts/ocf.py validate --all` and `python3 scripts/ocf.py build-index`.
Expected outputs are a canonical record in `functions/` and refreshed generated
indexes/docs. For an audio implementation, compose or author a timed script
using `python3 scripts/ocf.py session compose --help` and then follow “Render an
audition.” Common failures are duplicate IDs/commands, missing required schema
fields, or unavailable evidence; do not invent provenance. Relevant sources:
`schemas/function.schema.json`, `scripts/ocf_tools/wizards.py`,
`scripts/ocf_tools/validators.py`, and `scripts/ocf_tools/indexes.py`.

### Edit a function

Inspect the record and schema first. Run
`python3 scripts/ocf.py edit function <ID-or-slug>` (uses `$EDITOR`), review the
diff, then run `python3 scripts/ocf.py validate --all` and
`python3 scripts/ocf.py build-index`. Preserve historical mappings, command
provenance, and protected narration. Generated indexes are outputs, not edit
targets. See `docs/SOURCE_FIRST_AUTHORING.md` and `docs/FUNCTION_LIFECYCLE.md`.

### Add a locale

Read `docs/LOCALIZATION.md` and `locales/README.md`. Add a pack under
`locales/<BCP-47-tag>/` using the locale schemas and stable resource IDs; do
not synthesize English from identifiers. Run
`python3 scripts/ocf.py locale validate --locale <tag>` and
`python3 scripts/ocf.py locale coverage --locale <tag>`. Missing spoken
resources can fail strict rendering even when UI fallback is available.

### Add or review a command

Read `docs/COMMAND_GRAMMAR.md` and `docs/COMMAND_REVIEW.md`; update canonical
command data with its source/provenance and rationale. Run
`python3 scripts/ocf.py validate --all` and
`python3 scripts/ocf.py review commands`. Never alter historical command
records to make the validator pass. `PLUS-SEE BETTER` remains canonical for
Sensory: Seeing; MORE/LESS modes are not active.

### Render an audition

Prerequisites: a timed script under `audio/scripts/`, a valid audio
implementation manifest, a compatible voice profile, and any selected optional
engine. Run `python3 scripts/ocf.py voice doctor` and
`python3 scripts/ocf.py audio build <AUDIO_ID> --output <working-dir> --format wav`
(add `--voice <profile>` and `--locale <tag>` as appropriate). Outputs are
local rendered masters and render metadata; existing outputs are protected
unless `--force` is specified. Missing TTS, codec, locale resources, or required
background engines produces a failure or documented degradation. See
`docs/AUDIO_PIPELINE.md`, `docs/LOCALIZATION.md`, and voice profiles in
`audio/voices/`.

### Produce audio files

`python3 scripts/ocf.py audio build <AUDIO_ID> --output <working-dir> --format
wav --format flac --format mp3` renders audition/master artifacts. For a complete
localized package, run
`python3 scripts/ocf.py audio release <AUDIO_ID-or-FUNCTION_ID> --locale en-US
--format flac --format mp3 --artwork <approved-cover.png> --output <release-root>
--dry-run`, inspect intended paths, then repeat without `--dry-run`. Use
`--voice <profile>`, `--version <version>`, repeatable `--tag KEY=VALUE`, and
`--force` as needed. Release metadata override keys are title, album, artist,
album_artist, date, track, language, comment, publisher, copyright, and label.
The command requires explicit PNG/JPEG artwork and ffmpeg/ffprobe for embedded
picture verification. It publishes only after codec decode, metadata, artwork,
transcript, manifest, and checksum checks. A forced replacement retains the
previous package in a sibling hidden archive directory. See
`docs/AUDIO_PIPELINE.md` and `schemas/audio-release.schema.json`.

### Add a voice preset

Read `docs/COMMUNITY_VOICES.md`, `docs/LOCALIZATION.md`, and
`audio/voices/README.md`. Add a profile following
`audio/voices/profiles/` and its schema, record only verified attribution and
dependency/licensing information, then run `python3 scripts/ocf.py voice doctor`
and focused voice tests. Keep private samples/weights local; never infer voice
identity from filenames. Missing optional providers should remain optional.

### Diagnose a failed render

Run `python3 scripts/ocf.py doctor --json` and
`python3 scripts/ocf.py voice doctor`; validate the function and locale, then
retry with an output path in a writable temporary/work directory. Inspect the
render manifest and captured backend error before changing configuration.
Check codec availability (`ffmpeg`/`flac`), voice backend and locale coverage,
and whether the manifest requires a background engine. See `docs/DOCTOR.md` and
`docs/AUDIO_PIPELINE.md`.

### Validate and refresh generated docs

Run `python3 scripts/ocf.py validate --all`,
`python3 scripts/ocf.py locale validate --locale en-US`,
`python3 scripts/ocf.py build-index --check`, and `make check`; run
`make lint` and `python3 -m pytest` for the complete local checks. If generated
indexes are stale, run `python3 scripts/ocf.py build-index`, inspect the diff,
then rerun `--check`. Never hand-edit generated command/function references.
See `docs/TEST_COVERAGE.md`, `Makefile`, and `.github/workflows/`.

### Agent discovery examples

These requests should lead an assistant to the built-in commands above; they
are guidance prompts, not separate executable interfaces:

- “Add a new function using the existing wizard.”
- “Show me how to localize a function into Spanish.”
- “Validate the command phrases for Nutricia.”
- “Render an audition using my selected voice preset.”
- “Package a release with MP3, FLAC, transcript, and artwork.” (Use
  `ocf audio release`; require an explicitly approved PNG/JPEG artwork file and
  do not infer rights clearance from successful packaging.)
- “Explain how to add a reusable voice preset.”
- “Check whether generated documentation is up to date.”

README and this file are provider-neutral repository discovery conventions;
they do not imply that every assistant product automatically reads them.

## Required task result format

For every task, report results inside one fenced plain-text code block. Include
completion status; branch, local commit and remote synchronization; completed
work and changed files; focused/full tests and exact counts; lint/validation
results; platforms actually exercised; warnings, failures, uncertainty, and
blockers; and a recommended next milestone. Include workflow URLs and commit/push
status only when those operations were actually performed and verified. Mark
unrun checks as SKIP or BLOCKED rather than implying success.
