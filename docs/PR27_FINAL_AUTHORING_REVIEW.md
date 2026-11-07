# PR 27 final authoring boundary review

This follow-up starts from `0a408a56cdc8fbf6af219879d0b021def995d308`.
It is not owner approval or a claim that later CI has passed.

## Repaired boundaries

- Offline source/proposal preparation reads identity and embedded analytical
  provenance from canonical locale records. It no longer reads editorial
  workspace records, installs narration sidecars, modifies locale manifests,
  upgrades placeholders or writes a public report containing selected source.
- Explicit local JSON proposals have no runtime resource envelope, retain
  source hash/identity checks, remain pending human review, and refuse changed
  inputs or human edits at an existing destination. No rights attestation is
  manufactured by preparing a proposal.
- Exact-text editorial workspaces remain isolated SOURCE/WORKING/RELEASE drafts,
  not alternate definitions. Their separate schemas cannot validate as locale
  function resources. All packaged resource roots and audio directories reject
  draft output, including resolved symlinks and per-file destinations.
- Editorial skeletons use embedded canonical evidence/specifications only.
  The synthetic-only predecessor-layer reader is removed, and synthetic tests
  supply the same canonical-shaped records as application callers.
- The research extraction driver also emits nested, non-authoritative local JSON
  proposals, never installable per-function layer YAML. It preserves all-input
  preflight, create-once publication and customized-data protection. Research
  roots and reusable private prompts reject editorial writes as well.
- Negative filename/directory inventories are replaced with a tracked-tree
  structural audit. Two pinned dummy schema/projection examples are explicit
  non-runtime exceptions; real canonical identities cannot use that exception.
  Generated guide paths are not function sources. Immutable dependency hash
  keys remain provenance, not executable source locations.

## Verification and owner review

Run `PYTHONPATH=scripts python scripts/tools/audit_function_authority.py` for
the full Git-tracked YAML/JSON inventory. New regression tests cover private
draft isolation, runtime/source containment, symlink promotion, create-once
publication, edited-proposal preservation, source/proposal hashes, unavailable
source status and all-input preflight before writing a batch.

Focused boundary/importer/editorial/catalog tests passed locally on Linux with
Python 3.12.3 (141 tests); additional workflow/tool contracts passed (49 tests,
overlapping the first selection). `make lint` passed; optional markdownlint was
not installed. These are focused checks, not a full-suite or coverage result.
The exhaustive follow-up also passed 144 editorial/importer/authority tests and
9 selected extraction-driver tests (12 other content tests deliberately not in
that focused selection). A broader foreground content-test attempt exceeded its
timeout and is not a full-module pass. All 381 tracked YAML/JSON files passed the
structural audit; remaining explicit historical path keys in source tests verify
immutable audio provenance only. All 15 locks and 825 historical dependency keys
remain unchanged, as do every locale resource and generated session declaration.
The first foreground `make check` attempt exceeded its execution timeout and
is not a pass. Final full-suite, coverage and exact-head cross-platform CI must
be recorded before treating this follow-up as verified for PR 27.

No function wording, locale resource, audio lock, audio edition, source
recording or voice asset is changed. Human editorial/listening/publication
approvals remain independent. PR 27 must not be merged without the required
human review and explicit owner merge authorization.
