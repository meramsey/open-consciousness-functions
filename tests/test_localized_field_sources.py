"""L2 preparation: exact field provenance through the existing locale loader."""

import copy

import pytest
import yaml
from ocf_tools.locale import LocaleCatalog, LocalizationError
from test_localized_function_resources import (
    COMMAND_ID,
    FUNCTION_ID,
    function_record,
    function_resource,
    write_pack,
)

pytestmark = pytest.mark.unit


def literal_resource():
    data = function_resource()
    data["title"] = {"text": "Localized title", "status": "reviewed", "version": "1.2.0"}
    data["description"] = {
        "text": "Existing approved description.",
        "status": "reviewed",
        "version": "1.0.0",
    }
    data["activation"]["display_cue"] = {"text": "PLUS-EMPATHIZE", "version": "1.0.0"}
    data["activation"]["spoken_cue"] = {"text": "Plus Empathize", "version": "1.0.0"}
    return data


def test_trace_points_to_actual_yaml_attributes_and_versions(tmp_path):
    write_pack(tmp_path, literal_resource())
    catalog = LocaleCatalog(tmp_path, function_records=lambda: [function_record()])
    assert catalog.problems == []
    trace = catalog.function_field_sources(FUNCTION_ID, "en-US")
    assert trace["resolved_locale"] == "en-US" and trace["fallback"] is False
    title = trace["fields"]["/title/text"]
    assert title == {
        "file": "locales/en-US/OCF-EMO-003-Empathize.yaml",
        "yaml_pointer": "/title/text",
        "value": "Localized title",
    }
    assert trace["fields"]["/title/version"]["value"] == "1.2.0"
    assert trace["fields"]["/activation/command_id"]["value"] == COMMAND_ID
    assert (
        trace["fields"]["/entries/hplus.function.ocf-emo-003.opener/text"]["value"]
        == "An unchanged opener."
    )
    assert trace["fields"]["/tags"]["value"] == []


def test_modifying_localized_title_changes_alias_and_trace_not_global_record(tmp_path):
    data = literal_resource()
    folder = write_pack(tmp_path, data)
    before = copy.deepcopy(function_record())
    data["title"]["text"] = "Changed fixture title"
    (folder / "OCF-EMO-003-Empathize.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    catalog = LocaleCatalog(tmp_path, function_records=lambda: [function_record()])
    assert (
        catalog.function_field_sources(FUNCTION_ID, "en-US")["fields"]["/title/text"]["value"]
        == "Changed fixture title"
    )
    assert (
        catalog.resource("functions.ocf-emo-003.title", "en-US", domain="ui", fallback=False)[
            0
        ].text
        == "Changed fixture title"
    )
    assert function_record().canonical_name == before.canonical_name == "Empathize"


def test_trace_uses_literal_values_and_never_falls_back_for_missing_function_locale(tmp_path):
    write_pack(tmp_path, function_resource())
    catalog = LocaleCatalog(tmp_path, function_records=lambda: [function_record()])
    trace = catalog.function_field_sources(FUNCTION_ID, "en-US")
    assert trace["fields"]["/title/text"]["value"] == "Empathize"
    with pytest.raises(LocalizationError, match="no localized function metadata"):
        catalog.function_field_sources(FUNCTION_ID, "es")


def test_arrays_and_dotted_resource_keys_have_unambiguous_field_pointers(tmp_path):
    data = literal_resource()
    data["tags"] = [{"text": "Approved fixture tag", "status": "reviewed", "version": "1.0.0"}]
    write_pack(tmp_path, data)
    catalog = LocaleCatalog(tmp_path, function_records=lambda: [function_record()])
    trace = catalog.function_field_sources(FUNCTION_ID, "en-US")
    assert trace["fields"]["/tags/0/text"]["value"] == "Approved fixture tag"
    assert all(row["yaml_pointer"] == pointer for pointer, row in trace["fields"].items())
