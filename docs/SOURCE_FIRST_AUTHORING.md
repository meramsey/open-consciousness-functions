# Source-first working authoring

Status: shipped local `ocf content` workflow. Existing function-content sidecars,
semantic stage schemas and runtime narration interfaces remain unchanged. New
`editorial-function.schema.json` and `editorial-block.schema.json` validate the
local editorial representation, not public runtime resources.

## Workflow

**SOURCE immutable → WORKING starts exact → HUMAN edits → RELEASE explicit →
measured timing.**

1. **SOURCE:** Use available local sources only, without external downloads.
   Preserve exact bytes and SHA-256 identity. Record ranged extents for every
   selected chunk so its text can be traced to the original source. Do not
   normalize, correct, paraphrase or overwrite the source. Record unknown source
   availability and authentication explicitly; a reconstruction is not source.
2. **WORKING:** Initialize each block with the exact selected source text. Keep
   source and working text distinct and diffable. Existing analytical locators
   seed **CANDIDATE** semantic boundaries; they do not validate original section
   order or permit rewriting. Human review must resolve uncertain boundaries.
3. **HUMAN:** Editors decide what to retain, correct or change. Mandatory
   paraphrasing, distancing and automatic originality checks are not working
   gates. Record transcript corrections, uncertainty, claims/accessibility flags
   and material design changes as separate metadata. Never automatically rewrite
   source or working text to resolve claims. Preserve provenance after edits.
4. **RELEASE:** Approve explicitly against the current block text hash. Review
   alone is not release approval. Human release review applies the claims,
   accessibility and autonomy contract in [narration standard](NARRATION_STANDARD.md).
   Record rights clearance and its evidence; rights gate release/package inclusion,
   not working edits. Tools record attestations, not legal conclusions.
5. **Measured timing:** Only after approved release selection, use the existing
   narration/session toolchain and measure actual speech and localized timing.
   An untimed textual preview is neither final audio nor timing evidence. Keep
   narration, semantics, DSP, cues, TTS and metadata separate.

## Local workspace and shared blocks

The default workspace is `.ocf-authoring/`, ignored by Git and excluded from
wheel and source-distribution data. Explicit `--workspace DIR` selects a local workspace;
source availability must not introduce hidden runtime dependencies.

Shared source/working registry chunks allow reuse without copying blocks into
every function. A reference must retain originating source SHA-256 and ranged
locators, not substitute the consuming function's locators. Reuse does not imply
approval, source authentication or validated section order. Every referenced
block must pass the release gate. Keep registry source/working chunks out of
packages; release artifacts are selected separately.

Keep `previous_candidates` paths intact for human comparison. Never choose or
promote them automatically at runtime, or overwrite existing candidate files
when creating the source-first workspace.

## Review and release status

Reviewer status is one of:

| Status | Meaning |
| --- | --- |
| `inherited` | Initial source text carried into WORKING, not human-reviewed |
| `needs_review` | Human review remains required |
| `reviewed_unchanged` | Human reviewed the text and retained it unchanged |
| `reviewed_modified` | Human reviewed the edited working text |
| `transcript_uncertain` | Transcript wording or extent remains uncertain |
| `blocked` | Unresolved issue prevents progression |

Release status is separately `pending` or `approved`. Approval records the
reviewer, approval text hash, rights status and nonempty rights evidence. Allowed
rights statuses are `verified_redistributable` and `user_cleared`; neither is a
tool-generated legal determination. Source presence, analytical completion,
unchanged text and a reviewed status do not independently approve release.

Any text change makes its prior approval stale: the current text hash must match
the approval hash. Unreviewed, uncertain, blocked, pending, stale or uncleared
blocks cannot enter release preview or packages. A release containing shared
references must satisfy these requirements for all referenced blocks as well.
Do not relabel retained source wording as OCF-original.

## Commands

```text
ocf content skeletonize --source-root DIR --workspace DIR [--function ID]
ocf content diff ID --workspace DIR [--json]
ocf content diff ID --workspace DIR --filter function-specific
ocf content dashboard --workspace DIR [--json] [--filter changed|unreviewed|uncertain|function-specific|reusable]
ocf content review ID --block BLOCK --status STATUS --reviewer NAME --workspace DIR
ocf content approve ID --block BLOCK --reviewer NAME --rights verified_redistributable|user_cleared --rights-evidence STRING --workspace DIR
ocf content preview ID --workspace DIR [--output FILE] [--release] [--json]
ocf content variants --workspace DIR --output DIR/variants.json --json
ocf content insert ID --block b900 --before b003 --semantic function.command.rehearsal --text-file new-text.txt --reviewer NAME
```

- `skeletonize` creates source-first working blocks from available local sources
  and candidate analytical locators, optionally for one function. It preserves
  exact text and provenance; it does not generate replacement narration.
- `diff` compares WORKING against SOURCE for the selected function, including
  referenced shared blocks and their originating locators.
- `dashboard` reports working changes, review uncertainty, function-specific and
  reusable blocks. Its filters are review views, not approval or runtime selection.
- `review` records one of the reviewer statuses above and the named reviewer;
  it does not approve release or rewrite text.
- `approve` records explicit release approval for the current block text hash
  with the named reviewer and allowed rights status/evidence. It must enforce
  human review readiness rather than bypass unresolved review flags.
- `preview` defaults to **untimed textual draft review**, including pending or
  flagged working text with its review context. `--release` permits only fully
  approved current text with allowed rights, including every shared reference.
   Neither mode renders final audio or assigns measured timing.

## Edit one block

Run `ocf content diff OCF-FND-002 --filter function-specific --json`. Each row
supplies `working_file`, a path relative to `.ocf-authoring/blocks/`'s parent.
Open that YAML file and edit only `working.text`. Do not edit `source`, semantic
identity, function/source ranges, or generated timestamps. A shared file affects
every listed occurrence: inspect `content variants` before editing reusable text.
Shared source paragraphs occur once, with per-function provenance in the skeleton.

Keep `working.corrections` separate from wording edits. A correction has
`original`, `proposed`, `status` (`pending`, `applied`, `rejected`) and `reason`.
Adding a proposal never changes text. A human can apply it to `working.text` and
mark it applied. Unified diffs show all actual edits even when correction metadata
is present. A removed block keeps its source/range but has empty working text.
`content insert` creates a human-only block with no invented source range.

For a reusable substitution, set `working.template_ref` to another block's
registry hash. Its semantic identity must match; the consuming source and locator
remain intact. The substitution and every referenced block require release review.
Cycles and semantic changes fail rather than rewriting a function.

Mark `reviewed_unchanged` to deliberately retain exact wording, or
`reviewed_modified` after intentional changes. The named human reviewer is
acknowledging the attached claims/accessibility/boundary flags; there is no automatic
claims correction. Review and approval history is recorded with text hashes. Manual
edits remain visible against SOURCE and invalidate prior review/release hashes.

Only `content preview ID --release --output FILE` selects fully reviewed,
rights-cleared expression for the existing rendering tools. Output is a separate
view with speech-end dependencies; the editable blocks remain untimed. No state
directive or DSP program is inferred from source wording. Bind actual reusable
stages/state transitions in a reviewed session separately. Use voice/renderings,
measure durations, export SRT/LRC with the measured manifest, then render DSP. The
working preview permits local review, but does not approve or package the text.

`content dashboard --output DIR/dashboard.json --json` creates a bulk review
index. `content variants` reports exact-text groups and diffs against the first
group in each candidate semantic family. The 0.9 similarity label is only an
informational minor/material **candidate**, never an originality gate, authenticity
test, automatic selection, or determination of semantic equivalence. The human
must inspect the actual diff and source context. Variant output stays local.

## Preserved boundaries

Preserve all 55 historical mappings and all 16 source-unavailable records with
`reimplementation_status: planned`. Do not fabricate text for unavailable sources.
Canonical commands and provenance remain authoritative. Keep Attention scripts,
existing candidates, RC1 narration, frozen pilot editorial decisions and V2/V2.1
DSP/auditions unchanged. In particular, do not alter the V2.1 induction curve or
level before the listening comparison. This workflow does not reopen those
decisions or validate historical mechanisms.

See [function content](FUNCTION_CONTENT.md) for existing analytical layers and
[source attribution](SOURCE_ATTRIBUTION.md) for provenance and distribution rules.
