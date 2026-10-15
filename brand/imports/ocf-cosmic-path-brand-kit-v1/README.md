# OCF Cosmic Path + Resonance Rings — Brand Kit v1

**Original candidate art, not an approved final OCF brand.** This standalone import kit was assembled in ChatGPT on 2026-10-15 to replace an underpowered procedural approximation in OpenCode.

## Contents
- `reference/generated-art-direction-board.png`: generated cinematic art-direction mockup, including the atmospheric look and composition; `reference/*-reference.png` are cropped reference panels (not publication-master assets).
- `svg/`: authored standalone scalable vector companion artwork with gradients and editable shapes, plus a title-placeholder album template.
- `png/`: deterministic PNG renders of the authored SVG files, including icon sizes 32–1024 pixels.
- `docs/quick-review.png`: contact sheet.
- `manifest.json`: SHA-256 and intended use for every file.
- `OPENCODE_IMPORT_PROMPT.txt`: copyable agent instructions.

**Fidelity distinction:** The cinematic reference board contains richer generated nebula and ribbon detail than the SVG companion. The SVG is a new procedural vector interpretation, **not** an exact vectorization of the raster board. Prefer the imported reference composition during brand review rather than claiming SVG matches it pixel-for-pixel. Do not ship the reference board as an album cover; it is a labeled mood board. Production-grade cinematic source artwork should be generated as separate high-resolution masters if this vector interpretation is insufficient.

## Safe install
Extract this directory inside your repository under `brand/imports/ocf-cosmic-path-v1/` (or keep in a staging folder and point OpenCode to it). Do not overwrite existing brand versions or the locked audio configuration. The OpenCode prompt imports candidates through existing brand/theme/release mechanisms, validates previews, and waits for human branding sign-off.

## Constraints
OCF is an independent open-source brand. No Monroe, Human Plus, or Hemi-Sync labels/logos are used. No personal voices, training data, third-party fonts, or model weights are included. Attribution and release review remain separate. The assets use browser/system fallback fonts; no font files are distributed.
