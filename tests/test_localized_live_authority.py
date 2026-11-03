"""Live L2 reader contracts: literal YAML, immutable compatibility, no audio."""

import json

import pytest
import yaml
from ocf_tools import agent_api, generators, listening_guides, locale
from ocf_tools.command_docs import build_command_index
from ocf_tools.content import discover
from ocf_tools.locale import LocaleCatalog
from ocf_tools.localized_activation import digest
from ocf_tools.localized_authority import description, title
from test_localized_catalog_trace import literal_catalog as isolated_catalog
from test_localized_function_resources import function_record, function_resource, write_pack


@pytest.fixture
def literal_catalog(tmp_path):
    return isolated_catalog.__wrapped__(tmp_path)


@pytest.mark.unit
def test_superseded_compatibility_words_cannot_override_yaml_or_be_edited(tmp_path):
    data = function_resource()
    data["title"] = {"text": "Authoritative fixture title", "version": "2.0.0"}
    folder = write_pack(tmp_path, data)
    predecessor = {
        "schema_version": "1.0",
        "locale": "en-US",
        "domain": "ui",
        "entries": {"functions.ocf-emo-003.title": "Old compatibility title"},
    }
    (folder / "old.yaml").write_text(yaml.safe_dump(predecessor), encoding="utf-8")
    manifest = yaml.safe_load((folder / "manifest.yaml").read_text())
    manifest["resources"].insert(
        0,
        {
            "file": "old.yaml",
            "domain": "ui",
            "superseded_keys": ["functions.ocf-emo-003.title"],
            "compatibility_sha256": digest(
                json.dumps(predecessor, sort_keys=True, ensure_ascii=False)
            ),
        },
    )
    (folder / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    catalog = LocaleCatalog(tmp_path, function_records=lambda: [function_record()])
    assert catalog.problems == []
    assert (
        catalog.resource("functions.ocf-emo-003.title", "en-US", domain="ui", fallback=False)[
            0
        ].text
        == "Authoritative fixture title"
    )
    predecessor["entries"]["functions.ocf-emo-003.title"] = "Forbidden competing edit"
    (folder / "old.yaml").write_text(yaml.safe_dump(predecessor), encoding="utf-8")
    assert any(
        "compatibility resource drift" in error for error in LocaleCatalog(tmp_path).problems
    )


@pytest.mark.integration
def test_yaml_title_and_description_propagate_across_reader_outputs(
    literal_catalog, monkeypatch, capsys
):
    records, original, catalog = literal_catalog
    record = records[0]
    pack = catalog.require("en-US")
    # Change the isolated YAML, then reconstruct the ordinary resource catalog.
    source = pack.path / pack.localized_function_files[record.id]
    data = yaml.safe_load(source.read_text())
    data["title"]["text"] = "Distinctive fixture title"
    data["description"]["text"] = "Existing fixture description changed deliberately."
    data["tags"] = [{"text": "Synthetic fixture tag", "status": "reviewed", "version": "1.0.0"}]
    data["common_uses"] = [
        {"text": "Synthetic fixture use", "status": "reviewed", "version": "1.0.0"}
    ]
    source.write_text(yaml.safe_dump(data), encoding="utf-8")
    changed = LocaleCatalog(catalog.root, function_records=lambda: records)
    changed.require("en-US").entries.update(
        {
            k: v
            for k, v in original.require("en-US").entries.items()
            if k not in changed.require("en-US").entries
        }
    )
    assert changed.problems == []
    monkeypatch.setattr(locale, "LocaleCatalog", lambda *a, **k: changed)
    monkeypatch.setattr("ocf_tools.localized_authority.LocaleCatalog", lambda *a, **k: changed)
    monkeypatch.setattr(listening_guides, "LocaleCatalog", lambda *a, **k: changed)
    assert title(record) == "Distinctive fixture title"
    assert description(record) == data["description"]["text"]
    assert (
        generators.row_for(record, catalog=changed)["canonical_name"] == "Distinctive fixture title"
    )
    assert "Distinctive fixture title" in generators.function_index_markdown()
    assert "Distinctive fixture title" in generators.function_index_csv()
    assert "Distinctive fixture title" in generators.function_index_json()
    command_index = build_command_index("en-US", catalog=changed)
    assert len(command_index["functions"]) == 58
    row = next(r for r in command_index["functions"] if r["function_id"] == record.id)
    assert row["title"]["text"] == "Distinctive fixture title"
    assert row["short_description"]["text"] == data["description"]["text"]
    assert discover(record)["title"] == "Distinctive fixture title"
    api = agent_api.get_function(record.id)
    assert api["data"]["name"] == "Distinctive fixture title"
    assert api["data"]["purpose"] == data["description"]["text"]
    assert api["data"]["tags"] == data["tags"]
    assert discover(record)["common_uses"] == data["common_uses"]
    assert row["tags"] == data["tags"]
    guide = listening_guides.function_guide_markdown(record, catalog=changed)
    assert "Synthetic fixture tag" in guide and "Synthetic fixture use" in guide
    listing = agent_api.list_functions(limit=10)
    assert any(r["name"] == "Distinctive fixture title" for r in listing["items"])
    assert "Distinctive fixture title" in listening_guides._guide_catalog(records)
    assert b"Distinctive fixture title" in listening_guides.portable_index_html(records)
    from ocf_tools.cli import main
    from ocf_tools.vocabulary import lookup

    assert main(["functions", "describe", record.id, "--json"]) == 0
    cli_result = json.loads(capsys.readouterr().out)
    assert cli_result["functions"][0]["canonical"]["name"] == "Distinctive fixture title"
    assert (
        lookup("Distinctive fixture title", records=records, catalog=changed)[0]["function_id"]
        == record.id
    )
    assert record.canonical_name != "Distinctive fixture title"
    from dataclasses import replace

    from ocf_tools import validators

    monkeypatch.setattr(validators, "LocaleCatalog", lambda: changed)
    checked = validators.validate_command_metadata(records)
    assert not [issue for issue in checked.issues if issue.code == "function-source-authority"]
    key = record.documentation["title_key"]
    changed.require("en-US").entries[key] = replace(
        changed.require("en-US").entries[key], text="Shadowing alias"
    )
    checked = validators.validate_command_metadata(records)
    assert any(
        issue.code == "function-source-authority" and issue.target == record.id
        for issue in checked.issues
    )


@pytest.mark.integration
def test_approved_relationship_words_come_from_function_yaml(literal_catalog):
    records, original, catalog = literal_catalog
    record = next(record for record in records if record.id == "OCF-BOD-006")
    pack = catalog.require("en-US")
    source = pack.path / pack.localized_function_files[record.id]
    data = yaml.safe_load(source.read_text())
    relation = data["relationships"]["related_functions"][0]
    assert relation["function_id"] == "OCF-BOD-002"
    relation["description"]["text"] = "Synthetic fixture approved-edge description."
    source.write_text(yaml.safe_dump(data), encoding="utf-8")
    changed = LocaleCatalog(catalog.root, function_records=lambda: records)
    changed.require("en-US").entries.update(
        {
            key: value
            for key, value in original.require("en-US").entries.items()
            if key not in changed.require("en-US").entries
        }
    )
    assert changed.problems == []
    row = next(
        row
        for row in build_command_index("en-US", catalog=changed)["functions"]
        if row["function_id"] == record.id
    )
    assert row["related_functions"][0]["description"]["text"] == relation["description"]["text"]
    assert relation["description"]["text"] in listening_guides.function_guide_markdown(
        record, catalog=changed
    )


@pytest.mark.integration
def test_registry_fallback_cue_becomes_literal_yaml_authority_before_cache(
    literal_catalog, monkeypatch
):
    from ocf_tools import speech_cache
    from ocf_tools.commands import localized_cue
    from ocf_tools.cue_templates import value

    records, original, catalog = literal_catalog
    record = next(record for record in records if record.id == "OCF-BOD-010")
    primary = next(
        command for command in record.command_records if command.designation == "primary"
    )
    assert not primary.localization.get("spoken_cue_key")
    before = localized_cue(record, primary, catalog=catalog)
    source = (
        catalog.require("en-US").path / catalog.require("en-US").localized_function_files[record.id]
    )
    data = yaml.safe_load(source.read_text())
    data["activation"]["spoken_cue"]["text"] = "Synthetic fixture spoken cue"
    data["activation"]["display_cue"]["text"] = "SYNTHETIC-FIXTURE-CUE"
    source.write_text(yaml.safe_dump(data), encoding="utf-8")
    changed = LocaleCatalog(catalog.root, function_records=lambda: records)
    assert changed.problems == []
    cue = localized_cue(record, primary, catalog=changed, strict=True)
    assert cue["spoken_cue"] == "Synthetic fixture spoken cue"
    assert cue["display_cue"] == "SYNTHETIC-FIXTURE-CUE"
    assert cue.get("version") == before.get("version")
    assert value(record, "cue.primary", "en-US", changed)[0] == cue["spoken_cue"]
    assert primary.data["spoken"] != cue["spoken_cue"]
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: {"fixture_voice": "unchanged"})
    spec = {"locale": "en-US"}
    old_key = speech_cache._synthesis_identity(spec, before["spoken_cue"])[1]
    assert speech_cache._synthesis_identity(spec, before["spoken_cue"])[1] == old_key
    assert speech_cache._synthesis_identity(spec, cue["spoken_cue"])[1] != old_key
