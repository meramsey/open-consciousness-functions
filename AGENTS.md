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
