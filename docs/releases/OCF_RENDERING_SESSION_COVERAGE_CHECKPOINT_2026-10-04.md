# Rendering and session coverage checkpoint — 2026-10-04

Starting commit: `ac203bd`, the CLI/wizard/generator checkpoint. This continuation
resumed the recorded rendering work after an interrupted provider/tool run; no
prior work or reference material was reset, restored, deleted or rewritten.

## Recovery commits

| Commit | Purpose |
| --- | --- |
| `c8b45f5` | Rendering boundaries; cue descriptor cleanup, reference fades, master metadata and output protection |
| `4841b92` | Complete voice/audio unit contracts; empty native-error decoding and justified invariant cleanup |
| `d41d2eb` | Complete session contracts; explicit timing, repeated LRC words and owner protections |

The report/documentation commit is discoverable with
`git log -1 --format=%H -- docs/releases/OCF_RENDERING_SESSION_COVERAGE_CHECKPOINT_2026-10-04.md`.
No push, unrelated staging, listening-artifact overwrite or production rendering.

## Coverage and test counts

| Metric | Start | Final |
| --- | ---: | ---: |
| Unit cases passed | 449 | 575 |
| Integration cases passed | 286 | 286 |
| Total cases | 735 | 861 |
| First-party statements | 7352 | 7385 |
| Covered lines | 5616 | 6244 |
| Unit line coverage | 76.38737758433079% | 84.54976303317535% |
| Missing lines | 1736 | 1141 |
| First-party branches | 2908 | 2928 |
| Covered branches | 1986 | 2366 |
| Unit branch coverage | 68.29436038514443% | 80.80601092896175% |
| Missing branches | 922 | 562 |
| Excluded statements | 0 | 0 |

Raw exact missing lines and branch endpoint pairs for every module:
`audio/rendered/coverage-rendering-session-2026-10-04.json` (ignored).
Intermediate rendering/target reports remain separate. The initial interrupted
coverage run did not complete and was not counted; the subsequent full run did.

`audio_build.py`, `voice.py` and `session.py` now have **100% unit lines and
branches**. Twenty measured modules are fully covered, including the small
`__init__` module. The repository-wide **100% target remains unmet and the hard
gate remains disabled**. Scope includes all application and tool Python; no
existing integration cases were reclassified and no reachable no-cover exclusion
was introduced.

## New isolated contracts

- `tests/test_voice_contracts.py`: backend/profile precedence; multilingual model
  metadata; pronunciation versus display text; native argument/error/timeout/file
  protocol; descriptor closure and cleanup; synthetic PCM width/channels/resampling;
  cue grids/flow; validation failures, duplicate cues, sample rounding and measured
  sidecars. Native calls and repository-resource collaborators are injected.
- `tests/test_audio_boundaries.py`: encoder/decode/mix command planning, provenance
  versus rights, preset tiers, scratch paths, synthetic reference PCM and fades,
  build preflight, overwrite protection, derivative failure and independent master
  metadata. The build coordinator uses stubbed narration, DSP, mix, encoder and
  resource-discovery boundaries rather than a real end-to-end render.
- `tests/test_session_contracts.py`: injected schema/stage/locale resources; local
  template errors and listing; slot/repeat pacing; optional stages, immutable
  semantic overrides, owner variables, explicit timing and output collision paths.

Real ffmpeg/available engine and multi-component repository workflows remain
integration. Synthetic fixtures contain no source recordings or narration claims.

## Objective fixes

1. Cue rendering discarded the descriptor returned by `mkstemp`. It now closes
   the descriptor before invoking a backend and retains error/timeout cleanup.
   Successful processes producing empty output files now raise an OCF error.
2. A nonzero backend exit with empty stdout/stderr used a string fallback and
   called `.decode`, producing `AttributeError` instead of the normal diagnostic.
   The fallback is now bytes; stdout/file protocols are regression-tested.
3. Malformed Piper JSON object/language/code shapes raised attribute errors.
   Structural checks now produce clear model-locale errors. Valid sidecar language
   still overrides a mislabelled profile; no identity is inferred from filenames.
4. Reference-master mixing calculated the end crossfade, then overwrote it with
   the interior splice copy. The interior excludes both fades; deterministic stereo
   samples assert the actual end envelope. This corrects future reference-master
   mixing, not the preserved V2.1 induction profile or audition.
5. SBaGenX/reference scratch filenames could escape the scratch directory when
   derived from absolute/slashed preset names. All use the existing safe stem
   helper. Directory-only output no longer passes a file-production check.
6. Reference decoding assumes stereo interleaved PCM; the ffmpeg plan now requests
   two channels explicitly instead of misinterpreting mono samples as stereo frames.
7. Requested derivative encoders could all fail, leaving an empty output list and
   `IndexError` despite a usable WAV master. Derivative-only requests also mislabeled
   the first MP3/FLAC output as the master. Master identity/checksum is now always
   the actual WAV, independently of derivative selection or partial codec failures.
8. The master rate/channels previously came from mono narration even when ffmpeg
   mixed to stereo at another rate. Header measurements now report actual master
   metadata when readable, with the existing duration fallback otherwise.
9. Background mixing ignored `overwrite=False` at its native boundary. Build
   preflight now protects existing master/selected-derivative/render-manifest paths
   before TTS or DSP execution. Tests preserve the original bytes. This is a
   preflight collision contract, not a claim of race-free transactional output.
10. Original provenance was described as automatically “committable.” Tags now
    separate original/source-derived classification from release/rights approval.
    An empty but present import snapshot cannot silently become original. Default
    source-derived text remains citation-only unless separately release-cleared;
    no wording or working-edit gate was added.
11. Template listing indexed an empty optional description and could crash. Empty
    descriptions now list safely.
12. Repeated LRC slots promised to strip timestamp control markup but spoke it as
    text. Repetition now retains the words and schedules the passes without speaking
    those control tags; SOURCE/initial WORKING files are not altered.
13. Explicit zero timing arguments were replaced by defaults through `or`.
    Explicit zero duration is retained; non-finite/negative duration and nonpositive/
    non-finite line spacing fail clearly.
14. Function-specific templates allowed an explicit different command owner.
    Conflicting owners now fail rather than rebinding function-specific material.

Reachability decisions: the master path is always `.wav`, so a non-WAV suffix
fallback was redundant. For file-mode cues the scratch path is always allocated;
the invariant is asserted rather than inventing a None-returning allocator. RMS
blocks use positive block size and `start < len(samples)`, so their slices cannot
be empty under the non-mutating owned-buffer flow. These redundant checks were
removed; real decode, process and output failures remain tested.

## Validation and preserved boundaries

Actually run on Linux/Python 3.12:

- Final **575 unit tests passed** with branch coverage and native process guard.
- Final **286 integration tests passed** separately (861 total selected cases).
- Focused rendering/native-stub/legacy voice group: 126 passed after compatibility
  checks; subsequent boundary group: 120 passed; final resumed rendering-only new
  tests: 104 passed. Session/legacy session/semantics/planning group: 57 passed.
- `make check`: **0 errors / 7 existing warnings**; schema validation and generated
  index freshness pass. No generated indexes or source schema/data contracts changed.
- Ruff rule check and formatting pass (100 Python files); internal Markdown links
  and whitespace pass. `markdownlint` is absent and skipped by the existing target.
- `locale validate`: **0 errors / 1 existing partial-Spanish warning**, 89 missing
  canonical keys. No translation or narration resource was changed.
- Core doctor passed; optional Farfield/Piper/Podman remain absent on the tested PATH.
- Live editorial corpus still has 55 targets, 388 exact unchanged occurrences,
  55 uncertain occurrences, zero reviewed/release-approved and all rights unknown.
- Existing V2.1 approaches, measured/localized timing, PCM-envelope and recording
  regressions passed. Profiles, carriers/modulations, curve/level, cue identities,
  semantic stage YAML and frozen RC1/pilot wording were untouched.

Compatibility failures from old literal citation-only metadata assertions were
resolved by retaining that conservative default while clarifying separate release
clearance; provenance tests were not weakened or reclassified.

No native macOS/Windows, package rebuild/install, setup apply, container build,
MCP, listening approval or new production/development audition was performed here.
Integration audio uses test fixtures, not preserved listening/reference artifacts.

Pending AGENTS/ARCHITECTURE infrastructure edits and untracked agent docs/config,
Attention draft, `ReusablePrompts/` and `references/HumanPlusTranscripts/` remain
preserved. Only this task's code/tests/report were staged. No reference or local
editorial working text was copied into distributable data.

## Remaining largest gaps and exact next actions

| Module | Missing lines | Missing branches |
| --- | ---: | ---: |
| validators.py | 229 | 133 |
| tools/verify_development_v2.py | 140 | 26 |
| locale.py | 109 | 82 |
| semantic_dsp.py | 100 | 53 |
| tools/analyze_v4_short.py | 66 | 24 |
| tools/render_development_v2.py | 65 | 20 |
| editorial.py | 63 | 51 |
| tools/preview_preparation_learning.py | 63 | 25 |
| corpus.py | 49 | 26 |
| tools/analyze_corpus_relations.py | 47 | 25 |
| tools/bootstrap_legacy_map.py | 38 | 14 |
| tools/enrich_function_evidence.py | 38 | 16 |

Next: isolated narration/locale validator failure matrices; locale resolution and
message/version errors; DSP planning/error boundaries with synthetic stems;
research-driver argument/file/error contracts with decoders injected; remaining
editorial flags/filter/release edge cases. Review race/atomicity and unusual
interactive-navigation behavior as separate behavioral work, not coverage claims.
Preserve all 55/16 targets, source-first editing, frozen review items and honest
unit/integration taxonomy. Enable 100% gates only after both real metrics pass.
