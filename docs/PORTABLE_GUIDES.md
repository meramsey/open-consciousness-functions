# Portable OCF guide collection

OCF can generate a self-contained, offline guide collection without including
private reference audio or source recordings. The generator derives the 58
function entries from the canonical per-locale function resources and uses the existing approved
guide/content services.

From the repository root:

```bash
PYTHONPATH=scripts .venv/bin/python -m ocf_tools.listening_guides \
  --portable-output .ocf-work/guides/OCF-Guides-v0.3.0 \
  --zip .ocf-work/guides/OCF-Guides-v0.3.0.zip
```

The output contains:

- `index.html`: searchable offline guide browser with embedded CSS/JavaScript,
  grouped by canonical function domain in stable catalog order.
- `index.md` and `index.pdf`: matching category-grouped, concise directories with
  verified handbook page references and clickable page links.
- `listening-guide.{md,html,pdf}`: general listening guidance.
- `complete-guide.pdf`: standalone handbook containing all function guides,
  a visible page-numbered clickable TOC, matching outlines/bookmarks and internal
  cross-guide navigation. Pagination is resolved by ReportLab's multi-pass layout
  and checked against the finished PDF using the optional guide dependency pypdf.
- `functions/<FUNCTION-ID>.{md,html,pdf}`: one guide in three formats for each
  catalog function, with its implementation and source status retained.
- `cue-reference`, `relationship-map`, `complementary-map`, `learning-order` and
  `tag-discovery` in Markdown, HTML and PDF: current cues, reviewed directional
  links, separately labeled draft suggestions and browsing references.
- Build provenance, integrity checksums and a developer audit, kept separate from
  reader-facing practice instructions.

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

## How relationships reach every format

The owning function YAML supplies `tags`, `common_uses` and `relationships`.
Reviewed links require the matching embedded approval record; draft proposals
retain their status. The generator uses the same Markdown content for HTML and
PDF, and the portable browser searches the canonical tags and common uses.
A historical companion suggestion does not by itself approve an OCF practice
sequence. The learning-order reference is a browsing directory, not a routine
or activation chain.

Keep a fresh versioned collection after metadata or guide changes. Compare
individual function links, the relationship map and handbook destinations when
reviewing an edition; a successful build alone does not establish that the
catalog contains every relationship in an external reference.
