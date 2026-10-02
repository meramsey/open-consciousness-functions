# Pre-existing technical debt

## TD-001 — inherited repository-wide lint findings

Status: resolved in Phase2B (annotation import, redundant checksum removal,
import ordering and final newlines; no rule suppressed). Baseline checkpoint
`4093063`. The Phase 8C audit compared rule,
file and message signatures against that checkpoint: **15 before, 15 after,
zero introduced findings**. User approval explicitly excludes this debt as a
blocker for **OCF Preparation Learning en-US RC1**.

Reproduce with `ruff check --no-cache --output-format concise scripts tests`.
Line numbers may move; the debt is identified by file/rule rather than line.

| File | Rule / issue | Count |
| --- | --- | ---: |
| `scripts/ocf_tools/audio_build.py` | F841: unused `master_check` | 1 |
| `scripts/ocf_tools/voice.py` | F821: undefined `ResolvedEvent` annotations | 5 |
| `scripts/ocf_tools/voice.py` | UP037: quoted forward annotations | 5 |
| `scripts/ocf_tools/sbagenx.py` | W292: missing final newline | 1 |
| `tests/test_audio_build.py` | I001: import ordering | 1 |
| `tests/test_audio_build.py` | W292: missing final newline | 1 |
| `tests/test_sbagenx_integration.py` | W292: missing final newline | 1 |

Resolve in a separate cleanup checkpoint with relevant tests. Do not rewrite
narration, alter DSP recipes, or skip checks to hide these findings.
