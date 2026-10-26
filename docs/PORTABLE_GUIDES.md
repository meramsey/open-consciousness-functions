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

- `index.html`: searchable offline guide browser with embedded CSS/JavaScript.
- `index.md` and `index.pdf`: concise collection directories.
- `listening-guide.{md,html,pdf}`: general listening guidance.
- `complete-guide.pdf`: standalone handbook containing all function guides.
- `functions/<FUNCTION-ID>.{md,html,pdf}`: one guide in three formats for each
  implemented function.

The output directory must be new or empty; generation refuses to overwrite an
existing collection. The ZIP is optional and is suitable for relocation or
offline sharing. Links are generated relative to the collection root and do
not require the private audio edition, network access, or machine-specific
paths. Private FLAC/MP3 files are intentionally excluded.

Validate a generated collection after copying it elsewhere with:

```bash
PYTHONPATH=scripts .venv/bin/python -m pytest -q tests/test_portable_guides.py
```

The standalone PDF is reader-facing documentation; it does not grant human
listening approval, publication authorization, or rights clearance for any
audio edition.
