# Unit coverage policy and current gap

Target: **100% lines and 100% branches** of first-party testable application
and library code. No reachable branch is excluded merely because it is hard to
test. Coverage is not a claim that the complete system is bug-free.

## Phase2B test taxonomy and expanded denominator

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
