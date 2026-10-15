# Original candidate OCF visual identity

## Visual refinement 0.2.0

The new [comparison gallery](../brand/versions/0.2.0/gallery/index.html) retains
the 0.1.0 baseline alongside refined dark/light logos, a minimal icon, album
artwork, an application tile and a dedicated 2:1 social composition. Download
or open the directory locally to use the self-contained HTML gallery. It has
mobile/desktop layouts, jump navigation, independent interface theme controls,
and 32/64/128-pixel icon comparisons. All designs remain unapproved candidates.

`brand/versions/0.2.0/identity.json` owns the new geometry and composition sizes.
`ocf-refined-dark`, `ocf-refined-light`, and `ocf-refined-minimal` are explicit
opt-in themes. Existing identity, palettes, surface defaults, candidate SVGs and
previous galleries remain available unchanged.

Generation uses the existing optional artwork extra:
`python -m pip install -e '.[artwork]'`. Viewing the exported gallery requires
only a local browser.

The refinement uses graduated layered ring arcs, a continuous two-cubic tapered
ribbon, directional highlights, a gold focal light and soft procedural radial
illumination. The light finish is designed with pearl/ice surfaces, ink text,
subtle shading and metallic gold; it is not a color inversion of the dark
finish. Minimal icons omit atmospheric effects. Logo, icon, app, album and
social compositions have separate proportions and typography.

SVG and raster renderers consume one scene description. SVG wordmarks are
outlined from the configured font so viewing does not require a font download.
The supplied font is Pillow's bundled Aileron; font licensing remains separate
from the original OCF emblem geometry. Raster exports are supersampled at
preview sizes, and procedural star placement is fixed-seed, not random per run.

```bash
python scripts/ocf.py artwork refine --output .ocf-work/renders/new-brand-comparison
python scripts/ocf.py artwork refine --output brand/versions/0.2.0/gallery --vector-only --check
python scripts/ocf.py artwork brand --variant primary --theme ocf-refined-dark \
  --resolution 960 --output .ocf-work/renders/refined-logo.png
python scripts/ocf.py artwork brand --variant app --theme ocf-refined-dark \
  --resolution 64 --output .ocf-work/renders/refined-app-64.png
python scripts/ocf.py artwork generate OCF-SLP-005 --theme ocf-refined-dark --resolution 1400
```

Choose a new output path for each review; generation refuses to overwrite an
existing comparison directory or explicit artwork file. `--vector-only` creates
the portable source gallery without binary previews. Custom artwork can be
added with `--custom-theme FILE` extending a refined theme, while `--ui-theme`
selects the gallery interface independently.

Refined logo/cover raster exports require at least 320 pixels; social previews
require 640; text-free icon/app exports support 32 pixels. Cover titles fit at
readable sizes within two lines; an impossible title/version fails explicitly
instead of being clipped or reduced to miniature text. Use a suitable licensed
font for localized glyph coverage. The existing release pipeline accepts the
new themes and records brand version 0.2.0, configuration fingerprints and
candidate provenance. An explicit custom cover still takes precedence.

## Retained baseline 0.1.0

The original procedural "Cosmic Path / Resonance Rings" geometry is defined
in `brand/identity.json`. Palettes live in `brand/themes/`; `brand/surfaces.json`
selects UI, artwork and documentation themes independently. All assets are
**candidates**, with no recorded human design approval. They are not copied,
traced or cropped from historical artwork, and are not automatically installed
as the final public project logo.

The geometry combines a winding illuminated path, concentric rings and a
central star. Eight variants cover primary, icon, monochrome, light, dark,
album, app and social uses. SVG is source-friendly; PNG exports use the same
geometry and palette. Social exports have a wide composition.

```bash
python -m pip install -e '.[artwork]'
python scripts/ocf.py artwork themes
python scripts/ocf.py artwork gallery --output .ocf-work/renders/ocf-review-gallery.html
python scripts/ocf.py artwork theme --surface ui
python scripts/ocf.py artwork theme --surface artwork --theme ocf-dark
python scripts/ocf.py artwork brand --variant icon --output .ocf-work/renders/ocf-icon.svg
python scripts/ocf.py artwork brand --variant social --output .ocf-work/renders/ocf-social.png
python scripts/ocf.py artwork generate OCF-SLP-005 --theme ocf-dark --resolution 1400
python scripts/ocf.py artwork generate OCF-FND-002 --locale es --theme ocf-light --format jpeg
```

Core operation stays offline. Pillow/fontTools are optional artwork dependencies.
PNG/JPEG cache identity includes localized title, brand/theme configuration,
font bytes, resolution, output format and renderer version. Cache checksums are
verified. Explicit output paths refuse overwrites, including custom covers.

Custom themes are JSON files with `extends` pointing to a built-in theme or
another local theme file. Resolution validates the final schema and text
contrast (at least 4.5:1). Cycles and unknown fields fail. Explicit theme choice
wins over the surface default; per-call overrides win over inherited values.
`artwork theme` emits framework-neutral CSS tokens. The generated offline review
gallery consumes independent interface/artwork selections. OCF has no shipped
desktop application GUI; this gallery and token API do not claim one.

The default font is Pillow's bundled Aileron. For broader Unicode coverage,
select an installed appropriately licensed TTF/OTF with `--font FILE`; its
checksum participates in identity. Missing glyphs fail with code points instead
of silently drawing tofu. RTL text requires Pillow's RAQM shaping support.
Text wraps and scales within reserved title bounds. Rendering never invents a
translation; UI title fallback is recorded in the artifact settings.

Geometry/code follow the repository's Apache-2.0 license. Fonts and optional
raster artwork retain their separate licenses and review requirements. No
proprietary fonts, historical covers or third-party brand assets are bundled.
