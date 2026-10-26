"""Isolated cover policy, native-picture parsing and export failure boundaries.

No repository catalogues, real codecs, voices or subprocesses are used here.
The existing repository/codec integration tests retain their classifications.
"""

import json
from types import SimpleNamespace as NS

import pytest
from ocf_tools import artwork_content as content
from ocf_tools import audition_exports as exports
from ocf_tools import brand_import
from ocf_tools.locale import LocalizationError, NarrationResource
from ocf_tools.utils import OCFError, sha256_of_file

pytestmark = pytest.mark.unit


@pytest.fixture
def policy(monkeypatch):
    primary = NS(
        id="PRIMARY",
        designation="primary",
        role="activation",
        data={"spoken_review": "reviewed"},
        localization={"display_cue_key": "unit.display", "spoken_cue_key": "unit.spoken"},
    )
    secondary = NS(id="MODE", designation="secondary", role="mode", data={}, localization={})
    historical = NS(
        id="OLD", designation="secondary", role="legacy-alias", data={}, localization={}
    )
    unavailable = NS(
        id="INACTIVE",
        designation="secondary",
        role="mode",
        data={"availability": "historical-lookup"},
        localization={},
    )
    owner = NS(
        id="OCF-TST-999",
        command_records=[primary, secondary, historical, unavailable],
        documentation={"purpose_key": "unit.purpose"},
    )
    entries = {
        "unit.display": NS(text="PLUS-UNIT", status="reviewed", version="1.0.0"),
        "unit.purpose": NS(text="Synthetic unit purpose", status="reviewed", version="1.0.0"),
        "functions.ocf-tst-999.artwork-description": NS(
            text="Synthetic unit copy", status="draft", version="1.0.0"
        ),
    }
    view = {"binding_status": "resolved", "display_locale": "en-US", "spoken_locale": "en-US"}
    calls = []

    def localized(owner_arg, command, locale, **kwargs):
        assert owner_arg is owner
        calls.append((command.id, locale, kwargs["strict"]))
        return {
            "command_id": command.id,
            "display_cue": "PLUS-UNIT" if command is primary else "PLUS-UNIT MODE",
            "spoken_cue": "Synthetic spoken cue",
            **view,
        }

    resources = []

    def resource(key, locale, *, domain, fallback):
        resources.append((key, locale, domain, fallback))
        if key not in entries:
            raise LocalizationError("missing unit resource " + key)
        item = entries[key]
        entry = NarrationResource(
            key=key,
            locale=locale,
            domain=domain,
            text=item.text,
            status=item.status,
            version=item.version,
        )
        return entry, NS(origin_locale=locale, fallback=False)

    catalog = NS(resource=resource, plural_rules_for=lambda _: None)
    monkeypatch.setattr(content, "load_function_by_id", lambda _: owner)
    monkeypatch.setattr(content, "LocaleCatalog", lambda: catalog)
    monkeypatch.setattr(content, "localized_cue", localized)
    return NS(
        owner=owner,
        primary=primary,
        entries=entries,
        view=view,
        calls=calls,
        resources=resources,
        catalog=catalog,
    )


def test_policy_uses_primary_filters_history_and_preserves_secondary_metadata(policy):
    result = content.function_artwork_content(policy.owner.id)
    assert result["primary"]["command_id"] == "PRIMARY"
    assert [c["command_id"] for c in result["secondary_commands"]] == ["MODE"]
    assert result["description"] == "Synthetic unit copy"
    assert all(not call[-1] for call in policy.resources)
    tags = content.content_tags(result)
    assert tags["OCF_SHORT_DESCRIPTION"] == "Synthetic unit copy"
    assert tags["OCF_DESCRIPTION_REVIEW"] == "draft"
    assert tags["OCF_FUNCTION_PURPOSE"] == "Synthetic unit purpose"
    assert json.loads(tags["OCF_SECONDARY_COMMANDS"])[0]["command_id"] == "MODE"
    assert "description" not in tags  # Do not alias/overwrite existing comments.


def test_optional_copy_missing_is_omitted_but_missing_purpose_is_not(policy):
    policy.entries.pop("functions.ocf-tst-999.artwork-description")
    result = content.function_artwork_content(policy.owner.id)
    assert result["description"] is None
    assert result["description_resolution"]["status"] == "missing-for-locale"
    assert "OCF_SHORT_DESCRIPTION" not in content.content_tags(result)
    policy.entries.pop("unit.purpose")
    with pytest.raises(LocalizationError, match="missing unit resource"):
        content.function_artwork_content(policy.owner.id)


def test_unreviewed_purpose_and_translated_copy_fail_in_strict_mode(policy):
    policy.entries["unit.purpose"].status = "draft"
    with pytest.raises(LocalizationError, match="locale review"):
        content.function_artwork_content(policy.owner.id)
    policy.entries["unit.purpose"].status = "reviewed"
    policy.owner.command_records = [policy.primary]
    policy.view.update(display_locale="es", spoken_locale="es")
    with pytest.raises(LocalizationError, match="locale review"):
        content.function_artwork_content(policy.owner.id, "es")
    policy.entries["functions.ocf-tst-999.artwork-description"].status = "reviewed"
    assert content.function_artwork_content(policy.owner.id, "es")["description"]


def test_no_silent_display_or_spoken_language_fallback(policy):
    policy.owner.command_records = [policy.primary]
    policy.entries["functions.ocf-tst-999.artwork-description"].status = "reviewed"
    policy.view.update(display_locale="es", spoken_locale="en-US")
    with pytest.raises(LocalizationError, match="across languages"):
        content.function_artwork_content(policy.owner.id, "es")
    policy.primary.localization.pop("display_cue_key")
    with pytest.raises(LocalizationError, match="display cue binding is missing"):
        content.function_artwork_content(policy.owner.id, "es")


def test_unreviewed_primary_fails_and_explicit_preview_fallback_is_recorded(policy):
    policy.view["binding_status"] = "requires-locale-review"
    with pytest.raises(LocalizationError, match="reviewed cue"):
        content.function_artwork_content(policy.owner.id)
    result = content.function_artwork_content(policy.owner.id, strict=False)
    assert result["strict_locale"] is False
    assert all(call[-1] for call in policy.resources)


def test_english_source_review_is_not_a_translation_review(policy):
    policy.entries["unit.display"].status = None
    assert (
        content.function_artwork_content(policy.owner.id)["primary"]["display_cue"] == "PLUS-UNIT"
    )
    policy.primary.data["spoken_review"] = "unresolved"
    with pytest.raises(LocalizationError, match="locale review"):
        content.function_artwork_content(policy.owner.id)


def test_english_parent_command_without_resource_keeps_source_identity(policy, monkeypatch):
    policy.owner.command_records = [policy.primary]
    policy.primary.localization = {}
    calls = []

    def source(owner, command, locale, **kwargs):
        calls.append(locale)
        return {
            "binding_status": "unbound" if locale == "en-GB" else "resolved",
            "spoken_locale": "en-US",
            "display_cue": "PLUS-UNIT",
            "spoken_cue": "Synthetic",
        }

    monkeypatch.setattr(content, "localized_cue", source)
    policy.entries["functions.ocf-tst-999.artwork-description"].status = "reviewed"
    result = content.function_artwork_content(policy.owner.id, "en-GB")
    assert calls == ["en-GB", "en-US"]
    assert result["primary"]["requested_locale"] == "en-GB"
    assert result["primary"]["spoken_fallback"] is True


def test_unknown_and_cueless_functions_never_invent_primary_identity(policy, monkeypatch):
    policy.owner.command_records = []
    policy.owner.documentation = {}
    result = content.function_artwork_content(policy.owner.id)
    assert result["primary"] is None and result["purpose"] is None
    assert "OCF_PRIMARY_DISPLAY_CUE" not in content.content_tags(result)
    monkeypatch.setattr(content, "load_function_by_id", lambda _: None)
    with pytest.raises(OCFError, match="unknown artwork function"):
        content.function_artwork_content("OCF-TST-999")


@pytest.fixture
def font_bytes():
    from PIL import ImageFont

    return ImageFont.load_default(size=32).path.getvalue()


@pytest.mark.parametrize("size", [128, 256, 512, 2400])
def test_pure_layout_reserves_footer_prioritizes_cue_and_suppresses_small_copy(font_bytes, size):
    layout = brand_import.cover_layout(
        "Unit title",
        "Unit footer v0.1.0",
        font_bytes,
        size,
        cue="PLUS-UNIT",
        description="Synthetic artwork copy",
    )
    assert layout["title_lines"] == ["Unit title"]
    assert layout["cue_lines"] == ["PLUS-UNIT"]
    assert bool(layout["description_lines"]) == (size >= 512)
    assert layout["font_sizes"]["title"] > layout["font_sizes"]["cue"]
    assert layout["bounds"]["title"][-1][3] < layout["bounds"]["cue"][0][1]
    assert all(
        b[3] < layout["bounds"]["footer"][1]
        for region in ("title", "cue", "description")
        for b in layout["bounds"][region]
    )


def test_pure_layout_wraps_words_and_handles_description_only_and_legacy_title(font_bytes):
    wrapped = brand_import.cover_layout(
        "A longer synthetic title with deliberately wrapped words",
        "Footer",
        font_bytes,
        512,
        cue="PLUS-A LONG SYNTHETIC CUE",
        description="A synthetic description with enough text to use multiple readable lines in the reserved area",
    )
    assert len(wrapped["title_lines"]) > 1
    description_only = brand_import.cover_layout(
        "Title", "Footer", font_bytes, 512, description="Description"
    )
    assert description_only["cue_lines"] == [] and description_only["description_lines"] == [
        "Description"
    ]
    legacy = brand_import.cover_layout("Original title layout", "Footer", font_bytes, 512)
    assert legacy["title_lines"] and "cue_lines" not in legacy
    with pytest.raises(OCFError, match="header/identifier"):
        brand_import.cover_layout("Title", "X" * 300, font_bytes, 512)
    with pytest.raises(OCFError, match="cannot fit legibly"):
        brand_import.cover_layout("X" * 1000, "Footer", font_bytes, 512, cue="PLUS-UNIT")


@pytest.mark.parametrize("description_color", [None, "#888888"])
def test_raster_uses_existing_image_and_role_colors_with_injected_asset(
    tmp_path, monkeypatch, font_bytes, description_color
):
    from PIL import Image

    path = tmp_path / "synthetic-emblem.png"
    Image.new("RGB", (16, 16), "#345678").save(path)
    monkeypatch.setattr(brand_import, "asset", lambda *args: path)
    layout = brand_import.cover_layout(
        "Unit title", "Footer", font_bytes, 512, cue="PLUS-UNIT", description="Description"
    )
    theme = {"palette": {"background": "#001122", "foreground": "#FFFFFF", "accent": "#00FFFF"}}
    image = brand_import.cover_raster(
        layout, theme, font_bytes, 512, description_color=description_color
    )
    assert image.size == (512, 512)
    assert image.getpixel((256, 160)) == (0x34, 0x56, 0x78)
    assert image.getpixel((0, 0)) == (0, 0x11, 0x22)
    assert (0, 255, 255) in {color for _, color in image.getcolors(512 * 512)}


def test_native_front_cover_blocks_and_malformed_frames_are_bounded(tmp_path):
    flac = tmp_path / "unit.flac"
    flac.write_bytes(b"fLaC" + b"\x00\x00\x00\x02xx" + b"\x86\x00\x00\x04" + (3).to_bytes(4, "big"))
    assert exports.front_cover_type(flac) == 3
    payload = b"\0image/png\0\x03\0synthetic-png"
    frame = b"APIC" + len(payload).to_bytes(4, "big") + b"\0\0" + payload
    mp3 = tmp_path / "unit.mp3"
    mp3.write_bytes(b"ID3\x03\0\0\0\0\0" + bytes([len(frame)]) + frame)
    assert exports.front_cover_type(mp3) == 3
    for bad in [
        b"unknown",
        b"fLaC\x80\0\0\0",
        b"ID3\x03\0\0\0\0\0\x0a" + b"APIC" + b"\0" * 6,
        b"ID3\x03\0\0\0\0\0\x0b" + b"APIC\0\0\0\x05\0\0x",
    ]:
        mp3.write_bytes(bad)
        with pytest.raises(OCFError, match="front-cover"):
            exports.front_cover_type(mp3)


def test_audio_probe_and_hash_failure_paths_do_not_launch_processes(tmp_path, monkeypatch):
    monkeypatch.setattr(exports.shutil, "which", lambda _: None)
    with pytest.raises(OCFError, match="ffprobe is required"):
        exports._probe(tmp_path / "unit.mp3")
    monkeypatch.setattr(exports.shutil, "which", lambda _: "mock-ffmpeg")
    monkeypatch.setattr(exports, "_ffmpeg", lambda: "mock-ffmpeg")
    response = NS(returncode=1, stdout="", stderr="decode fixture failure")
    monkeypatch.setattr(exports, "workspace_run", lambda *a, **k: response)
    with pytest.raises(OCFError, match="could not inspect"):
        exports._probe(tmp_path / "unit.mp3")
    with pytest.raises(OCFError, match="integrity check failed"):
        exports.audio_hash(tmp_path / "unit.mp3")
    response.returncode = 0
    response.stdout = json.dumps({"streams": [], "format": {"duration": "1"}})
    with pytest.raises(OCFError, match="exactly one audio stream"):
        exports._probe(tmp_path / "unit.mp3")
    response.stdout = json.dumps(
        {
            "streams": [
                {"codec_type": "audio", "codec_name": "mp3", "channels": 2, "sample_rate": "44100"}
            ],
            "format": {"duration": "1.25", "tags": {"ARTIST": "Unit narrator"}},
        }
    )
    assert exports._probe(tmp_path / "unit.mp3")["tags"] == {"artist": "Unit narrator"}
    response.stdout = "malformed hash response"
    with pytest.raises(OCFError, match="integrity check failed"):
        exports.audio_hash(tmp_path / "unit.mp3")
    response.stdout = "SHA256=unit-hash\n"
    assert exports.audio_hash(tmp_path / "unit.mp3", packets=True) == "unit-hash"


def test_source_artifact_escape_size_and_checksum_errors(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    path = root / "unit.txt"
    path.write_text("unit artifact", encoding="utf-8")
    item = exports._artifact(path)
    assert exports._source_artifact(root, item) == path
    for unsafe in ["../unit.txt", "C:\\outside.txt", "/outside.txt", "..\\outside.txt"]:
        with pytest.raises(OCFError, match="unsafe"):
            exports._source_artifact(root, item | {"path": unsafe})
    with pytest.raises(OCFError, match="truncated"):
        exports._source_artifact(root, item | {"size_bytes": 0})
    with pytest.raises(OCFError, match="checksum"):
        exports._source_artifact(root, item | {"sha256": "0" * 64})
    assert sha256_of_file(path) == item["sha256"]


def test_edition_authority_binding_and_validation_errors_are_source_independent(
    tmp_path, monkeypatch
):
    # Structural schema validation has real repository integration coverage;
    # here isolate version precedence and exact source/voice identity coupling.
    validation = []
    monkeypatch.setattr(exports, "_load_schema", lambda _: {})
    monkeypatch.setattr(exports, "validate_against_schema", lambda *args: validation[:])
    report_path = tmp_path / "synthetic-report.json"
    report_path.write_text("synthetic metadata fixture", encoding="utf-8")
    report = {
        "function_id": "OCF-TST-999",
        "requested_locale": "en-US",
        "voice_profile": {"id": "unit-voice"},
        "artifacts": {"wav": {"sha256": "a" * 64}},
        "template": {"version": "9.9.9"},
        "narration_version": "8.8.8",
    }
    with pytest.raises(OCFError, match="missing audio/session edition"):
        exports._edition(report, report_path, None, None)
    edition, origin = exports._edition(report, report_path, "0.1.0", None)
    assert origin == "explicit-audition-edition" and edition["kind"] == "private-audition"
    assert edition["publication_approval"] is False and edition["human_listening_approval"] is None
    assert edition["session_report_sha256"] == sha256_of_file(report_path)
    file = tmp_path / "edition.json"
    file.write_text(json.dumps(edition), encoding="utf-8")
    assert exports._edition(report, report_path, None, file) == (edition, "audition-edition-record")
    with pytest.raises(OCFError, match="conflicts"):
        exports._edition(report, report_path, "0.2.0", file)
    report["voice_profile"]["id"] = "different-unit-voice"
    with pytest.raises(OCFError, match="different audio, voice"):
        exports._edition(report, report_path, None, file)
    report["voice_profile"]["id"] = "unit-voice"
    validation.append("synthetic schema error")
    with pytest.raises(OCFError, match="invalid audition edition record"):
        exports._edition(report, report_path, None, file)
    with pytest.raises(OCFError, match="invalid audition edition:"):
        exports._edition(report, report_path, "invalid", None)
    validation.clear()
    report["audition_version"] = "1.2.3"
    assert exports._edition(report, report_path, None, None)[1] == "render-audition-version"
    report.pop("audition_version")
    report["audio_implementation_id"] = "unit-audio"
    monkeypatch.setattr(
        exports, "find_audio_manifest", lambda _: {"function_id": "OCF-TST-999", "version": "2.3.4"}
    )
    assert exports._edition(report, report_path, None, None)[0]["version"] == "2.3.4"
    assert exports._edition(report, report_path, None, None)[1] == "registered-audio-implementation"
    monkeypatch.setattr(exports, "find_audio_manifest", lambda _: None)
    with pytest.raises(OCFError, match="missing audio/session edition"):
        exports._edition(report, report_path, None, None)
