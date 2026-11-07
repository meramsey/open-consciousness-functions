# PR 27 Windows job-state sharing correction

## Observed failure

Exact-head CI at `acee15081044e0d5ad87b4752a8cfc639cd56613` failed
`test_running_job_cancellation_and_concurrent_duplicate_prevention` on Windows
Python 3.12.10. The annotation reports `PermissionError: [Errno 13] Permission
denied` from `io.open(state.json)`, not a native `[WinError ...]` exception.
Evidence: [workflow 42350872866](https://github.com/meramsey/open-consciousness-functions/actions/runs/42350872866).

The existing reader retried only exceptions carrying `winerror` 5, 32 or 33.
Windows CRT file opens can instead surface a sharing denial as `EACCES` without
that attribute, so this real failure bypassed the retry entirely. Extending the
test deadline or weakening cancellation assertions would not repair the reader.

## Correctness boundaries

- Retain eight attempts and seven bounded backoffs totaling 0.81 seconds.
- Also classify `EACCES` without `winerror` on Windows only. That representation
  cannot distinguish sharing from an ACL denial, so a persistent denial exhausts
  the bound and raises the original exception. There is no fabricated state or
  success fallback. Unclassified/non-Windows denials fail immediately.
- Use the same state reader in worker cleanup and managed execution, not only
  status polling. Atomic publication still writes complete fsynced bytes before
  replacement; exclusive publication and writer retry rules are unchanged.
- Fail closed when the scheduler cannot read an existing record due to a
  permission error. It must not interpret that as an incomplete publication and
  dispatch a second possible owner. Missing historical publications retain their
  existing handling and regression tests.
- Heartbeat shutdown/join, process-tree cancellation, terminal-state reporting,
  scheduler/executor leases and duplicate-work assertions are unchanged.

## Verification

Focused new error-classification/bounded-retry/fail-closed regressions plus the
existing real job lifecycle, cancellation, duplicate prevention and process-tree
tests: **26 passed on Linux/Python 3.12.3**. Ruff check/format passed. No test was
skipped, deleted or reclassified for this correction. Native Windows and every
required exact-head CI gate still have to pass on the successor commit before
the defect is considered resolved. Prior coverage or this Linux result alone
does not establish the successor's Windows correctness or coverage.

No function definitions, narration, audio locks, approved historical provenance
or audio editions are modified. Required human PR review and merge authorization
remain separate from technical verification.
