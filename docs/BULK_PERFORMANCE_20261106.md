# Bulk performance investigation — 2026-11-06

Status updated 2026-11-07: **real public audio-stage and all-58 planning
improvements verified locally; successor full/native CI pending**. All results
below come from terminal receipts, not dispatched/running jobs. They are bounded
public fixtures, not private full-length listening editions.

No private recording, voice model or listening edition was rendered, changed or
published. No default lock, approved narration, voice selection, crossfade or mix
setting was edited. This investigation is a separate branch stacked on the shared test
performance change, not part of PR 27's authoring cleanup.

## Completed real audio comparison

The same benchmark harness (`a28d13856ebcd8315fb781ed16d70f7e5b5a5ceac88be3f96351d01c1a0c9a51`)
ran against baseline `83094a3c6f781a87a315d1b6185f136c9df69e4c` and optimized
`fd4a7886c562324e84e330e8708d63c08375a152`. Three independent paired invocations
each rendered four 20-second public synthetic fixtures, at one and two bounded
workers. Each worker case had an isolated initially empty speech cache. Actual
eSpeak-NG, OCF narration/PCM mixing, FFmpeg stereo AM signal generation and FLAC
encoding/decoding ran; no synthesis or codec stage was mocked in measurements.
Fixture ZIP packaging is not the production release/rights/artwork workflow.

| Workers / phase, four fixtures | Baseline median | Optimized median | Reduction |
| --- | ---: | ---: | ---: |
| 1 / cold, including shared DSP generation | 7.917201s | 3.858027s | 51.27% |
| 1 / warm speech cache | 7.243179s | 3.130173s | 56.78% |
| 2 / cold, including shared DSP generation | 7.340281s | 3.217930s | 56.16% |
| 2 / warm speech cache | 6.909423s | 2.818263s | 59.21% |
| 1 / partial-batch recovery | 1.816940s | 0.768531s | 57.70% |
| 2 / partial-batch recovery | 1.775039s | 0.757423s | 57.33% |

Two-worker warm throughput was approximately 2084 -> 5110 **20-second synthetic
fixtures/hour**, not production full-length sessions/hour. One to two workers
provided only modest additional scaling: Python mixing remains partly GIL-bound
and external-tool/validation overhead remains. More workers are not assumed
optimal. Fully verified resume stayed roughly 6–10ms per four-artifact batch;
it verifies and reuses outputs, and is not counted as rendering throughput.

Protection/equivalence evidence:

- Cold requests: five synthesis misses and three hits per batch in both sources;
  the shared unit was generated once. Warm requests: eight hits, zero misses.
  No invalidated/bypassed entries. The optimization did not gain speed by
  synthesizing fewer unique units or weakening cache checks.
- An explicit pre-publication interruption failed one fixture; recovery rendered
  that one and verified/reused the other three. The complete-resume case verified
  all four without synthesis. Same rendered/reused populations before and after.
- Every compared speech WAV, mixed WAV, FLAC and fixture bundle hash matched
  across both sources and cold/warm/resume/recovery phases. FLAC was actually
  decoded and checked sample-for-sample against the WAV.
- Exhaustive unit comparison covers every signed PCM16 value, odd-byte decoder
  behavior, clipping/float/NaN/infinity return semantics, big-endian array
  handling, complete mono/stereo WAV bytes and negative downmix rounding.
  A timing-independent smoke guard requires one bulk conversion per buffer,
  preventing a silent return to the profiled per-sample byte I/O path.
- Only equivalent clipping comparisons and stdlib array decoding/packing changed;
  gain arithmetic, synthesis inputs, timing, sample rate selection, fades,
  crossfades, DSP profiles, encoding policy and atomic publication remain intact.

Linux/Python 3.12.3; the same public tool binaries were fingerprinted. In two
100ms-sampled repetitions, whole-harness baseline user+system CPU was about
75s versus 50s optimized. Sampled process-tree peak RSS was 185.8–195.8MB versus
134.5–134.7MB; owned fixture disk high-water was about 84.214MB in both.
Sampling can miss short-lived peaks. CPU percentage increased as the same
parallel external-tool work completed sooner; total CPU seconds decreased.
GPU/private voice models were not used. Raw per-phase timings, cache counts,
hash evidence, Linux I/O block counters and sampling limits are saved in the
[machine-readable terminal report](benchmarks/bulk-generation-20261107.json).

## Completed all-58 planning equivalence

Two complete batches per source: baseline `c8ea153` median **496.253880s**;
optimized `fd4a788` median **161.458224s** (**67.46% reduction**). All 58 complete
plan/shared/expanded output hashes matched, not merely IDs/counts. This planning
gain is separate from the measured audio-stage gain and is not added to it.

## Real public Farfield/cache characterization

The supported project environment exposes the installed Farfield launcher.
A separate 40-second seeded, tone-only Focus 10 -> 11 program completed at
`b4567bec0cd70861456bee4111b1b0d944665746`: **105.783385s** with two verified
stem-cache misses/stores, then **8.575504s** with two hits. Both output hashes:
`da848c3b6b088935ea29f8f7cbd35a02133fa1d2271c4938f5e24cb43940ed6e`.
This measures the existing DSP cache; it is **not** a new before/after speedup
claim for Farfield. Its cold generation and remaining warm overhead warrant
further profiling. No reference recording or private voice was used.

The old tone-only probe failed preflight because it inherited a spoken
`close.close` anchor without a closing event. Its fixture now deep-copies the
profile and removes that inapplicable anchor only in memory, alongside its
existing synthetic-stage overrides. Tests prove production profile fields and
anchors remain unchanged. Production validation was not relaxed.

## Benchmark failure diagnosis and reproduction

The initial bulk full suite stopped with 2912 passed / 5 skipped / 2 failures:
the optional planning workflow had an unquoted colon followed by a space in its pip command. Quoting
the YAML fixed both the security-workflow parser and structural-audit failures;
neither assertion was weakened. The first optimized audio probe also exposed
eSpeak-NG's silent empty-output behavior at WAV path lengths >=200 characters
(199 succeeded, 200/201/220 failed with exit zero). Both measurement sources now
use identical short, marked tool scratch under the canonical workspace, retaining
separate artifact trees. The failed receipts remain preserved and are excluded
from performance statistics. No backend/voice switch or input rewrite hid the
failure. Long custom production eSpeak workspaces remain a separate limitation.

```bash
workspace_root=$(PYTHONPATH=scripts python -c 'from ocf_tools.paths import work_root; print(work_root())')
PYTHONPATH=scripts python scripts/tools/benchmark_synthetic_audio.py \
  --output "$workspace_root/benchmarks/public-audio" --sessions 4 --seconds 20 --workers 1 2
PYTHONPATH=scripts python scripts/tools/benchmark_synthetic_audio.py \
  --output "$workspace_root/benchmarks/public-profile" --sessions 1 --seconds 6 --workers 1 --profile
```

New reports count only newly rendered fixtures in `sessions_per_hour`. Use phase
wall time to compare verified resume, and compare historical throughput only
where every requested fixture completed a fresh render. Resume receipts bind the
input bed hash as well as the rendered artifact hashes.

Profiling requires one worker so it actually instruments worker CPU; profiled
times are not mixed into the normal timing pairs. The optional
`synthetic-audio-benchmark` workflow is manual-only, installs public CPU tools and
uploads hash/timing reports only, never voice assets or generated audio. All
ordinary mandatory integration and coverage gates remain.

## Earlier planning profile and single-function measurements

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

That initial change affected planning only. Subsequent real-audio profiling at
`903b06d` measured 8.893 profiled seconds, with 4.715 cumulative seconds in PCM
mixing, 1.727 in its WAV writer, 0.851 in narration WAV writing and 0.780 in PCM
unpacking. These overlapping costs motivated the later byte-equivalent PCM
changes measured above; no synthesis/DSP/cache identity or publication policy
was changed to obtain the reduction.

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
All 58 identities are selectable; their completed comparison is recorded in the
separate all-58 section above rather than inferred from this single-function table.

## Tests and remaining acceptance

Earlier focused planning/override/revision/harness tests: **46 passed**.
New PCM/audio-build/voice/harness selection: **170 passed**; subsequent focused
harness/PCM/DSP fixture checks also pass. These are focused results, not a claim
that a successor full suite or coverage run has completed. Existing full
integration and exact-head cross-platform checks remain required.

Still required before a broad production throughput claim: full-length function
session/multi-function end-to-end measurements, production release packaging
(without inventing eligibility/rights/artwork approval), optional GPU/model-load
and conditioning profiles where authorized public models are appropriate, further
Farfield/fingerprinting profiling, broader worker scaling/resource-limit tuning,
and successor full-suite coverage/native CI. The published fixture rates must
not be extrapolated into private production-session rates.

Retain independent supervision, integrity, collision protection, source/job
fingerprints, checkpoints/resume and atomic publication. No immutable editions
may be rerendered just to obtain a benchmark. Full validation/coverage and exact
head Linux/macOS/Windows results are not yet established for this branch.
