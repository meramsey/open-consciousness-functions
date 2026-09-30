# Source Attribution

Provenance is recorded, never guessed.

## Rules

1. **Citation-only by default.** Reference files that OCF cannot redistribute
   (third-party PDFs, audio, pamphlets) are recorded as references, not
   copied into the repository.
2. **Fingerprint local files.** `ocf import source` computes a SHA-256 and
   keeps the original untouched. Copying into `references/uploads/` happens
   only on explicit, informed consent and only for material you may
   redistribute.
3. **No fabricated locators.** If a page locator cannot be established from the
   actual source, write `null` / `pending-source-review`. Never invent page
   numbers or quotes.
4. **Short quotes only.** Concise factual mappings and short summaries are
   fine; long copyrighted excerpts are not.
5. **Storage is not attribution.** A binary may be committable (Git LFS, see
   `CONTRIBUTING.md`) or local-only (`.gitignore`) purely for practical
   reasons; neither implies anything about its provenance. License and
   attribution fields decide that, and they are required before a binary is
   added — never the file's convenience.

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