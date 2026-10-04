# Unit-coverage engineering checkpoint — 2026-10-04

Starting commit: `f03852c` (source-first corpus/validation checkpoint).
Scope: reachable isolated application/tool contracts toward 100% unit line and
branch coverage. This is substantial progress, **not achievement of the 100%
repository target**. No hard 100% CI gate was enabled.

## Recovery commits

| Commit | Work |
| --- | --- |
| `2845393` | Optional-engine and record contracts; Farfield metadata and SBaGenX failure handling; named proposal-ID fix |
| `a5785ad` | Transcript handler contracts; SRT precision, empty WebVTT and output-validation fixes |
| `41ad63c` | Command/collection, semantic and clock failure contracts; invalid measured-duration rejection |
| `338b3d2` | Parser/semantic completion, deterministic discovery/I/O tests and resource-loader fixes |

The subsequent checkpoint commit includes the last loader assertions, local-date
docstring correction and this report; resolve it with
`git log -1 --format=%H -- docs/releases/OCF_UNIT_COVERAGE_CHECKPOINT_2026-10-04.md`.
No push, reference edits, audio staging or unrelated worktree rollback.

## Measured results

| Metric | Starting checkpoint | Final measurement |
| --- | ---: | ---: |
| Unit tests passed | 229 | 357 |
| Integration tests passed | 286 | 286 |
| Total selected cases | 515 | 643 |
| First-party statements | 7316 | 7325 |
| Covered lines | 4229 | 4897 |
| Line coverage | 57.80481137233461% | 66.8532423208191% |
| Missing lines | 3087 | 2428 |
| First-party branches | 2908 | 2908 |
| Covered branches | 1441 | 1765 |
| Branch coverage | 49.55295735900963% | 60.694635488308116% |
| Missing branches | 1467 | 1143 |
| Excluded statements | 0 | 0 |

Final raw report: `audio/rendered/coverage-overnight-2026-10-04.json`, gitignored.
It contains **exact missing lines and branch endpoint pairs for every module**.
The previous source-first report remains available separately. Coverage.py's
combined percentage is not reported as line coverage.

Scope remains all executable Python under `scripts/ocf_tools/` and
`scripts/tools/`; no hard tool or reachable error path was excluded. The native
subprocess boundary remains forbidden in unit tests. No existing integration
test was reclassified. New command-planning tests stub native execution; CLI/
repository and real ffmpeg workflows remain integration.

## Modules at 100% unit lines and branches

`__init__.py`, `audio.py`, `bootstrap.py`, `diagnostics.py`, `farfield.py`,
`indexes.py`, `models.py`, `paths.py`, `sbagenx.py`, `semantics.py`, `timing.py`,
`transcript.py`, `utils.py`, and `voice_registry.py` (all under `scripts/ocf_tools/`).
The count includes the small `__init__` module; it does not imply other modules
are complete.

Five new isolated test modules protect substantive behavior:

- `tests/test_engine_contracts.py`: optional-tool probes, unavailable/time-out/
  malformed metadata, URI decoding, preset tiers, argument planning, output
  overrides, command failures and stale-output detection.
- `tests/test_record_contracts.py`: canonical/legacy ownership, unknown provenance,
  mutable-copy isolation, release/mode metadata, spoken command counts, next IDs,
  confirmation and atomic-collision behavior.
- `tests/test_transcript_handlers.py`: format parsing, exact source snapshots,
  timestamp precision, invalid inputs, handler error translation, cancelled human
  segmentation, validation routing and measured-cue fallback.
- `tests/test_validation_contracts.py`: isolated command/collection rules,
  compatibility rationale, unavailable-target invariants, semantic namespaces,
  cue binding errors, invalid clocks/durations and setup failure boundaries.
- `tests/test_loader_contracts.py`: synthetic resource discovery, missing-directory
  fallback, primary precedence, YAML errors, Unicode, file-versus-directory
  filtering and atomic-write cleanup. Dates are injected, not wall-clock fixtures.

## Objective fixes and reachability decisions

1. Farfield metadata could raise on list/numeric JSON values and could not resolve
   percent-escaped local checkout URLs. Nonlocal/malformed URLs are ignored and
   local paths decoded; explicit preset overrides and committed precedence remain.
   Empty version output now remains unknown rather than an empty version string.
   Explicit `.yml` paths are accepted consistently with named `.yml` presets.
2. SBaGenX previously reported success when a failed command found an old output
   file. A nonzero process status or non-file output now reports failure.
3. Proposal IDs used the filename's last hyphen-delimited token, so the existing
   named-proposal convention crashed ID allocation. Numeric OCFP prefixes are
   now extracted while preserving names and skipping unrelated files.
4. SRT one-/two-digit decimal fractions were treated as milliseconds rather than
   decimal fractions of a second. Supported fractional precision is now correct;
   source snapshot/wording remains exact.
5. Header-only WebVTT input raised `IndexError`; it now parses as an empty source.
6. Segment `--output` validated the original input instead of the generated target;
   it now validates the selected output.
7. Negative/non-finite measured durations could create invalid render ledgers;
   scheduling now rejects them explicitly.
8. The scheduler's no-eligible-node error was genuinely unreachable: timeline
   resolution already rejects missing dependencies and cycles; the remaining DAG
   always has an eligible node. That redundant condition was removed, with tests
   retaining real cycle/missing-target errors. No reachable behavior was hidden.
9. Discovery accepted directories with YAML suffixes. Loaders now require files.
   Audio companion-directory fallback also works when the primary tree is absent.
10. UTF-8 decoding and read failures could escape the common OCF error boundary.
    They now produce `OCFError` without repairing or normalizing input text.

The `ParsedTranscript.snapshot` annotation now reflects its existing optional
snapshot branch. The date helper docstring reflects local-calendar behavior;
its runtime behavior was not changed or represented as UTC.

## Remaining largest gaps

| Module | Missing lines | Missing branches |
| --- | ---: | ---: |
| cli.py | 292 | 136 |
| prompts.py | 277 | 50 |
| audio_build.py | 236 | 131 |
| validators.py | 229 | 133 |
| voice.py | 199 | 125 |
| session.py | 160 | 104 |
| tools/verify_development_v2.py | 140 | 26 |
| generators.py | 122 | 34 |
| locale.py | 109 | 82 |
| semantic_dsp.py | 100 | 53 |

Next priorities: isolated CLI routing/error translation; wizard field/control
handling with injected prompts/writes/validators; remaining narration/locale
validator cases; audio build and voice command planning; synthetic research-driver
entrypoints. Continue checking actual reachability before writing coverage-only
tests. Retain external engine executions in integration. Finish the real line and
branch targets before enabling their CI gates.

## Validation and preserved boundaries

Actually executed on Linux/Python 3.12:

- Final full unit selection: **357 passed**, 286 deselected, with branch coverage.
- Full integration selection after runtime fixes: **286 passed**, 356 then-current
  unit cases deselected. The subsequently added date test/docstring changed no
  runtime behavior. Both selections pass; no combined-scope coverage claim.
- Focused engine/record/integration-wizard group: 85 passed; transcript group:
  86 passed; semantic/clock group: 56 passed; loader/index/boundary/parser group:
  93 passed; final parser/semantic additions: 68 passed; final loader group: 10.
- `make check`: 0 errors / 7 existing warnings, schemas and indexes fresh.
- `locale validate`: 0 errors / 1 existing partial-Spanish warning (89 keys).
- Ruff rules and formatting pass; Markdown internal links and whitespace pass.
  `markdownlint` is absent and was skipped by the existing target.
- Core `doctor --json`: passed. Optional Farfield/Piper/Podman are absent from the
  tested PATH; core functionality does not require them.
- Live editorial dashboard still has 55 targets, 388 unchanged block occurrences,
  55 uncertain occurrences, 0 reviewed/approved, all rights unknown. No source-first
  review decision or working wording was changed.
- Existing V2.1, localized timing, PCM-envelope and optional-adapter integration
  regressions passed. No state-profile/preset/locale/stage/function changes.

macOS/Windows, package rebuild/install, setup apply and container execution were
not run for this coverage checkpoint. No new audition/production audio was built;
external-audio integration used test fixtures, not preserved listening artifacts.
No native-OS/package/audio-listening approval is claimed.

The prior AGENTS/ARCHITECTURE infrastructure edits and untracked `.opencode/`,
AGENT_DEVELOPMENT/AUDIO_PIPELINE documents and Attention draft remain intact.
`ReusablePrompts/`, `references/HumanPlusTranscripts/`, the local editorial corpus
and listening artifacts were not staged or modified. Remaining working-tree
changes are the previously pending project work, not failed coverage changes.

Frozen RC1/V2/V2.1 and Relax/Hearing/Sleep Easy editorial/listening items remain
pending human review. No mass narration, translation, rights clearance or release
promotion occurred. The 100% coverage target remains an explicit engineering
follow-up rather than a claimed completed gate.
