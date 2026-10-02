# Phase2B engineering/research checkpoint — 2026-10-02

Starting commit:`bdf2524be723e9b29f9ee6b9278080e80307f43a` on`main`.
The prior overnight report was read completely before work. Initial tracked
worktree/index were clean; untracked`ReusablePrompts/` and
`references/HumanPlusTranscripts/` were preserved. This is a **partial execution
checkpoint**, not completion of all Phase2B goals: full functional extraction and
100% unit coverage remain substantial independent follow-up work.

## Recovery commits, chronological

| Hash | Purpose |
| --- | --- |
| `21407edbee9bdcca7930fe3d01e74541e3c55113` | Immutable/hash-verified local audition preservation |
| `3f709468da55b79b8892a67c0da49934baa122f1` | Separate function evidence/specification/decision/binding model and rich discovery |
| `479996f5eeaea6828650d550b271e3f30bbabca3` | Structured authoring-plan preflight, no editorial/render effects |
| `5662b46f924f38d3b3a386570b85927438d51193` | Full-file corpus relationship census and documentary classification refinement |
| `a574eb45a6c1d327f6cf02c3597cac816a380ae0` | Resolve TD-001 and normalize Python formatting |
| `bea2a3d17f2c96307dfa092872fa8e587a42a976` | Honest unit/integration taxonomy and cross-OS core CI |
| `0f73192af6ab123f12152a46c3d0423101e617d9` | Required/core/workflow/optional structured doctor |
| `1642e54b0d333ca43b3d33f44b2f7b6c2e1af06b` | Packaged runtime resources independent of working directory |
| `33c8e6b4e5bf0478e9fe0faf06160b4ad97467d2` | Safe dry-run/idempotent native core bootstrap |
| `827bafca59ea818a002275346950c32632f1a437` | Optional non-root CPU container and actual mounted-recording smoke |
| `4952909c958bdd6df0f5fe48c97b28fca5857b94` | Session-bound recording import, explicit disabled narration, rights-aware voice registry |
| `8ef9af1bcf7451336f338433ed1912f2399a6d10` | Meaningful failure-path tests; invalid CLI requests return nonzero |
| `a20a839f968b49c3435abff80dbfa0a8c842b96c` | Current interfaces, resource registry and coverage documentation |

The report's own commit is returned in the session and discoverable with
`git log -1 --format=%H -- docs/releases/OCF_PHASE2B_CHECKPOINT_2026-10-02.md`.
No push, history rewrite, source migration, reference asset/audio staging or
secret/private input staging. Tracked tree was clean before this report commit.

## Review freeze and preserved listening artifacts

No RC1/pilot narration, template or locale resource changed. A baseline-to-current
Git diff for locale data, RC1/three pilot templates and F10/F11 manifests was empty.
No RC2, subjective approval, production-master label, aesthetic/cue choice or
mass final narration. Hearing/Sleep Easy decisions are recorded as **pilot-scoped,
provisional, material changes requiring human review**, never historical evidence.
`OCF-BG-0012` remains approximate V4-derived candidate; newer F11`0006` stays pure
SAM and`0007` stays continuous-theta alternate. No optional DSP redesign attempted.

Persistent gitignored destinations follow the existing rendered-audio policy:

- `audio/rendered/auditions/preparation-learning-v2/`: all19 available original
  files, including FLAC/MP3, authoritative WAV, speech/DSP/states, render/verification
  metadata, subtitles, frozen inputs, measured ledger and logs.
- `audio/rendered/auditions/function-pilots/`: all six available pilot WAV/YAML files.
- Local preservation JSON manifests verify source/copy SHA256 before/after;
  source artifacts remain intact. A local README records the preservation checkpoint.
  Early pilots lacked per-event producer metadata; no missing details were invented.

Preservation code is idempotent and refuses different existing destination bytes.
No listening audio is committed; source references remain unmodified/untracked.

## Function model, extraction and grammar

[Permanent additive model](../FUNCTION_CONTENT.md) implemented with five schemas,
library validation, cross-layer references, proposal and runtime discovery.
Existing function YAML owns identity/display/purpose/command metadata; separate
evidence, specification, OCF decisions, locale expression and runtime bindings
have independent authority. Mockups cannot authenticate themselves; historical
assertions require authenticated source evidence. Locale bindings cannot redefine
provenance, and OCF choices cannot be promoted into source-fact records.

Extraction status across55 targets: **complete0 / partial55 / unknown0 / blocked0**.
These are partially populated metadata/candidate records, **not55 completed
functional specifications**. State requirements, practical operations, unknown
release/reset/rehearsal/consolidation and unresolved claim conversions remain
explicitly unknown where evidence has not been reviewed. Unknown/not-present/
not-applicable/inferred are distinct. Initializer refuses customized-record
overwrite; no new narration or missing operation was fabricated.

All277 reference files were rehashed; complete text representations parsed;
PDF text inspected with pdftotext; ZIP members read/hashed in memory without
filesystem extraction. The[corpus report](../research/PHASE2B_CORPUS_GRAMMAR.md)
and`phase2b-corpus-relations.json` preserve39 normalized-content representation
groups (shared words, not independent authentication/semantic equality).
50 PDFs refined to secondary pamphlet candidates; five remain unclassified.
Current file classes:107 source-designated transcripts,10 partial derivatives,
33 mockups,84 secondary documents,43 unknown. Original inventory remains intact
as the earlier knowledge state. Authenticated original-recording transcripts:0.

Broader39-source-TXT structural candidate census: preparation39, association38,
future-use37, closer36, opener35, main34, return32. Strong recurring candidates
support separate shared preparation/association/closing architecture; actual main
operations remain function-specific. Detector nonmatches do not prove absence.
Canonical domain/mode metadata supports family investigation without title-based
identity inference; reviewed enhancement/reduction taxonomy and generation/version
differences remain uncertain. No historical cadence or ASR repetition adopted.

## Discovery and deterministic authoring

- `functions list|describe --rich --json` has a schema, explicit null/unknown
  durations/requirements, locale/template/voice references, safety/review and
  provenance categories. Generated JSON index includes the same capabilities;
  raw CLI output and existing CSV remain compatible. All55 mappings preserved.
- `plan FILE --json` validates structured template/locale/function-owner/DSP/
  recording choices, returns corrective JSON/nonzero failures, preserves draft
  status and reports target duration as a request rather than measured audio.
  No natural-language engine, vendor LLM, audio execution, model download or wording.
- `AGENTS.md` and[guide](../USER_GUIDE.md) document actual live interfaces;
  full wizard/GUI, translations and fixed language list remain roadmap work.

## Test taxonomy, coverage and lint

Audited isolated contracts carry`unit`; an autouse process-boundary guard forbids
real native subprocess execution. Native ffmpeg cases are`audio_integration`/
`external_tool`/`integration`; remaining repository/multi-component tests are
conservatively integration until finer audit. Platform/E2E markers are available.
Classification is behavioral, not based on speed or a desired coverage badge.

**Actual unit run:**119 passed,295 integration tests deselected. Current first-party
application/tool denominator:6671 lines and2580 branches. Covered3306 lines
(**49.55778743816519%**) and991 branches (**38.41085271317829%**).
**Remaining3365 lines /1589 branches; zero excluded statements.** Exact per-file
missing lines/branches:`audio/rendered/phase2b-unit-coverage.json` (gitignored).
Includes research/extraction/preservation/link/build tools, not just easy modules.
Minimal root/build/bootstrap entrypoint wrappers delegate to measured business
logic. Old no-cover annotations do not exclude reachable paths.

The previous80.7381%/71.2273% was a narrower **combined** scope; these metrics are
not directly comparable.100% unit coverage/CI enforcement is **not achieved**;
no denominator shrink or knowingly failing100% CI gate. Meaningful added tests
cover provenance contradictions, atomic-write recovery, explicit state/source
selection, registry duplication, session/text binding and invalid CLI exit status.

TD-001 resolved: missing annotation imports, redundant checksum, import order and
newlines fixed; full Python formatting normalized. Ruff checks and formatting now
pass. One narrow UP036 annotation is justified for standalone bootstrap's old-runtime
guard, not a no-cover exclusion or global rule disable.

## Platform, package, setup and containers

Actually run on **Linux/Python3.12**:

- Source core schema/localization/index validation and tests.
- Final wheel build/install,55-function discovery, core doctor and full packaged
  validation from an unrelated working directory. Final wheel artifact SHA256:
  `94c0246ba12f07f1794c599f22d4cfe99f0a9dcfb4092cbd1e7eaf46ac3942d8`.
  It is local/generated, not staged. Runtime resources use importlib.resources;
  explicit writable`OCF_DATA_ROOT` supports contributor workflows. No source
  audio/reference wording/models packaged; citation-only Attention binding/template
  omitted from the wheel, while historical function metadata is retained.
- Native setup dry-run/unit checks plus actual apply **twice** to a disposable
  environment: create, then reuse, ordinary satisfied core requirements, doctor
  success. No privileges, configuration overwrite or optional tool/model installs.
- Actual Docker build/core doctor/validation and mounted synthetic recorded-audio
  generation with network disabled and host UID/GID. Output1.1s mono44100Hz plus
  measured sidecar. Final verified image identity:
  `sha256:1c4706fa8ebb57ce1362378ad3cce658eef17bde78f0f268c226c4bd4b68dd64`.
  Base digest/core Python packages/ffmpeg pinned; Debian transitive snapshot pinning
  still needed for bit-exact image claims. CPU/non-root; no arbitrary auto-container,
  user recordings, reference assets or models baked in. Original synthetic inputs
  and earlier smoke outputs preserved.

macOS/Windows: unit CI matrix configured with Python3.11/3.12, platform path-adapter
tests/static audit performed; **no native or remote runner verification claimed**.
Farfield's POSIX source-checkout discovery remains a bounded optional adapter;
committed presets remain authoritative. Docker Desktop host mounting was not run
on macOS/Windows. Zip-app packaging and installed authoring without a writable
checkout are not claimed.

Doctor now differentiates core, selected workflow and optional tools with a stable
JSON schema. Missing optional engines do not fail core. Presence is not model/
codec compatibility, license proof or OS certification. Check workflow with
`--workflow encode|farfield|sbagenx|piper|container`; no downloads/execution by doctor.

## Recording sources and community voices

`voice import-recordings` requires explicit occurrence-ID → filename JSON mapping,
measures actual decoded duration/sample metadata, retains original filenames,
narration keys, speaker, session/text hashes and pending content-review status.
Missing/unknown/duplicate keys, escaping files, unmapped audio and wrong session/
text are diagnosed. No originals changed; decode/resampling occurs only in derived
output. Compressed original codec remains unknown unless separately probed.
Metadata declaration is not speech recognition or consent authentication.

Narration modes now include TTS profiles, user/external recordings and explicit
disabled narration for **speech-free** semantic documents; required speech cannot
silently disappear. Timing/subtitles/DSP use actual durations and existing anchors.
Community voice packs are a **metadata foundation**, separate from generation
profiles: schema/loader/validation/`voice packs --json`, currently no assets registered.
Software/model/data/personality rights, consent, redistribution, hashes/versions,
locale/backend/settings/install status are separate. Bundling contradicting explicit
denial/unknown rights is rejected; no legal adjudication, model download or cloning.

## Validation, defects and unverified work

- Starting full suite385passed. Latest complete suite413passed before one extra
  isolated Markdown-boundary test; final unit selection119passed. The same295
  integration cases passed in that complete run after correcting a false-positive
  CLI routing test. Final collection414 tests.
- `make check`:0errors/7existing warnings; schemas/locales55 mappings and16 planned
  source-unavailable targets preserved; generated indexes fresh.
- Ruff rule check and format check pass; Markdown links and whitespace pass.
- Packaged and container validation also0errors/7existing warnings; Spanish89 keys
  remain missing intentionally. No translation fabricated or fallback made silent.
- Fixed objective defects: copied600-mode YAML unreadable to non-root container
  user (image-only permissions corrected); invalid argparse requests returned
  success (now2); old test used nonexistent`--backend` and passed only because of
  that bug (now asserts actual`--voice`/locale forwarding); link checker scanned
  generated wheel/build artifacts (now scoped to authored source docs).
- No unresolved test regression observed. Not achieved: complete functional grammar/
  per-function semantic extraction,100% unit coverage/gates, native macOS/Windows,
  signed/distributed voice packs and full guided GUI/wizard. Frozen human decisions
  remain V2 listening/mastering, Relax/Hearing/Sleep Easy editorial purpose/style
  and originality, especially Hearing's material reinterpretation and Sleep Easy
  historical/design boundary. They were not adopted as approved policy.

## Exact next actions

1. Continue full manual functional extraction into existing55 partial specs,
   with hash/source locators and distinct unknown/not-present/inferred status.
   Do not mass-generate wording or promote frozen pilot design choices.
2. Audit remaining integration cases for genuine isolated contracts, then test
   reachable gaps module-by-module. Start from the exact3365-line/1589-branch JSON
   report. Add synthetic numerical research-tool tests with explicit dev dependencies;
   do not remove hard tools from the denominator. Enforce100% only when achieved.
3. Obtain actual cross-OS CI results and test installed-wheel workflows/native
   setup/recording imports on macOS/Windows; refine optional process adapters.
4. Extend package/content authenticity and richer manual operation data, measured
   duration provenance and codec/speaker diagnostics; keep licensing declarative.
5. Snapshot Debian dependencies/sign container artifacts if stronger reproducibility
   is required; add model/voice installation only with appropriate recorded rights.
6. Preserve the human-review freeze while engineering continues. No routine approval
   gate blocks those independent tasks; this execution ends at committed recovery
   boundaries because complete extraction/coverage exceeds the current window.

Tracked implementation work is committed; the only intentional untracked user
directories remain`ReusablePrompts/` and`references/HumanPlusTranscripts/`.
Local listening/coverage/build/test artifacts stay gitignored or temporary.
