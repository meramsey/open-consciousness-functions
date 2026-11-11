# Export existing masters for public review

`audio export-public` prepares a new local candidate from a verified retained
listening delivery. It never synthesizes speech, renders a background, or changes
the source delivery. It does not upload files or grant publication permission.
The audio distribution repository owns publication manifests, exact-asset owner
approval, GitHub Releases, and the public library.

## Prepare an individual candidate

Use a verified delivery receipt and independently recorded SHA-256. Supply the
public voice identity explicitly; a private profile name is not a distribution
permission. Choose a new descriptive output directory for each session.

```bash
python scripts/ocf.py audio export-public /path/to/delivery.json \
  --expected-source-sha256 RECEIPT_SHA256 \
  --public-voice-id approved-voice --public-voice-name 'Approved Voice' \
  --source-commit ORIGINAL_RENDER_COMMIT --source-version SOURCE_VERSION \
  --export-commit EXPORT_CODE_COMMIT \
  --output /path/to/new-candidate --dry-run
```

Replace the placeholders with actual recorded values. Remove `--dry-run` to
export. FFmpeg/ffprobe, NumPy, SoundFile and the artwork dependencies must be
available in the project environment. No voice backend is needed.

The FLAC keeps its compressed audio packets, decoded PCM and actual bit depth.
The default MP3 is encoded directly from that lossless FLAC at 320 kbps stereo.
`--reuse-existing-mp3` instead preserves an existing MP3's packets and decoded
PCM, without claiming it has a higher bitrate. Existing files are never
recompressed in place. The retained FLAC is identified as the master; this does
not claim to recover an original WAV that was not retained.

The exporter validates source sizes/checksums, stereo sample counts, finite
samples, clipping, output decode alignment, embedded cover bytes and public
metadata. Global and audio-stream metadata and chapters are discarded before
explicit public tags are written. Covers containing EXIF or unreviewed image metadata are rejected; approved cover
bytes are never silently changed. Unknown PNG chunks, unreviewed JPEG application/comment
segments, nested thumbnails and trailing container data are also rejected.
Permitted PNG chunks must have valid payload sizes, values, order and CRCs. All
IDAT chunks form one complete zlib stream with the exact scanline byte count;
unused compressed input, additional streams and decoded trailers fail preflight.
Ordinary and progressive JPEGs use the same full export and dry-run checks.
Transcripts, subtitles and the selected cover
are copied unchanged and still require content and rights review. Preparation
Learning sorts first and has its own session kind, with no fabricated function ID.

## Provenance and approval

`export-candidate.json` follows `schemas/public-export-candidate.schema.json`.
It records artifact hashes, retained-master provenance, encoder operations and a
technical receipt. Publication approval is always false. Review the exact
candidate artwork, wording, public voice name and redistribution permissions
before handing assets to the distribution publisher.

For a render made from a frozen working tree, provide `--render-source FILE`
with the recorded base commit, a public-source-only snapshot hash and its scope.
An optional audio-code-equivalent commit describes later equivalent code; it
must not replace the actual render base. `--export-commit` independently records
the later export code revision. Do not fabricate a clean render commit or place
private source paths, voice references or consent documents in public metadata.

A successful export removes only its owned assembly snapshots. Failed scratch
is retained for diagnosis. Existing candidates are never overwritten. For a
large batch, use the project's supervised production controller and independent
watchdog; a CLI process alone is not durable production monitoring.
