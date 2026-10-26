import json
import shutil
from pathlib import Path

import pytest
from ocf_tools import artwork, brand_import, release
from ocf_tools.utils import OCFError, sha256_of_file
from test_artwork import unicode_font_fixture


def test_supplied_inventory_hashes_dimensions_and_tampering(tmp_path):
    result = brand_import.verify()
    assert len(result["files"]) == 33
    assert result["human_approval"] is None
    dimensions = {row["path"]: row["dimensions"] for row in result["files"]}
    assert dimensions["png/ocf-github-social-1280x640.png"] == [1280, 640]
    assert dimensions["png/ocf-app-icon-32.png"] == [32, 32]
    root = tmp_path / "kit"
    shutil.copytree(brand_import.source_root(), root)
    target = root / "svg/ocf-app-icon-1024.svg"
    raw = target.read_bytes()
    target.write_bytes(raw.replace(b"1024", b"1025", 1))
    with pytest.raises(OCFError, match="SHA-256"):
        brand_import.verify(root)
    target.write_bytes(raw)
    (root / "extra.txt").write_text("unlisted")
    with pytest.raises(OCFError, match="inventory"):
        brand_import.verify(root)


def test_import_exports_are_unchanged_and_surface_defaults_remain_independent(tmp_path):
    assert artwork.identity()["version"] == "0.1.0"
    assert artwork.load_theme("ocf-refined-dark")["brand_revision"] == "0.2.0"
    assert artwork.theme_tokens("ui")["theme"]["id"] == "ocf-light"
    assert artwork.theme_tokens("artwork")["theme"]["id"] == "ocf-cosmic-dark"
    for finish in ("dark", "light", "minimal"):
        theme = "ocf-cosmic-" + finish
        data = artwork.load_theme(theme)
        source = brand_import.asset("primary", data)
        assert artwork.brand_svg("primary", theme).encode() == source.read_bytes()
        for variant in artwork.identity()["variants"]:
            assert brand_import.asset(variant, data).is_file()
    for size in (32, 64, 128):
        output = tmp_path / f"icon-{size}.png"
        report = artwork.export_brand(
            output, variant="app", theme="ocf-cosmic-dark", resolution=size
        )
        assert report["sha256"] == sha256_of_file(
            brand_import.source_root() / f"png/ocf-app-icon-{size}.png"
        )
        with pytest.raises(OCFError, match="overwrite"):
            artwork.export_brand(output, variant="app", theme="ocf-cosmic-dark")


def test_localized_import_cover_custom_theme_cache_and_release_override(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from PIL import Image

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    custom = tmp_path / "custom.json"
    custom.write_text(
        json.dumps(
            {"extends": "ocf-cosmic-light", "id": "custom-cosmic", "palette": {"accent": "#125577"}}
        )
    )
    kwargs = dict(
        locale="es", theme=str(custom), resolution=1200, version="review-1", strict_locale=False
    )
    report = artwork.generate_cover("OCF-SLP-005", **kwargs)
    assert report["settings"]["brand"]["version"] == "0.3.0"
    assert report["settings"]["locale"] == "es"
    assert report["settings"]["title"] == "Sleep Easy"
    assert report["settings"]["title_resolution"]["fallback"] is True
    assert report["settings"]["release_version"] == "review-1"
    assert report["settings"]["theme"]["palette"]["accent"] == "#125577"
    assert report["human_approval"] is None
    assert artwork.generate_cover("OCF-SLP-005", **kwargs)["cache"] == "hit"
    Path(report["path"]).write_bytes(b"bad cache")
    assert artwork.generate_cover("OCF-SLP-005", **kwargs)["cache"] == "miss"
    with Image.open(report["path"]) as image:
        assert image.size == (1200, 1200)
    assert report["layout_bounds"]["title"][-1][3] < report["layout_bounds"]["footer"][1]
    monkeypatch.setattr(
        release,
        "_select_audio_manifest",
        lambda _: {"id": "OCF-AUDIO-9000", "function_id": "OCF-SLP-005"},
    )
    preview = release.package_release(
        "OCF-SLP-005", artwork_theme=str(custom), artwork_resolution=1200, dry_run=True
    )
    assert preview["artwork_provenance"]["brand_version"] == "0.3.0"
    assert preview["artwork_provenance"]["publication_approval"] is False
    override = release.package_release(
        "OCF-SLP-005", artwork=report["path"], artwork_theme="missing", dry_run=True
    )
    assert override["artwork_provenance"]["source"] == "explicit-user-cover"
    with pytest.raises(OCFError, match="glyphs"):
        artwork.generate_cover("OCF-SLP-005", theme="ocf-cosmic-dark", title_override="\U0001f680")
    monkeypatch.setattr(
        release,
        "_function_title",
        lambda *_: (
            "Énergie et attention",
            {"resolved_locale": "fr", "requested_locale": "fr", "fallback": False},
        ),
    )
    translated = artwork.generate_cover(
        "OCF-SLP-005",
        **(kwargs | {"locale": "fr"}),
        overrides={"font": unicode_font_fixture(tmp_path / "font.ttf")},
    )
    assert translated["settings"]["title"] == "Énergie et attention"
    assert translated["settings"]["title_locale"] == "fr"
    assert translated["settings"]["title_resolution"]["fallback"] is False


@pytest.mark.parametrize("finish", ["dark", "light", "minimal"])
def test_imported_layout_preflight_bounds_and_rejection(finish, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    font_path = unicode_font_fixture(tmp_path / "font.ttf")
    report = artwork.generate_cover(
        "OCF-SLP-005",
        theme="ocf-cosmic-" + finish,
        resolution=320,
        version="M" * 32,
        title_override="Énergie et attention tranquille",
        overrides={"font": font_path},
        dry_run=True,
    )
    assert report["dry_run"]
    raw, _ = artwork._font_assets(font_path)
    footer = "OCF-SLP-005 / en-US - " + "M" * 32
    layout = brand_import.cover_layout(report["settings"]["title"], footer, raw, 320)
    for bounds in [
        layout["bounds"]["header"],
        layout["bounds"]["footer"],
        *layout["bounds"]["title"],
    ]:
        assert 0 <= bounds[0] < bounds[2] <= 320
        assert 0 <= bounds[1] < bounds[3] <= 320
    assert layout["bounds"]["title"][0][1] > 320 * 0.70
    assert layout["bounds"]["title"][-1][3] < layout["bounds"]["footer"][1]
    with pytest.raises(OCFError, match="legibly"):
        artwork.generate_cover(
            "OCF-SLP-005",
            theme="ocf-cosmic-" + finish,
            resolution=320,
            title_override="Énergie et attention " * 100,
            overrides={"font": font_path},
            dry_run=True,
        )


def test_gallery_generation_custom_controls_and_inventory_rejection(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    custom = tmp_path / "theme.json"
    custom.write_text(
        json.dumps({"extends": "ocf-cosmic-light", "id": "custom-cosmic"}), encoding="utf-8"
    )
    root = tmp_path / "review"
    brand_import.comparison_gallery(root, ui_theme="ocf-cosmic-dark", artwork_theme=str(custom))
    assert brand_import.comparison_gallery(root, check=True)["status"] == "passed"
    html = (root / "index.html").read_text(encoding="utf-8")
    assert "Selected artwork theme: custom-cosmic" in html
    assert '"custom": {"background": "#050C21"' in html
    with pytest.raises(OCFError, match="already exists"):
        brand_import.comparison_gallery(root)
    manifest = root / "manifest.json"
    raw = manifest.read_text(encoding="utf-8")
    report = json.loads(raw)
    (root / "previous-dark.svg").unlink()
    report["files"].pop("previous-dark.svg")
    manifest.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(OCFError, match="inventory"):
        brand_import.comparison_gallery(root, check=True)
    manifest.write_text(raw, encoding="utf-8")
    (root / "previous-dark.svg").write_text("tampered", encoding="utf-8")
    with pytest.raises(OCFError, match="checksum"):
        brand_import.comparison_gallery(root, check=True)
    (root / "unexpected.txt").write_text("extra")
    with pytest.raises(OCFError, match="inventory"):
        brand_import.comparison_gallery(root, check=True)


def test_committed_import_gallery():
    root = artwork.BRAND / "versions/0.3.0/gallery"
    assert brand_import.comparison_gallery(root, check=True)["status"] == "passed"
    html = (root / "index.html").read_text(encoding="utf-8")
    assert "not exact copies" in html and "Independent interface theme" in html
    for size in (32, 64, 128):
        assert f'width="{size}"' in html
    assert "1200 × 1200" in html and "1280 × 640" in html
