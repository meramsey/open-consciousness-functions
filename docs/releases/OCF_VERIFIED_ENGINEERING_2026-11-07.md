# Verified engineering handoff — 2026-11-07

This documentation-only receipt preserves the tested engineering heads rather
than modifying them merely to report their completed CI results. It is not a
human review, listening approval, publication permission or merge authorization.
No protected branch was merged.

## Exact-head CI and complete coverage

All required checks completed successfully: 23 on PR 27, 22 each on the two
performance topic pushes (dependency review is PR-only). Python 3.11/3.12 unit
and Linux/macOS/Windows integration jobs pass. Complete instrumented Linux
results use Python 3.12.16, two workers, zero failures/errors, five skips and zero
excluded statements at every head below.

| Workstream / head | Full passed | Statements | Branches |
| --- | ---: | ---: | ---: |
| PR 27 `e65634eadb3567566568931ae00f293f2300812f` | 2911 | 89.750262% | 84.581362% |
| Tests `f9408ec2d3393dec7ea3e1c6e67cbc34f624a622` | 2920 | 89.793866% | 84.617756% |
| Bulk `c1093b752ee14e17a380b0b17869d7d0089ea5d2` | 2970 | 89.981316% | 84.698672% |

The PR coverage checkout was merge commit
`124d9c730469ea9e30d3d780c94e7f4485c42183`; its Git tree was verified identical
to requested head `e65634e`. The topic push checkouts match their head SHAs.
The separate statement/branch floors remain 89.5% / 84.0%, and full-suite
deselection/taxonomy guards pass. Actual compact artifacts were read using a
read-only repository-managed credential; no audio was extracted or published.

- [PR 27 test/coverage run](https://github.com/meramsey/open-consciousness-functions/actions/runs/42370863148)
- [Test-performance native run](https://github.com/meramsey/open-consciousness-functions/actions/runs/42371518857)
- [Bulk-performance native run](https://github.com/meramsey/open-consciousness-functions/actions/runs/42379605309)
- [Numeric artifact verification](https://github.com/meramsey/open-consciousness-functions/actions/runs/42383823720)
- [Updated human review packet](https://github.com/meramsey/open-consciousness-functions/pull/27#issuecomment-6707957655)

## Windows correction and source preservation

The CRT `EACCES` representation without `winerror` now receives bounded Windows
state-read retries. Permanent failures propagate; an unreadable existing job
fails closed instead of allowing duplicate dispatch. Worker cleanup uses the
same reader. Cancellation/process-tree assertions and atomic publication remain.
The reported Windows integration failure is resolved on the exact PR head.

The canonical audit retains 58 en-US definitions, 177 protected narration entries,
all 15 immutable audio locks and 825 historical dependency keys. No private
editions, voice models or reference recordings were rerendered or published.
The old importer/editorial/source-layer routes remain retired or non-authoritative.

## Measured full-suite and hosted CI improvement

The controlled local full-suite pair at `c8ea153` / `9690b68` retained all 2905
baseline identities and added eight: 2900 -> 2908 passed, five skips in both.
Full pytest fell **2726.60s -> 1135.98s (58.34%)**; complete coverage including
reporting fell **6956.585s -> 2805.481s (59.67%)**, with both coverage percentages
increased. No meaningful tests or checks were removed. See the
[full test report](../TEST_PERFORMANCE_20261106.md).

Observed hosted CI check spans at the corrected `e65634e` and `f9408ec` heads
were **6233s -> 2560s (58.93%)**; their coverage jobs were **6232s -> 2559s**.
These involve separate hosted runners/queue/install conditions, not a controlled
same-machine benchmark. The local pair remains the controlled comparison.

## Actual public audio, planning and packaging probes

Three four-session, 20-second paired audio batches show **51.27% / 56.16% cold**
and **56.78% / 59.21% warm** median reductions at one/two workers. All WAV, FLAC
and fixture ZIP hashes match; decoded lossless PCM also matches. Cache requests,
rendered/reused populations and failure/recovery checks remain equivalent.
All 58 complete planning outputs match: **496.253880s -> 161.458224s (67.46%)**.
See the [bulk report](../BULK_PERFORMANCE_20261106.md) and its linked raw summary.

The additional three paired single-session runs at `83094a3` / `c1093b7` show
median cold **2.432800s -> 1.405168s (42.24%)** and warm
**1.828772s -> 0.804520s (56.01%)**, also byte-exact. These use the same public
20-second fixture and actual CPU TTS/mix/encoding APIs, not private sessions.

Real 40-second Farfield cache characterization completed at `b4567be`:
**105.783385s cold / 8.575504s warm**, identical output hash. That measures the
existing cache, not a new Farfield-engine optimization. The identical existing
release integration module passed **31 tests in each source**, with real codec,
artwork readback, manifest and publication/failure checks, **38.33s -> 20.38s**.
Its upstream render is a frozen public-tone fixture; this is a packaging-stage
integration probe, not complete production release throughput.

Full-length private/GPU/session-generation throughput and production release
approval are not inferred from these bounded public measurements. No private
voice/model benchmark or successor audio-default lock was created.

## Roadmap and remaining administrative block

All 102 original checkbox states and five additions remain preserved. The
verified `9172168` roadmap bytes are unchanged at synchronized head
`8e8ff2d5aafe3c925b595d357dec38121fcb2979`; no feature was silently marked shipped.

Separate draft PR creation was attempted once using scoped managed credentials.
Repository policy explicitly denied it: **GitHub Actions is not permitted to
create or approve pull requests**. The policy was not changed and automatic
retries were disabled. The published documentation branch remains available;
required human PR review and owner merge authorization remain outstanding.
