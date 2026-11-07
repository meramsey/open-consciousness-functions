"""Whole-catalog L2 contract preparation in an isolated, non-active locale pack."""

import copy

import pytest
import yaml
from ocf_tools.command_docs import build_command_index
from ocf_tools.commands import localized_cue
from ocf_tools.function_catalog import resources
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocaleCatalog, LocalizationError
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration


@pytest.fixture
def literal_catalog(tmp_path):
    records = load_all_functions()
    original = LocaleCatalog()
    directory = tmp_path / "en-US"
    directory.mkdir()
    manifest_resources = []
    for path, _data in resources(REPO_ROOT):
        filename = path.name
        (directory / filename).write_bytes(path.read_bytes())
        manifest_resources.append({"file": filename, "domain": "function"})
    (directory / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "locale": "en-US",
                "status": "canonical",
                "language_name": "English",
                "semantic_version": "1.0.0",
                "resources": manifest_resources,
            }
        ),
        encoding="utf-8",
    )
    catalog = LocaleCatalog(tmp_path, function_records=lambda: records)
    assert catalog.problems == []
    # Shared UI/preparation keys are not being migrated in this fixture. Keep
    # them in memory without letting old function keys replace literal aliases.
    pack = catalog.require("en-US")
    pack.entries.update(
        {
            key: value
            for key, value in original.require("en-US").entries.items()
            if key not in pack.entries
        }
    )
    return records, original, catalog


def test_all_58_literal_sources_trace_and_preserve_175_entries(literal_catalog):
    records, original, catalog = literal_catalog
    pack = catalog.require("en-US")
    assert len(pack.localized_functions) == len(records) == 58
    count = 0
    for record in records:
        data = pack.localized_functions[record.id]
        trace = catalog.function_field_sources(record.id, "en-US")
        assert trace["fields"]["/title/text"]["value"] == data["title"]["text"]
        assert trace["fields"]["/description/text"]["value"] == data["description"]["text"]
        assert (
            trace["fields"]["/activation/command_id"]["value"] == data["activation"]["command_id"]
        )
        assert len(data["secondary_commands"]) == len(record.command_records) - 1
        for key in data["entries"]:
            before = original.raw_resource(key, "en-US", domain="narration", fallback=False)[0]
            after = catalog.raw_resource(key, "en-US", domain="narration", fallback=False)[0]
            assert (before.text, before.version, before.status) == (
                after.text,
                after.version,
                after.status,
            )
            assert (
                original.resource(key, "en-US", domain="narration", fallback=False)[0].text
                == catalog.resource(key, "en-US", domain="narration", fallback=False)[0].text
            )
            count += 1
        for command in record.command_records:
            old = localized_cue(record, command, catalog=original)
            new = localized_cue(record, command, catalog=catalog)
            # Authority provenance changes deliberately; semantic words,
            # review, locale, version and binding eligibility must not.
            for field in (
                "display_cue",
                "spoken_cue",
                "binding_status",
                "spoken_locale",
                "resource_status",
                "version",
            ):
                assert old.get(field) == new.get(field), (record.id, command.id, field)
    assert count == 175


def test_fixture_title_reaches_command_index_without_global_registry_edit(literal_catalog):
    records, original, catalog = literal_catalog
    pack = catalog.require("en-US")
    selected = records[0]
    data = copy.deepcopy(pack.localized_functions[selected.id])
    data["title"]["text"] = "Synthetic fixture title"
    pack.localized_functions[selected.id] = data
    # Reconstruct aliases using the same ordinary catalog projection, rather
    # than hand-editing a generated index or global function definition.
    prefix = "functions." + selected.id.lower()
    for suffix in ("title", "purpose", "short-description"):
        pack.entries.pop(prefix + "." + suffix, None)
    for key in data.get("metadata_entries", {}):
        pack.entries.pop(key, None)
    for command in selected.command_records:
        for suffix in ("display-cue", "spoken-cue", "label", "explanation", "usage"):
            pack.entries.pop("commands." + command.id.lower() + "." + suffix, None)
    # Project only the changed function; other aliases remain as built.
    other = pack.localized_functions
    pack.localized_functions = {selected.id: data}
    catalog._project_localized_function_aliases()
    pack.localized_functions = other
    assert catalog.problems == []
    index = build_command_index("en-US", catalog=catalog)
    assert len(index["functions"]) == 58
    row = next(row for row in index["functions"] if row["function_id"] == selected.id)
    assert row["title"]["text"] == "Synthetic fixture title"
    assert selected.canonical_name != "Synthetic fixture title"
    assert (
        catalog.function_field_sources(selected.id, "en-US")["fields"]["/title/text"]["value"]
        == "Synthetic fixture title"
    )


@pytest.mark.parametrize("status", [None, "draft"])
def test_unreviewed_spoken_metadata_is_never_promoted_by_global_review(literal_catalog, status):
    records, original, catalog = literal_catalog
    selected = records[0]
    pack = catalog.require("en-US")
    filename = pack.localized_function_files[selected.id]
    path = pack.path / filename
    data = yaml.safe_load(path.read_text())
    if status is None:
        data["activation"]["spoken_cue"].pop("status", None)
    else:
        data["activation"]["spoken_cue"]["status"] = status
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    changed = LocaleCatalog(catalog.root, function_records=lambda: records)
    assert changed.problems == []
    primary = next(
        command for command in selected.command_records if command.designation == "primary"
    )
    assert primary.data["spoken_review"] == "reviewed"
    with pytest.raises(LocalizationError, match="requires locale terminology review"):
        localized_cue(selected, primary, catalog=changed, strict=True)
