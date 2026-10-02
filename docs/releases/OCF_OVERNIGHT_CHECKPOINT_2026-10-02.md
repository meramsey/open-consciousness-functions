# OCF unattended run — audio completion and foundation checkpoint

Date:2026-10-02. **Audio phase complete; larger foundation phase partially
implemented.** This run reached its execution window after validated recovery
commits. Remaining independent work is explicitly queued below; no routine
editorial approval gate was used to block engineering. No mass final narration.

## Starting and ending Git state

- Start: `main` at`061b2989ef13aca213112965d640fa43a036ec4a`, with current-phase
  tracked changes to ignores, F11 manifests, attribution, schemas, audio/CLI/
  validation code, plus new research, candidate, state-profile and dispatcher
  files already in progress. They were resumed, validated and preserved.
- Pre-existing untracked user inputs: `ReusablePrompts/` and
  `references/HumanPlusTranscripts/`. Both remain untracked and untouched.
- All implementation changes listed below are committed. No reference audio,
  transcripts, ZIP/image/PDF assets, credentials or local audition binaries staged.
  No push, history rewrite or destructive migration performed.
- Tracked worktree/index clean before this report commit; the two user directories
  remain visible in `git status`. Local renders/reports/cache/environment are
  outside the worktree or ignored, not silently absorbed into commits.

## Chronological implementation commits

| Hash | Purpose |
| --- | --- |
| `b65f4c566ba23c1bc70f33a68d7a77f7e35b89ab` | Direct V4-short research and preserved evidence boundaries |
| `995dc24414d5dce3ef479d17df5f3b8f0d1e5596` | Labelled V4-derived F10 candidate; newer F11 canonical/alternate correction |
| `b233575d2e25e02deb46b277a0422419fac5b2a7` | Configurable measured-ledger semantic DSP dispatch and tests |
| `d838290353135eda600a95c9371621f81c277bf7` | V2 reused-speech render/verification tooling and report |
| `a04749eb5847f4a00198259489c76f3757c183ef` | Permanent purposeful/original authoring standard and architecture baseline |
| `8273815d5e056a52a1215ea96e06e33cd1a2466d` |277-file corpus inventory/evidence schema and agent discovery |
| `1a931e0576b01af2dd680edc53dd41e64e361e8f` | Original Relax/Hearing/Sleep Easy draft rehearsal pilots |
| `b2cfa7aaa83c10a30ff538f15155986f89af4390` | Honest coverage measurement/policy and shipped/planned roadmap |
| `ffe7dd0956aa39a2194094c59e5fec9939f1c201` | Event-mapped user/external recordings as a first-class voice source |
| `aaa884651f5e4c33d98853557e3b7ff23e75c628` | Persist exact voice timing/provenance sidecars for subtitles and DSP reuse |

The report's own checkpoint hash is returned in the session summary and can be
resolved with `git log -1 --format=%H -- docs/releases/OCF_OVERNIGHT_CHECKPOINT_2026-10-02.md`.

## Audio phase: completed with disclosed candidate limitations

See [direct-source report](../research/V4_SHORT_MEASUREMENTS.md),
[historical evidence audit](../research/FOCUS_STATE_EVIDENCE_AUDIT.md),
[semantic DSP contract](../SEMANTIC_DSP.md) and
[V2 report](OCF_PREPARATION_LEARNING_DEV_V2.md).

F10 supplied399.530249s excerpt confirms five persistent right-high pairs:
39.75/40.25,79.25/80.75,158.05/161.95,198/202,317.95/322.05Hz. The additional
ground40 pair is directly measured. Relative resolved powers:+3.88/0/−4.76/
−8.20/−10.87dB. Low families are extremely stable across multiple windows and
edges; upper short-window amplitudes reflect periodic modulation/interference,
not established equivalent frequency drift. ~2Hz sidebands are mainly common-mode
PM, not simple AM; upper families also show staggered30s common-ear AM.

The coherent bed has a broad low-frequency hump and curved/notched full spectrum,
not a generic pink/brown law. Measured near-zero interaural delay supports a
shared-bed approximation. Supported main-band fit241.1Hz/+20.2/−48dB per decade,
~1.57dB RMS residual; full high-frequency texture is not reconstructed.
`OCF-BG-0012` is a **V4-derived candidate**, not universally canonical F10.
Farfield cannot express the measured PM/AM topologies exactly: both are omitted,
never falsely replaced with another mechanism. Symmetric ears, RMS calibration,
phase initialization and output levels are documented OCF design choices.

Matched F11-short peak/bed evidence was compared as its own generation/time axis;
it does not validate transferring old offsets or replace newer-source evidence.
Canonical **newer** F11 state selection is`OCF-BG-0006` pure three-family40Hz
antiphase SAM. `0007` remains the theta-enhanced alternate with continuous175/179
pair explicitly distinguished from source intermittency. Historical aliases and
Attention consumers are preserved. No state identity inferred from frequencies.

Dispatcher is shipped: profiles bind semantic states to manifests/engines,
or explicitly disable them. It resolves measured end-dependent anchors, checks
from-state consistency/windows, refuses missing required bindings/short stems,
and records provenance/hashes/calibration. F10 onset uses its explicit ledger
event; cross-generation equal-power morphs are OCF choices. Narration, DSP and
TTS remain independent; `cue_id` is untouched and physical cues remain disabled.

### V2 artifacts and actual verification

Directory:`/tmp/opencode/OCF-Preparation-Learning-en-US-RC1-dev-audition-V2/`.
Prefix:`DEVELOPMENT-AUDITION-V2-OCF-Preparation-Learning-en-US-RC1`.
Master WAV, listening FLAC/MP3, isolated speech/DSP WAVs, actual SRT/LRC,
frozen semantic/resolved inputs, measured ledger, render manifests, engine log
and`verification.json` are present. V1 speech/subtitles reused unchanged; no TTS
rebuild or speech-rate change during the DSP phase. Manifest contains base commit
and actual working-source/preset fingerprints; later error-handling changes are
not falsely claimed to be the earlier rendered source bytes.

- Length1238.265261s; stereo44100Hz PCM24;54,607,498frames.
- Master peak−2.4773dBFS; RMS~−22.1954dBFS; zero clipped samples.
- FLAC and WAV decode identically; decoded float64 PCM SHA256:
  `7465bbb26e9852d2536e505a445a363e79201c0e2224e3c86c051e363aa91116`.
- Actual F10 spectra checked in510–570s/1060–1120s; family levels within0.6dB.
- Actual F11 checked720–840s:±40Hz sidebands antiphase within1.2°;
 175/179 probes >50dB below the main carrier. Silent ordinary windows and all
  eight transition boundaries checked; synthetic-state integration checks
  measured PCM midpoint gains and deterministic repeated output.
- No subjective listening, efficacy, final cue alignment or production-mastering
  approval claimed. Exact F10 modulation/full-band bed reproduction is follow-up.

## Corpus, authoring and pilot status

Authoring standard extended in place at`docs/NARRATION_STANDARD.md`: purposeful
sentences/operations, concrete instructions, useful silence/repetition,
sensory flexibility without repeated modality lists, neutral experiential language,
autonomy, claims conversion and independent originality review. RC1 words unchanged.

Inventory: [matrix](../research/HUMANPLUS_EVIDENCE_MATRIX.md), machine-readable
`docs/research/humanplus-corpus-inventory.json`, schema-defined live`corpus inventory`.
Every local file is fingerprinted; source text is not copied into runtime metadata.
Binary evidence remains unknown until content-specific review.

| Count | Result |
| --- | ---: |
| Files recursively inventoried |277 |
| Distinct target functions represented |55 |
| Operator-designated source transcript derivatives |107 |
| Partial source transcript derivatives (explicit gaps) |10 |
| Reconstruction/mockup files |33 |
| Secondary/context documents |34 |
| Unknown evidence objects |93 |
| Independently authenticated original-recording transcripts |0 |

117 source derivatives are multiple formats of39 functions, not117 distinct
historical functions. All16 legacy-source-unavailable targets have mockup research
and remain OCF reimplementation planned: See-Be, Regenerate, Short Fix, Emergency
Injury, Emergency Toxic, Empathizing, Zoning, Release, Light Foot, Make Your Day,
Strong-Quick, Sensory Smell/Taste/Touch, Sleep Easy, Stay Awake. Completeness and
historical accuracy are not established merely by apparent file boundaries.

Full-text sample review covered Relax, Hearing, Recall and Sleep Easy research.
Recall's explicit gap/incomplete ending ruled it out as a strong pilot. Provisional
grammar separates preparation/state entry, opener, target operation/association,
rehearsal/future use, closer, consolidation and waking return; ASR repeated tokens
are not accepted as intentional narration. This is a limited-sample hypothesis,
not a completed cross-corpus/generation analysis.

Pilots: **Relax** (single release operation), **Hearing** (adjustable two-mode
operation), **Sleep Easy** (mockup-informed source-unavailable target). All are
original English locale resources with semantic session templates, existing reusable
stages, command ownership and timing tests. Marked DRAFT/PILOT/REQUIRES HUMAN CONTENT
REVIEW. They are short ordinary-waking rehearsals, not full production Focus11
installations; source authenticity/completeness remains qualified.

Hearing's physical-hearing claims become attention practice, a material change
requiring review. Sleep Easy's safe-rest adjustments are OCF design inferences,
not recovered wording. Deliberate rehearsal replaces automatic-learning claims.
Originality/style review remains provisional; no final wording propagated to the
remaining52 functions. Full permanent function-content/provenance schema and
remaining-corpus semantic specifications are **not completed**; candidate line
locators are analysis aids, not completed semantic extraction.

Local pilot previews: `/tmp/opencode/relax-pilot.yaml`/`.wav` (100.583s),
`hearing-pilot.yaml`/`.wav` (113.434s), `sleep-easy-pilot.yaml`/`.wav` (123.076s),
each six utterances using existing Piper profile; actual totals were printed.
These early previews did not retain per-event metadata; the subsequent CLI now
writes measured sidecars for future voice/render-speech runs. No human listener
approval claimed.

## Discovery, coverage and platform status

- Function index preserves all55 canonical records and fresh generated views.
  New`functions list|describe --json` exposes actual records; rich per-function
  locale/state/session/duration/voice/DSP capability indexing remains incomplete.
- `capabilities --json` derives live command paths from registered CLI parsers,
  has a schema and tests, and does not advertise unshipped preparation commands.
  `AGENTS.md` supplies concise vendor-neutral discovery/workflow boundaries.
  Full guided natural-language authoring wizard/dry-run planner is not shipped.
- Coverage policy targets100% lines/branches. Current **combined-suite**, not
  unit-only:4485/5555lines (**80.7381%**),1567/2200branches (**71.2273%**).
  Application/library scope=`scripts/ocf_tools/`; zero excluded statements,
  including old no-cover-marked paths. Tool scripts/entrypoint scope still needs
  an audit; no100% CI enforcement claim or denominator shrink to hide gaps.
  See[policy](../TEST_COVERAGE.md). Raw snapshot is local in
  `/tmp/opencode/ocf-foundation-coverage-final.json` (supported Python3.12 combined run).
- Supported Linux/Python3.12 environment created independently at
  `/tmp/opencode/ocf-foundation-test-venv/`:385 tests passed and doctor10/10.
  macOS/Windows execution, installed-package data paths and cross-OS CI are pending.
  This temporary verification environment is not an idempotent setup product.
- Setup/bootstrap and optional container toolchain **not implemented**. No model
  downloads, privileges or arbitrary container execution. Native workflow retained.
- [User recordings](../USER_NARRATION.md) **shipped** through voice/render-speech/
  build`--recordings`: explicit occurrence IDs, schema/locale/missing-extra/hash/path
  checks, original preservation, optional in-memory ffmpeg decode, actual durations,
  existing reflow/overlap rules, subtitles from canonical text, source provenance.
  No TTS fallback or time-stretch. Directory-import wizard/normalization controls,
  narration-key aliases, disabled narration and GUI recorder remain pending.
- Community/open-license voice registry **not implemented**. Roadmap requires
  separate software/model/training-data/voice/redistribution terms and attribution,
  explicit hashes/versions/consent; downloadability is not licensing.
- Documentation updated: authoring, DSP/V2, evidence/matrix, pilots, coverage,
  recordings, agent entry point, user guide and roadmap. GUI framework and final
  language list deferred; clients must use shared APIs/schemas.

## Checks, failures and uncertainty record

- Audio checkpoint366 tests passed; foundation370/375 passed; final385 passed
  both in the existing environment and supported Linux/Python3.12.
- `make check`:0errors/7warnings; all55 functions and16 planned unavailable
  targets preserved; generated indexes fresh. Markdown links and diff whitespace pass.
- Spanish remains intentionally partial:89 missing canonical narration keys,
  including16 new pilot keys. No translations fabricated or silently substituted.
- Ruff rule lint still reports the15 inherited TD-001 findings; no new findings
  introduced. Full formatting/lint debt is not declared green.
- Default Python3.9 doctor reports9/10 due to the declared≥3.11 requirement;
  supported temporary Python3.12 doctor reports10/10. No global interpreter changed.
- Resolved failures: floating-point endpoint residue; stale indexes; masked PSD
  integration overcount; float32 RMS accumulation; missing schema`$id`; incorrect
  old locale count assertion after new resources; PCM24/WAV_EXTENSIBLE test-reader
  assumption. No validation was weakened to hide them.
- A proposed Markdown transcript-export example was rejected by the real parser
  (only SRT/VTT/LRC shipped); corrected documentation uses real voice preview.
  Legacy parse-error handling returns help/success and merits a separate compatibility
  audit. No nonexistent Markdown command is advertised as shipped.
- Fixed an existing build CLI omission of locale/fallback forwarding, verified by
  the new prerecorded-build routing test. Exact F10 reconstruction, corpus audio
  authenticity and pilot editorial/material-claim changes remain unresolved.

## Provisional decisions and exact next actions

1. Listen to V2 and the three pilot previews; review F10 omissions/equal-ear/master
   levels, ordinary-waking rehearsal scope, Hearing's attention reinterpretation
   and Sleep Easy's inferred safe-rest design. Keep pilots provisional meanwhile.
2. Continue complete source/PDF/ZIP content review and hash-addressed provenance;
   distinguish pamphlets, ASR derivatives, authentic recordings and reconstructions.
   Extract semantic specifications for remaining functions without final mass words.
3. Propose/add permanent function-content evidence/specification schema and generated
   rich index fields with runtime consumers, tests and explicit missing metadata.
4. Separate unit/integration markers, audit all first-party testable tools, add
   meaningful tests for1070missing lines/633missing branches in the current
   library snapshot, then enforce separate100% line/branch CI gates.
5. Audit installed-data discovery and OS-specific binary adapters; add and run
   Linux/macOS/Windows CI. Resolve TD-001 in a scoped cleanup checkpoint.
6. Implement idempotent dry-run/native setup with preserved assets/configuration,
   required/optional doctor distinction; add consent-based non-root cached container
   workflow and test host paths on supported systems.
7. Extend user-recording directory import/package authoring and model licensing
   registry. Do not bundle unknown community voices or infer rights.
8. Extend guided authoring/structured plans/templates discovery and executable docs;
   continue roadmap work without selecting a GUI framework or frozen language list.
9. For faithful V4 DSP, propose supported common-mode different-carrier PM and
   family-phased AM, test source/render modulation acceptance and full-band residuals;
   never silently relabel the current approximation as exact or universally canonical.
