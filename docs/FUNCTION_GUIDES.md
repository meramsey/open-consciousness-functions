# Generating listening and function guides

The source general guide is [LISTENING_GUIDE.md](LISTENING_GUIDE.md). Function
guides derive from canonical function YAML, command and locale helpers, and
`artwork_content`; generated prose is not new reviewed narration. No source
transcripts or audio are copied. Descriptions retain their locale review status.

From a source checkout, install the optional `.[guides]` dependency and run:

```bash
PYTHONPATH=scripts python -m ocf_tools.listening_guides --output .ocf-work/guides
PYTHONPATH=scripts python -m ocf_tools.listening_guides --output .ocf-work/guides --check
```

The default produces `listening-guide.md` / `.pdf` / `.html`, the same three
index formats, and one Markdown/PDF/HTML set per registry function in `functions/`
(currently 58 functions, 180 files total).
`--markdown-only` needs no ReportLab installation. Relative outputs resolve from
the repository root. Existing target files are never overwritten: use a new
directory for a new snapshot. `--check` compares all expected bytes without
writing; it does not delete unrelated files. Files publish completely and
exclusively through OCF's shared atomic writer, including PDF bytes. Generated
Markdown is the text authority for its matching PDF and HTML. The renderer supports a deliberately small
Markdown subset: headings, paragraphs, bullets, inline code, and links.

## Authority and missing data

Exact active primary and secondary display/spoken cues use existing locale and
command resolution. Legacy aliases and inactive commands are not presented as
current commands. Missing reviewed speech is explicitly labeled. Purposes and
artwork descriptions retain resource status; drafts are not promoted to reviewed
text. Lifecycle and availability values are catalog metadata, not efficacy,
eligibility, persistence guarantees, or listening approval.

This version deliberately does not publish activation procedures or relationships:
the guide helpers do not expose a uniform human-review gate for those declarations.
Each guide labels that omission rather than turning empty fields or names into
instructions. No narration, legacy mapping, or canonical metadata is changed.

## PDF behavior and limits

PDFs are light, print-friendly, have page numbers, heading bookmarks, and relative
links between generated guides. Text is selectable/searchable. The renderer uses
committed brand TrueType fonts when present, otherwise ReportLab's bundled Vera
font; it never relies on machine-specific font paths or downloads fonts.
Unsupported glyphs fail explicitly. Output is byte-deterministic for unchanged
sources and the same ReportLab/font version. Dependency or font changes may
require a fresh snapshot. PDFs are not tagged PDF/UA or accessibility-certified.
Keep Markdown alongside them for alternative readers.

HTML is UTF-8, offline and responsive to the browser viewport, with semantic
headings/lists and relative links to other HTML guides. Unsafe link schemes are
not emitted as active links. Native browser/PDF-reader UI and accessibility
certification are not implied by byte or text-extraction checks.

No themes, cover artwork, audio generation, or mass-committed generated
artifacts are included. Run `python -m pytest tests/test_listening_guides.py`;
PDF tests need the optional dependency, and extraction checks need `pdftotext`.
