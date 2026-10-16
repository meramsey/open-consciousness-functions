# Modernization coverage checkpoint

## Final hardened measurement

The follow-up full Linux/Python 3.12.3 measurement passed **1,894 tests / two
optional skips** in **444.30 seconds**, with 1,245 unit and 651 integration cases.
There were zero deselections, taxonomy errors or excluded statements.

| Scope | Covered statements / total | Statements | Covered branches / total | Branches |
| --- | --- | --- | --- | --- |
| Combined | 15,539 / 17,382 | 89.3971% | 5,904 / 7,004 | 84.2947% |
| Unit contexts | 9,797 / 17,382 | 56.3629% | 4,326 / 7,004 | 61.7647% |
| Integration contexts | 9,393 / 17,382 | 54.0387% | 4,008 / 7,004 | 57.2244% |

Raw reports: `.ocf-work/logs/coverage/modernization-hardened/`. Successful managed
scratch was removed through the shared workspace helper; reports were retained.
Unit gaps remain **7,585 statements / 2,678 branches**. The measured floors below
still pass, and the 100% unit target remains unmet.

The harness now neutralizes inherited/configured pytest selection, rejects
unexpected deselection, anchors relative reporting paths to the repository root
and cleans only successful marked scratch (honoring `OCF_KEEP_WORK`). Focused
synthetic tests exercise these paths, including reporting from another working
directory. Windows CI also exposed native backslashes in example fingerprint
keys; the generator now serializes portable POSIX paths and normalized newlines.
No schema or validator was weakened to fix these failures.

## Earlier measured result

Linux/Python 3.12.3, coverage.py 7.16.2, pytest-cov 7.1.0, two `loadfile` workers:
**1,891 passed, two skipped**, 442.01 seconds with instrumentation. There were
1,242 isolated unit cases and 651 integration cases collected; no test had a
missing or ambiguous classification. The skipped tests require explicit opt-in
to full Piper Sleep Easy synthesis and complete Piper/Farfield session rendering.
They were not enabled or newly skipped for this modernization.

| Scope | Covered statements / total | Statements | Covered branches / total | Branches |
| --- | --- | --- | --- | --- |
| Combined | 15,516 / 17,368 | 89.3367% | 5,899 / 7,000 | 84.2714% |
| Unit contexts | 9,776 / 17,368 | 56.2874% | 4,321 / 7,000 | 61.7286% |
| Integration contexts | 9,393 / 17,368 | 54.0822% | 4,008 / 7,000 | 57.2571% |

Zero excluded statements; no source omission. Unit/integration are strict
per-test-context contributions, overlap and are not additive. Startup and
unattributed subprocess execution are combined-only. Hard-killed execution
cannot be assumed to flush coverage. No coverage.py combined score is relabelled
as statement coverage.

Against the [unchanged baseline](OCF_MODERNIZATION_BASELINE.md), the denominator
grew by 1,505 statements and 638 branches. Combined covered statements grew by
1,382 and covered branches by 568; both combined percentages increased.
Unit covered statements grew by 645 and branches by 332, but its percentages
decreased because the new adapter/service/tool code expanded the denominator.
The 100% unit target remains unmet: **7,592 statements / 2,679 branches** remain
uncovered by unit contexts. This checkpoint does not claim to have completed it.

## Shipped measurement and gates

`python -m ocf_tools.coverage_report run` explicitly runs the entire suite;
`check SUMMARY` checks retained output without repeating tests. Data, logs, JUnit,
collection taxonomy and all three JSON reports remain under the validated work
root. Existing report directories are never overwritten. The measurement harness
is test support, not another operational job queue.

The initial measured regression floors are separate **89% combined statements /
83% combined branches** and **56% unit-context statements / 61% unit-context
branches**. These are guards, not completion targets. CI runs an instrumented
Linux job with optional adapters, FFmpeg and espeak-ng, and uploads only report
JSON, JUnit and the pytest log. Native OS jobs remain independent. No private
audio/model/reference payload is an uploaded coverage artifact.

The first modernization measurement passed all 1,851 then-current cases but
detected one previously double-marked pure integrity-comparison test. Its
module-wide integration marker conflicted with its explicit unit marker. The
fix marks the actual repository integrity scan integration and leaves the pure
dictionary comparison unit. No workflow was reclassified to improve timing or
coverage. The subsequent full run above includes 40 additional meaningful
synthetic authoring and release boundary cases and has no taxonomy errors.

## Behavior protected by the new cases

- Contained unsaved configuration lookup, locale/command validation, typed
  completion/navigation, local-event migration refusal, schema pointers,
  alias complexity, index invalidation and bounded resource use.
- Release metadata identity/path restrictions, absent or ambiguous registered
  implementations, malformed JPEG markers, codec/probe errors, malformed probe
  JSON, tag mismatches, missing/extraction/hash-mismatched artwork and cleanup.
- A real defect found by non-square JPEG metadata testing: the SOF parser now
  returns width then height rather than interchanging them. Existing actual
  MP3/FLAC round-trip integration remains required.
- Coverage gate arithmetic distinguishes statements from branches, rejects
  exclusions and ambiguous classification, preserves failed output and verifies
  that startup execution is not falsely attributed to a unit test.

Raw successful local reports:
`.ocf-work/logs/coverage/modernization-verified/`. The earlier taxonomy-gate failure
is retained separately under `modernization-final/`; its pytest suite itself had
no failures. Measurements were made on the staged source tree before the coverage
checkpoint commit. Exact-final-commit GitHub Actions, rather than this historical
measurement, establish published commit verification. See
[current measurement instructions](../TEST_COVERAGE.md).
