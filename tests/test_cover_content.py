"""Cue authority, locale review and responsive cover typography regressions."""

from copy import deepcopy
from dataclasses import replace

import pytest
from ocf_tools import artwork, artwork_content, brand_import
from ocf_tools.commands import CommandMetadataError
from ocf_tools.indexes import load_function_by_id
from ocf_tools.locale import LocaleCatalog, LocalizationError, NarrationResource
from ocf_tools.utils import OCFError

FUNCTIONS = [
    ("OCF-EXP-001", "PLUS-MANIFEST", "Align your intention with the reality you choose"),
    ("OCF-EXP-003", "PLUS-DISSOLVE", "Release unwanted beliefs and recurring patterns"),
    ("OCF-EXP-006", "PLUS-INTUITION", "Strengthen intuitive awareness and understanding"),
    ("OCF-EXP-005", "PLUS-CLEAR ZONE", "An intention for calm, undisturbed personal space"),
]


@pytest.mark.parametrize("owner,cue,description", FUNCTIONS)
def test_content_uses_reviewed_primary_and_independent_proposed_copy(owner, cue, description):
    content = artwork_content.function_artwork_content(owner)
    assert content["primary"]["display_cue"] == cue
    assert content["description"] == description
    assert content["description_resolution"]["status"] == "draft"
    assert content["purpose"]
    tags = artwork_content.content_tags(content)
    assert tags["OCF_PRIMARY_SPOKEN_CUE"] == content["primary"]["spoken_cue"]
    assert tags["OCF_FUNCTION_PURPOSE"] == content["purpose"]
    if owner == "OCF-EXP-005":
        assert len(content["secondary_commands"]) == 2
        assert (
            "Observe" in tags["OCF_SECONDARY_COMMANDS"]
            and "Suspend" in tags["OCF_SECONDARY_COMMANDS"]
        )
        assert "OBSERVE" not in content["primary"]["display_cue"]


def test_artwork_cannot_override_or_ignore_function_cue_authority(monkeypatch):
    record = deepcopy(load_function_by_id("OCF-EXP-001"))
    record.data["canonical"]["command"]["primary"] = "PLUS-SYNTHETIC TEST"
    monkeypatch.setattr(artwork_content, "load_function_by_id", lambda _: record)
    with pytest.raises(CommandMetadataError, match="conflicts with function YAML"):
        artwork_content.function_artwork_content(record.id)


def localized_fixture():
    # Deliberately synthetic locale labels, not proposed real translations.
    catalog = LocaleCatalog()
    pack = catalog.require("es")
    for key, domain, text in [
        ("functions.ocf-exp-001.title", "ui", "TEST TITLE ES"),
        ("functions.ocf-exp-001.purpose", "ui", "TEST PURPOSE ES"),
        ("functions.ocf-exp-001.artwork-description", "ui", "TEST DESCRIPTION ES"),
        ("commands.ocf-cmd-exp-001-primary.display-cue", "ui", "TEST-CUE-ES"),
        ("commands.ocf-cmd-exp-001-primary.spoken-cue", "narration", "TEST SPOKEN ES"),
    ]:
        pack.entries[key] = NarrationResource(
            key=key, locale="es", domain=domain, text=text, status="reviewed", version="1.0.0"
        )
    return catalog


def test_localized_description_and_cue_require_review_without_english_fallback(
    monkeypatch, tmp_path
):
    catalog = localized_fixture()
    content = artwork_content.function_artwork_content("OCF-EXP-001", "es", catalog=catalog)
    assert content["description"] == "TEST DESCRIPTION ES"
    assert content["primary"]["display_cue"] == "TEST-CUE-ES"
    key = "functions.ocf-exp-001.artwork-description"
    catalog.require("es").entries.pop(key)
    missing = artwork_content.function_artwork_content("OCF-EXP-001", "es", catalog=catalog)
    assert missing["description"] is None  # No fallback to the English proposal.
    catalog.require("es").entries[key] = NarrationResource(
        key=key, locale="es", domain="ui", text="TEST DRAFT ES", status="draft"
    )
    with pytest.raises(LocalizationError, match="locale review"):
        artwork_content.function_artwork_content("OCF-EXP-001", "es", catalog=catalog)
    catalog.require("es").entries.pop(key)
    catalog.require("es").entries.pop("commands.ocf-cmd-exp-001-primary.display-cue")
    with pytest.raises(LocalizationError, match="missing resource"):
        artwork_content.function_artwork_content("OCF-EXP-001", "es", catalog=catalog)


@pytest.mark.parametrize("owner,cue,description", FUNCTIONS)
@pytest.mark.parametrize("resolution", [2400, 512, 256, 128])
def test_cover_hierarchy_at_required_sizes(
    owner, cue, description, resolution, tmp_path, monkeypatch
):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from PIL import Image

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    report = artwork.generate_cover(
        owner, resolution=resolution, version="0.1.0", status_label="BETA / PRIVATE"
    )
    with Image.open(report["path"]) as image:
        assert image.size == (resolution, resolution)
        assert image.getbbox()
    settings = report["settings"]
    assert cue in settings["visible_text"]
    assert settings["cue_color"] == "#50D8EF"
    assert settings["content_layout"]["font_sizes"]["cue"] * 128 / 1000 >= 9
    assert (
        settings["content_layout"]["font_sizes"]["title"]
        > settings["content_layout"]["font_sizes"]["cue"]
    )
    assert (description in settings["visible_text"]) == (resolution >= 512)
    boxes = report["layout_bounds"]
    for region in (boxes["title"], boxes["cue"], boxes["description"]):
        for box in region:
            assert 0 <= box[0] < box[2] <= resolution and 0 <= box[1] < box[3] <= resolution
            assert box[3] < boxes["footer"][1]
    assert boxes["title"][-1][3] < boxes["cue"][0][1]
    if boxes["description"]:
        assert boxes["cue"][-1][3] < boxes["description"][0][1]
    if resolution == 128:
        assert boxes["cue"][0][3] - boxes["cue"][0][1] >= 6


def test_wrapping_and_overlong_text_fail_without_clipping():
    pytest.importorskip("PIL")
    raw, _ = artwork._font_assets("pillow-aileron")
    layout = brand_import.cover_layout(
        "An intentionally longer localized function title",
        "OCF-EXP-001 / en-US - v0.1.0",
        raw,
        2400,
        cue="PLUS-A LONG LOCALIZED ACTIVATION CUE",
        description="An independently localized optional description for this function that remains concise and readable.",
    )
    assert len(layout["title_lines"]) > 1 or len(layout["description_lines"]) > 1
    for field in ["title", "cue", "description"]:
        assert layout["bounds"][field][-1][3] < layout["bounds"]["footer"][1]
    with pytest.raises(OCFError, match="cannot fit legibly"):
        brand_import.cover_layout("X" * 1000, "footer", raw, 2400, cue="PLUS-TEST")


@pytest.mark.parametrize("theme", ["ocf-cosmic-dark", "ocf-cosmic-light", "custom"])
def test_theme_compatibility_and_optional_minimalist_layout(theme, tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    if theme == "custom":
        import json

        file = tmp_path / "custom.json"
        file.write_text(json.dumps({"id": "custom-cue", "extends": "ocf-cosmic-light"}))
        theme = str(file)
    detailed = artwork.generate_cover("OCF-EXP-005", theme=theme, resolution=512)
    settings = detailed["settings"]
    palette = settings["theme"]["palette"]
    assert artwork.contrast(settings["cue_color"], palette["background"]) >= 4.5
    assert artwork.contrast(settings["description_color"], palette["background"]) >= 4.5
    no_description = artwork.generate_cover(
        "OCF-EXP-005", theme=theme, resolution=512, show_description=False
    )
    assert not no_description["layout_bounds"]["description"]
    minimalist = artwork.generate_cover(
        "OCF-EXP-005", theme=theme, resolution=512, show_description=False, show_cue=False
    )
    assert "PLUS-CLEAR ZONE" not in minimalist["settings"]["visible_text"]


def test_description_data_changes_artwork_fingerprint_without_narration_changes(
    monkeypatch, tmp_path
):
    pytest.importorskip("PIL")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    first = artwork.generate_cover("OCF-EXP-001", resolution=512)
    catalog = LocaleCatalog()
    key = "functions.ocf-exp-001.artwork-description"
    catalog.require("en-US").entries[key] = replace(
        catalog.require("en-US").entries[key], text="Synthetic alternate artwork description"
    )
    monkeypatch.setattr(artwork, "LocaleCatalog", lambda: catalog)
    second = artwork.generate_cover("OCF-EXP-001", resolution=512)
    assert first["fingerprint"] != second["fingerprint"]
    assert (
        second["settings"]["function_content"]["description"]
        == "Synthetic alternate artwork description"
    )
