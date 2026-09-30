# Legacy maps

This directory preserves factual, permissive-license metadata about the
historical **Monroe H-PLUS** function system for research and compatibility.

## Contents

- `README.md` — this file, the authoritative 55-function legacy record.
- `hplus-command-map.json` / `hplus-command-map.csv` — *generated* command maps
  (run `python3 scripts/ocf.py build-index` to regenerate).
- `source-notes/` — optional structured notes from source reviews
  (see `templates/source-review.md`).

## The 55 documented functions

The initial OCF legacy map includes exactly **55 documented functions**:

- **39** whose original/reference training material is currently **available**.
- **16** documented functions whose original/reference training material is
  currently **unavailable** — they remain **full OCF reimplementation targets**
  (`ocf.reimplementation_status: planned`).

The 16 source-unavailable legacy functions are NOT "missing functions". They
are valid, first-class OCF targets eligible for original training scripts,
community reimplementation proposals, review, experimentation, and future
audio implementations based on documented legacy information. They must never
be falsely represented as reconstructed original Monroe audio.

## Availability summary

| Count | Source material            | Status                                      |
| ----- | -------------------------- | ------------------------------------------- |
| 39    | Available                 | Legacy-mapped, reimplementation planned      |
| 16    | Unavailable               | Legacy-mapped, reimplementation planned      |

See `docs/AVAILABILITY_MATRIX.md` and `docs/REIMPLEMENTATION_ROADMAP.md` for
per-function detail.

## Independence and licensing

These mappings are concise factual metadata, not copyrighted expression, and
are published under the project's Apache-2.0 license. OCF is not affiliated
with, endorsed by, or owned by The Monroe Institute, Hemi-Sync, Interstate
Industries, or any related entity. OCF does not redistribute Monroe training
audio.