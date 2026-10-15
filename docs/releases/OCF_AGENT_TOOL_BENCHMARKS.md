# Agent-tool measurements and verification scope

Measured locally on Linux/Python 3.12 using
`python scripts/tools/benchmark_agent_tools.py`. Raw results are retained in
`.ocf-work/logs/agent-tool-benchmark.json`. The proxy is UTF-8 bytes plus
characters divided by four; no tokenizer or provider usage data was available.
These are not billed-token savings and not an exhaustive agent productivity study.

Response sizes and single-run elapsed times:

- Function lookup: rich CLI 15,972 bytes / 0.311 s; compact 956 bytes / 0.148 s.
- Session inspection: expanded CLI 142,975 bytes / 0.842 s; compact 786 bytes /
  0.608 s. Summary intentionally omits full narration and expanded timing data.
- Audio preflight: full CLI 140,691 bytes / 0.754 s; compact 600 bytes / 0.596 s.
- Single-function validation: CLI 43 bytes / 0.218 s; structured 183 bytes /
  0.709 s. The structured adapter also checks complete narration dependencies,
  so scope is broader; this operation did not reduce response bytes or time.
- Focused pytest: verbose CLI 469 bytes / 0.312 s; job result 636 bytes /
  0.001 s to retrieve. Explicit start returned in 0.065 s; completion took
  0.667 s with three polling calls. Jobs improve nonblocking behavior, not the
  execution time of this tiny test selection. Result: 11 passed, 0 skipped.
- Job polling: raw state 493 bytes / 0.00038 s; compact 412 bytes / 0.00035 s.

Function lookup, validation, session inspection and audio preview each used one
call per variant. Focused tests used one baseline call versus start, three polls
and result retrieval. This benchmark does not claim fewer calls for async jobs.
Two audio previews performed zero synthesis operations; their hypothetical full
renders were deliberately not started, not measured as billing savings.

Parser-cache microbenchmark: one cold small YAML parse 0.000231 s; 100 warm
deep-copy returns 0.001045 s total, 100 hits and 1 miss. This is process-local
exact-content caching, bounded to 128 small entries. Files are still read;
same-size rewrites, schema-reference edits, mutation isolation and safe-loader
fallback are covered by tests. No cached validation success replaces a final gate.

## Documentation audit scope

The generated inventory covers tracked Markdown, schema descriptions, CLI help
and wizard source. It records headings/purpose, audience, canonical references,
commands, schemas, maintenance type, hashes, broken links, exact duplicates,
historical status and correction guidance. It explicitly leaves semantic review
unverified where no review was performed. Historical release/research/draft pages
remain historical instead of being rewritten to claim current functionality.

Current entry points were reorganized: root README, AGENTS, contributing,
documentation navigation, user/agent guides, audio layout, bulk workflows and
MCP setup. Scoped `--help` no longer appends the entire global command reference.
Known stale paths and unavailable wizard-module references were corrected.

Client configuration shapes were checked against the official SDK/OpenCode,
Claude Code and Codex sources cited in `docs/MCP.md`; this does not claim native
client UI testing. Official SDK stdio initialize/tool/resource/prompt integration
is exercised locally and in the optional-dependency CI matrix.
