# Submission Guidelines

How to get new content into OCF cleanly.

## Before you submit

1. Read `CONTRIBUTING.md`, `AGENTS.md`, and this guide.
2. Skim `docs/COMMAND_GRAMMAR.md`, `docs/NAMING_GUIDELINES.md`, and
   `docs/SAFETY_POLICY.md` depending on what you are submitting.
3. Inspect `templates/` — they encode the expected shape.

## What you can submit

- **New functions** — original community-authored functions.
- **Reimplementation proposals** — original scripts for the 16
  source-unavailable legacy functions (open pathway, always welcome).
- **Command changes** — only with the full change record and rationale.
- **Audio implementations** — via manifest + transcript; never third-party
  copyrighted audio.
- **Background presets** — via manifest; optional engine configs.
- **Testing reports** — factual observations, labeled as anecdotal.
- **Documentation fixes**, **schema improvements**, **tooling bug fixes**.

## Required for a function proposal

Problem · Purpose · Proposed name · Command · Command-length rationale ·
Activation · Release · Persistence · Safety · Compatibility · Evidence state ·
Alternatives · Implementation · Testing · Sources · Licensing.

See `templates/proposal.md`.

## Required for a command change

- Legacy command
- Proposed OCF command
- Reason (from the change criteria in `COMMAND_GRAMMAR.md`)
- Old spoken-word count
- New spoken-word count
- Compatibility strategy
- Review state

Changed commands keep their legacy command as an alias with
`compatibility.rationale`, and must be `normalized`, `proposed`, or
`review-required` until approved.

## Video/audio content

- Transcripts are community-authored original text.
- Never upload Monroe or other third-party audio.
- Every audio implementation records license, narrator, language, safety
  intro, and review state in its manifest.
- Renders are reproducible when seeds are recorded.
- **Submitted audio files are Git LFS objects.** If your contribution includes
  a committable binary asset (an original OCF cue sound, a clearly licensed
  recording, a figure), just add it — `.gitattributes` routes
  `wav/flac/mp3/m4a/ogg/opus/aif/aiff` and `png/jpg/jpeg/gif/webp` through LFS
  automatically. Do not run `git lfs track`, and do not `git add -f` a file
  that `.gitignore` excludes.
- `.gitignore` excludes rendered masters, operator reference audio, and
  reference PDFs on **licensing** grounds, not size grounds. A file you believe
  should be committed is a licensing/attribution question: open a proposal and
  record the license. See `docs/SOURCE_ATTRIBUTION.md`.
- Files you keep local (citation-only imports, lawfully held sources) are
  expected to stay local — commit the manifest, provenance, and checksums
  instead. `ocf import source` records the SHA-256 without copying anything.

## Process

1. Draft in `proposals/draft/` (wizard recommended).
2. Maintainers move to `proposals/review/`; discussion happens there or in
   the issue/PR.
3. Accepted → `accepted/`; the function command may then be `approved`.
4. Rejected / withdrawn items keep their ID and rationale.

## Hygiene

- Run `python3 scripts/ocf.py validate --all` before PR.
- Run `python3 scripts/ocf.py build-index` and commit the regenerated files
  (or rely on CI to enforce freshness).
- Never hand-edit generated files.
- Unknown fields stay `pending-source-review` — obligation over guesswork.