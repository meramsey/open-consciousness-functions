import io
import json
from pathlib import Path

import pytest
from ocf_tools import artwork
from ocf_tools.utils import OCFError


def unicode_font_fixture(path):
    """Temporary custom-font fixture: add a real E+acute outline, not a tofu alias."""
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont

    raw, _ = artwork._font_assets("pillow-aileron")
    font = TTFont(io.BytesIO(raw))
    name = font.getBestCmap()[ord("E")]
    pen = TTGlyphPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    units = font["head"].unitsPerEm
    top = font["glyf"][name].yMax
    pen.moveTo((round(0.3 * units), top + round(0.03 * units)))
    pen.lineTo((round(0.45 * units), top + round(0.18 * units)))
    pen.lineTo((round(0.55 * units), top + round(0.18 * units)))
    pen.lineTo((round(0.38 * units), top + round(0.03 * units)))
    pen.closePath()
    new_name = "fixtureEacute"
    font["glyf"][new_name] = pen.glyph()
    font["hmtx"][new_name] = font["hmtx"][name]
    order = font.getGlyphOrder()
    font.setGlyphOrder(order if new_name in order else [*order, new_name])
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[ord("É")] = new_name
    font.save(path)
    font.close()
    return str(path)


def test_themes_are_independent_validated_and_inheritance_is_bounded(tmp_path):
    assert artwork.theme_tokens("ui")["theme"]["id"] == "ocf-light"
    assert artwork.theme_tokens("artwork")["theme"]["id"] == "ocf-cosmic-dark"
    with pytest.raises(OCFError, match="contrast"):
        artwork.load_theme(overrides={"palette": {"foreground": "#071426"}})
    custom = tmp_path / "custom.json"
    custom.write_text(json.dumps({"id": "custom", "extends": "custom.json"}))
    with pytest.raises(OCFError, match="cyclic"):
        artwork.load_theme(str(custom))
    assert len(artwork.identity()["variants"]) == 8
    for variant in artwork.identity()["variants"]:
        assert "candidate" in artwork.brand_svg(variant)
        assert (artwork.BRAND / "candidates" / f"{variant}.svg").read_text(
            encoding="utf-8"
        ) == artwork.brand_svg(variant)
    preview = tmp_path / "gallery.html"
    artwork.gallery(preview)
    html = preview.read_text(encoding="utf-8")
    assert 'ui.value="ocf-light"' in html and 'art.value="ocf-cosmic-dark"' in html
    assert "https://" not in html


def test_localized_artwork_cache_integrity_and_no_overwrite(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from PIL import Image

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    first = artwork.generate_cover("OCF-SLP-005", resolution=320)
    second = artwork.generate_cover("OCF-SLP-005", resolution=320)
    assert first["sha256"] == second["sha256"] and second["cache"] == "hit"
    with Image.open(first["path"]) as image:
        assert image.size == (320, 320) and image.format == "PNG"
    assert first["settings"]["title"] == "Sleep Easy" and first["human_approval"] is None
    Path(first["path"]).write_bytes(b"broken")
    repaired = artwork.generate_cover("OCF-SLP-005", resolution=320)
    assert repaired["sha256"] == first["sha256"]
    custom = tmp_path / "custom.png"
    custom.write_bytes(b"operator cover")
    with pytest.raises(OCFError, match="overwrite"):
        artwork.generate_cover("OCF-SLP-005", resolution=320, output=custom)
    assert custom.read_bytes() == b"operator cover"
    jpeg = artwork.generate_cover(
        "OCF-FND-002", locale="es", resolution=256, format="jpeg", theme="ocf-light"
    )
    with Image.open(jpeg["path"]) as image:
        assert image.format == "JPEG"
    long = artwork.generate_cover(
        "OCF-SLP-005",
        resolution=256,
        theme="ocf-dark",
        title_override="Énergie et attention " * 12,
        version="W" * 32,
        overrides={"font": unicode_font_fixture(tmp_path / "unicode-fixture.ttf")},
    )
    assert len(long["title_lines"]) <= 3
    assert (
        max(box[3] for box in long["layout_bounds"]["title"]) < long["layout_bounds"]["footer"][1]
    )
    assert all(0 <= v <= 256 for box in long["layout_bounds"]["title"] for v in box)


def test_generated_release_preview_is_nonmutating_and_custom_cover_wins(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from ocf_tools import release

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(
        release,
        "_select_audio_manifest",
        lambda _: {"id": "OCF-AUDIO-9000", "function_id": "OCF-SLP-005"},
    )
    preview = release.package_release(
        "OCF-SLP-005",
        artwork_theme="ocf-dark",
        artwork_resolution=256,
        dry_run=True,
        output=tmp_path / "out",
    )
    assert preview["artwork_provenance"]["source"] == "generated-ocf"
    assert not (tmp_path / "work").exists() and not (tmp_path / "out").exists()
    cover = artwork.generate_cover("OCF-SLP-005", resolution=320)
    custom = release.package_release(
        "OCF-SLP-005",
        artwork=cover["path"],
        artwork_theme="missing-theme",
        dry_run=True,
        output=tmp_path / "out",
    )
    assert custom["artwork_provenance"]["source"] == "explicit-user-cover"
    changed = artwork.generate_cover(
        "OCF-SLP-005", resolution=320, title_override="Operator title", dry_run=True
    )
    assert changed["settings"]["title_resolution"]["resource_key"] is None
    assert changed["settings"]["title_resolution"]["source"] == "operator-title-override"
    package = release.package_release(
        "OCF-SLP-005",
        artwork=cover["path"],
        metadata_overrides={"title": "Operator title"},
        dry_run=True,
        output=tmp_path / "out",
    )
    assert package["title_resolution"]["resource_key"] is None
    assert package["title_resolution"]["source"] == "operator-title-override"


def test_rtl_operator_title_requires_shaping_even_for_english_locale(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from PIL import features

    raw, glyphs = artwork._font_assets("pillow-aileron")
    text = "مرحبا"
    monkeypatch.setattr(artwork, "_font_assets", lambda _: (raw, glyphs | {ord(c) for c in text}))
    monkeypatch.setattr(features, "check", lambda _: False)
    with pytest.raises(OCFError, match="RAQM"):
        artwork.generate_cover("OCF-SLP-005", title_override=text, dry_run=True)
