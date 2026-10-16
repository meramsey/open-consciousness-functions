# Unit coverage policy and current gap

## Current reproducible measurement

Use Python 3.11+ with `requirements-dev.txt` and any optional extras being tested:

```bash
python -m pip install -r requirements-dev.txt -e ".[mcp,artwork,lsp]"
python -m ocf_tools.coverage_report run
python -m ocf_tools.coverage_report check .ocf-work/logs/coverage/YOUR_RUN/summary.json
```

The explicit `run` command executes the **full** pytest suite with two `loadfile`
workers. It measures all executable Python under `scripts/ocf_tools` and
`scripts/tools`, including unimported modules. Coverage.py 7.16.2 / pytest-cov
7.1.0 collect branches, subprocesses, `_exit` and `execv` paths with per-test
contexts. No source omissions or statement exclusions are configured, including
old `pragma: no cover` annotations. Default output is a unique directory under
the validated OCF work root's `logs/coverage/`; an existing output directory is
rejected, preserving failed diagnostics. A short independent pytest basetemp
retains the production release path-length guard. Successful managed scratch is
cleaned through the shared workspace helper (unless `OCF_KEEP_WORK` is set);
failed/interrupted scratch and reports remain available. Reporting anchors
relative coverage filenames at the repository root, even from another directory.
Inherited `PYTEST_ADDOPTS` and configured `addopts` cannot filter this explicit
full-suite run, and unexpected deselection fails its gate.

Reports include raw combined, unit-context and integration-context JSON, exact
missing statements/branches, JUnit, collection taxonomy, pytest logs and a compact
summary with platform/version/counts. Unit/integration rows are **strict
attributed contributions**, not separate complete process runs: startup and
unattributed subprocess execution are combined-only. Contributions overlap and
must not be summed. Hard-killed processes cannot be assumed to flush coverage.

`tests/coverage-floors.json` gates statements and branches independently for the
combined suite and isolated unit contribution. CI runs the full instrumented
suite on Linux/Python 3.12 with codecs and optional adapters, retains reports even
on failure and rejects ambiguous/missing unit/integration classification. The
floors are measured regression guards, **not a claim of 100% unit coverage**.
Raise floors from verified measurements as meaningful tests close the remaining
gap; do not reduce scope, reclassify workflows or exclude branches to pass them.

The [modernization baseline](releases/OCF_MODERNIZATION_BASELINE.md) records the
unchanged starting commit's 1,779 passing tests and exact statement/branch counts.
The [modernization measurement](releases/OCF_MODERNIZATION_COVERAGE.md) records
1,894 passing cases, 89.3971% combined statements / 84.2947% combined branches,
and the still-incomplete 56.3629% / 61.7647% unit-context contribution.
New modules expand the denominator, so compare absolute coverage and remaining
gaps as well as percentages. Historical snapshots below retain their original
scope/tooling/limitations; their old temporary paths are not current commands or
evidence that today's repository has 100% unit coverage.

Target: **100% lines and 100% branches** of first-party testable application
and library code. No reachable branch is excluded merely because it is hard to
test. Coverage is not a claim that the complete system is bug-free.

## Historical Phase2B test taxonomy and expanded denominator

`pytest -m unit` selects audited isolated contracts using memory/temp data and
versioned declarative fixtures; native subprocess execution is prohibited by an
autouse boundary guard. Real ffmpeg tests carry`audio_integration`, `external_tool`
and`integration`. Repository/multi-component tests conservatively remain
`integration` until a finer audit; this classification does not inflate unit
coverage based on speed. `e2e` and`platform` markers are available for those tests.

The measured denominator now includes **all executable Python under both
`scripts/ocf_tools/` and `scripts/tools/`**, including research drivers, link
checking, preservation and extraction. No reachable logic is excluded. The tiny
`scripts/ocf.py`/shell launcher wrappers only establish import paths and delegate
to the measured CLI; they are entrypoint boilerplate, exercised by workflow tests,
not application/library behavior in this denominator. Generated data, vendored
engines and declarative assets are not Python statements in it.

```bash
python -m coverage run -m pytest -m unit
python -m coverage json -o unit-coverage.json
python -m pytest -m integration
```

The earlier narrower combined snapshots below are historical, not current unit
results. The100% unit gate is enabled only after both real metrics reach100%;
classification changes do not remove application/tool modules from measurement.

Initial measurable denominator: every executable statement and branch under
`scripts/ocf_tools/`, including CLI, validators, localization, loaders, paths,
semantics, DSP, voice/audio planning, wizards and error handling. No modules are
omitted; legacy `pragma: no cover` annotations do not exclude statements in the
configured report. YAML/JSON/data, generated catalogs, reference assets and
third-party engines have no first-party Python behavior in this denominator.

Research/development drivers under `scripts/tools/` are outside this initial
**application/library baseline**. Their testable behavior must be separately
audited before claiming full first-party testable-scope coverage. Tooling such as
setup/bootstrap and link checking must not be excluded from the eventual target.
Tiny entrypoints are not yet granted a blanket exemption.

```bash
python -m coverage run -m pytest
python -m coverage report
python -m coverage json -o coverage.json
```

The existing suite includes unit **and integration** tests; this first report
is explicitly **combined-suite coverage**, not verified unit-only coverage.
Separate suite markers and a unit-only run are required before asserting the
100% unit target. Tests must verify behavior: failure paths, ownership,
translations, timing, PCM boundaries and structured output, not merely call lines.

CI enforcement of100% is **pending**, not shipped. Enabling a knowingly failing
gate or shrinking the denominator would not establish the requested policy.
Measure the current gap, add meaningful unit tests, then enable separate line
and branch100% gates. OS CI and real external-engine integration complement those
gates; neither replaces unit coverage.

## First measured checkpoint

The370-test combined suite passed with coverage enabled. No statements were
excluded. Application/library denominator:5427 statements and2150 branches.
Covered4344 statements (**80.0442% lines**) and1511 branches (**70.2791% branches**).
Combined coverage.py percentage77.2733% must not be relabelled line coverage.
Raw JSON is local at `/tmp/opencode/ocf-foundation-coverage.json`.
This snapshot predates the three pilot/discovery additions; rerun after further
behavior changes. Unit-only percentages are **not yet measured**.

Latest combined suite:375 tests passed,5467 statements/2168 branches,
4388 covered lines (**80.2634%**) and1533 covered branches (**70.7103%**),
zero excluded statements. Raw report:
`/tmp/opencode/ocf-foundation-coverage-final.json`. Requested unit-only100%
coverage and CI enforcement remain incomplete.

Prerecorded-narration checkpoint:385 tests passed;5544 statements/2198 branches,
4473 covered lines (**80.6818%**) and1564 covered branches (**71.1556%**),
zero excluded statements. This supersedes the previous snapshot in the same local
`ocf-foundation-coverage-final.json` path; it is still combined-suite coverage.

Final supported Linux/Python3.12 snapshot after voice timing-sidecar support:
385 tests passed;5555 statements/2200 branches;4485 covered lines
(**80.7381%**) and1567 covered branches (**71.2273%**), zero excluded statements.
This is the current snapshot at the same local JSON path.

## Phase2B unit-only checkpoint (expanded scope)

Actual supported Linux/Python3.12 run: **119 unit tests passed**,295 integration
tests deselected. Covered3306/6671lines (**49.55778743816519%**) and991/2580branches
(**38.41085271317829%**). Remaining: **3365 lines and1589 branches**, zero excluded
statements. Exact per-file missing lines/branches are recorded in the gitignored
`audio/rendered/phase2b-unit-coverage.json`; regenerate with the unit command above.

These are unit-only metrics over application **and tool** code, not comparable
to the previous narrower combined-suite80.7381%/71.2273% snapshot.100% is not
achieved and CI enforcement is deliberately pending. Core unit CI is configured
on three OSes; remote macOS/Windows results are not claimed from this Linux run.
Root`setup.py` and`scripts/setup_ocf.py` are delegating build/bootstrap wrappers;
their business logic is measured in tool/application modules. No reachable error
path is hidden by no-cover markers. Native-bootstrap's minimum-version guard has
a narrowly documented UP036 lint exception because the standalone setup script
may be invoked before a supported interpreter is established; it is not excluded
from coverage.

## Phase2C unit-only measurement

Fresh baseline reproduced119 unit tests over6671 statements/2580 branches.
After isolated parser audit, synthetic research tests, completeness/failure and
prompt-control tests: **147 unit tests passed;283 integration tests passed**.
Current denominator6788 statements/2628 branches;3654 covered lines
(**53.83028874484384%**) and1126 covered branches (**42.84627092846271%**).
Remaining **3134 lines /1502 branches**, zero excluded statements. Exact per-file
results:`audio/rendered/phase2c-unit-final.json` (gitignored).
No100% gate enabled because the target remains unmet. Twelve parser/timeline tests
were individually reviewed as isolated string/in-memory contracts; CLI/schema/
repository workflows were not blanket reclassified. Numerical fixtures use
synthetic signals/noise and explicit dev math dependencies, never reference audio.

## Source-first authoring checkpoint — 2026-10-03

Actual Linux/Python 3.12 selection: **229 unit / 286 integration tests passed**.
The new editorial contracts retain exact source text, distinguish human review
from release approval, and test hash staleness, template provenance, source
uncertainty, package exclusion and failure paths. Two new multi-component
CLI/timing cases remain integration; synthetic fixtures alone do not redefine
test taxonomy.

Unit-only denominator: **7316 statements / 2908 branches**, with **4229 covered
lines (57.80481137233461%) / 1441 covered branches (49.55295735900963%)**.
Remaining **3087 lines / 1467 branches**, zero excluded statements. Exact report:
`audio/rendered/source-first-unit-2026-10-03.json` (gitignored). The 100% gate
remains disabled. See the [migration checkpoint](releases/OCF_SOURCE_FIRST_CHECKPOINT_2026-10-03.md).

## Unit-contract continuation — 2026-10-04

Actual Linux/Python 3.12: **357 unit / 286 integration cases passed**.
Unit-only **4897/7325 lines (66.8532423208191%)** and **1765/2908 branches
(60.694635488308116%)**. Remaining **2428 lines / 1143 branches**, zero excluded
statements. Fourteen measured modules (including `__init__`) now have 100% unit
lines/branches; the repository-wide target and CI gate remain unmet/disabled.

No integration case was reclassified and no reachable code was excluded. Exact
missing statements/branches: `audio/rendered/coverage-overnight-2026-10-04.json`.
See the [coverage checkpoint](releases/OCF_UNIT_COVERAGE_CHECKPOINT_2026-10-04.md)
for fixes, reachability decisions, scope, tests and next gaps.

## CLI/wizard/generator continuation — 2026-10-04

Actual Linux/Python 3.12: **449 unit / 286 integration cases passed**.
Unit-only **5616/7352 lines (76.38737758433079%)** and **1986/2908 branches
(68.29436038514443%)**. Remaining **1736 lines / 922 branches**, zero excluded
statements. CLI, prompts and generators join the fully covered modules (17 total,
including `__init__`); the overall 100% target/gate remains unmet/disabled.

Exact report: `audio/rendered/coverage-cli-wizard-2026-10-04.json` (gitignored).
No integration cases were reclassified. See the
[continuation checkpoint](releases/OCF_CLI_WIZARD_COVERAGE_CHECKPOINT_2026-10-04.md)
for failure-path fixes, reachability decisions and remaining priorities.

## Rendering/session continuation — 2026-10-04

Actual Linux/Python 3.12: **575 unit / 286 integration cases passed**.
Unit-only **6244/7385 lines (84.54976303317535%)** and **2366/2928 branches
(80.80601092896175%)**. Remaining **1141 lines / 562 branches**, zero excluded
statements. Voice, audio-build and session join the fully covered modules (20 total,
including `__init__`). The repository-wide 100% target/gate remains unmet/disabled.

Exact missing-line/branch report:
`audio/rendered/coverage-rendering-session-2026-10-04.json` (ignored).
No integration case was reclassified. See the
[rendering checkpoint](releases/OCF_RENDERING_SESSION_COVERAGE_CHECKPOINT_2026-10-04.md)
for fixes, reachability decisions, validation and remaining priorities.

## Semantic DSP unit-gap audit — 2026-10-04

The `semantic_dsp.py` audit added deterministic unit contracts for profile and
timing validation, transition/approach boundaries, gain expressions, renderer
engine dispatch, duration verification, RMS calibration, command failures, and
CLI preflight. Focused unit selection: **34 passed**; the full semantic DSP test
module: **36 passed**. Focused coverage reports **261/261 statements and
126/126 branches (100% line and branch coverage)** with no exclusions.

The repository-wide unit suite could not collect in this environment: Python
3.9.6 lacks `scipy` and `soundfile`, required by a synthetic research-driver
test. System Python 3.12.3 is present but has no pytest installation. The focused
module ran on Linux/Python 3.9.6; this runtime is below the package's declared
minimum Python 3.11, so no native supported-runtime claim is made. `make check`
passed with 0 errors and the same 7 existing warnings.

Focused coverage report: `/tmp/opencode/semantic-dsp-final.json`
(temporary, not committed). Next audit: `editorial.py`, then research drivers and
remaining first-party tools/modules.

## Editorial unit-gap audit — 2026-10-04

The editorial audit added contracts for path/package boundaries, locator
partitioning, source I/O and identity failures, shared-chunk flag merging,
inserted-block and reusable-origin invariants, filters, review requirements,
parser options, and all workflow dispatch/export paths. The focused unit
selection passed **92 tests**; the complete editorial test module passed **94
tests** (including its two integration cases). `editorial.py` measured
**417/417 statements and 228/228 branches (100% line and branch coverage)**,
with zero excluded lines.

Removed one redundant defensive branch that rejected blocks on unavailable
sources after schema validation: `editorial-function.schema.json` already
requires `blocks.maxItems: 0` for unavailable sources, so that branch was
unreachable for every valid document and could not execute without bypassing
the contract validator. The schema test continues to enforce this invariant.
Focused coverage report: `/tmp/opencode/editorial-unit.json` (temporary, not
committed). Next audit: research drivers, then remaining first-party tools and
modules.

## Corpus inventory and relation tooling — 2026-10-04

Synthetic fixtures now cover corpus inventory/classification, candidate
locators, the generated evidence matrix, text-format equivalence, changed-input
refusal, PDF extraction outcomes, ZIP member hashing/size limits, reporting,
and read-only output-path enforcement. The focused unit module passed **11
tests**. Both `ocf_tools/corpus.py` and `tools/analyze_corpus_relations.py`
measure **100% unit line and branch coverage**, with no exclusions. No corpus
reference material was read or changed. Detailed report:
`/tmp/opencode/corpus-rel.json` (temporary, not committed).

## Separated content and extraction driver — 2026-10-04

Added source/observation/locator validation failures, template and locale binding
outcomes, unknown library records, extracted-layer preflight/idempotence, and
the executable extraction entrypoint. The focused unit module passed **14
tests**. Both `ocf_tools/content.py` and `tools/extract_function_content.py`
measure **100% unit line and branch coverage**, with no exclusions. Report:
`/tmp/opencode/content-unit.json` (temporary, not committed).

## Prerecorded narration recording contracts — 2026-10-04

Recording coverage now includes session/text fingerprints, schema/locale and
text-hash mismatches, decode errors and empty decoded audio, explicit event
mapping, path containment, overwrite refusal, unmapped assets, and successful
package creation with originals preserved. The unit selection passed **21
tests**; the complete module passed **22 tests**, including the available
ffmpeg conversion integration. `ocf_tools/recordings.py` measures **100% unit
line and branch coverage**, with no exclusions. Report:
`/tmp/opencode/recordings.json` (temporary, not committed).

The same focused pass expanded authoring-plan contracts for voice selection,
slot files, profile state compatibility, and matching/mismatched recorded-event
packages. `ocf_tools/planning.py` measures **100% unit line and branch
coverage**; its focused module passed **5 tests**. Report:
`/tmp/opencode/planning.json` (temporary, not committed).

## Locale catalog edge contracts — 2026-10-04

Locale unit coverage now exercises absent catalog roots, stale/missing pack
entries, domain mismatch, non-strict issue reporting, empty inline events, and
number-grouping edges. Removed two guards unreachable for normalized locale
truncations and the formatter's prevalidated grouped-integer domain; behavior
is preserved because each candidate is a strict prefix and grouped input
always has at least one leading digit. The focused locale selection passed
**104 tests**. `ocf_tools/locale.py` measures **100% unit line and branch
coverage**, with no exclusions. Report:
`/tmp/opencode/locale-final.json` (temporary, not committed).

## Deterministic first-party tools — 2026-10-04

Added filesystem-backed unit checks for Markdown link policy, synthetic
container fixture generation, and all 55 legacy bootstrap mappings using an
isolated temporary root. The link scanner now recognizes empty Markdown link
targets so its existing empty-target handling is actually reachable. The
focused tool tests pass; `tools/check_markdown_links.py` and
`tools/container_smoke_fixture.py` measure **100% unit line and branch
coverage**. The legacy bootstrap writer's callable `main()` is tested against
temporary roots for both 55-record and unexpected-count outcomes; its
`__main__` dispatch is exercised with writes redirected to a synthetic writer,
so canonical records remain untouched. Detailed report:
`/tmp/opencode/tool-contracts.json` (temporary, not committed).

Additional filesystem-tool audits reached **100% unit line and branch
coverage** for `tools/build_package_data.py`, `tools/preserve_auditions.py`,
and `tools/apply_function_reviews.py`. Synthetic tests exercise package
exclusions/symlinks/build-manifest staging, byte-preserving/idempotent
preservation including source mutation during copy, and manual review source,
brochure, validation, CLI-default, and explicit `--apply` boundaries. Focused
reports: `/tmp/opencode/package-final.json`,
`/tmp/opencode/preserve-final.json`, and `/tmp/opencode/review-tool.json`
(temporary, not committed).

The same continuation now measures **100% focused unit line and branch
coverage** for `tools/analyze_v4_short.py`, `tools/preview_preparation_learning.py`,
and `tools/bootstrap_legacy_map.py`. `analyze_v4_short.py` is tested with
synthetic signals only; an independent-noise boundary test exposed that short
Welch windows could yield spuriously high coherence from too few averages, so
delay fitting now requires at least eight Welch segments. The 100-second
research windows retain their existing estimator. Preparation preview tests
use synthetic text and do not load or rewrite frozen RC1 wording. Bootstrap
writer/entrypoint tests route all generated records to temporary roots or an
injected writer. Reports: `/tmp/opencode/analyze-v4.json` and
`/tmp/opencode/tool-contracts-py312.json` (temporary, not committed).

`tools/verify_development_v2.py` has deterministic synthetic-PCM coverage for
hashing, block reads, RMS/peak statistics, spectral amplitude, and declared
approach acceptance. Its remaining full-audition acceptance flow reads V2/V2.1
audition files and writes an acceptance report; that flow remains frozen until
the pending human V2-versus-V2.1 comparison. `tools/render_development_v2.py`
reaches **100% focused unit line and branch coverage** using only synthetic V1
files and fake DSP/ffmpeg boundaries; no listening audio is generated. A failure
test found that missing copied files could leave a partially-created audition
directory, so the renderer now preflights all V1 assets and subtitles before
creating output. The remaining verifier main path's V2 audio acceptance report
is intentionally unexecuted under the human listening freeze.

## Phase2C final unit-scope checkpoint — 2026-10-04

Linux/Python 3.12.3 full unit selection: **804 passed**. Full integration
selection: **286 passed**. Combined complete suite: **1,090 passed**. Coverage
ran with `branch = true`, `source = [scripts/ocf_tools, scripts/tools]`, and
`exclude_lines = []`; no lines were excluded and no denominator was reduced.
The measured denominator is **7,440 statements and 2,946 branches**: **7,375
covered statements (99.13% line coverage)** and **2,928 covered branches
(99.52%)**. Coverage.py's combined report is 99.24%. The exact remaining 65
lines and 14 branches are all in `scripts/tools/verify_development_v2.py`'s
full V2 acoustic acceptance flow:

- Lines: `145-153`, `156-164`, `167-183`, `185-186`, `191`, `201-211`, `218`,
  `224-225`, `228-243`, `250`, `266-267`.
- Branch arcs: `164→167`, `164→168`, `168→169`, `168→172`, `173→174`,
  `173→175`, `178→179`, `178→201`, `207→208`, `207→218`, `234→235`,
  `234→236`, `236→237`, `236→250`.

The remaining code reads a V2 DSP bed/master/listening encode, asserts specific
F10/F11 spectral and temporal acceptance conditions, and writes an
`acceptance: passed` report. The human V2-versus-V2.1 comparison remains
pending. Exercising these lines with fabricated acceptance measurements or
using frozen audition artifacts would cross that human-review boundary. Its
independent PCM/statistics, spectral amplitude, and raised-cosine approach
helpers are covered with synthetic fixtures; the full acceptance flow is the
sole objectively blocked residual. Exact JSON report:
`/tmp/opencode/phase2c-unit-final.json` (temporary, not committed).

This concludes the Phase2C coverage continuation at **804 unit / 286
integration / 1,090 total tests passed**. The honest full first-party unit
scope remains **99.13% line / 99.52% branch coverage** for the one documented
human-review blocker; no coverage gate or measured denominator was weakened.
See [the final engineering checkpoint](releases/OCF_PHASE2C_UNIT_COVERAGE_FINAL_2026-10-04.md)
for commits, platform/dependency details, TODO audit, and final validation.
