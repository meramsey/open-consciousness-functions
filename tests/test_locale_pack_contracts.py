"""Local synthetic pack loading, fallback and version diagnostics; no translations installed."""

import pytest
import yaml
from ocf_tools import locale as l

pytestmark = pytest.mark.unit


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def make_pack(root, tag="en-US", **extra):
    path = root / tag
    manifest = {
        "locale": tag,
        "status": "canonical" if tag == "en-US" else "draft",
        "semantic_version": "2.0.0",
        "resources": [{"file": "words.yaml", "domain": "narration"}],
        **extra,
    }
    write(path / "manifest.yaml", manifest)
    write(
        path / "words.yaml",
        {"locale": manifest["locale"], "domain": "narration", "entries": {"fixture.key": "Café"}},
    )
    return path, manifest


@pytest.mark.parametrize(
    "change,match",
    [
        ({"locale": None}, "declares no"),
        ({"resources": {}}, "array of objects"),
        ({"resources": [1]}, "array of objects"),
        ({"resources": [{"file": "../private.yaml"}]}, "local .yaml"),
        ({"resources": [{"file": "missing.yaml"}]}, "file is missing"),
    ],
)
def test_manifest_errors_are_explicit_and_never_rewritten(tmp_path, change, match):
    path, manifest = make_pack(tmp_path, **change)
    before = (path / "manifest.yaml").read_bytes()
    with pytest.raises(l.LocalizationError, match=match):
        l.load_pack(path)
    assert (path / "manifest.yaml").read_bytes() == before


def test_missing_invalid_yaml_and_catalog_error_collection(tmp_path):
    with pytest.raises(l.LocalizationError, match="no manifest"):
        l.load_pack(tmp_path / "missing")
    path, manifest = make_pack(tmp_path)
    (path / "manifest.yaml").write_text("[broken")
    assert l.LocaleCatalog(tmp_path).problems
    write(path / "manifest.yaml", manifest)
    (path / "words.yaml").write_text("[broken")
    with pytest.raises(l.LocalizationError, match="cannot read locale resource"):
        l.load_pack(path)
    catalog = l.LocaleCatalog(tmp_path)
    assert catalog.problems and catalog.locales() == []


@pytest.mark.parametrize(
    "data,match",
    [
        ({"locale": "fr", "domain": "narration", "entries": {}}, "does not match pack"),
        ({"locale": "en-US", "domain": "ui", "entries": {}}, "does not match manifest"),
        ({"locale": "en-US", "entries": []}, "entries must be an object"),
        ({"locale": "en-US", "entries": {"BAD": "words"}}, "invalid key"),
        ({"locale": "en-US", "entries": {"fixture.key": 2}}, "string or object"),
        ({"locale": "en-US", "entries": {"fixture.key": {"text": ""}}}, "non-empty"),
        (
            {
                "locale": "en-US",
                "entries": {"fixture.key": {"text": "words", "variables": ["bad name"]}},
            },
            "invalid variable",
        ),
    ],
)
def test_resource_errors_preserve_original_data(tmp_path, data, match):
    path, _ = make_pack(tmp_path)
    write(path / "words.yaml", data)
    before = (path / "words.yaml").read_bytes()
    with pytest.raises(l.LocalizationError, match=match):
        l.load_pack(path)
    assert (path / "words.yaml").read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("variables", "count"),
        ("requires_events", "event.key"),
        ("required_pronunciation", "command"),
        ("pronunciation", []),
        ("timing", "bad"),
    ],
)
def test_entry_shape_errors_are_localization_errors(field, value):
    with pytest.raises(l.LocalizationError, match="must be"):
        l._entry_from_value(
            "fixture.key", {"text": "Words", field: value}, "en-US", "narration", "words.yaml"
        )


def test_duplicate_entries_and_escaping_symlink_are_rejected(tmp_path):
    path, manifest = make_pack(tmp_path)
    manifest["resources"].append({"file": "other.yaml", "domain": "narration"})
    write(path / "manifest.yaml", manifest)
    write(path / "other.yaml", {"locale": "en-US", "entries": {"fixture.key": "Duplicate"}})
    with pytest.raises(l.LocalizationError, match="duplicate key"):
        l.load_pack(path)
    outside = tmp_path / "private.yaml"
    write(outside, {"locale": "en-US", "entries": {"fixture.key": "Private source"}})
    (path / "words.yaml").unlink()
    try:
        (path / "words.yaml").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(l.LocalizationError, match="escapes locale pack"):
        l.load_pack(path)


def test_catalog_directory_variants_duplicates_and_provenance(tmp_path):
    make_pack(tmp_path)
    make_pack(
        tmp_path, "fr", translation={"source_locale": "en-US", "source_semantic_version": "1.0.0"}
    )
    make_pack(tmp_path, "en-us", status="canonical")
    make_pack(tmp_path, "de", locale="es")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "_private").mkdir()
    (tmp_path / "notes.txt").write_text("ignored")
    catalog = l.LocaleCatalog(tmp_path)
    assert catalog.locales() == ["en-US", "fr"]
    assert any("duplicate locale" in error for error in catalog.problems)
    assert any("does not match declared" in error for error in catalog.problems)
    assert catalog.provenance()["fr"]["translation"]["source_locale"] == "en-US"
    assert catalog.coverage("fr") == {"covered": 1, "total": 1, "percent": 100.0}
    pack = catalog.require("fr")
    assert pack.domains() == {"narration"} and "from en-US" in pack.describe()


def test_catalog_duplicate_detection_via_normalized_keys():
    """Test duplicate locale detection via normalized keys, independent of filesystem."""
    from pathlib import Path

    from ocf_tools.locale import LocalePack

    # Create two packs that normalize to the same locale
    pack1 = LocalePack(
        {"locale": "en-US", "status": "canonical", "semantic_version": "1.0.0", "resources": []},
        {"test.key": {"text": "Pack 1"}},
        Path("en-US"),
    )
    pack2 = LocalePack(
        {"locale": "en-us", "status": "draft", "semantic_version": "1.0.0", "resources": []},
        {"test.key": {"text": "Pack 2"}},
        Path("en-us"),
    )

    # Use from_packs to test duplicate detection logic directly
    catalog = l.LocaleCatalog.from_packs([("en-US", pack1), ("en-us", pack2)])

    # The normalized key "en-US" should be registered once with a duplicate error
    assert catalog.locales() == ["en-US"]
    assert any("duplicate locale" in error for error in catalog.problems)


def test_catalog_without_canonical_and_version_gaps_are_explicit(tmp_path):
    path, _ = make_pack(tmp_path, "fr")
    catalog = l.LocaleCatalog(tmp_path)
    assert catalog.canonical is None
    assert catalog.missing_keys("fr") == [] and catalog.unknown_keys("fr") == []
    assert catalog.coverage("fr")["percent"] == 100.0
    assert catalog.stale_keys("fr") == [] and not catalog.stale_translations("fr")
    make_pack(tmp_path)
    catalog = l.LocaleCatalog(tmp_path)
    assert catalog.stale_translations("fr")
    assert catalog.stale_keys("en-US") == []
    assert catalog.canonical.plural_rules() is None
    catalog.canonical.manifest["plural_rules"] = {"one": "n == 1"}
    assert catalog.plural_rules_for("en-US") == {"one": "n == 1"}


def test_resource_render_metadata_pseudo_grammar_and_missing_pack(tmp_path):
    path, _ = make_pack(tmp_path)
    catalog = l.LocaleCatalog(tmp_path)
    catalog.canonical.manifest["plural_rules"] = {"one": "n == 1", "other": "*"}
    pseudo = l.build_pseudo_pack(catalog, "en-US")
    assert pseudo.manifest["plural_rules"] == catalog.canonical.plural_rules()
    resource = l.NarrationResource(
        "fixture.key", "en-US", "narration", "Words", pronunciation={"token": {"espeak-ng": "hint"}}
    )
    assert resource.hint_for("espeak-ng", "token") == "hint"
    assert resource.hint_for("piper", "token") is None
    assert "canonical" in catalog.canonical.describe()
    with pytest.raises(l.LocalizationError, match="no locale pack"):
        catalog.require("de")
    translated, _ = make_pack(tmp_path, "fr")
    data = {
        "locale": "fr",
        "domain": "narration",
        "entries": {"unknown.key": {"text": "Words", "version": "1.0.0"}},
    }
    write(translated / "words.yaml", data)
    catalog = l.LocaleCatalog(tmp_path)
    assert catalog.stale_keys("fr") == []


def test_document_reports_explicit_fallback_missing_keys_and_inline_origins(tmp_path):
    make_pack(tmp_path)
    catalog = l.LocaleCatalog(tmp_path)
    doc = {"timeline": [{"id": "a", "narration_key": "missing.key"}, {"id": "b", "text": "Inline"}]}
    report = l.ResolutionReport()
    resolved = l.resolve_document(doc, "en-US", catalog=catalog, strict=False, report=report)
    assert report.issues and report.inline_events == 1
    assert report.as_dict()["locale"] == "en-US"
    assert resolved["timeline"][0].get("text") is None
    assert l.missing_narration_keys(doc, "en-US", catalog) == ["missing.key"]
    resolved = l.resolve_document(
        {"timeline": [{"id": "a", "narration_key": "fixture.key"}]},
        "de",
        catalog=catalog,
        strict=False,
    )
    assert resolved["narration"]["resolved"][0]["locale"] == "en-US"
    bad_shape = {"timeline": [1, {"id": "a"}], "sections": [1, {"timeline": [1, {"id": "b"}]}]}
    assert [event["id"] for event in l.iter_events(bad_shape)] == ["a", "b"]
