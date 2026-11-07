# Test performance investigation — 2026-11-06

Status: **full Linux suite and coverage speedup verified; successor cross-platform
CI pending**. Terminal results collected on 2026-11-07 supersede the earlier
microbenchmark-only status. No queued job is included in the results below.

## Completed full-suite comparison

Baseline `c8ea153ef18e0d349bdb687f7ad445edc0bdbe01` and optimized
`9690b686340aab4898ed6a2f7a955cbc29c37901` ran sequentially in the same
existing Linux/Python 3.12.3 environment with two workers and `--dist loadfile`.
Every required local validation, locale, lint, full pytest and full coverage gate
completed successfully. The optimized branch was pushed only after those gates.

| End-to-end command / metric | Baseline | Optimized | Wall reduction |
| --- | ---: | ---: | ---: |
| Full pytest, no coverage | 2726.60s | 1135.98s | 58.34% |
| Full coverage workflow, including reporting | 6956.585s | 2805.481s | 59.67% |
| Instrumented pytest portion | 6948.666s | 2797.652s | 59.74% |
| Standalone unit tier, no coverage | 242.01s | 111.87s | 53.77% |
| Standalone integration tier, no coverage | 2269.95s | 986.87s | 56.52% |
| Full no-coverage user CPU | 4860.05s | 2117.48s | — |
| Full no-coverage system CPU | 222.55s | 151.01s | — |
| Full no-coverage maximum RSS | 1280104 KiB | 1278400 KiB | — |
| Full coverage maximum RSS | 1289108 KiB | 1289692 KiB | — |

GNU time reports end-to-end no-coverage wall/CPU and maximum RSS; RSS is not an
aggregate simultaneous-worker memory measurement. Coverage wall times come from
the coverage runner's terminal summaries. Resource use is not claimed to have
fallen in every dimension. Setup/install overhead was not measured or included:
both sources reused the existing environment. OS caches were not cleared; the
baseline/optimized full-suite pair was run once. Repeated component measurements
support the identified bottleneck, but are not repeated full-suite trials or CI
critical-path measurements. See the machine-readable
[terminal summary](benchmarks/test-execution-20261107.json).

Protection and coverage comparison:

- JUnit identity sets: all **2905 baseline identities retained**, none removed;
  eight regression/harness tests added, for 2913 optimized identities.
- Baseline: **2900 passed, 5 skipped**, zero failures/errors.
- Optimized: **2908 passed, 5 skipped**, zero failures/errors.
- Coverage: **89.811083% statements / 84.653364% branches** baseline;
  **89.833634% statements / 84.679408% branches** optimized.
- Statements: 21393/23820 -> 21437/23863; branches: 8230/9722 -> 8241/9732.
  Excluded statements: zero in both. Full measurement deselection and taxonomy
  gates passed. The original 89.5% / 84.0% floors are unchanged.
- Real integration/failure-path checks were executed, not moved outside the gate
  or replaced wholesale by mocks. Required native/OS CI jobs remain unchanged.

The later Windows CRT state-sharing correction is integrated into this branch;
its additional regressions are not retroactively counted in these measured
populations. Explicit push triggers on the two performance branches run the
existing full Python 3.11/3.12 and Linux/macOS/Windows verification jobs even when
GitHub API authentication cannot create a PR. No job population/gate is weakened.
Until that successor exact-head CI completes, these results prove Linux local
performance and protection retention, not cross-platform correctness.

## Measured bottleneck and change

A cProfile baseline of three complete `LocaleCatalog` constructions plus one
function-record load at `b45f1fdc64f42335e140bf6337296cc28b43ee91` made
26,693,350 calls in 7.733 instrumented seconds. It performed 37 complete
canonical-resource scans. Relationship projection accounted for 5.914 seconds;
deep-copy isolation accounted for 6.099 overlapping cumulative seconds. Safe
YAML parsing already has a content-keyed cache: adding another global parse
cache would not address the main problem.

`20f902a70e4221785a21f8829b060e87280b07a0` instead reads one validated
relationship snapshot per catalog construction and projects the six approved
relationships from it. Standalone relationship operations still read fresh
resources; no cross-operation/global mutable cache or invalidation heuristic
was introduced. Missing owners/approved targets still fail. Each returned
projection is independently mutable. Manifest/source checks remain in the
existing canonical reader. No tests, markers, coverage rules or OS jobs were
removed or weakened.

## Bounded public-data benchmark

Linux 7.2.6 x86_64/glibc 2.39, Python 3.12.3, one process, existing environment,
five sequential catalog constructions in each fresh process. Each includes all
locale functions/entries, with no audio engine or private asset. Other machine
activity included the independent baseline repository-validation service;
these are exploratory measurements, not isolated CI or full-suite benchmarks.

| Metric | Baseline b45f1fd | Optimized 20f902a |
| --- | ---: | ---: |
| First construction, seconds | 0.901766 | 0.436545 |
| Median wall seconds (five constructions) | 0.598542 | 0.138479 |
| Canonical resource scans per construction | 12 | 1 |

The measured median reduction is **76.86%** for this specific operation.
Both outputs have the same complete catalog semantic fingerprint:
`abf3ab60c8068cb5ae75d5d3b74651be0f607a016a96397ba1b52ccd26edf095`.
This does not prove rendered PCM equality or a 76.86% full-suite improvement.

Reproduce from an installed development environment with
`PYTHONPATH=scripts python scripts/tools/benchmark_catalog.py --iterations 5`.
To compare revisions, invoke the same harness with `PYTHONPATH` selecting each
clean worktree's scripts. Reports include actual source SHA, dirty flag,
platform/Python, per-run wall/CPU time and semantic fingerprints. The first
iteration includes initial parsing; subsequent iterations exercise existing
immutable parsing reuse. Output hashing is outside the timed construction.

## Verification and workflows

Focused relationship, guide, catalog, live-authority and locale tests: **67
passed** in 85.03 seconds on Linux/Python 3.12.3. Additional harness and mutation
regressions are part of the branch. Focused checks are not full coverage.

FAST, no coverage instrumentation:

```bash
make test-fast
make test-fast PYTEST_ARGS="-m unit"
make test-fast PYTEST_ARGS="-m integration"
```

The default FAST command runs the entire applicable suite with two isolated
workers and file distribution; tier commands explicitly select a population.
None reports full coverage. Two workers retain the existing bounded default;
this is not a claim that worker tuning is complete.

FULL, mandatory instrumented suite:

```bash
make test-full
make check
make lint
```

`test-full` invokes the unchanged coverage runner: all tests, subprocess
instrumentation, separate statement/branch floors, taxonomy and deselection
checks, complete run fingerprint and retained failure diagnostics. The floors
remain 89.5% statements / 84.0% branches. The last reviewed 89.7314% / 84.5798%
and 2,874 passed / 5 skipped are historical reference values, not measurements
of this optimization. Full Python 3.11/3.12 Linux/macOS/Windows CI remains
mandatory. Neither a local profile nor this report is permission to merge.

## Remaining measurements and limitations

The independent owners reached verified terminal completion for both compared
sources, including slowest-50 reporting, JUnit timing, coverage and the identity
comparison. Their durable receipts were collected rather than inferred from live
PIDs. Successor exact-head cross-platform CI and CI critical-path speedups are
still pending and must not be inferred from the local reduction.

Still measure setup/install; finer fixture initialization and audio generation;
subprocess startup; schema/index scans;
temporary I/O and cleanup; collection/import; coverage startup, combining and
reporting; bounded xdist scheduling/scaling; CPU/RAM/disk utilization; and
retained cross-platform CI critical-path timings. Compare the same meaningful
test population, explicitly accounting for added regression tests. Keep real
integration/failure-path checks, mutation isolation and all coverage obligations.
The >=30% local overall wall-time target was exceeded in this measured pair;
repeated full-suite reproducibility and CI reductions remain to be established.
