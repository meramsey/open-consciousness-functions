"""Unchanged supplied art, verified provenance, and offline comparison exports."""

from __future__ import annotations

import io
import json
import shutil
import struct
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

from .utils import OCFError, sha256_of_file, write_text_atomic
from .validators import _load_schema, validate_against_schema


def identity():
    from .artwork import BRAND

    data = json.loads((BRAND / "versions/0.3.0/identity.json").read_text(encoding="utf-8"))
    errors = validate_against_schema(data, _load_schema("brand-import.schema.json"))
    if errors:
        raise OCFError("invalid imported identity: " + " | ".join(errors))
    return data


def source_root():
    from .artwork import BRAND

    return BRAND / identity()["source"]


def verify(root: Path | None = None):
    """Check complete inventory, hashes, byte counts and actual asset dimensions."""
    root = root or source_root()
    if sha256_of_file(root / "manifest.json") != identity()["source_manifest_sha256"]:
        raise OCFError("imported manifest SHA-256 mismatch")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    seen = set()
    for row in manifest["files"]:
        name = row["path"]
        relative = Path(name)
        path = root / relative
        if relative.is_absolute() or ".." in relative.parts or name in seen:
            raise OCFError("unsafe or duplicate imported asset path")
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise OCFError("imported asset escapes source directory")
        seen.add(name)
        if not path.is_file() or path.stat().st_size != row["bytes"]:
            raise OCFError(f"imported asset byte-count mismatch: {name}")
        if sha256_of_file(path) != row["sha256"]:
            raise OCFError(f"imported asset SHA-256 mismatch: {name}")
        dimensions = None
        if path.suffix == ".png":
            raw = path.read_bytes()
            if raw[:8] != b"\x89PNG\r\n\x1a\n":
                raise OCFError("invalid imported PNG")
            dimensions = list(struct.unpack(">II", raw[16:24]))
        elif path.suffix == ".svg":
            tree = ET.parse(path).getroot()
            dimensions = [int(tree.attrib[key]) for key in ("width", "height")]
        if dimensions and any(not 1 <= v <= 12000 for v in dimensions):
            raise OCFError("invalid imported asset dimensions")
        rows.append({**row, "dimensions": dimensions})
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != seen | {"manifest.json"}:
        raise OCFError("imported asset inventory mismatch")
    return {
        "status": "passed",
        "files": rows,
        "manifest_sha256": sha256_of_file(root / "manifest.json"),
        "review_status": "candidate",
        "human_approval": None,
    }


def asset(variant, theme, suffix="svg", resolution=1024):
    """Select an original supplied file; never redraw it or use mood-board crops."""
    finish = theme["finish"]
    if variant in ("light", "dark"):
        finish = variant
    if variant == "monochrome":
        finish = "minimal"
    if variant == "social":
        name = "ocf-github-social-1280x640"
    elif variant == "app":
        size = (
            resolution if suffix == "png" and resolution in (32, 64, 128, 256, 512, 1024) else 1024
        )
        name = f"ocf-app-icon-{size}"
    elif variant in ("primary", "light", "dark") and finish != "minimal":
        name = f"ocf-primary-{finish}-1600x600"
    elif variant == "album" and finish != "minimal":
        name = f"ocf-album-sleep-easy-{finish}-1200"
    else:
        name = f"ocf-emblem-{finish}-1024"
    return source_root() / suffix / f"{name}.{suffix}"


def export(output, variant, theme, resolution):
    verify()
    if output.suffix.lower() not in (".svg", ".png"):
        raise OCFError("imported brand exports support .svg or .png")
    source = asset(variant, theme, output.suffix.lower()[1:], resolution)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as target, source.open("rb") as supplied:
            shutil.copyfileobj(supplied, target)
    except FileExistsError as exc:
        raise OCFError("refusing to overwrite brand artwork") from exc
    return {
        "path": str(output),
        "sha256": sha256_of_file(output),
        "source": source.name,
        "review_status": "candidate",
        "human_approval": None,
        "unchanged_supplied_asset": True,
    }


def cover_layout(title, footer, font_bytes, resolution, *, cue=None, description=None):
    """Fit localized text around supplied art; fail before cache writes or dry-run."""
    from PIL import Image, ImageDraw, ImageFont

    scale = resolution * 2 / 1000
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def font(size):
        return ImageFont.truetype(io.BytesIO(font_bytes), max(1, round(size * scale)))

    def box(text, y, size, anchor="mt"):
        return list(draw.textbbox((resolution, y * scale), text, font=font(size), anchor=anchor))

    nodes = []
    for text, y, anchor, initial, minimum in (
        ("Open Consciousness Functions", 55, "mt", 30, 18),
        (footer, 965, "mb", 25, 14),
    ):
        for size in range(initial, minimum - 1, -1):
            bounds = box(text, y, size, anchor)
            if bounds[0] >= 80 * scale and bounds[2] <= 920 * scale:
                break
        else:
            raise OCFError("cover header/identifier cannot fit legibly")
        nodes.append({"text": text, "y": y, "size": size, "anchor": anchor, "box": bounds})
    if cue or description:
        # Keep the supplied emblem and header/footer in their existing positions.
        # Fit only the title/cue/description stack into the space beneath it.
        def wrap(text, size, maximum):
            lines, current = [], ""
            for character in text:
                if draw.textlength(current + character, font=font(size)) > 840 * scale:
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
            return lines if len(lines) <= maximum else None

        hidden = bool(description and resolution < 512)
        shown_description = None if hidden else description
        # Size the master for real player thumbnails too: a 72-unit cue retains
        # roughly nine pixels of type at 128px, without relying on a separate UI.
        initial = 104
        for title_size in range(initial, 41, -1):
            title_lines = wrap(title, title_size, 2)
            if not title_lines:
                continue
            cue_size = min(72, title_size / 1.4)
            cue_lines = wrap(cue, cue_size, 2) if cue else []
            description_size = min(22, title_size / 2.7)
            description_lines = (
                wrap(shown_description, description_size, 2) if shown_description else []
            )
            if cue_lines is None or description_lines is None:
                continue
            stack, boxes = [], {"title": [], "cue": [], "description": []}
            y = 715 if resolution < 320 else 725
            for role, lines, size in (
                ("title", title_lines, title_size),
                ("cue", cue_lines, cue_size),
                ("description", description_lines, description_size),
            ):
                for line_index, line in enumerate(lines):
                    bounds = box(line, y, size)
                    stack.append(
                        {
                            "text": line,
                            "y": y,
                            "size": size,
                            "anchor": "mt",
                            "box": bounds,
                            "color_role": role,
                        }
                    )
                    boxes[role].append(bounds)
                    y = y + size * 1.15 if line_index + 1 < len(lines) else bounds[3] / scale
                if lines:
                    y += 12
            if all(
                b[0] >= 80 * scale
                and b[2] <= 920 * scale
                and b[3] < min(925 * scale, nodes[1]["box"][1])
                for role in boxes.values()
                for b in role
            ):
                nodes.extend(stack)
                bounds = {
                    "header": [v / 2 for v in nodes[0]["box"]],
                    "footer": [v / 2 for v in nodes[1]["box"]],
                    **{
                        role: [[v / 2 for v in b] for b in values] for role, values in boxes.items()
                    },
                }
                return {
                    "nodes": nodes,
                    "title_lines": title_lines,
                    "bounds": bounds,
                    "cue_lines": cue_lines,
                    "description_lines": description_lines,
                    "description_hidden_reason": "small-artwork" if hidden else None,
                    "font_sizes": {
                        "title": title_size,
                        "cue": cue_size,
                        "description": description_size,
                    },
                }
        raise OCFError("localized title/cue/description cannot fit legibly without clipping")
    for size in range(70, 27, -1):
        lines, current = [], ""
        for character in title:
            if draw.textlength(current + character, font=font(size)) > 840 * scale:
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
        boxes = [box(line, 740 + i * size * 1.2, size) for i, line in enumerate(lines)]
        if len(lines) <= 2 and all(
            b[0] >= 80 * scale
            and b[2] <= 920 * scale
            and b[3] < min(925 * scale, nodes[1]["box"][1])
            for b in boxes
        ):
            break
    else:
        raise OCFError("localized title cannot fit legibly; choose a shorter title or another font")
    for i, (line, bounds) in enumerate(zip(lines, boxes, strict=True)):
        nodes.append(
            {"text": line, "y": 740 + i * size * 1.2, "size": size, "anchor": "mt", "box": bounds}
        )
    bounds = {
        "header": [v / 2 for v in nodes[0]["box"]],
        "footer": [v / 2 for v in nodes[1]["box"]],
        "title": [[v / 2 for v in b] for b in boxes],
    }
    return {"nodes": nodes, "title_lines": lines, "bounds": bounds}


def cover_raster(layout, theme, font_bytes, resolution, *, description_color=None):
    from PIL import Image, ImageDraw, ImageFont

    width = resolution * 2
    image = Image.new("RGB", (width, width), theme["palette"]["background"])
    with Image.open(asset("icon", theme, "png")) as supplied:
        supplied.load()
        size = round(width * 0.60)
        image.paste(
            supplied.convert("RGB").resize((size, size), Image.Resampling.LANCZOS),
            ((width - size) // 2, round(width * 0.10)),
        )
    draw = ImageDraw.Draw(image)
    scale = width / 1000
    for node in layout["nodes"]:
        draw.text(
            (resolution, node["y"] * scale),
            node["text"],
            anchor=node["anchor"],
            font=ImageFont.truetype(io.BytesIO(font_bytes), max(1, round(node["size"] * scale))),
            fill=theme["palette"]["accent"]
            if node.get("color_role") == "cue"
            else description_color
            if node.get("color_role") == "description" and description_color
            else theme["palette"]["foreground"],
        )
    return image.resize((resolution, resolution), Image.Resampling.LANCZOS)


def _gallery_names():
    names = {
        "index.html",
        "selected-custom-album.png",
        "previous-social.svg",
        "supplied-ocf-github-social-1280x640.png",
    }
    for finish in ("dark", "light", "minimal"):
        names.update(
            {
                f"previous-{finish}.svg",
                f"previous-album-{finish}.png",
                f"localized-album-{finish}.png",
            }
        )
        name = (
            f"ocf-primary-{finish}-1600x600.svg"
            if finish != "minimal"
            else "ocf-emblem-minimal-1024.svg"
        )
        names.add("supplied-" + name)
    for size in (32, 64, 128):
        names.update({f"previous-app-{size}.png", f"supplied-ocf-app-icon-{size}.png"})
    names.update(f"supplied-ocf-album-sleep-easy-{finish}-1200.png" for finish in ("dark", "light"))
    names.update("supplied-" + p.name for p in (source_root() / "reference").glob("*.png"))
    return names


def comparison_gallery(output: Path, *, check=False, ui_theme=None, artwork_theme=None):
    """Portable repository-local review; originals stay in their immutable import."""
    from .artwork import export_brand, generate_cover, load_theme, theme_tokens

    verification = verify()
    if check:
        report = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        if report["source"] != verification:
            raise OCFError("import gallery source mismatch")
        expected = _gallery_names()
        if set(report["files"]) != expected or {p.name for p in output.iterdir()} != expected | {
            "manifest.json"
        }:
            raise OCFError("import gallery inventory mismatch")
        for name, checksum in report["files"].items():
            if (output / name).is_symlink() or not (output / name).is_file():
                raise OCFError("unsafe import gallery file")
            if sha256_of_file(output / name) != checksum:
                raise OCFError("import gallery checksum mismatch: " + name)
        return {"status": "passed", "path": str(output)}
    if output.exists():
        raise OCFError("comparison directory already exists")
    custom = load_theme(artwork_theme or "ocf-cosmic-dark")
    if custom.get("brand_revision") != "0.3.0":
        raise OCFError("import comparison requires an imported artwork theme")
    theme_tokens("ui", ui_theme)
    output.mkdir(parents=True)
    sections = []

    def pair(label, old, new, width=None):
        attrs = f' width="{width}" height="{width}"' if width else ""
        sections.append(
            f'<section><h2>{escape(label)}</h2><div class="pair">'
            f'<figure><figcaption>Previous 0.2.0</figcaption><a href="{old}"><img src="{old}" alt="Previous {escape(label)}"{attrs}></a></figure>'
            f'<figure><figcaption>Imported 0.3.0 candidate</figcaption><a href="{new}"><img src="{new}" alt="Imported {escape(label)}"{attrs}></a></figure></div></section>'
        )

    def supplied(path):
        name = "supplied-" + path.name
        shutil.copyfile(path, output / name)
        return name

    for finish in ("dark", "light", "minimal"):
        theme = load_theme("ocf-cosmic-" + finish)
        old = f"previous-{finish}.svg"
        export_brand(output / old, theme="ocf-refined-" + finish)
        pair(f"{finish.title()} logo", old, supplied(asset("primary", theme)))
    for size in (32, 64, 128):
        old = f"previous-app-{size}.png"
        export_brand(output / old, variant="app", theme="ocf-refined-dark", resolution=size)
        pair(f"App icon at {size} pixels", old, supplied(asset("app", custom, "png", size)), size)
    for finish in ("dark", "light", "minimal"):
        old, new = f"previous-album-{finish}.png", f"localized-album-{finish}.png"
        generate_cover(
            "OCF-SLP-005", theme="ocf-refined-" + finish, resolution=1200, output=output / old
        )
        generate_cover(
            "OCF-SLP-005", theme="ocf-cosmic-" + finish, resolution=1200, output=output / new
        )
        pair(f"Localized album / {finish} / full 1200 × 1200 (open image)", old, new)
    # Include the unchanged supplied album compositions, independently of localized derivatives.
    for finish in ("dark", "light"):
        path = supplied(asset("album", load_theme("ocf-cosmic-" + finish), "png"))
        sections.append(
            f'<section><h2>Supplied {finish} album — original 1200 × 1200</h2><a href="{path}"><img src="{path}" alt="Supplied {finish} album"></a></section>'
        )
    custom_cover = "selected-custom-album.png"
    generate_cover(
        "OCF-SLP-005",
        theme=artwork_theme or "ocf-cosmic-dark",
        resolution=1200,
        output=output / custom_cover,
    )
    sections.append(
        f'<section><h2>Selected artwork theme: {escape(custom["id"])}</h2><a href="{custom_cover}"><img src="{custom_cover}" alt="Selected custom artwork"></a></section>'
    )
    old = "previous-social.svg"
    export_brand(output / old, variant="social", theme="ocf-refined-dark")
    pair("GitHub social / 1280 × 640 imported PNG", old, supplied(asset("social", custom, "png")))
    for path in sorted((source_root() / "reference").glob("*.png")):
        name = supplied(path)
        sections.append(
            f'<section><h2>Reference only: {escape(path.stem)}</h2><a href="{name}"><img src="{name}" alt="Cinematic reference, not publication master"></a></section>'
        )
    palettes = {
        name: load_theme(name, surface="ui")["palette"]
        for name in ("ocf-cosmic-dark", "ocf-cosmic-light", "ocf-cosmic-minimal")
    }
    palettes["custom"] = theme_tokens("ui", ui_theme)["theme"]["palette"]
    payload = json.dumps(palettes).replace("<", "\\u003c")
    html = (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>OCF supplied Cosmic Path candidate comparison</title><style>
body{font:16px system-ui;margin:2rem;background:var(--bg,#f7f9ff);color:var(--fg,#152346)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem}figure{margin:0}section{padding:1rem 0;border-bottom:1px solid #888}
img{max-width:100%;height:auto}img[width]{max-width:none}select{font:inherit}a{color:inherit}
@media(max-width:720px){.pair{grid-template-columns:1fr}body{margin:1rem}}
</style><h1>Supplied Cosmic Path — 0.3.0 candidate</h1>
<p>No human branding approval recorded. SVG companions are not exact copies of cinematic references.
Localized covers reuse unchanged supplied emblem PNGs with OCF title layout; they do not reproduce the cinematic board or the supplied album composition.</p>
<label>Independent interface theme <select id="ui"><option>ocf-cosmic-dark</option><option>ocf-cosmic-light</option><option>ocf-cosmic-minimal</option><option selected>custom</option></select></label>
<p>Artwork comparisons remain independent of this interface control. Click album images for full-resolution review.</p>
"""
        + "".join(sections)
        + """<script>const palettes=PAYLOAD;const ui=document.getElementById('ui');function update(){const p=palettes[ui.value];document.body.style.setProperty('--bg',p.background);document.body.style.setProperty('--fg',p.foreground)}ui.addEventListener('change',update);update();</script></html>""".replace(
            "PAYLOAD", payload
        )
    )
    write_text_atomic(output / "index.html", html, overwrite=False)
    report = {
        "source": verification,
        "review_status": "candidate",
        "human_approval": None,
        "files": {p.name: sha256_of_file(p) for p in sorted(output.iterdir()) if p.is_file()},
    }
    write_text_atomic(
        output / "manifest.json", json.dumps(report, indent=2) + "\n", overwrite=False
    )
    return {
        "path": str(output / "index.html"),
        "review_status": "candidate",
        "human_approval": None,
    }
