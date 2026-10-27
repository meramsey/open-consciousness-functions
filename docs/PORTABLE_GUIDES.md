# Portable OCF guide collection

OCF can generate a self-contained, offline guide collection without including
private reference audio or source recordings. The generator derives the 58
function entries from the canonical registry and uses the existing approved
guide/content services.

From the repository root:

```bash
PYTHONPATH=scripts .venv/bin/python -m ocf_tools.listening_guides \
  --portable-output .ocf-work/guides/OCF-Guides-v0.3.0 \
  --zip .ocf-work/guides/OCF-Guides-v0.3.0.zip
```

The output contains:

- `index.html`: searchable offline guide browser with embedded CSS/JavaScript,
  grouped by canonical function domain in stable registry order.
- `index.md` and `index.pdf`: matching category-grouped, concise directories with
  verified handbook page references and clickable page links.
- `listening-guide.{md,html,pdf}`: general listening guidance.
- `complete-guide.pdf`: standalone handbook containing all function guides,
  a visible page-numbered clickable TOC, matching outlines/bookmarks and internal
  cross-guide navigation. Pagination is resolved by ReportLab's multi-pass layout
  and checked against the finished PDF using the optional guide dependency pypdf.
- `functions/<FUNCTION-ID>.{md,html,pdf}`: one guide in three formats for each
  implemented function.

The output directory must be new or empty; generation refuses to overwrite an
existing collection. The ZIP is optional and is suitable for relocation or
offline sharing. Links are generated relative to the collection root and do
not require the private audio edition, network access, or machine-specific
paths. Private FLAC/MP3 files are intentionally excluded.

Validate a generated collection after copying it elsewhere with:

```bash
PYTHONPATH=scripts .venv/bin/python -m ocf_tools.listening_guides \
  --validate-portable /path/to/copied/OCF-Guides-v0.3.0
python -m pytest tests/test_portable_guides.py
```

Generation performs the same validation before creating the ZIP. Checks cover
all directory references, visible TOC numbers, each TOC link's actual row and
destination, outline destinations, internal PDF destinations, local Markdown and
HTML links, and HTML assets. The report includes inventory and checked-link
counts. Missing/escaping links, wrong guide destinations and out-of-bounds pages
fail generation. ZIP entries use stable names, timestamps and permissions; no
temporary/cache files are included. PDF page-fragment links depend on reader
support; the handbook's TOC uses native internal PDF links. These checks do not
certify PDF/UA accessibility or replace visual review.

The standalone PDF is reader-facing documentation; it does not grant human
listening approval, publication authorization, or rights clearance for any
audio edition.
