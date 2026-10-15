"""OCF 0.2.0 visual candidate: shared vector scene, offline raster, comparison gallery."""

from __future__ import annotations

import hashlib
import io
import json
import math
import random
from html import escape
from pathlib import Path

from .paths import REPO_ROOT
from .utils import OCFError, read_json_object, sha256_of_file, write_text_atomic
from .validators import _load_schema, validate_against_schema

VERSION = "0.2.0"
SOURCE = REPO_ROOT / "brand" / "versions" / VERSION / "identity.json"


def identity() -> dict:
    data = read_json_object(SOURCE)
    errors = validate_against_schema(data, _load_schema("brand-refinement.schema.json"))
    if errors:
        raise OCFError("invalid refined identity: " + " | ".join(errors))
    return data


def _ribbon(geometry, pose):
    points = []
    controls = geometry["path"]
    for segment in (controls[:4], controls[3:]):
        for i in range(81):
            if points and i == 0:
                continue
            t = i / 80
            weights = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t**3)
            points.append(
                tuple(sum(w * p[j] for w, p in zip(weights, segment, strict=True)) for j in (0, 1))
            )
    sx, sy, ox, oy = pose
    left, right = [], []
    for i, (x, y) in enumerate(points):
        before, after = points[max(0, i - 1)], points[min(len(points) - 1, i + 1)]
        dx, dy = after[0] - before[0], after[1] - before[1]
        length = math.hypot(dx, dy) or 1
        progress = i / (len(points) - 1)
        width = (
            geometry["path_tip_width"]
            + (geometry["path_base_width"] - geometry["path_tip_width"]) * (1 - progress) ** 1.45
        )
        nx, ny = -dy / length * width / 2, dx / length * width / 2
        left.append(((x + nx) * sx + ox, (y + ny) * sy + oy))
        right.append(((x - nx) * sx + ox, (y - ny) * sy + oy))
    return left, right


def scene(
    theme: dict, composition: str, *, title: str = "Sleep Easy", identifier: str = "OCF-SLP-005"
) -> dict:
    brand = identity()
    if composition not in brand["compositions"]:
        raise OCFError("unknown refined composition")
    layout = brand["compositions"][composition]
    width, height = layout["width"], layout["height"]
    p, g = theme["palette"], brand["geometry"]
    finish = theme.get("finish", "dark")
    simple = finish == "minimal" or composition == "icon"
    light = finish == "light"
    sx, sy, ox, oy = layout["emblem"]
    cx, cy = g["center"][0] * sx + ox, g["center"][1] * sy + oy

    def color(name, fallback):
        return p.get(name, p[fallback])

    gradients = {
        "background": {
            "kind": "linear",
            "range": [0, height],
            "stops": [
                [0, p["background"], 1],
                [0.52, color("surface", "background"), 1],
                [1, p["background"], 1],
            ],
        },
        "rings": {
            "kind": "linear",
            "range": [cy - 350 * sy, cy + 350 * sy],
            "stops": [
                [0, p["accent"], 1],
                [0.45, p["accent"], 1],
                [0.8, p["secondary"], 1],
                [1, color("rose", "secondary"), 1],
            ],
        },
        "path": {
            "kind": "linear",
            "range": [cy, 930 * sy + oy],
            "stops": [
                [0, p["highlight"], 1],
                [0.18, p["accent"], 1],
                [0.62, p["secondary"], 1],
                [0.88, color("rose", "secondary"), 0.9],
                [1, color("rose", "secondary"), 0],
            ],
        },
        "path-glint": {
            "kind": "linear",
            "range": [cy, 930 * sy + oy],
            "stops": [
                [0, p["highlight"], 0.6],
                [0.55, p["foreground"] if not light else p["background"], 0.3],
                [0.85, p["foreground"] if not light else p["background"], 0.16],
                [1, p["background"], 0],
            ],
        },
        "path-shadow": {
            "kind": "linear",
            "range": [cy, 930 * sy + oy],
            "stops": [
                [0, p["foreground"] if light else p["background"], 0.12],
                [0.65, p["foreground"] if light else p["background"], 0.18],
                [1, p["background"], 0],
            ],
        },
        "gold": {
            "kind": "linear",
            "range": [cy - 50 * sy, cy + 50 * sy],
            "stops": [
                [0, p["highlight"], 1],
                [0.4, p["foreground"] if not light else p["highlight"], 1],
                [1, color("gold_shadow", "highlight"), 1],
            ],
        },
        "cyan-glow": {
            "kind": "radial",
            "stops": [
                [0, p["accent"], 0.26 if not light else 0.10],
                [0.5, p["accent"], 0.09],
                [1, p["accent"], 0],
            ],
        },
        "violet-glow": {
            "kind": "radial",
            "stops": [
                [0, color("atmosphere", "secondary"), 0.75 if not light else 0.7],
                [0.55, color("atmosphere", "secondary"), 0.18],
                [1, color("atmosphere", "secondary"), 0],
            ],
        },
        "gold-glow": {
            "kind": "radial",
            "stops": [
                [0, p["highlight"], 0.62 if not light else 0.16],
                [0.18, p["highlight"], 0.25 if not light else 0.08],
                [0.55, p["highlight"], 0.07],
                [1, p["highlight"], 0],
            ],
        },
    }
    nodes = []

    def node(kind, **values):
        nodes.append({"kind": kind, **values})

    node("rect", box=[0, 0, width, height], fill=p["background"] if simple else "@background")
    if not simple:
        node(
            "ellipse",
            box=[cx - 650 * sx, cy - 500 * sy, cx + 450 * sx, cy + 500 * sy],
            fill="@cyan-glow",
        )
        node(
            "ellipse",
            box=[cx - 500 * sx, cy - 150 * sy, cx + 700 * sx, cy + 700 * sy],
            fill="@violet-glow",
            opacity=0.55 if light else 0.8,
        )
        if composition in {"album", "social"} and not light:
            rng = random.Random(2302)
            for _ in range(24):
                x, y = rng.uniform(0.08, 0.93) * width, rng.uniform(0.12, 0.73) * height
                radius = rng.uniform(0.6, 1.2)
                node(
                    "ellipse",
                    box=[x - radius, y - radius, x + radius, y + radius],
                    fill=p["foreground"],
                    opacity=0.22,
                )
    for i, ring in enumerate(g["rings"]):
        r = ring["radius"]
        box = [cx - r * sx, cy - r * sy, cx + r * sx, cy + r * sy]
        stroke_width = (max(ring["width"], 12) if simple else ring["width"]) * math.sqrt(sx * sy)
        if not simple:
            node(
                "arc",
                box=box,
                start=0,
                end=359.99,
                width=max(1.2, stroke_width * 0.18),
                fill=color("ring_shadow", "accent"),
                opacity=0.7 if light else 0.4,
            )
            if theme["effects"]["glow"] and not light:
                node(
                    "arc",
                    box=box,
                    start=ring["start"],
                    end=ring["end"],
                    width=stroke_width * 3,
                    fill=p["accent"],
                    opacity=0.045,
                )
            node(
                "arc",
                box=box,
                start=ring["start"],
                end=ring["end"],
                width=stroke_width + 4 * sx,
                fill=color("ring_shadow", "accent"),
                opacity=0.38,
            )
        if theme["effects"]["rings"]:
            node(
                "arc",
                box=box,
                start=ring["start"],
                end=ring["end"],
                width=stroke_width,
                fill=p["foreground"] if simple else "@rings",
                opacity=1 if simple else 0.92,
            )
            if not simple:
                node(
                    "arc",
                    box=box,
                    start=ring["start"] + 8,
                    end=ring["start"] + 126,
                    width=max(1.0, stroke_width * 0.2),
                    fill=p["foreground"] if not light else p["background"],
                    opacity=0.6 if not light else 0.5,
                )
    left, right = _ribbon(g, layout["emblem"])
    polygon = left + list(reversed(right))
    if not simple:
        node(
            "polygon",
            points=[(x + 3 * sx, y + 6 * sy) for x, y in polygon],
            fill="@path-shadow",
        )
    node("polygon", points=polygon, fill=p["foreground"] if simple else "@path")
    if not simple:
        strip_a = [
            (a[0] * 0.88 + b[0] * 0.12, a[1] * 0.88 + b[1] * 0.12)
            for a, b in zip(left, right, strict=True)
        ]
        strip_b = [
            (a[0] * 0.62 + b[0] * 0.38, a[1] * 0.62 + b[1] * 0.38)
            for a, b in zip(left, right, strict=True)
        ]
        node(
            "polygon",
            points=strip_a + list(reversed(strip_b)),
            fill="@path-glint",
            opacity=1 if not light else 0.65,
        )
        node("line", points=left, width=max(1, 1.3 * sx), fill="@path-glint", opacity=0.8)
    if not simple and theme["effects"]["glow"]:
        node(
            "ellipse",
            box=[cx - 145 * sx, cy - 145 * sy, cx + 145 * sx, cy + 145 * sy],
            fill="@gold-glow",
        )
        node(
            "ellipse",
            box=[cx - 52 * sx, cy - 52 * sy, cx + 52 * sx, cy + 52 * sy],
            fill="@gold-glow",
        )
        for dx, dy in ((95 * sx, 0), (0, 100 * sy)):
            node(
                "line",
                points=[(cx - dx, cy - dy), (cx + dx, cy + dy)],
                width=max(0.8, sx),
                fill=p["highlight"],
                opacity=0.38 if not light else 0.25,
            )
    radius = g["star_radius"] * (0.88 if simple else 1)
    star = [
        (
            cx
            + math.cos(i * math.pi / 4 - math.pi / 2)
            * (radius if i % 2 == 0 else radius * 0.17)
            * sx,
            cy
            + math.sin(i * math.pi / 4 - math.pi / 2)
            * (radius * 1.2 if i % 2 == 0 else radius * 0.17)
            * sy,
        )
        for i in range(8)
    ]
    node("polygon", points=star, fill=p["foreground"] if simple else "@gold")
    if not simple:
        radius = g["core_radius"]
        node(
            "ellipse",
            box=[cx - radius * sx, cy - radius * sy, cx + radius * sx, cy + radius * sy],
            fill=p["foreground"] if not light else p["background"],
        )

    def text(value, x, y, size, align="left", tracking=0):
        node(
            "text",
            text=value,
            x=x,
            y=y,
            size=size,
            align=align,
            tracking=tracking,
            fill=p["foreground"],
        )

    if composition == "logo":
        text("Open Consciousness", 595, 166, 72)
        text("Functions", 595, 268, 100)
        node("line", points=[(598, 400), (720, 400)], width=3, fill=p["highlight"])
    elif composition == "social":
        text("OCF", 110, 110, 62, tracking=6)
        for line, y in zip(("Open", "Consciousness", "Functions"), (250, 354, 458), strict=True):
            text(line, 110, y, 94)
        node("line", points=[(114, 604), (250, 604)], width=4, fill=p["highlight"])
    elif composition == "album":
        text("Open Consciousness", 65, 48, 38)
        text("Functions", 65, 96, 38)
        text("OCF", 935, 54, 48, "right", 3)
        # Real localized cover text is fitted later using the supplied font.
        node("cover-title", text=title, fill=p["foreground"])
        text(identifier, 65, 952, 32)
    return {
        "brand": brand,
        "width": width,
        "height": height,
        "composition": composition,
        "theme": theme,
        "gradients": gradients,
        "nodes": nodes,
        "corner_radius": 190 if composition == "app" else 0,
    }


def _font(raw, size):
    from PIL import ImageFont

    return ImageFont.truetype(io.BytesIO(raw), max(1, round(size)))


def _text_layout(node, raw):
    font = _font(raw, node["size"])
    text, tracking = node["text"], node.get("tracking", 0)
    width = font.getlength(text) + max(0, len(text) - 1) * tracking
    x = node["x"] - (
        width / 2 if node.get("align") == "center" else width if node.get("align") == "right" else 0
    )
    bounds = font.getbbox(text, anchor="ls")
    baseline = node["y"] - bounds[1]
    return (
        font,
        x,
        baseline,
        [x + bounds[0], node["y"], x + width, node["y"] + bounds[3] - bounds[1]],
    )


def fit_title(graph, raw):
    if "title_boxes" in graph:
        return graph
    result = []
    boxes, title_lines = [], []
    for node in graph["nodes"]:
        if node["kind"] != "cover-title":
            result.append(node)
            continue
        for size in range(88, 43, -1):
            font = _font(raw, size)
            lines, current = [], ""
            for char in node["text"].strip():
                if font.getlength(current + char) > 870:
                    at = current.rfind(" ")
                    if at > 0:
                        lines.append(current[:at])
                        current = current[at + 1 :] + char
                    else:
                        lines.append(current)
                        current = char
                else:
                    current += char
            if current:
                lines.append(current)
            start = 808 if len(lines) == 1 else 772
            proposed = [
                {
                    "kind": "text",
                    "text": line,
                    "x": 65,
                    "y": start + i * size * 1.12,
                    "size": size,
                    "align": "left",
                    "fill": node["fill"],
                    "tracking": 0,
                }
                for i, line in enumerate(lines)
            ]
            measured = [_text_layout(n, raw)[3] for n in proposed]
            if 0 < len(lines) <= 2 and all(b[2] <= 935 and b[3] <= 923 for b in measured):
                result.extend(proposed)
                boxes.extend(measured)
                title_lines = lines
                break
        else:
            raise OCFError(
                "refined cover title cannot fit legibly; use a shorter explicit title or the baseline layout"
            )
    for node in result:
        if node["kind"] == "text":
            box = _text_layout(node, raw)[3]
            if (
                box[0] < 0
                or box[2] > graph["width"] - 20
                or box[1] < 0
                or box[3] > graph["height"] - 15
            ):
                raise OCFError(
                    "refined typography cannot fit legibly; shorten the explicit text/version or choose another font/layout"
                )
    graph["nodes"] = result
    graph["title_lines"], graph["title_boxes"] = title_lines, boxes
    return graph


def _rgba(color, opacity=1):
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5)) + (round(255 * opacity),)


def _sample(stops, t):
    t = min(1, max(0, t))
    for a, b in zip(stops, stops[1:]):
        if t <= b[0]:
            amount = (t - a[0]) / (b[0] - a[0])
            ca, cb = _rgba(a[1], a[2]), _rgba(b[1], b[2])
            return tuple(round(x + (y - x) * amount) for x, y in zip(ca, cb, strict=True))
    return _rgba(stops[-1][1], stops[-1][2])


def raster(graph, raw, width: int):
    from PIL import Image, ImageChops, ImageDraw

    if not 32 <= width <= 4096:
        raise OCFError("refined export width must be 32..4096")
    minimum = (
        32
        if graph["composition"] in {"icon", "app"}
        else 640
        if graph["composition"] == "social"
        else 320
    )
    if width < minimum:
        raise OCFError(
            f"{graph['composition']} needs at least {minimum} pixels for legible typography"
        )
    graph = fit_title(graph, raw)
    final = (width, round(width * graph["height"] / graph["width"]))
    working_width = max(256, width * 2) if width <= 1600 else width
    scale = working_width / graph["width"]
    size = (working_width, round(graph["height"] * scale))
    image = Image.new("RGBA", size)
    gradients = {}
    for node in graph["nodes"]:
        if node["kind"] == "text":
            _, x, baseline, _ = _text_layout(node, raw)
            draw = ImageDraw.Draw(image)
            font = _font(raw, node["size"] * scale)
            if node.get("tracking", 0):
                offset = 0
                for char in node["text"]:
                    draw.text(
                        ((x + offset) * scale, baseline * scale),
                        char,
                        font=font,
                        anchor="ls",
                        fill=node["fill"],
                    )
                    offset += _font(raw, node["size"]).getlength(char) + node["tracking"]
            else:
                draw.text(
                    (x * scale, baseline * scale),
                    node["text"],
                    font=font,
                    anchor="ls",
                    fill=node["fill"],
                )
            continue
        mask = Image.new("L", size)
        draw = ImageDraw.Draw(mask)
        kind = node["kind"]
        box = [v * scale for v in node.get("box", [])]
        points = [(x * scale, y * scale) for x, y in node.get("points", [])]
        if kind == "rect":
            draw.rectangle(box, fill=255)
        elif kind == "ellipse":
            draw.ellipse(box, fill=255)
        elif kind == "polygon":
            draw.polygon(points, fill=255)
        elif kind == "line":
            draw.line(points, fill=255, width=max(1, round(node["width"] * scale)))
        elif kind == "arc":
            line_width = max(1, round(node["width"] * scale))
            # Pillow draws ellipse strokes inward; SVG centers them on the
            # declared curve. Expand the mask bounds to preserve one geometry.
            box = [
                box[0] - line_width / 2,
                box[1] - line_width / 2,
                box[2] + line_width / 2,
                box[3] + line_width / 2,
            ]
            draw.arc(
                box,
                node["start"],
                node["end"],
                fill=255,
                width=line_width,
            )
        fill = node["fill"]
        if fill.startswith("@"):
            name = fill[1:]
            spec = graph["gradients"][name]
            if spec["kind"] == "radial":
                # Local radial alpha/color stops, identical to the SVG ellipse.
                bw, bh = max(1, round(box[2] - box[0])), max(1, round(box[3] - box[1]))
                radius = (
                    Image.radial_gradient("L")
                    .point(lambda v: min(255, round(v * math.sqrt(2))))
                    .resize((bw, bh), Image.Resampling.BICUBIC)
                )
                table = [_sample(spec["stops"], i / 255) for i in range(256)]
                layer = Image.merge(
                    "RGBA", tuple(radius.point([c[j] for c in table]) for j in range(4))
                )
                field = Image.new("RGBA", size)
                field.paste(layer, (round(box[0]), round(box[1])))
            else:
                if name not in gradients:
                    y0, y1 = spec["range"]
                    strip = Image.new("RGBA", (1, size[1]))
                    strip.putdata(
                        [
                            _sample(spec["stops"], (i / scale - y0) / (y1 - y0))
                            for i in range(size[1])
                        ]
                    )
                    gradients[name] = strip.resize(size)
                field = gradients[name].copy()
        else:
            field = Image.new("RGBA", size, _rgba(fill))
        alpha = ImageChops.multiply(field.getchannel("A"), mask)
        if node.get("opacity", 1) != 1:
            opacity = node["opacity"]
            alpha = alpha.point(lambda v: round(v * opacity))
        field.putalpha(alpha)
        image = Image.alpha_composite(image, field)
    if graph["corner_radius"]:
        mask = Image.new("L", size)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, size[0] - 1, size[1] - 1), radius=graph["corner_radius"] * scale, fill=255
        )
        image.putalpha(mask)
    image = image.resize(final, Image.Resampling.LANCZOS)
    if graph["corner_radius"]:
        # Remove sub-visible Lanczos ringing in fully transparent app corners.
        image.putalpha(image.getchannel("A").point(lambda value: 0 if value < 2 else value))
    return image, graph


def vector(graph, raw) -> str:
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.ttLib import TTFont

    graph = fit_title(graph, raw)
    prefix = (
        "ocf-v2-"
        + hashlib.sha256(
            json.dumps(
                {
                    "brand": graph["brand"],
                    "theme": graph["theme"],
                    "composition": graph["composition"],
                    "texts": [n["text"] for n in graph["nodes"] if n["kind"] == "text"],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:12]
        + "-"
    )
    width, height = graph["width"], graph["height"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
        f"<title>Open Consciousness Functions — {VERSION} {graph['composition']} candidate</title>",
        "<desc>Original Cosmic Path and Resonance Rings. Human approval is pending.</desc>",
        "<defs>",
    ]
    for name, gradient in graph["gradients"].items():
        if not any(node["fill"] == "@" + name for node in graph["nodes"]):
            continue
        if gradient["kind"] == "radial":
            tag = "radialGradient"
            parts.append(f'<{tag} id="{prefix}{name}" cx="50%" cy="50%" r="50%">')
        else:
            tag = "linearGradient"
            y0, y1 = gradient["range"]
            parts.append(
                f'<{tag} id="{prefix}{name}" gradientUnits="userSpaceOnUse" x1="0" y1="{y0}" x2="0" y2="{y1}">'
            )
        parts += [
            f'<stop offset="{offset}" stop-color="{color}" stop-opacity="{alpha}"/>'
            for offset, color, alpha in gradient["stops"]
        ]
        parts.append(f"</{tag}>")
    parts.append(
        f'<clipPath id="{prefix}frame"><rect width="{width}" height="{height}" rx="{graph["corner_radius"]}"/></clipPath></defs><g clip-path="url(#{prefix}frame)">'
    )
    with TTFont(io.BytesIO(raw)) as font:
        glyphs = font.getGlyphSet()
        cmap = font.getBestCmap()
        units = font["head"].unitsPerEm
        for node in graph["nodes"]:
            fill = node["fill"]
            fill = f"url(#{prefix}{fill[1:]})" if fill.startswith("@") else fill
            opacity = node.get("opacity", 1)
            style = f'fill="{fill}" opacity="{opacity}"'
            kind = node["kind"]
            if kind == "text":
                pilfont, x, baseline, _ = _text_layout(node, raw)
                parts.append(f'<g aria-label="{escape(node["text"], quote=True)}" {style}>')
                for i, char in enumerate(node["text"]):
                    if char.isspace():
                        continue
                    if ord(char) not in cmap:
                        raise OCFError(f"font lacks U+{ord(char):04X}")
                    pen = SVGPathPen(glyphs)
                    glyphs[cmap[ord(char)]].draw(pen)
                    offset = (
                        pilfont.getlength(node["text"][: i + 1])
                        - pilfont.getlength(char)
                        + i * node.get("tracking", 0)
                    )
                    factor = node["size"] / units
                    parts.append(
                        f'<path d="{pen.getCommands()}" transform="translate({x + offset:.3f} {baseline:.3f}) scale({factor:.7f} {-factor:.7f})"/>'
                    )
                parts.append("</g>")
            elif kind == "rect":
                x0, y0, x1, y1 = node["box"]
                parts.append(
                    f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" {style}/>'
                )
            elif kind == "ellipse":
                x0, y0, x1, y1 = node["box"]
                parts.append(
                    f'<ellipse cx="{(x0 + x1) / 2}" cy="{(y0 + y1) / 2}" rx="{(x1 - x0) / 2}" ry="{(y1 - y0) / 2}" {style}/>'
                )
            elif kind in {"polygon", "line"}:
                points = " ".join(f"{x:.3f},{y:.3f}" for x, y in node["points"])
                if kind == "polygon":
                    parts.append(f'<polygon points="{points}" {style}/>')
                else:
                    parts.append(
                        f'<polyline points="{points}" fill="none" stroke="{fill}" stroke-width="{node["width"]}" opacity="{opacity}"/>'
                    )
            elif kind == "arc":
                x0, y0, x1, y1 = node["box"]
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
                a, b = math.radians(node["start"]), math.radians(node["end"])
                path = f"M {cx + rx * math.cos(a):.3f} {cy + ry * math.sin(a):.3f} A {rx} {ry} 0 {int(node['end'] - node['start'] > 180)} 1 {cx + rx * math.cos(b):.3f} {cy + ry * math.sin(b):.3f}"
                parts.append(
                    f'<path d="{path}" fill="none" stroke="{fill}" stroke-width="{node["width"]}" opacity="{opacity}"/>'
                )
    parts.append("</g></svg>\n")
    return "\n".join(parts)


def composition_for(variant: str) -> str:
    if variant not in identity()["variants"]:
        raise OCFError("unknown refined brand variant")
    return {"primary": "logo", "dark": "logo", "light": "logo", "monochrome": "icon"}.get(
        variant, variant
    )


def export(output: Path, variant: str, theme: dict, raw: bytes, resolution: int) -> dict:
    if output.exists():
        raise OCFError("refusing to overwrite existing candidate artwork")
    graph = scene(theme, composition_for(variant))
    if output.suffix.lower() == ".svg":
        write_text_atomic(output, vector(graph, raw), overwrite=False)
    elif output.suffix.lower() == ".png":
        image, _ = raster(graph, raw, resolution)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as handle:
            image.save(handle, format="PNG", compress_level=9)
    else:
        raise OCFError("refined brand exports require .svg or .png")
    return {
        "path": str(output),
        "sha256": sha256_of_file(output),
        "variant": variant,
        "brand_version": VERSION,
        "review_status": "candidate",
        "human_approval": None,
    }


def comparison_gallery(
    output: Path,
    *,
    vector_only: bool = False,
    ui_theme: str = "ocf-light",
    custom_theme: str | None = None,
    check: bool = False,
) -> dict:
    """Publish a new, self-contained comparison. Existing output is never replaced."""
    from . import artwork
    from .paths import (
        publish_workspace_temp_directory,
        record_workspace_failure,
        workspace_temp_directory,
    )
    from .session_plans import digest

    choices = [
        (
            "baseline",
            "Current baseline · 0.1.0",
            "primary",
            "ocf-dark",
            640,
            320,
            "Original candidate, retained exactly for comparison.",
        ),
        (
            "refined-dark",
            "Refined dark logo",
            "primary",
            "ocf-refined-dark",
            960,
            640,
            "Larger emblem, dimensional ribbon and a two-line wordmark.",
        ),
        (
            "refined-light",
            "Refined light logo",
            "primary",
            "ocf-refined-light",
            960,
            640,
            "Pearl / ice atmosphere, ink typography and metallic gold.",
        ),
        (
            "refined-minimal",
            "Refined minimal icon",
            "monochrome",
            "ocf-refined-minimal",
            512,
            192,
            "A simplified, single-ink mark for small-scale recognition.",
        ),
        (
            "refined-album",
            "Refined album artwork",
            "album",
            "ocf-refined-dark",
            1000,
            400,
            "An expansive resonance field, restrained atmosphere and prominent title.",
        ),
        (
            "refined-app",
            "Refined application icon",
            "app",
            "ocf-refined-dark",
            512,
            256,
            "A rounded tile with an enlarged emblem; no miniature lettering.",
        ),
        (
            "refined-social",
            "Refined repository / social preview",
            "social",
            "ocf-refined-dark",
            1280,
            640,
            "A dedicated 2:1 composition with a large three-line wordmark.",
        ),
    ]
    if custom_theme:
        value = artwork.load_theme(custom_theme)
        if value.get("brand_revision") != VERSION:
            raise OCFError("custom comparison theme must extend an ocf-refined theme")
        choices.append(
            (
                "refined-custom",
                "Custom artwork theme",
                "primary",
                custom_theme,
                960,
                640,
                "An explicit custom artwork choice, independent of the gallery interface.",
            )
        )
    inputs = {
        "brand_sha256": sha256_of_file(SOURCE),
        "renderer_sha256": sha256_of_file(Path(__file__)),
        "artwork_integration_sha256": sha256_of_file(Path(artwork.__file__)),
        "baseline_svg_sha256": sha256_of_file(artwork.BRAND / "candidates/primary.svg"),
        "themes": {key: digest(artwork.load_theme(theme)) for key, _, _, theme, _, _, _ in choices},
        "fonts": {
            key: hashlib.sha256(
                artwork._font_assets(artwork.load_theme(theme)["font"])[0]
            ).hexdigest()
            for key, _, _, theme, _, _, _ in choices
        },
        "ui_theme": {
            key: value
            for key, value in artwork.load_theme(ui_theme, surface="ui").items()
            if key in {"id", "palette", "ui_font_family"}
        },
        "vector_only": vector_only,
    }
    if check:
        manifest = read_json_object(output / "manifest.json")
        if manifest.get("inputs") != inputs:
            raise OCFError("comparison gallery inputs are stale; generate a new review directory")
        for item in manifest["files"]:
            relative = Path(item["path"])
            path = (output / relative).resolve()
            if (
                relative.is_absolute()
                or not path.is_relative_to(output.resolve())
                or not path.is_file()
                or sha256_of_file(path) != item["sha256"]
            ):
                raise OCFError("comparison gallery artifact mismatch")
        return {
            "status": "passed",
            "assets": len(manifest["files"]),
            "brand_version": VERSION,
            "review_status": "candidate",
        }
    if output.exists():
        raise OCFError("comparison gallery already exists; choose a new directory")
    stage = workspace_temp_directory(prefix="ocf-brand-comparison-")
    try:
        files, cards = [], []
        for key, label, variant, theme, resolution, display, note in choices:
            svg = stage / (key + ".svg")
            report = artwork.export_brand(svg, variant=variant, theme=theme)
            files.append(
                {
                    "path": svg.name,
                    "sha256": report["sha256"],
                    "brand_version": "0.1.0" if key == "baseline" else VERSION,
                }
            )
            if not vector_only:
                png = stage / (key + ".png")
                if variant == "album":
                    report = artwork.generate_cover(
                        "OCF-SLP-005", theme=theme, resolution=resolution, output=png
                    )
                else:
                    report = artwork.export_brand(
                        png, variant=variant, theme=theme, resolution=resolution
                    )
                files.append(
                    {
                        "path": png.name,
                        "sha256": report["sha256"],
                        "brand_version": "0.1.0" if key == "baseline" else VERSION,
                    }
                )
            sizes = ""
            if variant in {"app", "monochrome"}:
                sizes = '<div class="sizes">'
                for size in (32, 64, 128):
                    name = svg.name
                    if not vector_only:
                        small = stage / f"{key}-{size}.png"
                        report = artwork.export_brand(
                            small, variant=variant, theme=theme, resolution=size
                        )
                        files.append(
                            {
                                "path": small.name,
                                "sha256": report["sha256"],
                                "brand_version": VERSION,
                            }
                        )
                        name = small.name
                    sizes += f'<figure><img src="{name}" width="{size}" height="{size}" alt="{escape(label)} at {size} pixels"><figcaption>{size} px</figcaption></figure>'
                sizes += "</div>"
            dimensions = (
                {"width": 1000, "height": 1000}
                if key == "baseline"
                else identity()["compositions"][composition_for(variant)]
            )
            shown_height = round(display * dimensions["height"] / dimensions["width"])
            cards.append(
                f'<article id="{key}"><div class="card-heading"><h2>{escape(label)}</h2><span>Candidate</span></div><div class="art"><img class="main-preview" src="{svg.name}" width="{display}" height="{shown_height}" style="--target:{display}px" alt="{escape(label)}"></div>{sizes}<p>{escape(note)}</p><nav><a href="{svg.name}">Open vector at full size</a>'
                + ("" if vector_only else f' · <a href="{key}.png">PNG export</a>')
                + "</nav></article>"
            )
        ui = inputs["ui_theme"]["palette"]
        themes = {
            name: artwork.load_theme(name, surface="ui")["palette"]
            for name in ("ocf-light", "ocf-dark", "ocf-minimal")
        }
        themes["selected"] = ui
        html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCF · Visual refinement 0.2.0 comparison</title><style>
*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
.wrap{max-width:1320px;margin:auto;padding:clamp(16px,4vw,48px)}header{max-width:920px;margin-bottom:32px}h1{font-size:clamp(28px,5vw,48px);line-height:1.12;letter-spacing:-.025em;margin:12px 0 20px}h2{font-size:20px;line-height:1.3;margin:0}.eyebrow{font-size:14px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
select{font:inherit;padding:8px 12px;border:1px solid var(--accent);border-radius:8px;background:var(--bg);color:var(--fg);max-width:100%}.controls{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:24px 0}.notice{border-left:3px solid var(--accent);padding-left:16px}
main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}article{min-width:0;border:1px solid color-mix(in srgb,var(--fg) 18%,transparent);border-radius:16px;padding:clamp(16px,2.5vw,28px)}.card-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.card-heading span{font-size:12px;text-transform:uppercase;letter-spacing:.07em;border:1px solid var(--accent);padding:3px 7px;border-radius:99px;white-space:nowrap}
.art{display:flex;align-items:center;justify-content:center;min-height:220px;padding:24px 0}.main-preview{display:block;width:min(100%,var(--target));height:auto}p{max-width:70ch}nav{font-size:14px}a{color:var(--fg);text-underline-offset:4px}a:focus-visible,select:focus-visible{outline:3px solid var(--accent);outline-offset:4px}.sizes{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:18px}.sizes figure{margin:0;text-align:center}.sizes figcaption{font-size:13px;margin-top:8px}.sizes img{display:block}.wide main{grid-template-columns:1fr}.wide .main-preview{width:min(100%,calc(var(--target)*1.5))}
@media(max-width:720px){main{grid-template-columns:1fr;gap:18px}.card-heading{display:block}.card-heading span{display:inline-block;margin-top:8px}.art{min-height:0}.sizes{gap:12px}}
.jump{display:flex;flex-wrap:wrap;gap:8px 18px;margin:20px 0}details{font-size:14px;margin:14px 0}summary{cursor:pointer}
</style></head><body><div class="wrap"><header><div class="eyebrow">OCF · Candidate comparison · 0.2.0</div><h1>Cosmic Path.<br>Refined resonance.</h1><p>Original visual candidates. Human design approval remains pending.</p><div class="controls"><label for="ui">Gallery interface</label><select id="ui"><option value="selected">Selected interface theme</option><option value="ocf-light">Light</option><option value="ocf-dark">Dark</option><option value="ocf-minimal">Minimal</option></select><label><input type="checkbox" id="large"> Larger comparison</label></div><nav class="jump" aria-label="Jump to comparison"><a href="#baseline">Baseline</a><a href="#refined-dark">Dark</a><a href="#refined-light">Light</a><a href="#refined-minimal">Minimal</a><a href="#refined-album">Album</a><a href="#refined-app">App</a><a href="#refined-social">Social</a></nav><details><summary>Review notes and theme independence</summary><p>The retained baseline and refined compositions are shown at practical display sizes. Interface appearance is independent of the artwork: changing this page theme does not recolor the fixed dark, light and minimal comparisons. No final identity is published by this gallery.</p></details></header><main>CARDS</main></div><script>
const themes=THEMES;const select=document.getElementById('ui');function apply(){const p=themes[select.value];document.body.style.setProperty('--bg',p.background);document.body.style.setProperty('--fg',p.foreground);document.body.style.setProperty('--accent',p.accent)}select.addEventListener('change',apply);document.getElementById('large').addEventListener('change',e=>document.body.classList.toggle('wide',e.target.checked));apply();
</script></body></html>"""
        write_text_atomic(
            stage / "index.html",
            html.replace("CARDS", "\n".join(cards)).replace(
                "THEMES", json.dumps(themes).replace("<", "\\u003c")
            ),
        )
        files.append({"path": "index.html", "sha256": sha256_of_file(stage / "index.html")})
        manifest = {
            "schema_version": "1.0",
            "brand_version": VERSION,
            "baseline_version": "0.1.0",
            "review_status": "candidate",
            "human_approval": None,
            "inputs": inputs,
            "files": files,
        }
        write_text_atomic(
            stage / "manifest.json",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        publish_workspace_temp_directory(stage, output)
        return {
            "gallery": str(output / "index.html"),
            "manifest": str(output / "manifest.json"),
            "assets": len(files),
            "brand_version": VERSION,
            "review_status": "candidate",
            "human_approval": None,
        }
    except BaseException as exc:
        record_workspace_failure(stage.name, f"brand comparison failed: {exc}")
        raise
