import json
import xml.etree.ElementTree as ET

import pytest
from ocf_tools import artwork
from ocf_tools import brand_refinement as refined
from ocf_tools.utils import OCFError, sha256_of_file


def test_refinement_contract_keeps_baseline_and_independent_defaults():
    assert artwork.identity()["version"] == "0.1.0"
    new = refined.identity()
    assert new["version"] == "0.2.0" and new["human_approval"] is None
    assert set(new["compositions"]) == {"logo", "icon", "app", "album", "social"}
    for finish in ("dark", "light", "minimal"):
        theme = artwork.load_theme("ocf-refined-" + finish)
        assert theme["finish"] == finish and theme["brand_revision"] == "0.2.0"
        assert (
            artwork.contrast(theme["palette"]["background"], theme["palette"]["foreground"]) >= 4.5
        )
    assert artwork.theme_tokens("ui")["theme"]["id"] == "ocf-light"
    assert artwork.theme_tokens("artwork")["theme"]["id"] == "ocf-cosmic-dark"
    for variant in artwork.identity()["variants"]:
        assert artwork.brand_svg(variant) == (
            artwork.BRAND / "candidates" / f"{variant}.svg"
        ).read_text(encoding="utf-8")
    points = new["geometry"]["path"]
    before = [points[3][i] - points[2][i] for i in (0, 1)]
    after = [points[4][i] - points[3][i] for i in (0, 1)]
    assert before[0] * after[1] == before[1] * after[0]  # continuous join tangent
    assert before[0] * after[0] + before[1] * after[1] > 0
    assert new["geometry"]["path_base_width"] > new["geometry"]["path_tip_width"] * 8


def test_vector_compositions_are_original_self_contained_and_typographic(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    ns = {"s": "http://www.w3.org/2000/svg"}
    for variant, dimensions in (
        ("primary", "0 0 1600 560"),
        ("app", "0 0 1000 1000"),
        ("album", "0 0 1000 1000"),
        ("social", "0 0 1600 800"),
    ):
        svg = artwork.brand_svg(variant, "ocf-refined-dark")
        tree = ET.fromstring(svg)
        assert tree.attrib["viewBox"] == dimensions
        assert tree.findall(".//s:linearGradient", ns) and tree.findall(".//s:radialGradient", ns)
        assert not tree.findall(".//s:image", ns) and not tree.findall(".//s:script", ns)
        assert not tree.findall(".//s:text", ns)  # portable outlined wordmark
        assert "Open Consciousness Functions" in svg
        assert "candidate" in svg and "@font-face" not in svg
    icon = ET.fromstring(artwork.brand_svg("monochrome", "ocf-refined-minimal"))
    assert not icon.findall(".//s:linearGradient", ns)


def test_refined_raster_cache_dimensions_and_legibility(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from PIL import Image

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    first = artwork.generate_cover("OCF-SLP-005", theme="ocf-refined-dark", resolution=320)
    repeated = artwork.generate_cover("OCF-SLP-005", theme="ocf-refined-dark", resolution=320)
    assert repeated["cache"] == "hit" and first["sha256"] == repeated["sha256"]
    assert first["settings"]["brand"]["version"] == "0.2.0"
    assert first["human_approval"] is None
    with Image.open(first["path"]) as image:
        assert image.size == (320, 320)
        assert len(set(image.convert("RGB").resize((40, 40)).get_flattened_data())) > 300
    assert first["layout_bounds"]["title"][0][3] < first["layout_bounds"]["footer"][1]
    for size in (32, 64, 128):
        output = tmp_path / f"app-{size}.png"
        artwork.export_brand(output, variant="app", theme="ocf-refined-dark", resolution=size)
        with Image.open(output) as image:
            assert image.size == (size, size) and image.getpixel((0, 0))[3] == 0
    with pytest.raises(OCFError, match="legible"):
        artwork.generate_cover(
            "OCF-SLP-005", theme="ocf-refined-dark", resolution=256, dry_run=True
        )
    with pytest.raises(OCFError, match="legibly"):
        artwork.generate_cover(
            "OCF-SLP-005",
            theme="ocf-refined-dark",
            resolution=320,
            title_override="Unreasonably long title " * 40,
            dry_run=True,
        )


def test_comparison_is_deterministic_non_destructive_and_responsive(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    root = tmp_path / "review"
    refined.comparison_gallery(root, vector_only=True)
    assert refined.comparison_gallery(root, vector_only=True, check=True)["status"] == "passed"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["human_approval"] is None
    assert sha256_of_file(root / "baseline.svg") == sha256_of_file(
        artwork.BRAND / "candidates/primary.svg"
    )
    html = (root / "index.html").read_text(encoding="utf-8")
    for name in (
        "baseline",
        "refined-dark",
        "refined-light",
        "refined-minimal",
        "refined-album",
        "refined-app",
        "refined-social",
    ):
        assert f'id="{name}"' in html
    assert "@media(max-width:720px)" in html and 'loading="lazy"' not in html
    assert 'width="32"' in html and 'width="64"' in html and 'width="128"' in html
    with pytest.raises(OCFError, match="already exists"):
        refined.comparison_gallery(root, vector_only=True)
    second = tmp_path / "second"
    refined.comparison_gallery(second, vector_only=True)
    assert (root / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    (root / "refined-dark.svg").write_text("tampered")
    with pytest.raises(OCFError, match="mismatch"):
        refined.comparison_gallery(root, vector_only=True, check=True)


def test_release_preview_retains_refined_candidate_provenance(monkeypatch, tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from ocf_tools import release

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(
        release,
        "_select_audio_manifest",
        lambda _: {"id": "OCF-AUDIO-9000", "function_id": "OCF-SLP-005"},
    )
    result = release.package_release(
        "OCF-SLP-005",
        artwork_theme="ocf-refined-light",
        artwork_resolution=320,
        dry_run=True,
        output=tmp_path / "out",
    )
    assert result["artwork_provenance"]["brand_version"] == "0.2.0"
    assert result["artwork_provenance"]["review_status"] == "candidate"
    assert result["artwork_provenance"]["publication_approval"] is False
    assert not (tmp_path / "work").exists()


def test_committed_vector_gallery_matches_declared_inputs():
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    assert (
        refined.comparison_gallery(refined.SOURCE.parent / "gallery", vector_only=True, check=True)[
            "status"
        ]
        == "passed"
    )
