# Original candidate OCF visual identity

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
