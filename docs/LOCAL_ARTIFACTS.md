# Persistent local auditions

New default OCF auditions and their local reports are retained under the
gitignored **`.ocf-work/renders/auditions/`** tree. Historical frozen artifacts
described below remain in their original `audio/rendered/auditions/` locations.
Audition audio and machine-local provenance are not staged or redistributed.

`scripts/tools/preserve_auditions.py SOURCE OUTPUT` copies existing artifacts,
compares SHA256 before/after, reuses identical copies and refuses to overwrite
different bytes. It never invokes TTS or changes source/reference material.
Per-copy preservation manifests remain local. Keep original render manifests,
ledgers, subtitles and frozen inputs alongside audio; a preservation checksum
does not authenticate source history or approve listening/mastering choices.

Phase2B destinations: `audio/rendered/auditions/preparation-learning-v2/` and
`audio/rendered/auditions/function-pilots/`. The former preserves the complete
available V2 directory; the latter preserves the three available WAV/YAML pairs.
Early pilot renders had no per-event manifest. Their exact bytes are preserved;
historical production details not present in the checkpoint are not invented.
Local README files record the checkpoint and provenance limitations.

`audio/rendered/auditions/preparation-learning-v2.1/` preserves the Development
Audition V2.1 comparison render for the F10 induction finding. It reuses V1 speech
byte-for-byte and keeps its own directory so V2 remains the reference: see
`docs/releases/OCF_PREPARATION_LEARNING_DEV_V2_1.md`.
