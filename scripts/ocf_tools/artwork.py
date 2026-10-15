"""Original candidate vector branding and deterministic offline localized artwork."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import unicodedata
from html import escape
from pathlib import Path

from .artifact_names import ArtifactNamer
from .audio_defaults import overlay
from .indexes import load_function_by_id
from .locale import LocaleCatalog, normalize_tag
from .paths import REPO_ROOT, work_path
from .session_plans import digest
from .utils import OCFError, read_json_object, sha256_of_file, write_text_atomic
from .validators import _load_schema, validate_against_schema

BRAND = REPO_ROOT / "brand"


def identity() -> dict:
    data = json.loads((BRAND / "identity.json").read_text(encoding="utf-8"))
    errors = validate_against_schema(data, _load_schema("brand.schema.json"))
    if errors:
        raise OCFError("invalid brand identity: " + " | ".join(errors))
    return data


def contrast(a: str, b: str) -> float:
    def luminance(color):
        values = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
        return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def load_theme(
    reference: str | None = None,
    *,
    surface: str = "artwork",
    overrides: dict | None = None,
    _seen=(),
) -> dict:
    defaults = json.loads((BRAND / "surfaces.json").read_text())
    if surface not in ("ui", "artwork", "documentation"):
        raise OCFError("surface must be ui, artwork or documentation")
    reference = reference or defaults[surface]
    path = Path(reference)
    if not path.is_file():
        if "/" in reference or "\\" in reference or reference.startswith("."):
            raise OCFError("custom theme file does not exist")
        path = BRAND / "themes" / (reference + ".json")
    resolved = str(path.resolve())
    if resolved in _seen or len(_seen) > 8:
        raise OCFError("cyclic/excessive theme inheritance")
    try:
        data = read_json_object(path)
    except (OSError, ValueError) as exc:
        raise OCFError(f"cannot load theme {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise OCFError("theme must be a JSON object")
    if data.get("extends"):
        parent = data["extends"]
        if (path.parent / parent).is_file():
            parent = str(path.parent / parent)
        data = overlay(load_theme(parent, surface=surface, _seen=(*_seen, resolved)), data)
    data = overlay(data, overrides or {})
    errors = validate_against_schema(data, _load_schema("theme.schema.json"))
    if errors:
        raise OCFError("invalid theme: " + " | ".join(errors))
    ratio = contrast(data["palette"]["background"], data["palette"]["foreground"])
    if not math.isfinite(data["minimum_contrast"]) or ratio < data["minimum_contrast"]:
        raise OCFError(f"theme text contrast {ratio:.2f} is below {data['minimum_contrast']}")
    return data


def theme_tokens(surface: str = "ui", theme: str | None = None) -> dict:
    data = load_theme(theme, surface=surface)
    css = (
        ":root {\n"
        + "\n".join(f"  --ocf-{key}: {value};" for key, value in sorted(data["palette"].items()))
        + "\n}\n"
    )
    css = css.replace(
        "\n}", f"\n  --ocf-font-family: {data.get('ui_font_family', 'system-ui, sans-serif')};\n}}"
    )
    return {"surface": surface, "theme": data, "sha256": digest(data), "css": css}


def gallery(output: Path, *, ui_theme: str | None = None, artwork_theme: str | None = None) -> dict:
    themes = [p.stem for p in sorted((BRAND / "themes").glob("*.json"))]
    data = {
        name: {
            "palette": load_theme(name)["palette"],
            "variants": {v: brand_svg(v, name) for v in identity()["variants"]},
        }
        for name in themes
    }
    selected = {
        "ui": load_theme(surface="ui")["id"],
        "artwork": load_theme(surface="artwork")["id"],
    }
    for surface, reference in (("ui", ui_theme), ("artwork", artwork_theme)):
        if reference:
            value = load_theme(reference, surface=surface)
            key = reference if reference in themes else surface + "-custom"
            data[key] = {
                "palette": value["palette"],
                "ui_font_family": value.get("ui_font_family", "system-ui, sans-serif"),
                "variants": {v: brand_svg(v, reference) for v in identity()["variants"]},
            }
            selected[surface] = key
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    options = "".join(f'<option value="{escape(name)}">{escape(name)}</option>' for name in data)
    html = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>OCF original candidate review</title><style>
body{font-family:var(--font,system-ui),sans-serif;margin:2rem;background:var(--bg);color:var(--fg)}
select{font:inherit;margin:.5rem;padding:.4rem}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem}
article{border:1px solid var(--accent);padding:1rem}svg{width:100%;height:auto}label{display:inline-block}
</style><h1>OCF candidate review gallery</h1><p>Original procedural candidates. No final human design approval is recorded.</p>
<label>Interface theme <select id="ui">OPTIONS</select></label><label>Artwork theme <select id="art">OPTIONS</select></label><main id="cards"></main>
<script>const themes=PAYLOAD; const ui=document.getElementById('ui'),art=document.getElementById('art');
ui.value=UI_SELECTED; art.value=ART_SELECTED;
function render(){const p=themes[ui.value].palette;document.body.style.setProperty('--bg',p.background);document.body.style.setProperty('--fg',p.foreground);document.body.style.setProperty('--accent',p.accent);document.body.style.setProperty('--font',themes[ui.value].ui_font_family||'system-ui');
const cards=document.getElementById('cards');cards.replaceChildren();for(const [name,svg] of Object.entries(themes[art.value].variants)){const card=document.createElement('article');const label=document.createElement('h2');label.textContent=name;card.appendChild(label);const visual=document.createElement('div');visual.innerHTML=svg;card.appendChild(visual);cards.appendChild(card);}}
ui.addEventListener('change',render);art.addEventListener('change',render);render();</script></html>"""
    write_text_atomic(
        output,
        html.replace("OPTIONS", options)
        .replace("PAYLOAD", payload)
        .replace("UI_SELECTED", json.dumps(selected["ui"]))
        .replace("ART_SELECTED", json.dumps(selected["artwork"])),
        overwrite=False,
    )
    return {
        "path": str(output),
        "offline": True,
        "independent_controls": ["ui", "artwork"],
        "review_status": "candidate",
    }


def _star(geometry):
    x, y = geometry["center"]
    radius = geometry["star_radius"]
    return [
        (
            x + math.cos(i * math.pi / 4 - math.pi / 2) * (radius if i % 2 == 0 else radius * 0.28),
            y + math.sin(i * math.pi / 4 - math.pi / 2) * (radius if i % 2 == 0 else radius * 0.28),
        )
        for i in range(8)
    ]


def brand_svg(variant: str = "primary", theme: str | None = None) -> str:
    brand = identity()
    if variant not in brand["variants"]:
        raise OCFError("unknown brand variant")
    theme = theme or (
        "ocf-light"
        if variant == "light"
        else "ocf-minimal"
        if variant == "monochrome"
        else "ocf-dark"
    )
    data = load_theme(theme)
    p, g = data["palette"], brand["geometry"]
    width = 1600 if variant == "social" else 1000
    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 1000" role="img"><title>OCF original candidate — {escape(variant)}</title>',
        f'<rect width="{width}" height="1000" fill="{p["background"]}"/>',
        f'<g transform="translate({(width - 1000) // 2},0)">',
    ]
    x, y = g["center"]
    if data["effects"]["rings"]:
        body += [
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{p["accent"]}" stroke-width="5" opacity="0.65"/>'
            for r in g["rings"]
        ]
    a, b, c, d = g["path"]
    body.append(
        f'<path d="M {a[0]} {a[1]} C {b[0]} {b[1]} {c[0]} {c[1]} {d[0]} {d[1]}" fill="none" stroke="{p["secondary"]}" stroke-width="{g["path_width"]}" stroke-linecap="round"/>'
    )
    body.append(
        f'<polygon points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in _star(g))}" fill="{p["highlight"]}"/>'
    )
    if variant in ("primary", "social", "light", "dark"):
        body.append(
            f'<text x="500" y="830" text-anchor="middle" fill="{p["foreground"]}" font-family="sans-serif" font-size="42">Open Consciousness Functions</text>'
        )
    else:
        body.append(
            f'<text x="500" y="830" text-anchor="middle" fill="{p["foreground"]}" font-family="sans-serif" font-size="86">OCF</text>'
        )
    return "\n".join(body + ["</g></svg>\n"])


def _font_assets(font: str):
    try:
        from fontTools.ttLib import TTFont
        from PIL import ImageFont
    except ImportError as exc:
        raise OCFError(
            "artwork requires the optional artwork extra: pip install -e '.[artwork]'"
        ) from exc
    if font == "pillow-aileron":
        sample = ImageFont.load_default(size=32)
        raw = sample.path.getvalue()
    else:
        path = Path(os.path.expandvars(font)).expanduser()
        if not path.is_file():
            raise OCFError(
                "configured font is unavailable; supply an installed licensed TTF/OTF file"
            )
        raw = path.read_bytes()
    from fontTools.ttLib import TTLibError

    try:
        with TTFont(io.BytesIO(raw)) as parsed:
            glyphs = set(parsed.getBestCmap() or {})
    except (TTLibError, OSError, ValueError) as exc:
        raise OCFError("configured font is not a readable supported TTF/OTF") from exc
    return raw, glyphs


def _draw_emblem(draw, scale: float, brand: dict, data: dict):
    g, p = brand["geometry"], data["palette"]
    if data["logo_variant"] == "monochrome":
        p = {**p, **{k: p["foreground"] for k in ("accent", "secondary", "highlight")}}
    x, y = g["center"]
    if data["effects"]["rings"]:
        for radius in g["rings"]:
            draw.ellipse(
                tuple(v * scale for v in (x - radius, y - radius, x + radius, y + radius)),
                outline=p["accent"],
                width=max(1, round(3 * scale)),
            )
    points = []
    for i in range(101):
        t = i / 100
        coefficients = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t**3)
        points.append(
            tuple(
                sum(c * xy[j] for c, xy in zip(coefficients, g["path"], strict=True)) * scale
                for j in (0, 1)
            )
        )
    draw.line(
        points, fill=p["secondary"], width=max(1, round(g["path_width"] * scale)), joint="curve"
    )
    if data["effects"]["glow"]:
        draw.line(points, fill=p["highlight"], width=max(1, round(5 * scale)), joint="curve")
    draw.polygon([(a * scale, b * scale) for a, b in _star(g)], fill=p["highlight"])


def export_brand(
    output: Path, *, variant: str = "primary", theme: str | None = None, resolution: int = 1000
) -> dict:
    svg = brand_svg(variant, theme)
    if output.exists():
        raise OCFError("refusing to overwrite brand artwork")
    if output.suffix.lower() == ".svg":
        write_text_atomic(output, svg, overwrite=False)
    elif output.suffix.lower() == ".png":
        if not 256 <= resolution <= 4096:
            raise OCFError("brand PNG resolution must be 256..4096")
        from PIL import Image, ImageDraw, ImageFont

        data = load_theme(
            theme
            or (
                "ocf-light"
                if variant == "light"
                else "ocf-minimal"
                if variant == "monochrome"
                else "ocf-dark"
            )
        )
        brand = identity()
        raw, _ = _font_assets(data["font"])
        image = Image.new("RGB", (resolution * 2, resolution * 2), data["palette"]["background"])
        draw = ImageDraw.Draw(image)
        scale = resolution * 2 / 1000
        _draw_emblem(draw, scale, brand, data)
        label = brand["name"] if variant in ("primary", "social", "light", "dark") else "OCF"
        draw.text(
            (resolution, 830 * scale),
            label,
            anchor="mt",
            fill=data["palette"]["foreground"],
            font=ImageFont.truetype(io.BytesIO(raw), round(42 * scale)),
        )
        image = image.resize((resolution, resolution), Image.Resampling.LANCZOS)
        if variant == "social":
            canvas = Image.new(
                "RGB", (round(resolution * 1.6), resolution), data["palette"]["background"]
            )
            canvas.paste(image, (round(resolution * 0.3), 0))
            image = canvas
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as handle:
            image.save(handle, format="PNG", compress_level=9)
    else:
        raise OCFError("brand exports support .svg or .png")
    return {
        "path": str(output),
        "sha256": sha256_of_file(output),
        "variant": variant,
        "review_status": "candidate",
        "human_approval": None,
    }


def generate_cover(
    function_id: str,
    *,
    locale: str = "en-US",
    theme: str | None = None,
    resolution: int = 1400,
    format: str = "png",
    version: str | None = None,
    overrides: dict | None = None,
    output: Path | None = None,
    dry_run: bool = False,
    title_override: str | None = None,
) -> dict:
    if (
        type(resolution) is not int
        or not 256 <= resolution <= 4096
        or format not in ("png", "jpeg")
    ):
        raise OCFError("artwork requires 256..4096 pixels and png/jpeg format")
    if version is not None and (len(version) > 32 or any(ord(c) < 32 for c in version)):
        raise OCFError("cover version must be at most 32 printable characters")
    record = load_function_by_id(function_id)
    if record is None:
        raise OCFError("unknown function")
    locale = normalize_tag(locale)
    catalog = LocaleCatalog()
    from .release import _function_title

    localized_title, title_resolution = _function_title(function_id, locale, catalog)
    title = unicodedata.normalize(
        "NFC", title_override if title_override is not None else localized_title
    )
    if not title.strip() or title.strip().casefold() == function_id.casefold():
        raise OCFError("artwork requires a meaningful function title, not only its identifier")
    if any(word in title.casefold() for word in ("hemi-sync", "human plus", "monroe")):
        raise OCFError("OCF artwork cannot include third-party brand names")
    data = load_theme(theme, overrides=overrides)
    brand = identity()
    font_bytes, glyphs = _font_assets(data["font"])
    footer = function_id + (f" - {version}" if version else "")
    texts = [brand["name"], title, footer]
    missing = sorted(
        {ord(c) for text in texts for c in text if not c.isspace() and ord(c) not in glyphs}
    )
    if missing:
        raise OCFError(
            "font lacks required Unicode glyphs: "
            + ", ".join(f"U+{c:04X}" for c in missing)
            + "; configure a licensed font covering this locale"
        )
    from PIL import Image, ImageDraw, ImageFont, features
    from PIL import __version__ as pillow_version

    if any(unicodedata.bidirectional(c) in {"R", "AL", "AN"} for c in title) and not features.check(
        "raqm"
    ):
        raise OCFError("RTL artwork requires Pillow with RAQM shaping support")
    settings = {
        "brand": brand,
        "theme": data,
        "function_id": function_id,
        "title": title,
        "locale": locale,
        "title_locale": title_resolution["resolved_locale"],
        "title_resolution": title_resolution,
        "resolution": resolution,
        "format": format,
        "release_version": version,
        "font_sha256": hashlib.sha256(font_bytes).hexdigest(),
        "pillow": pillow_version,
        "freetype": features.version_module("freetype2"),
        "raqm": features.version("raqm"),
        "renderer_sha256": sha256_of_file(Path(__file__)),
    }
    if title_override is not None:
        settings["title_locale"] = "operator-supplied"
        settings["title_resolution"] = {
            "requested_locale": locale,
            "resolved_locale": "operator-supplied",
            "resource_key": None,
            "fallback": False,
            "source": "operator-title-override",
        }
    fingerprint = digest(settings)
    root = work_path("cache", "artwork", fingerprint)
    filename = ArtifactNamer().filename(
        function_id,
        title,
        locale,
        "png" if format == "png" else "jpg",
        variant="cover",
        version=version,
    )
    path = root / filename
    report_path = root / "artwork.json"
    if dry_run:
        return {
            "dry_run": True,
            "path": str(path),
            "settings": settings,
            "fingerprint": fingerprint,
            "review_status": "candidate",
            "human_approval": None,
        }
    if report_path.is_file() and path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                report.get("settings") == settings
                and report.get("fingerprint") == fingerprint
                and report.get("sha256") == sha256_of_file(path)
            ):
                report.update(cache="hit", review_status="candidate", human_approval=None)
                return _publish_cover(path, report, output)
        except (ValueError, OSError, AttributeError):
            pass
    output_resolution = resolution
    resolution *= 2
    image = Image.new("RGB", (resolution, resolution), data["palette"]["background"])
    draw = ImageDraw.Draw(image)
    scale = resolution / 1000
    p = data["palette"]
    if data["layout"] == "minimal":
        emblem = Image.new("RGB", image.size, p["background"])
        _draw_emblem(ImageDraw.Draw(emblem), scale, brand, data)
        size = round(resolution * 0.65)
        image.paste(
            emblem.resize((size, size), Image.Resampling.LANCZOS),
            ((resolution - size) // 2, round(resolution * 0.1)),
        )
        draw = ImageDraw.Draw(image)
    else:
        _draw_emblem(draw, scale, brand, data)
    fonts = {}

    def font(size):
        if size not in fonts:
            fonts[size] = ImageFont.truetype(io.BytesIO(font_bytes), max(1, round(size * scale)))
        return fonts[size]

    # Wrap whole words, or individual Unicode characters for long/CJK tokens.
    lines = []
    for size in range(70, 15, -1):
        current = ""
        lines = []
        for character in title:
            if draw.textlength(current + character, font=font(size)) > resolution * 0.84:
                split = current.rfind(" ")
                if split > 0:
                    lines.append(current[:split])
                    current = current[split + 1 :] + character
                else:
                    lines.append(current)
                    current = character
            else:
                current += character
        if current:
            lines.append(current)
        title_y = 650 if data["layout"] == "minimal" else 720
        title_boxes = [
            draw.textbbox(
                (resolution / 2, (title_y + i * size * 1.2) * scale),
                line,
                anchor="mt",
                font=font(size),
            )
            for i, line in enumerate(lines)
        ]
        if len(lines) <= 3 and all(
            box[0] >= resolution * 0.08 and box[2] <= resolution * 0.92 and box[3] <= 925 * scale
            for box in title_boxes
        ):
            break
    else:
        raise OCFError("localized title cannot fit safely; choose a supported layout/font")
    header_size = 30
    while (
        draw.textlength(brand["name"], font=font(header_size)) > resolution * 0.84
        and header_size > 12
    ):
        header_size -= 1
    draw.text(
        (resolution / 2, 55 * scale),
        brand["name"],
        anchor="mt",
        font=font(header_size),
        fill=p["foreground"],
    )
    for index, line in enumerate(lines):
        draw.text(
            (
                resolution / 2,
                ((650 if data["layout"] == "minimal" else 720) + index * size * 1.2) * scale,
            ),
            line,
            anchor="mt",
            font=font(size),
            fill=p["foreground"],
        )
    footer_size = 25
    while draw.textlength(footer, font=font(footer_size)) > resolution * 0.84 and footer_size > 12:
        footer_size -= 1
    draw.text(
        (resolution / 2, 965 * scale),
        footer,
        anchor="mb",
        font=font(footer_size),
        fill=p["foreground"],
    )
    header_box = draw.textbbox(
        (resolution / 2, 55 * scale), brand["name"], anchor="mt", font=font(header_size)
    )
    footer_box = draw.textbbox(
        (resolution / 2, 965 * scale), footer, anchor="mb", font=font(footer_size)
    )
    if any(
        box[0] < 0 or box[2] > resolution or box[1] < 0 or box[3] > resolution
        for box in (header_box, footer_box)
    ):
        raise OCFError("configured font cannot fit cover header/identifier safely")
    root.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image = image.resize((output_resolution, output_resolution), Image.Resampling.LANCZOS)
    image.save(
        buffer,
        format="PNG" if format == "png" else "JPEG",
        **({"compress_level": 9} if format == "png" else {"quality": 95, "subsampling": 0}),
    )
    from .paths import workspace_temp_file

    descriptor, temporary = workspace_temp_file(suffix="." + format)
    os.close(descriptor)
    temporary.write_bytes(buffer.getvalue())
    os.replace(temporary, path)
    from .paths import cleanup_workspace_temp

    cleanup_workspace_temp(temporary.parent)
    report = {
        "schema_version": "1.0",
        "settings": settings,
        "fingerprint": fingerprint,
        "sha256": sha256_of_file(path),
        "path": str(path),
        "review_status": "candidate",
        "human_approval": None,
        "cache": "miss",
        "title_lines": lines,
        "layout_bounds": {
            "title": [[round(v / 2, 2) for v in box] for box in title_boxes],
            "header": [round(v / 2, 2) for v in header_box],
            "footer": [round(v / 2, 2) for v in footer_box],
        },
    }
    write_text_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return _publish_cover(path, report, output)


def _publish_cover(path: Path, report: dict, output: Path | None):
    if output:
        import shutil

        if output.exists():
            raise OCFError("refusing to overwrite existing artwork")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as target, path.open("rb") as source:
            shutil.copyfileobj(source, target)
        report = {**report, "path": str(output)}
    return report
