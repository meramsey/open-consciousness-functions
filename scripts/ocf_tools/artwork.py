"""Original candidate vector branding and deterministic offline localized artwork."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
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
    reader=None,
    lookup=None,
) -> dict:
    defaults = json.loads((BRAND / "surfaces.json").read_text())
    if surface not in ("ui", "artwork", "documentation"):
        raise OCFError("surface must be ui, artwork or documentation")
    reference = reference or defaults[surface]
    path = lookup("theme", reference) if lookup is not None else Path(reference)
    if lookup is None and not path.is_file():
        if "/" in reference or "\\" in reference or reference.startswith("."):
            raise OCFError("custom theme file does not exist")
        path = BRAND / "themes" / (reference + ".json")
    resolved = str(path.resolve())
    if resolved in _seen or len(_seen) > 8:
        raise OCFError("cyclic/excessive theme inheritance")
    try:
        data = reader(path) if reader is not None else read_json_object(path)
    except (OSError, ValueError) as exc:
        raise OCFError(f"cannot load theme {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise OCFError("theme must be a JSON object")
    if data.get("extends"):
        parent = data["extends"]
        if lookup is None and (path.parent / parent).is_file():
            parent = str(path.parent / parent)
        elif lookup is not None and (
            Path(parent).suffix == ".json" or "/" in parent or "\\" in parent
        ):
            parent = str(path.parent / parent)
        data = overlay(
            load_theme(
                parent, surface=surface, _seen=(*_seen, resolved), reader=reader, lookup=lookup
            ),
            data,
        )
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
    themes = [
        p.stem
        for p in sorted((BRAND / "themes").glob("*.json"))
        if load_theme(p.stem).get("brand_revision", "0.1.0") == "0.1.0"
    ]
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
    for surface, requested in (("ui", ui_theme), ("artwork", artwork_theme)):
        reference = requested or load_theme(surface=surface)["id"]
        if reference:
            value = load_theme(reference, surface=surface)
            key = (
                reference
                if reference in themes or (BRAND / "themes" / (reference + ".json")).is_file()
                else surface + "-custom"
            )
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
</style><h1>OCF candidate review gallery</h1><p>Versioned original/imported candidates. No final human design approval is recorded.</p>
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
    if data.get("brand_revision") == "0.3.0":
        from .brand_import import asset, verify

        verify()
        return asset(variant, data).read_text(encoding="utf-8")
    if data.get("brand_revision") == "0.2.0":
        from . import brand_refinement

        raw, _ = _font_assets(data["font"])
        return brand_refinement.vector(
            brand_refinement.scene(data, brand_refinement.composition_for(variant)), raw
        )
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

    def stroke(color, width):
        # A filled normal-offset outline avoids Pillow's short-segment joint
        # artifacts on a densely sampled, wide curved stroke.
        left, right = [], []
        for i, (x, y) in enumerate(points):
            before, after = points[max(0, i - 1)], points[min(len(points) - 1, i + 1)]
            dx, dy = after[0] - before[0], after[1] - before[1]
            length = math.hypot(dx, dy) or 1
            nx, ny = -dy / length * width / 2, dx / length * width / 2
            left.append((x + nx, y + ny))
            right.append((x - nx, y - ny))
        draw.polygon(left + list(reversed(right)), fill=color)
        for x, y in (points[0], points[-1]):
            draw.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=color)

    stroke(p["secondary"], g["path_width"] * scale)
    if data["effects"]["glow"]:
        stroke(p["highlight"], 5 * scale)
    draw.polygon([(a * scale, b * scale) for a, b in _star(g)], fill=p["highlight"])


def export_brand(
    output: Path, *, variant: str = "primary", theme: str | None = None, resolution: int = 1000
) -> dict:
    selected = load_theme(
        theme
        or (
            "ocf-light"
            if variant == "light"
            else "ocf-minimal"
            if variant == "monochrome"
            else "ocf-dark"
        )
    )
    if selected.get("brand_revision") == "0.3.0":
        from .brand_import import export

        return export(output, variant, selected, resolution)
    if selected.get("brand_revision") == "0.2.0":
        from .brand_refinement import export

        raw, _ = _font_assets(selected["font"])
        return export(output, variant, selected, raw, resolution)
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


def select_theme(record, explicit: str | None = None, implementation: dict | None = None):
    """Select only a reference/provenance; omitted selection stays inherited."""
    if explicit:
        return explicit, "explicit"
    if (implementation or {}).get("artwork_theme"):
        return implementation["artwork_theme"], "audio-implementation"
    if record.data.get("audio", {}).get("artwork_theme"):
        return record.data["audio"]["artwork_theme"], "function"
    return None, "artwork-surface-default"


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
    status_label: str | None = None,
    show_cue: bool = True,
    show_description: bool = True,
    strict_locale: bool = True,
) -> dict:
    if (
        type(resolution) is not int
        or not 128 <= resolution <= 4096
        or format not in ("png", "jpeg")
    ):
        raise OCFError("artwork requires 128..4096 pixels and png/jpeg format")
    if version is not None and (len(version) > 32 or any(ord(c) < 32 for c in version)):
        raise OCFError("cover version must be at most 32 printable characters")
    if status_label is not None and (
        len(status_label) > 32 or any(ord(c) < 32 for c in status_label)
    ):
        raise OCFError("cover status label must be at most 32 printable characters")
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
    theme_reference, theme_source = select_theme(record, theme)
    data = load_theme(theme_reference, overrides=overrides)
    if data.get("brand_revision") == "0.2.0" and resolution < 320:
        raise OCFError("refined covers require at least 320 pixels for legible typography")
    if data.get("brand_revision") not in {"0.2.0", "0.3.0"} and resolution < 256:
        raise OCFError("baseline covers require at least 256 pixels")
    content = None
    cue_text = description_text = None
    description_color = data["palette"]["foreground"]
    if data.get("brand_revision") == "0.3.0" and (show_cue or show_description):
        from .artwork_content import function_artwork_content
        from .locale import LocalizationError, locale_language

        if strict_locale and locale_language(
            title_resolution["resolved_locale"]
        ) != locale_language(locale):
            raise LocalizationError(
                "strict artwork title cannot silently fall back across languages"
            )
        content = function_artwork_content(
            function_id, locale, catalog=catalog, strict=strict_locale
        )
        cue_text = (content["primary"] or {}).get("display_cue") if show_cue else None
        description_text = content["description"] if show_description else None
        if (
            cue_text
            and contrast(data["palette"]["accent"], data["palette"]["background"])
            < data["minimum_contrast"]
        ):
            raise OCFError("artwork cue accent contrast is below the theme minimum")
        foreground, background = data["palette"]["foreground"], data["palette"]["background"]
        for weight in (0.72, 0.80, 0.90, 1.0):
            description_color = "#" + "".join(
                f"{round(int(foreground[i : i + 2], 16) * weight + int(background[i : i + 2], 16) * (1 - weight)):02X}"
                for i in (1, 3, 5)
            )
            if contrast(description_color, background) >= data["minimum_contrast"]:
                break
    if data.get("brand_revision") == "0.2.0":
        from .brand_refinement import identity as refined_identity

        brand = refined_identity()
    elif data.get("brand_revision") == "0.3.0":
        from .brand_import import identity as imported_identity

        brand = imported_identity()
    else:
        brand = identity()
    font_bytes, glyphs = _font_assets(data["font"])
    version_label = (
        f"v{version}" if version and re.fullmatch(r"\d+\.\d+\.\d+", version) else version
    )
    suffix = (f" - {version_label}" if version_label else "") + (
        f" - {status_label}" if status_label else ""
    )
    footer = function_id + suffix
    texts = [brand["name"], title, footer, cue_text or "", description_text or ""]
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

    if any(
        unicodedata.bidirectional(c) in {"R", "AL", "AN"} for text in texts for c in text
    ) and not features.check("raqm"):
        raise OCFError("RTL artwork requires Pillow with RAQM shaping support")
    settings = {
        "brand": brand,
        "theme": data,
        "theme_selection": theme_source,
        "function_id": function_id,
        "title": title,
        "locale": locale,
        "title_locale": title_resolution["resolved_locale"],
        "title_resolution": title_resolution,
        "resolution": resolution,
        "format": format,
        "release_version": version,
        "version_label": version_label,
        "status_label": status_label,
        "font_sha256": hashlib.sha256(font_bytes).hexdigest(),
        "pillow": pillow_version,
        "freetype": features.version_module("freetype2"),
        "raqm": features.version("raqm"),
        "renderer_sha256": sha256_of_file(Path(__file__)),
        "function_content": content,
        "show_cue": show_cue,
        "show_description": show_description,
        "strict_locale": strict_locale,
        "cue_color": data["palette"]["accent"],
        "description_color": description_color,
    }
    if data.get("brand_revision") == "0.3.0":
        from .brand_import import asset, verify

        settings["import_provenance"] = verify()
        settings["import_renderer_sha256"] = sha256_of_file(
            Path(__file__).with_name("brand_import.py")
        )
        settings["supplied_emblem"] = asset("icon", data, "png").name
        settings["composition"] = "supplied-emblem-with-localized-ocf-layout"
        footer = function_id + " / " + locale + suffix
        # Validate the final footer, including the locale, through the same font contract.
        if any(ord(c) not in glyphs for c in footer if not c.isspace()):
            raise OCFError("font lacks required Unicode glyphs for cover metadata")
        from .brand_import import cover_layout

        imported_layout = cover_layout(
            title, footer, font_bytes, resolution, cue=cue_text, description=description_text
        )
        settings["content_layout"] = {
            key: value for key, value in imported_layout.items() if key not in {"nodes", "bounds"}
        }
    if data.get("brand_revision") == "0.2.0":
        settings["refinement_renderer_sha256"] = sha256_of_file(
            Path(__file__).with_name("brand_refinement.py")
        )
        from .brand_refinement import fit_title, scene

        refined_graph = fit_title(scene(data, "album", title=title, identifier=footer), font_bytes)
    if title_override is not None:
        settings["title_locale"] = "operator-supplied"
        settings["title_resolution"] = {
            "requested_locale": locale,
            "resolved_locale": "operator-supplied",
            "resource_key": None,
            "fallback": False,
            "source": "operator-title-override",
        }
    settings["visible_text"] = [
        brand["name"],
        title,
        *([cue_text] if cue_text else []),
        *([description_text] if description_text and resolution >= 512 else []),
        footer,
    ]
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
    if data.get("brand_revision") == "0.3.0":
        from .brand_import import cover_raster

        return _save_cover(
            cover_raster(
                imported_layout, data, font_bytes, resolution, description_color=description_color
            ),
            settings,
            fingerprint,
            path,
            report_path,
            output,
            imported_layout["title_lines"],
            imported_layout["bounds"],
        )
    if data.get("brand_revision") == "0.2.0":
        from .brand_refinement import _text_layout, raster, scene

        image, graph = raster(refined_graph, font_bytes, resolution)
        factor = resolution / graph["width"]
        text_nodes = [node for node in graph["nodes"] if node["kind"] == "text"]
        header_boxes = [_text_layout(node, font_bytes)[3] for node in text_nodes[:3]]
        header_box = [
            min(box[0] for box in header_boxes),
            min(box[1] for box in header_boxes),
            max(box[2] for box in header_boxes),
            max(box[3] for box in header_boxes),
        ]
        footer_box = _text_layout(text_nodes[-1], font_bytes)[3]
        bounds = {
            "title": [[round(v * factor, 2) for v in box] for box in graph["title_boxes"]],
            "header": [round(v * factor, 2) for v in header_box],
            "footer": [round(v * factor, 2) for v in footer_box],
        }
        return _save_cover(
            image, settings, fingerprint, path, report_path, output, graph["title_lines"], bounds
        )
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
    image = image.resize((output_resolution, output_resolution), Image.Resampling.LANCZOS)
    bounds = {
        "title": [[round(v / 2, 2) for v in box] for box in title_boxes],
        "header": [round(v / 2, 2) for v in header_box],
        "footer": [round(v / 2, 2) for v in footer_box],
    }
    return _save_cover(image, settings, fingerprint, path, report_path, output, lines, bounds)


def _save_cover(image, settings, fingerprint, path, report_path, output, lines, bounds):
    path.parent.mkdir(parents=True, exist_ok=True)
    format = settings["format"]
    buffer = io.BytesIO()
    if format == "jpeg":
        image = image.convert("RGB")
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
        "layout_bounds": bounds,
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
