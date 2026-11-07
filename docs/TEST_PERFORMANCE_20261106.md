# Test performance investigation — 2026-11-06

Status: **partial; microbenchmark improvement, not a full-suite speedup claim**.

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

## Required remaining measurements

The independent exact-SHA baseline service serializes validation, full pytest
with the slowest 50 tests/JUnit timing and the instrumented full suite. Its
terminal receipts must be checked, not inferred from a live service. Equivalent
optimized full-suite runs, statement/branch percentages, peak resources and
cross-platform CI are **not yet verified**. No total-suite/CI speedup is claimed.

Still measure standalone unit/integration wall time; setup/install; fixture
initialization and audio generation; subprocess startup; schema/index scans;
temporary I/O and cleanup; collection/import; coverage startup, combining and
reporting; bounded xdist scheduling/scaling; CPU/RAM/disk utilization; and
retained cross-platform CI critical-path timings. Compare the same meaningful
test population, explicitly accounting for added regression tests. Keep real
integration/failure-path checks, mutation isolation and all coverage obligations.
The >=30% overall reduction remains a target, not an achieved result.
