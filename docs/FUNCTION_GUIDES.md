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

Listener guides now reuse the existing command-documentation service for ordered
procedures, command meanings, invocation/effect scopes, and lifecycle descriptions.
They do not invent a universal activation ritual or a missing duration/reset rule.
Historical lookup wording and retained compatibility aliases are separated from
primary/secondary controls. Source plans are not represented as released recordings.

The documentation-only approval `OCF-GUIDE-REVIEW-001` records the six directional
optional companion links and final batch confirmation. Canonical `companions`
must agree with that approval before links are published. The guide generator
resolves descriptions through locale keys; neither a similar name nor a matching
topic is approval. No cue, procedure operation/order, lifecycle, narration or DSP
change is authorized by this documentation batch. Immutable predecessors remain
verifiable through the checked metadata-only successor.

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

## Portable listener bundles

Existing private exports can be packaged without running any audio encoder:

```bash
PYTHONPATH=scripts python -m ocf_tools.listener_packages \
  .ocf-work/renders/EXISTING-EXPORT \
  --guides .ocf-work/guides \
  --output .ocf-work/renders/PRIVATE-PACKAGE
```

Supply multiple export directories for a collection. The collection includes one
shared `guides/` directory; a single-function bundle includes everything it needs.
The command copies the existing FLAC, MP3, cover, same-basename TXT/LRC/SRT/VTT,
timing receipt and edition/provenance manifest. It never remuxes, retags, mixes or
reencodes. Original exports are immutable. `package.json` records every included
file's relative path, size and SHA-256, plus source-manifest identities. Its SHA-256
is the package checkpoint checksum, not an archive checksum. `--resume` verifies
all existing bytes and exact source identities, refusing corrupt or foreign output.
Interrupted unpublished stages retain diagnostics in the workspace; retry publishes
a new stage, not a partial edition. Private output must stay in the OCF workspace.
Approved related-function guide dependencies are included transitively, without
implying that their audio is included. Package navigation links to the actual
edition audio, artwork, transcripts and timing receipt, with percent-encoded
filenames. Verification rejects missing or escaping relative guide links.

Guide changes require a new output directory and new package receipt. Resume
never replaces older guide bytes. Keep the audio edition unchanged when only
documentation changes; the package's guide approval and artifact hashes identify
the new guide snapshot separately. Existing packages and source exports remain
immutable; no reference-derived material is made eligible for public release.

The optional `--guides` cache must contain the current selected general/function
Markdown, PDF and HTML. Missing, corrupt or stale content fails explicitly; no
58-function PDF rebuild is performed. Without a cache, only the selected guides
and a small package-local navigation index are generated. English guides cannot
silently stand in for a translated edition. PDFs require `.[guides]`.

`audio export-audition --guides DIR` and `audio release --guides DIR` use this same
attachment helper inside their existing staging/approval workflow. The guide
option does not grant rights, listening approval or publication approval. This
bundle command is private-only and cannot promote reference-derived auditions
to formal releases. Do not upload private bundles, source recordings or lyrics.

## Guide completeness and approved relationships

All 58 current guides derive titles and primary/secondary cues from current
registry/locale data. Current en-US titles match canonical titles. They expose
review states, purpose, precautions, persistence and availability as metadata,
not promises. Searchable PDF text, bookmarks and links do not establish PDF/UA
compliance, visual clipping clearance or screen-reader usability.

All 73 operational primary/secondary commands have documented procedures. The
58 listener guides show those steps and the existing command explanations; 14
functions have additional scoped lifecycle metadata. Intuition's quiet-moment
and discernment steps use specific approved instructions rather than generic
`other` placeholders. Optional artwork copy is not required to show the existing
canonical short community description.

Appetite Choice's per-application scope is not permanent hunger suppression;
Food More/Food Less belong to Nutricia, not Appetite Choice. Body Tune-Up retains
its whole-body maintenance baseline and selected-area reinforcement. Clear Zone
Observe and Suspend are distinct mutually exclusive overrides with the declared
reset conditions. Injury/Toxic Exposure metadata is not emergency detection or
treatment. Focus is a function, not a Focus 10/11 stage. Manifest, Dissolve and
Intuition remain independent.

The six proposals first recorded at checkpoint `2b26883` received six explicit
approvals followed by final batch confirmation. Their exact approved explanations
and responses are retained in
[the documentation successor](../function-content/editorial/guide-review-001.json).
All are **optional and directional**. No reciprocal link, required sequence,
proven synergy, clinical benefit or listening/release approval is implied.

- Source `OCF-EXP-001` Manifest → related `OCF-EXP-003` Dissolve;
  category: contrasting intentions. Approved optional link: compare separate
  intention-setting and letting-go functions without prescribing a sequence.
  Provenance: canonical experimental function YAML; editorial review request.
- Source `OCF-EXP-001` Manifest → related `OCF-EXP-006` Intuition;
  category: complementary reflection. Approved optional link: offer a separately
  chosen intuition exercise, not a required part of Manifest.
  Provenance: canonical experimental function YAML; editorial review request.
- Source `OCF-EXP-003` Dissolve → related `OCF-EXP-006` Intuition;
  category: complementary reflection. Approved optional link: distinguish letting
  go from seeking understanding; neither enables or depends on the other.
  Provenance: canonical experimental function YAML; editorial review request.
- Source `OCF-BOD-006` Heart Flow → related `OCF-BOD-002` Circulation;
  category: adjacent body-awareness topics. Approved optional link: show separately
  selectable catalog topics without implying a combined physiological effect.
  Provenance: canonical body function YAML; editorial review request.
- Source `OCF-SLP-005` Sleep Easy → related `OCF-SLP-001` Restorative Sleep;
  category: adjacent sleep topics. Approved optional link: compare intended use
  and ending before choosing one; do not prescribe stacking recordings.
  Provenance: canonical sleep function YAML; editorial review request.
- Source `OCF-FND-002` Focus → related `OCF-COG-007` Think Fast;
  category: adjacent cognitive topics. Approved optional link: compare attention
  and thinking-oriented practice without confusing Focus with a Focus 10/11 stage
  or claiming either function improves the other's effects.
  Provenance: canonical foundation/cognition YAML; editorial review request.

The current full instructions and localized relationship text are generated in
the function guides. Earlier candidate wording is historical review evidence,
not an independently editable source for current guide behavior.

## Player compatibility: documented versus exercised

Reviewed 2026-10-24. No native player UI was exercised for this checkpoint.
Local tag/sidecar readback and unchanged packet/PCM hashes are file-level evidence
only. UTF-8 sidecars preserve Unicode; LRC uses centiseconds (truncated), while
SRT/VTT/SYLT use milliseconds. Timing is measured utterance/unit timing, not
word-level karaoke. Long sessions require testing seeking near the final cue.

- Poweramp: official release notes describe SYLT and external LRC support and
  **Rescan Lyrics Tags** for previously indexed files. Use same-basename LRC as
  the most portable fallback; do not assume that SYLT wins over USLT or that all
  FLAC tag variants behave identically. See the
  [official release notes](https://forum.powerampapp.com/files/category/2-poweramp-v3-latest-releases/).
  Direct forum-page retrieval was blocked; release-note search results were
  available, but exact current-build precedence remains unverified.
- Plexamp: Plex documents local `.lrc` and `.txt` files in the track directory
  with **identical basename**, and explicitly says embedded lyrics are not
  supported. Use the default Plex Music agent/scanner and refresh local metadata.
  Keep one audio format per imported test album to avoid duplicate tracks. See
  [Plex local lyrics/artwork](https://support.plex.tv/articles/215916117-adding-local-lyrics/)
  and [Plex client support](https://support.plex.tv/articles/215238778-automatic-lyrics-from-lyricfind/).
- VLC: use the supplied SRT via the subtitle-track interface as a manual fallback;
  native lyrics discovery, audio-only subtitle display and LRC behavior are not
  verified here. No embedded-lyrics compatibility claim is made.
- foobar2000: lyrics depend on the installed component. OpenLyrics documents
  timed/untimed text and configurable tag/file searches; this is not a claim of
  native SYLT support. Disable online searches for private sessions. See the
  [component documentation](https://wiki.hydrogenaudio.org/index.php?title=Foobar2000:Components/OpenLyrics_(foo_openlyrics)).
- MusicBee: embedded/sidecar precedence and synchronized display remain unverified
  in this checkpoint. Retain the matching LRC and test locally, not through a
  lyrics website. No native compatibility pass is claimed.

### Minimal private manual acceptance test

Use the existing Amy `OCF-EXP-006` Intuition v0.2.0 reference-V4 package, locally
only. Copy its MP3 plus **all same-basename sidecars** and `cover.png` into a
private player library; test FLAC in a separate folder afterward. Do not rename
only the audio. Do not enable lyrics upload/search plugins or public Plex sharing.
On Android, choose a local-only folder the player can access, grant only the
needed folder/media permission, and confirm the audio and sidecars remain together
after transfer. Check file extensions are visible and avoid cloud-synced test
folders. For Plexamp, use a private server/library under your control.

1. Record app/build, OS, format, import folder and lyrics settings. Keep normal
   speed; disable repeat, shuffle, crossfade and lyric offset adjustments.
2. Poweramp: include the folder in Music Folders, rescan the library and use
   Rescan Lyrics Tags if present. Open Lyrics by swiping up or the configured
   lyrics button. Record whether embedded or sidecar text was selected.
3. Plexamp: import into a private Plex Music library, rescan/refresh metadata,
   open the track's lyrics view. Embedded tags alone are not the expected path;
   matching LRC is. Record server version, client version and account capability
   if lyrics are unavailable rather than assuming a tagging fault.
4. Expect correct title, Amy narrator, edition, intact artwork and readable text;
   at beginning/middle/final spoken cue, expect the appropriate line to follow
   playback/seeking. Compare timestamps against LRC, allowing its 10 ms precision
   and device display latency. Confirm silence is not mistaken for word alignment.
5. Check non-ASCII punctuation and the final minute; record clipping, wrong cue,
   offset, stale cache or artwork disappearance. Repeat with FLAC. If testing
   embedded-only discovery, do so in a separate disposable copy, not the package.

Actual UI result: **awaiting user verification** for all five players. Do not
change narration, reencode audio or upload private text to diagnose player issues.
