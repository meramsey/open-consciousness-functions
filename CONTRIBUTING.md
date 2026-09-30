# Contributing

Thanks for considering a contribution to **Open Consciousness Functions
(OCF)**. Two paths exist — one for non-programmers, one for advanced
contributors.

## Easy contributor path

You do not need to know YAML, schemas, or git internals:

```bash
./scripts/ocf new function      # create a function record
./scripts/ocf new proposal      # propose something new
./scripts/ocf new audio         # register an audio implementation
./scripts/ocf new background    # register a background preset
./scripts/ocf new test-report   # file an observation
./scripts/ocf import source     # fingerprint a local source file
```

Every wizard:

- gives **help** for every field (`?`);
- lets you **skip** optional fields;
- shows a **final review screen** before writing;
- writes the file **atomically** and **validates it immediately**.

Then open a pull request with the created file(s).

## Timed-lyrics authoring

Adding a function **from timed lyrics** (an `.lrc` file, or `.srt`/`.vtt`/
`.txt`/`.md`) uses the transcript pipeline described in
[`docs/TIMED_TRANSCRIPTS.md`](docs/TIMED_TRANSCRIPTS.md):

```text
import timed lyrics (.lrc)      ocf transcript import FILE
assign sections                 ocf transcript segment/analyze/review FILE
assign state/focus              ocf transcript review FILE --state-profile <name>
create function record          ocf new function
register audio implementation   ocf new audio
choose voice + background       ocf voice * / ocf audio render-background
preview and build               ocf audio build
```

Rules that always apply:

- **Wording is never silently rewritten.** Imports keep the exact source text
  and timestamps; you edit deliberately.
- **Imported thirds-party/reference transcripts stay citation-only.** Timing
  may be reused; wording must be original or clearly lawful to redistribute.
  Local generation from a lawfully held file is permitted; committing the
  transcript wording is not.
- **Internally honest status** — the transcript pipeline (`ocf transcript …`)
  and the voice/audio-build steps (`ocf voice …`, `ocf audio build …`) are
  shipped; the preparation module (`ocf preparation …`) is specified but not
  yet live. Track each capability's status in
  [`docs/TIMED_TRANSCRIPTS.md`](docs/TIMED_TRANSCRIPTS.md) and `ROADMAP.md`.

## Advanced contributor path

Manual YAML editing, schema conformance, and generated-index discipline.

1. **Inspect the schemas first**: `schemas/*.schema.json`.
2. **Create or edit** a function record under `functions/<domain>/<slug>.yaml`
   (copy `templates/function.yaml`).
3. **Validate**: `python3 scripts/ocf.py validate --all`.
4. **Regenerate indexes**: `python3 scripts/ocf.py build-index`.
5. Add or update **tests** in `tests/` and run `python3 -m pytest`.
6. Open a PR. CI runs validation, tests, lint, and index-freshness checks.

### Hard rules

- **Never hand-edit generated files** (`FUNCTION_INDEX.md`,
  `function-index.*`, `legacy/hplus-command-map.*`, `docs/COMMAND_REVIEW.md`,
  and the matrices in `docs/`). Run `build-index`.
- **Never fabricate source details.** Unknown fields stay
  `pending-source-review` / `null` / `[]`.
- **Never delete or rewrite legacy mappings.** They are research metadata.
- **Never edit a schema without updating the format and tests together.**
- **Never claim effects.** Check `docs/EVIDENCE_AND_CLAIMS.md` and
  `docs/SAFETY_POLICY.md`.
- **Do not upload copyrighted audio.** Reference files are citation-only.
- **Never commit third-party or generated audio.** Renders, operator
  reference masters, and reference material are gitignored on *licensing*
  grounds — do not `git add -f` around that.
- **Keep the 55-function legacy map intact** (39 available + 16 unavailable),
  all valid OCF reimplementation targets.

## Large files and Git LFS

OCF may one day need to commit genuinely binary content: original OCF-authored
or clearly licensed community assets (for example focus-state cue sounds,
bundled chant/affirmation audio, large lawful reference material a proposal
has approved for redistribution). Such files are **Git LFS objects**, not
normal git blobs.

`.gitattributes` already declares the LFS policy, so there is nothing to
configure per file:

| Type                | Handling                                    |
| ------------------- | ------------------------------------------- |
| `wav flac mp3 m4a ogg opus aif aiff` | LFS (`filter=lfs`) |
| `png jpg jpeg gif webp`              | LFS (`filter=lfs`) |
| `md yaml yml json csv py toml txt lrc srt vtt sbg` | plain text, `eol=lf` |
| `pdf`                | undiffable; gitignored (citation-only)      |

Rules of thumb:

- **Just commit the file.** The filter runs automatically on `git add`; never
  run `git lfs track` by hand (that would edit `.gitattributes` behind the
  policy's back).
- **`.gitignore` still wins.** An ignored path is not committed *at all*,
  LFS or not. If you believe a file should be committed, that is a **licensing
  and attribution** question, not a size question — see
  `docs/SOURCE_ATTRIBUTION.md` and open a proposal.
- **Rendered audio stays local.** `audio/rendered/` and
  `audio/background/rendered/` are build outputs, not sources.
- Check what is tracked: `git lfs ls-files`; verify your clone can restore
  real bytes: `git lfs pull`.

First-time setup (per clone):

```bash
git lfs install          # already done by `git lfs install --local` in this repo
git lfs env              # confirm endpoints/filters
git lfs pull             # fetch LFS objects after cloning or switching branches
```

Escape hatch: a later `.gitattributes` line wins per attribute, so a small
icon can be kept as a normal git object with
`docs/img/logo.png -filter -lfs -diff`. Do that for small images only —
never to dodge the LFS quota for real audio.

CI note: `actions/checkout@v4` does **not** fetch LFS objects unless
`lfs: true` is passed. A job or test that needs an LFS-tracked asset must set
that explicitly; the current workflows do not need it.

### Command changes

Command changes need the full rationale described in
`docs/COMMAND_GRAMMAR.md`: legacy command, proposed command, reason, word
counts, compatibility strategy, and review state. Good short commands are
preserved (`PLUS-THINK`, `PLUS-FOCUS`); broken ones get a review-required
proposal.

## Proposal workflow

1. Draft in `proposals/draft/` (wizard or `templates/proposal.md`).
2. Maintainers move it to `proposals/review/` for discussion.
3. Accepted → `accepted/`; declined → `rejected/`; self-retired → `withdrawn/`.

See `docs/FUNCTION_LIFECYCLE.md` and `docs/SUBMISSION_GUIDELINES.md`.

## Development

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/ocf.py doctor
python3 -m pytest                 # tests
python3 scripts/ocf.py validate --all
python3 scripts/ocf.py build-index --check
ruff check scripts tests          # lint
```

Filter code through `docs/ARCHITECTURE.md` and `GOVERNANCE.md` before
submitting.