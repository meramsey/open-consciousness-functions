# Source Attribution

Provenance is recorded, never guessed.

## Rules

1. **Citation-only for repository distribution by default.** Reference files
   without recorded redistribution clearance (third-party PDFs, audio, pamphlets)
   are recorded as references, not copied into the repository or packages.
   This does not prohibit exact source-first working copies in a local authoring
   workspace; see [source-first authoring](SOURCE_FIRST_AUTHORING.md).
2. **Fingerprint local files.** `ocf import source` computes a SHA-256 and
   keeps the original untouched. Copying into `references/uploads/` happens
   only on explicit, informed consent and only for material you may
   redistribute.
3. **No fabricated locators.** If a page locator cannot be established from the
   actual source, write `null` / `pending-source-review`. Never invent page
   numbers or quotes.
4. **Separate working text from release.** Local SOURCE preserves exact bytes;
   WORKING starts exact and human editors decide changes. Mandatory paraphrasing,
   distancing and automatic originality are not working gates. Do not package
   source/working registry chunks. Release/package inclusion requires explicit
   human approval and recorded rights clearance; tools do not make legal
   conclusions about quotation, copying, similarity or redistribution.
5. **Storage is not attribution.** A binary may be committable (Git LFS, see
   `CONTRIBUTING.md`) or local-only (`.gitignore`) purely for practical
   reasons; neither implies anything about its provenance. License and
   attribution and rights evidence must be recorded before a binary is added —
   never infer clearance from the file's convenience or availability.

## Source-first review boundaries

The local default authoring workspace is `.ocf-authoring/`, which must be ignored
and excluded from packages. SOURCE fingerprints cover exact bytes, with ranged
extents for selected text. Shared blocks retain their originating source hashes
and locators even when referenced by other functions. Transcript corrections,
claims/accessibility flags and uncertainties are separate metadata, never silent
changes to SOURCE. An available or authenticated source is not rights clearance;
an unavailable source remains explicitly unavailable, never reconstructed as fact.

Review status and release approval are separate. Release approval records the
reviewer, current text hash, rights status (`verified_redistributable` or
`user_cleared`) and rights evidence. These are recorded human attestations, not
automated legal findings. Pending, stale or uncleared blocks cannot enter release
preview or a package. Exact source expression is not relabeled OCF-original.
Untimed draft preview remains available for human review without release approval.

## Attribution fields

Function records carry:

- `sources[]` — typed citations (`legacy-reference`, `web`, `reference-file`,
  `pending-source-review`) with title/locator/url;
- `attribution.original_authors` — legacy holders or upstream sources of the
  *described material*;
- `attribution.ocf_contributors` — community authors of the OCF record.

Audio manifests carry their own `contributor`, `narrator`, and `license`
fields. Background presets carry `author`, `provenance`, and `license`.

## Notices

- Every generated index and the README repeat the project independence notice.
- Reconstituted/re-imagined scripts must be labeled as OCF reimplementations,
  never as reconstructed original Monroe audio.
- `NOTICE.md` tracks licensing layers and the Farfield dependency note
  (external, see its own license).

## Review notes

Source reviews are recorded in `legacy/source-notes/` using
`templates/source-review.md`, keeping the reviewed evidence separate from
inference.

Focus-state acoustic evidence is additionally inventoried in
[`docs/research/`](research/README.md), including source fingerprints, the
unresolved Focus Ten V4 timeline mismatch and F11 canonical/alternate preset
provenance. These research records distinguish measured facts from derived
reconstructions and design choices; they do not override historical mappings
or runtime preset selection.
