# OCF Agent Contract

OCF is a declarative function/session authoring and audio toolchain. Schemas,
canonical YAML, repository tests and cited evidence are authoritative. The
agent reasons; OCF validates and executes. These instructions are provider-neutral.

## Start small

1. Inspect `git status`, branch/HEAD and relevant changes. Preserve unrelated
   work, especially `ReusablePrompts/` and `references/HumanPlusTranscripts/`.
2. Use `python scripts/ocf.py dev ocf_project_overview`, `capabilities --json`,
   or the optional MCP equivalents before loading large indexes.
3. Read the relevant schema before changing data/contracts. Use symbols and
   targeted reads, not recursive discovery through generated output, audio,
   caches or reference corpora.
4. Consult [agent development](docs/AGENT_DEVELOPMENT.md), then the focused guide
   in [documentation navigation](docs/README.md).
5. Run meaningful focused tests first. Run `make check` before claiming repository
   validation; final gates also include `make lint` and the full pytest suite.

## Canonical map

Function YAML also owns source-English command `spoken`/`spoken_review` and
`narration.sequence`. Locale copies and content bindings must agree; never create
a second English authority. Use [strict cue templates](docs/SYMBOLIC_CUES.md)
through LocaleCatalog before segmentation, cache keys or recording fingerprints.
Check raw-template and resolved-text hashes separately. Structural conversions
must preserve all resolved speech bytes and immutable predecessor manifests.
Review remaining vocabulary ONE function at a time; wait for explicit user input.

- `functions/`: identity, commands, legacy mappings and source availability.
- `function-content/`: separate evidence, specifications, decisions and bindings.
- `locales/`: stable localized narration/UI IDs and review/provenance metadata.
- `schemas/`: contracts; `scripts/ocf_tools/`: implementation and CLI services.
- `audio/templates/`: session/stage/pacing inheritance; `audio/background/`: DSP
  profiles and explicit presets; `audio/voices/`: optional voice profiles.
- `audio/defaults/`: immutable engineering configuration locks, not listening
  approval. New revisions require a deliberate new baseline.
- `audio/session-plans/`: generated compact declarations; regenerate using
  `audio plan --all --locale en-US`, verify with `--check`.
- Generated function/command indexes and matrices: `build-index`; never hand-edit.
- `.ocf-work/`: ignored scratch, logs, caches, local jobs and auditions.

## Non-negotiable data and editorial rules

- Preserve the 55 legacy mappings and all 16 source-unavailable planned
  reimplementation targets. Historical availability is not TTS eligibility.
- Preserve canonical `PLUS-THINK`, `PLUS-FOCUS` and `PLUS-SEE BETTER`. MORE/LESS
  is for new adjustable magnitude commands; do not rewrite historical mappings.
- Preserve all 177 protected narration entries unless explicitly authorized.
  Never fabricate source wording, evidence, locators, provenance, translations,
  licensing, consent, authentication, efficacy or historical mechanisms.
- Follow [source-first authoring](docs/SOURCE_FIRST_AUTHORING.md): immutable
  SOURCE → exact initial WORKING → HUMAN edits → explicit RELEASE approval →
  measured timing. Do not require paraphrasing, distancing or automatic
  originality checks to edit. Record flags/corrections separately from wording.
- Keep source/working chunks local and out of packages. Rights clearance gates
  release inclusion, not working edits; it is not an automated legal conclusion.
  Do not mass-generate final narration or promote old candidates at runtime.
- Narration, semantic state, DSP, cues, TTS and metadata are separate. State
  identity is not DSP onset; preserve measured anchors, return/reorientation and
  no duplicate arrival ramp. See [audio pipeline](docs/AUDIO_PIPELINE.md) and
  [semantic DSP](docs/SEMANTIC_DSP.md).
- Treat localization as data: stable IDs, strict spoken fallback, Unicode,
  measured localized timing, representation-neutral/autonomy-aware wording and
  support for varied sensory experience/aphantasia. See
  [localization](docs/LOCALIZATION.md) and [narration standard](docs/NARRATION_STANDARD.md).

## Runtime, security and portability

- Python 3.11+; Linux/macOS/Windows. Keep clean-checkout reproducibility: no
  absolute machine paths, hidden local assets, network-only core behavior,
  vendored optional engines or undocumented dependencies.
- Farfield/SBaGenX/TTS remain optional. Resolve committed presets deterministically;
  never infer identity from filenames or frequencies. Use `doctor`/`voice doctor`.
- Before reporting Piper missing, run `python scripts/ocf.py voice doctor` from
  the repo root: it checks the existing `.venv`, pyenv-selected interpreter,
  PATH and user-local Piper launcher/model hashes without installing/downloading.
  Use `voice smoke OCF-VOICE-9003 --locale en-US` for a one-sentence synthesis;
  see [setup](docs/SETUP.md) for supported overrides and troubleshooting.
- All routine scratch/cache/logs and default auditions use the canonical shared
  `.ocf-work/` for linked worktrees. Run `python scripts/ocf.py workspace status`
  before searching for old artifacts; it reports the shared project workspace
  and any legacy nested worktree workspaces. Use explicit `OCF_WORK_DIR` only to
  inspect or preserve legacy nested data; do not move it without inventory and
  checksum verification. Honor validated `OCF_WORK_DIR`; TMPDIR/TMP/TEMP
  overrides apply only to OCF-launched subprocesses. Preserve failed diagnostics.
  Use `workspace clean --dry-run` before deleting marked scratch.
- Do not expose secrets, upload references, execute arbitrary downloaded code,
  or commit ignored/private audio. Never modify/commit reference transcripts.
- Fix root causes, not validators or test classifications. Unit tests forbid real
  subprocesses; repository/audio integration remains integration. Never shrink
  coverage or skip expensive tests merely to improve timing.
- Commit/push only when requested. Review status/diff/history, stage intended
  files, preserve unrelated work; no force-push/history rewrite. Verify CI at the
  exact final commit before claiming success.

## Frozen boundaries

- `docs/PREPARATION_MODULE.md` and planned cues in `docs/TIMED_TRANSCRIPTS.md`
  are designs, not shipped commands. Preserve exactly:
  TODO: Finalize focus-state auditory cue sound design.
- RC1 narration, V2/V2.1 auditions and Relax/Hearing/Sleep Easy editorial
  decisions remain frozen pending human review. Do not change V2.1 induction
  curve/level before the V2/V2.1 listening comparison.
- OCF-BG-0012 is an approximate V4-derived F10 candidate; OCF-BG-0006 is canonical
  newer F11 pure SAM; OCF-BG-0007 is its theta-enhanced alternate.
- Keep `audio/scripts/attention.yaml` untouched. Regenerate adapted scripts only
  through session composition. Never commit listening audio.

## Workflows and tools

Use `dev ocf_get_workflow --arguments '{"name":"add-function"}'` or the matching
MCP tool. [Versioned workflow navigation](docs/workflows.json) covers adding a
function, reviewing narration, adding a locale, bulk planning, auditions,
render diagnosis, release packaging and final validation. Wizards use the same
application APIs as CLI generation; implementation lives in `prompts.py`.

Plan first with `audio plan FUNCTION_ID --expand`; generate source plans without
audio engines. `audio eligibility --all` derives capability without promoting
human/source status. Render explicitly with `audio render` or `audio render-many`;
use `--dry-run` first. Bulk renders use verified resume and unique output paths.
`new session-plan` invokes the same generator. See [bulk sessions](docs/BULK_SESSIONS.md).

For [recorded](docs/RECORDED_NARRATION.md) or
[hybrid narration](docs/HYBRID_NARRATION.md), inspect `narration sources` before
importing exact event/resource/unit bindings. Render with `audio render FUNCTION
--narration-sources FILE`; recorded-only needs no TTS voice and never falls back.
Hybrid requires an explicit fallback policy. CLI `narration validate` is source
compatibility preflight; use `narration inspect` or queued recording validation
for technical decode. Text hashes do not verify speech. A complete `session_stem`
requires all composed event markers, including nonspoken DSP boundaries; never
infer them or insert extra semantic silence. Preserve originals, declared speaker
identity and the independent stereo bed; narration processing never touches it.

Release packaging uses `audio release` with explicit PNG/JPEG artwork and an
eligible registered implementation. Preserve review/rights metadata and inspect
the dry-run. Packaging success is not release approval.

Original brand geometry/palettes live in `brand/`; generated visual assets are
candidates until human approval. UI/artwork/documentation themes are independent.
Explicit `--artwork-theme` may generate a local release cover, with candidate
provenance retained. Private voice models/datasets stay in `.ocf-work/`; portable
metadata does not grant distribution rights. Training is unsupported until an
adapter actually produces and verifies a model. See [branding](docs/BRANDING.md),
[voice workflows](docs/VOICE_WORKFLOWS.md) and [session overrides](docs/SESSION_OVERRIDES.md).
Use `voice capabilities` for shipped/local support, `voice export-profile` /
`import-profile` for deliberate metadata/private asset portability, and
`new voice-dataset MANIFEST` for import-first recording slots. See
[cloning boundaries](docs/VOICE_CLONING.md) and [training preparation](docs/VOICE_TRAINING.md).
Installed packages, synthetic fixtures and ordinary imported Piper auditions are
not verified cloning/training or speech-content approval.

Optional [local MCP](docs/MCP.md) is a compact adapter, not another OCF engine.
Use discovery summaries, pagination and targeted validation. Expensive tools
return job IDs; poll/cancel rather than starting duplicates. Full tests require
an explicit request. CLI fallback: `python scripts/ocf.py dev OPERATION
--arguments JSON`; core commands work without MCP. External MCP/web research is
for authoritative information unavailable locally, not routine repository discovery.
Use narrow read-only agents in `.opencode/agents/` for subsystem investigations;
do not delegate broad repository rereads.

## Final quality and reporting

Run `validate --all`, `locale validate --locale en-US`, `build-index --check`,
`audio plan --all --locale en-US --check`, `make check`, `make lint` and full
`python -m pytest` (or `-n 2 --dist loadfile`). Do not repeat broad tests without
new changes/failures. Record exact counts and optional-tool skips.

Every final OCF report MUST be exactly one plain-text fenced block using triple
backticks. No external Markdown tables or split blocks. Include completion
status, branch/local commit/remote synchronization, work and changed files,
focused/full test counts, lint/validation PASS/FAIL/SKIP, platforms actually run,
warnings/failures/uncertainty/blockers and next milestone. Include verified CI
URLs and commit/push status only when actually performed. Never claim native
OS, packaging, listening, audio or MCP verification unless it ran.
