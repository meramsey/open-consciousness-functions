import json
from pathlib import Path

import pytest
from ocf_tools import artwork
from ocf_tools.utils import OCFError


def test_themes_are_independent_validated_and_inheritance_is_bounded(tmp_path):
    assert artwork.theme_tokens("ui")["theme"]["id"] == "ocf-light"
    assert artwork.theme_tokens("artwork")["theme"]["id"] == "ocf-dark"
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
    assert "ui.value='ocf-light'" in html and "art.value='ocf-dark'" in html
    assert "https://" not in html


def test_localized_artwork_cache_integrity_and_no_overwrite(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from PIL import Image

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    first = artwork.generate_cover("OCF-SLP-005", resolution=256)
    second = artwork.generate_cover("OCF-SLP-005", resolution=256)
    assert first["sha256"] == second["sha256"] and second["cache"] == "hit"
    with Image.open(first["path"]) as image:
        assert image.size == (256, 256) and image.format == "PNG"
    assert first["settings"]["title"] == "Sleep Easy" and first["human_approval"] is None
    Path(first["path"]).write_bytes(b"broken")
    repaired = artwork.generate_cover("OCF-SLP-005", resolution=256)
    assert repaired["sha256"] == first["sha256"]
    custom = tmp_path / "custom.png"
    custom.write_bytes(b"operator cover")
    with pytest.raises(OCFError, match="overwrite"):
        artwork.generate_cover("OCF-SLP-005", resolution=256, output=custom)
    assert custom.read_bytes() == b"operator cover"
    jpeg = artwork.generate_cover(
        "OCF-FND-002", locale="es", resolution=256, format="jpeg", theme="ocf-light"
    )
    with Image.open(jpeg["path"]) as image:
        assert image.format == "JPEG"


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
    cover = artwork.generate_cover("OCF-SLP-005", resolution=256)
    custom = release.package_release(
        "OCF-SLP-005",
        artwork=cover["path"],
        artwork_theme="missing-theme",
        dry_run=True,
        output=tmp_path / "out",
    )
    assert custom["artwork_provenance"]["source"] == "explicit-user-cover"
