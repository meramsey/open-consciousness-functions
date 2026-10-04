# CLI, wizard and generator coverage checkpoint — 2026-10-04

Start: `731ab0f`, the prior unit-coverage checkpoint. Pending AGENTS/ARCHITECTURE
infrastructure changes, untracked agent docs/configuration, Attention draft and
intentional reference/user directories were preserved.

## Recovery commits

| Commit | Purpose |
| --- | --- |
| `315bd17` | Isolated CLI dispatch contracts; format selection, JSON mapping and locale-filter fixes |
| `a0a2ca8` | Context-scoped wizard cancellation, source-copy consent, editor failures and metadata-based ID allocation |
| `0acf574` | Complete CLI/generator contracts; generated index preserves explicit seed zero |

The report/coverage-document commit is discoverable with
`git log -1 --format=%H -- docs/releases/OCF_CLI_WIZARD_COVERAGE_CHECKPOINT_2026-10-04.md`.
No push, destructive rollback, source edits or audio staging.

## Actual unit progress

| Metric | Before | Final |
| --- | ---: | ---: |
| Unit cases passed | 357 | 449 |
| Integration cases passed | 286 | 286 |
| Total cases | 643 | 735 |
| First-party statements | 7325 | 7352 |
| Covered lines | 4897 | 5616 |
| Line coverage | 66.8532423208191% | 76.38737758433079% |
| Missing lines | 2428 | 1736 |
| First-party branches | 2908 | 2908 |
| Covered branches | 1765 | 1986 |
| Branch coverage | 60.694635488308116% | 68.29436038514443% |
| Missing branches | 1143 | 922 |
| Excluded statements | 0 | 0 |

Raw exact per-file missing lines/branch endpoint pairs:
`audio/rendered/coverage-cli-wizard-2026-10-04.json` (gitignored). The previous
report is preserved separately. These are unit-only line/branch metrics, not the
coverage.py combined percentage. The 100% gate remains **disabled/unmet**.

`cli.py`, `prompts.py` and `generators.py` now have 100% unit lines and branches.
Together with the previously completed modules, **17 measured modules** are at
100% (including the small `__init__` module). Remaining modules are not excluded.
No existing integration test was reclassified and no no-cover exclusion added.

## New tests and defects fixed

- `tests/test_cli_contracts.py`: 48 isolated routing/output cases. Repository,
  authoring, rendering, discovery, locale and process collaborators are injected.
  Protects callee exit codes, error translation, flags/defaults, Unicode JSON,
  strict/fallback forwarding, recordings/DSP, human-review dispatch and module
  entrypoint behavior. In-process entrypoint testing invokes no native process.
- `tests/test_wizard_contracts.py`: 41 isolated collection/control cases. Tests
  real quit/EOF/interrupt handling plus injected review/write/validation boundaries,
  source-copy decisions, compatibility/release collection, editor failures,
  temporary documents and identity allocation. Tests do not write real authoring
  files or interpret scripted fixture choices as human review of project content.
- `tests/test_generator_contracts.py`: 3 synthetic derived-data contracts spanning
  the owned serialization/orchestration methods. Verifies canonical/legacy identity,
  Unicode/CSV/Markdown quoting, unknown evidence, zero seeds, deterministic output,
  missing/drifted files and regeneration inside a temporary tree.

Objective corrections:

1. Explicit `audio build --format wav` previously appended to the three defaults,
   so it did not restrict output. Omitted options still mean all three; supplied
   options now mean precisely the supplied formats.
2. Missing, undecodable or malformed recording-map JSON could escape the common
   CLI error boundary. UTF-8 reads and JSON syntax errors now return normal OCF
   diagnostics. Duplicate keys remain errors; no mapping identity is inferred.
3. `locale validate --locale fr` used a string-prefix test and included `fr-CA`
   problems. Pure path containment now selects only the intended pack(s).
4. Several wizard fields ignored quit results and could continue collecting or
   serialize a quit token. A context-local guard causes quit/EOF/interrupt to
   terminate the active wizard before value consumption, while standalone
   `ask()` keeps its existing result protocol. Context state resets on every exit.
5. Skip/back at the source-copy question could fall through to copying. Copying
   now requires an explicit value choice; control responses leave the source alone.
6. Editor launch/nonzero-exit failures previously escaped or still proceeded to
   validation. They now raise an OCF diagnostic before validation is claimed.
7. Audio/background wizard filenames are lower-case, but old ID allocators only
   recognized upper-case filename prefixes. Allocation now reads declared YAML
   IDs, supporting named/lowercase files and `.yml` without conflating filenames
   with identity. Existing valid metadata and command mappings remain unchanged.
8. Background index formatting hid explicit seed `0` as an empty field. It now
   displays `0`; the index was regenerated with `build-index`, not hand-edited.
   The only generated-data diff is the `OCF-BG-0012` seed cell. No preset, level,
   curve, engine selection or evidence distinction changed.

Reachability decisions: duplicate `validate_all()` branches were collapsed;
locale dispatch's impossible unknown-kind tail was removed because argparse
rejects unregistered kinds before dispatch. Wizard quit-result checks became
unreachable after context-scoped cancellation raises before returning such a
result. Genuine quit/error paths are protected by regression tests, not excluded.

## Remaining gaps and next actions

| Module | Missing lines | Missing branches |
| --- | ---: | ---: |
| audio_build.py | 236 | 131 |
| validators.py | 229 | 133 |
| voice.py | 199 | 125 |
| session.py | 160 | 104 |
| tools/verify_development_v2.py | 140 | 26 |
| locale.py | 109 | 82 |
| semantic_dsp.py | 100 | 53 |
| tools/analyze_v4_short.py | 66 | 24 |
| tools/render_development_v2.py | 65 | 20 |
| editorial.py | 63 | 51 |
| tools/preview_preparation_learning.py | 63 | 25 |
| corpus.py | 49 | 26 |

Next: audio-build/voice command planning and decode errors with native execution
stubbed; remaining narration/locale validation failures; stage composition and
optional-feature/slot resolution; synthetic numerical driver entrypoints. Continue
auditing real reachability instead of generating calls only for coverage. Actual
engines/codecs, repository workflows and available cross-OS jobs remain integration.
Do not enable the 100% line/branch gates before both real targets are attained.

Full multi-field `back` navigation was not redesigned: this checkpoint protects
quit/EOF/interrupt and source-copy cancellation. Existing wizard navigation and
required-field validation deserve a separate behavioral audit; 100% structural
coverage is not a claim that every possible interactive input is correct.

## Validation and platform boundaries

Actually executed on Linux/Python 3.12:

- Final **449 unit cases passed** with branch coverage; **286 integration cases
  passed** separately (735 total cases).
- Focused CLI/legacy CLI/locale/recording-import group: 68 passed; wizard/prompt/
  legacy-wizard/record group: 75 passed; generator/CLI group: 51 passed.
- `build-index` regeneration and final freshness pass. Full schema/rule checks
  through `make check`: **0 errors / 7 existing warnings**.
- Localization validation: **0 errors / 1 existing partial-Spanish warning**,
  still 89 missing canonical keys. No translation was created or altered.
- Ruff rules and formatting pass (97 Python files); Markdown internal links and
  whitespace pass. `markdownlint` is absent and skipped by the existing target.
- Core doctor passed. Missing optional Farfield/Piper/Podman do not fail core.
- Source-first dashboard remains 55 targets / 388 unchanged block occurrences /
  55 uncertain / 0 reviewed / 0 release-approved / all rights unknown.
- Existing V2.1/localized timing/PCM integration regressions pass. RC1/pilot
  narration, semantic stages, state profiles, cues, presets and listening artifacts
  were not modified.

No native macOS/Windows, wheel/install rebuild, setup apply, container build,
MCP execution or listening review was performed during this checkpoint. No new
development or final narration/audio was generated. Scripted test fixtures are
not evidence of clinical effects, licensing, source authentication or content review.

All code/test improvements are committed; pending working-tree changes are the
pre-existing infrastructure/Attention work. `ReusablePrompts/` and
`references/HumanPlusTranscripts/` remain untouched/uncommitted. The local editorial
corpus and ignored reports were not packaged or staged. The 55/16 mappings,
PLUS-THINK/PLUS-FOCUS and F10/F11 evidence boundaries remain intact.
