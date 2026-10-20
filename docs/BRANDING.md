# Original candidate OCF visual identity

## New-cover default and repository presentation

New artwork without an explicit theme uses `ocf-cosmic-dark`, the imported 0.3.0
dark companion theme. This changes only `brand/surfaces.json`'s artwork surface;
UI remains `ocf-light`, documentation remains `ocf-minimal`, and existing covers
are not overwritten. `ocf-cosmic-light`, `ocf-cosmic-minimal`, custom files and
the earlier `ocf-dark`/refined themes remain explicit choices.

Cover precedence is explicit custom image, explicit theme, optional registered
`artwork_theme` in an audio implementation or function's `audio` metadata, then
the artwork-surface default for new generated covers. Function records and
implementations have not been edited to add these optional fields. Release
packaging still requires explicit/custom or configured artwork selection;
generating a default candidate does not grant publication approval.

The README uses a native-resolution crop of the supplied cinematic reference,
without a redraw or upscaling the export. The supplied high-resolution social
PNG remains an exact copy. [Presentation provenance and social-preview setup](../brand/versions/0.3.0/presentation/README.md)
record source/export hashes and explain the native reference resolution limit.
No GitHub repository social-preview setting was changed automatically.

The default cover renderer uses supplied companion pixels with localized OCF
title layout; it does not invent a high-resolution cinematic master or claim
that its vector companion reproduces the reference board exactly. Formal
candidate approval remains unset. Imported originals and previous brand
geometry/assets remain unchanged.

## Supplied Cosmic Path import 0.3.0

Private full-session listening copies use the same artwork generator through
`audio export-audition`, including default dark, light/custom overrides and
explicit `--no-artwork`. See [private listening exports](AUDIO_PIPELINE.md#private-listening-exports-from-completed-sessions).
The visible `vX.Y.Z` label is the hash-bound audition edition, independent of
brand version 0.3.0. Registered release covers likewise receive their resolved
audio/release version even when no CLI version override is supplied.

The [offline comparison gallery](../brand/versions/0.3.0/gallery/index.html)
compares the actual supplied artwork with 0.2.0, including 32/64/128-pixel app
icons, full-resolution 1200 × 1200 albums and 1280 × 640 GitHub social artwork.
The six cinematic reference images are retained and explicitly labeled.
This is an unapproved candidate; existing 0.1.0/0.2.0 and surface defaults remain.

Original files live unchanged in
`brand/imports/ocf-cosmic-path-brand-kit-v1/`: 10 SVGs, 14 deployable PNGs,
six reference PNGs, one review sheet and two instruction documents, plus the
manifest. `brand/versions/0.3.0/identity.json` pins that manifest's SHA-256.
`artwork import-review` checks all 33 supplied entries, byte counts, dimensions,
inventory completeness and checksums. PNGs are stored through existing Git LFS;
use `git lfs pull` after cloning. The supplied ZIP is local staging only.

Fidelity limitation: the supplied SVG/PNG companions are a vector interpretation,
not exact copies of the richer cinematic board. Original brand exports copy
supplied bytes, without redrawing or recoloring. SVG text uses system fallback
fonts; the kit contains no fonts, so its text appearance can vary by viewer.
References are comparison material, not production album masters. A cinematic
production identity needs separately supplied high-resolution masters and human
visual approval. No claim of identical cinematic reproduction is made.

Opt in with `ocf-cosmic-dark`, `ocf-cosmic-light` or `ocf-cosmic-minimal`.
Custom JSON themes can extend any of them. Interface CSS palette/font tokens
and album theme choices remain independent; custom palette changes affect the
interface and cover framing/text, not the immutable supplied emblem pixels.
The kit has one dark app icon and one social design; selecting light/minimal
does not invent new versions of those supplied compositions.

Localized album generation uses the established OCF title-layout machinery
with the supplied emblem PNG, not a procedural replacement. It includes the
localized function title, function ID, requested locale and release version.
UI-title fallback, Unicode/font validation, layout bounds, cache integrity and
operator title overrides use the existing contracts. These are clearly labeled
derived compositions, separate from the unchanged supplied Sleep Easy albums.
The original placeholder SVG template is retained as source material; it is
never passed directly to the release encoder with unresolved placeholders.
`artwork brand --variant album` exports the unchanged supplied example album;
use `artwork generate FUNCTION_ID` for actual localized function covers.

```bash
python scripts/ocf.py artwork import-review
python scripts/ocf.py artwork import-review --output .ocf-work/renders/cosmic-review
python scripts/ocf.py artwork import-review --output brand/versions/0.3.0/gallery --check
python scripts/ocf.py artwork theme --surface ui --theme ocf-cosmic-light
python scripts/ocf.py artwork generate OCF-SLP-005 --locale es --theme ocf-cosmic-dark --resolution 1200
python scripts/ocf.py artwork brand --variant app --theme ocf-cosmic-dark --resolution 32 --output .ocf-work/renders/cosmic-app-32.png
```

`import-review --ui-theme FILE --artwork-theme FILE` also supports independent
custom review choices. Comparison generation refuses an existing directory.
Brand exports keep the supplied native dimensions (the app icon selects an
exact supplied size when available); `--resolution` does not resample originals.
Generated localized covers support PNG/JPEG and the existing resolution range,
with at least 320 pixels for legible typography.

Existing `audio release --artwork-theme` integration records candidate brand
0.3.0 and configuration fingerprints. Explicit custom `--artwork` still wins.
Approval remains false. Embedding verification uses local synthetic audio with
real MP3/FLAC encoding, metadata read-back and byte-identical cover extraction;
it does not require packaging or publishing a public release:

```bash
python -m pytest tests/test_brand_import.py tests/test_artwork.py tests/test_brand_refinement.py tests/test_release.py
```

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

Baseline geometry/code follow the repository's Apache-2.0 license. Fonts and optional
raster artwork retain their separate licenses and review requirements. No
proprietary fonts or historical third-party covers are bundled. The supplied
0.3.0 kit retains its own candidate provenance and human release-review status.
