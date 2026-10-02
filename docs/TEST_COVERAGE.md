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
