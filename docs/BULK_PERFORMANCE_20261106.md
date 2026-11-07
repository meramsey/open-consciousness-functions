# Bulk performance investigation — 2026-11-06

Status: **partial; public planning optimization only, not a render benchmark**.

No private recording, voice model or listening edition was rendered, changed or
published. No default lock, narration, voice selection, crossfade or mix setting
was edited. This investigation is a separate branch stacked on the shared test
performance change, not part of PR 27's authoring cleanup.

## Profile-backed changes

The first complete-session source-plan profile at `b45f1fd` took 32.690 seconds
under cProfile (109,659,747 calls). Twelve catalog constructions and 153 canonical
resource scans dominated the workload: 27.939 overlapping cumulative seconds
were in catalog construction. Repeated approved-relationship discovery was the
largest avoidable cost. Existing content-keyed YAML parsing already caches
immutable parsing; deep-copy isolation, not initial parsing, dominated reuse.

The shared relationship snapshot change `20f902a` reduced the same profiled call
to 10.424 seconds and 21 canonical scans, without a global mutable cache. This
branch's additional `58248c5dac6fd5f6b3a012085f28572e695716f5` reuses the
existing completeness catalog for document resolution and final reviewed-entry
validation instead of constructing two more catalogs in the same preflight.
Revision overlays still resolve through `with_revision`; strict localized speech,
completeness, status, schema, command ownership and timing checks remain.

No synthesis, DSP, mixing, cache/resume identity or publication code was changed.
The remaining broad rendering optimizations must be supported by separate real
stage profiles; planning improvement alone does not prove faster audio rendering.

## Reproducible bounded public workload

Linux 7.2.6 x86_64/glibc 2.39, Python 3.12.3, one worker, existing environment.
Baseline `46713616450bbf4a6b1e2c5cd7de8e36c254047d` and optimized `58248c5`
were clean during three sequential complete source-plan builds for public
`OCF-FND-002`, using the same benchmark harness. A separate repository-validation
service was active, so these are exploratory same-machine measurements, not
isolated CI timings. Initial process/OS caches are not controlled TTS/audio caches.

| Planning metric | Baseline | Optimized |
| --- | ---: | ---: |
| First plan wall seconds | 9.835285 | 3.557357 |
| Next plan wall seconds | 10.799628 | 3.080720 |
| Third plan wall seconds | 10.228445 | 3.191299 |
| Median plan wall seconds | 10.228445 | 3.191299 |
| Median-derived planned sessions/hour | 351.96 | 1128.07 |

The measured median reduction is **68.80% for this single-function planning
workload**, not for a rendered session or multi-function batch. CPU seconds
closely tracked wall time. An additional single-plan `/usr/bin/time -v` sample
measured baseline 10.08s wall / 9.80s user / 0.28s system / 67,376 KiB peak RSS;
optimized 3.69s wall / 3.54s user / 0.14s system / 71,468 KiB peak RSS. Both used
approximately one CPU core. The latter optimized resource sample was at clean
merge `7f818a1`, with unchanged runtime code from `58248c5`. Peak memory was
slightly higher, not lower. No GPU/VRAM, rendering disk throughput or audio cache
effectiveness was measured. Process startup/bytecode can affect these I/O samples.

Every measured full plan/shared/expanded declaration had SHA-256
`4ae638609dec2e47938c5989017a5ffe3a2d4003fe63373dd50e626dc225993d`.
This covers the complete public planning output, including narration resolution,
Focus transitions, timing, source declarations and independent approval statuses.
It is **not** a rendered PCM or encoded-audio equivalence result.

```bash
PYTHONPATH=scripts python scripts/tools/benchmark_session_planning.py --iterations 3
PYTHONPATH=scripts python scripts/tools/benchmark_session_planning.py --all --iterations 1
```

The optional `session-planning-benchmark` workflow runs only by manual dispatch,
records wall/CPU/peak RSS and retains public hash-only planning reports. It never
synthesizes or renders private audio and is not an ordinary PR performance gate.
All 58 identities are selectable; a completed all-58 benchmark is not claimed here.

## Tests and remaining acceptance

Focused planning/override/revision/harness tests: **46 passed** in 53.65 seconds
on Linux/Python 3.12.3. This includes real canonical planning, revision/custom
affirmation boundaries and an exact baseline hash plus one-catalog-construction
regression. Existing full integration and cross-platform checks remain required.

Still required: equivalent full-58 planning measurements; single cold/warm audio
renders; multi-function cold/warm batches; partial resume; cache hits/misses and
duplicate synthesis; transient failure/recovery; bounded worker scaling; stage
timings for TTS, model/conditioning reuse, DSP/Farfield, mixing, PCM buffering,
encoding, hashing/validation, manifests and packaging; CPU/GPU/RAM/VRAM/disk
measurements; actual sessions/hour and failed/retried jobs; deterministic
byte-exact audio output or justified PCM/sample tolerances where nondeterministic.

Retain independent supervision, integrity, collision protection, source/job
fingerprints, checkpoints/resume and atomic publication. No immutable editions
may be rerendered just to obtain a benchmark. Full validation/coverage and exact
head Linux/macOS/Windows results are not yet established for this branch.
