# Bulk session test-performance measurements

Linux, Python 3.12.3, pytest 9.1.1. Baseline commit
`db74a9d1b5b85df496987b8d660b3ff5ec1bdd6f`; measurements after bulk rendering
include twelve additional tests, including full 55-function plan validation.

- Baseline serial: 1253 passed, 2 skipped; 552.86 s pytest / 553.32 s wall.
- Optimized serial: 1265 passed, 2 skipped; 285.98 s pytest / 286.36 s wall.
- Parallel: 1265 passed, 2 skipped; 174.82 s pytest / 175.06 s wall.
- Observed speedup: serial 1.93x versus baseline; parallel 3.16x versus baseline
  and 1.64x versus optimized serial. These are local whole-suite observations,
  not promises about CI or individual tests.
- GNU time maximum RSS: baseline 1,224,140 KiB, optimized serial 1,226,144 KiB,
  parallel 1,206,644 KiB. This is not summed concurrent-worker peak memory.
- Host: 16 logical CPUs, approximately 38 GiB available memory at parallel-run
  start. Chosen worker count: **2**, never automatic. Full sessions remain
  serial because their memory footprint differs from synthetic tests.

The implementation chooses PyYAML's C **safe** loader when available, with the
Python SafeLoader fallback. It does not switch dumpers, skip schema checks,
reuse mutable parsed catalogs, cache stale validation results, or reclassify
integration tests. Parity, Unicode, alias, mutation-isolation and unsafe-tag
rejection tests protect the loader change. No additional data cache was needed
to obtain the measured improvement.

`pytest-xdist==3.8.0` is a pinned development dependency. `pytest -n 2 --dist
loadfile` preserves file-local test grouping and uses process isolation.
Each run/worker has private pytest scratch and OCF workspace beneath
`.ocf-work/tmp/`. `pytest` remains the comprehensive serial command;
`make test-parallel` runs the same full suite with two workers. Existing unit,
integration, audio_integration, external_tool, e2e and platform markers remain;
the slow marker never excludes tests from the full gate.

No flaky failure was observed in these serial/parallel runs; two observations
do not establish a statistical flake rate. Raw durations and GNU time reports
are retained locally in `.ocf-work/logs/bulk-{baseline-pytest,optimized-serial,
optimized-parallel}.log`. CI now exercises repository integration on all three
OSes in addition to the Python 3.11/3.12 unit matrix.
