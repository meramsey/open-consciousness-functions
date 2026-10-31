"""Localized function metadata resources share the stable-ID locale catalog."""

import shutil
from types import SimpleNamespace

import pytest
from ocf_tools.locale import LocaleCatalog
from ocf_tools.paths import REPO_ROOT
from ocf_tools.validators import _load_schema, validate_against_schema, validate_locale_packs

pytestmark = pytest.mark.unit

FUNCTION_ID = "OCF-EMO-003"
COMMAND_ID = "OCF-CMD-EMO-003-PRIMARY"


def function_resource():
    return {
        "schema_version": "1.0",
        "locale": "en-US",
        "domain": "function",
        "function_id": FUNCTION_ID,
        "title": {"source": "function-yaml", "field": "title"},
        "description": {"source": "function-yaml", "field": "description"},
        "activation": {
            "command_id": COMMAND_ID,
            "display_cue": {
                "source": "function-yaml",
                "field": "primary-command",
                "command_id": COMMAND_ID,
            },
            "spoken_cue": {
                "source": "function-yaml",
                "field": "spoken-command",
                "command_id": COMMAND_ID,
            },
        },
        "secondary_commands": [],
        "tags": [],
        "common_uses": [],
        "relationships": {"related_functions": [], "complementary_functions": []},
        "changelog": [{"version": "1.0.0", "change": "Migrated without narration edits."}],
        "entries": {
            "hplus.function.ocf-emo-003.opener": {
                "text": "An unchanged opener.",
                "version": "1.1.0",
                "status": "reviewed",
            }
        },
    }


def function_record():
    command = SimpleNamespace(
        id=COMMAND_ID,
        function_id=FUNCTION_ID,
        designation="primary",
        phrase_ref={"source": "canonical-primary"},
        data={"spoken": "Plus Empathize", "spoken_review": "reviewed"},
    )
    return SimpleNamespace(
        id=FUNCTION_ID,
        canonical_name="Empathize",
        purpose_summary="Develops understanding through awareness.",
        canonical_command="PLUS-EMPATHIZE",
        command_records=[command],
    )


def write_pack(root, resource):
    locale = root / "en-US"
    locale.mkdir(parents=True)
    (locale / "manifest.yaml").write_text(
        "schema_version: '1.0'\nlocale: en-US\nlanguage_name: English\n"
        "status: canonical\nsemantic_version: 1.0.0\nresources:\n"
        "- file: OCF-EMO-003-Empathize.yaml\n  domain: function\n",
        encoding="utf-8",
    )
    import yaml

    (locale / "OCF-EMO-003-Empathize.yaml").write_text(
        yaml.safe_dump(resource, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return locale


def test_function_schema_requires_id_first_localized_metadata_and_keeps_entry_schema():
    data = function_resource()
    assert validate_against_schema(data, _load_schema("localized-function.schema.json")) == []
    data["function_id"] = "not-stable"
    assert any(
        "function_id" in error
        for error in validate_against_schema(data, _load_schema("localized-function.schema.json"))
    )


def test_locale_catalog_projects_canonical_references_and_loads_narration_by_key(tmp_path):
    write_pack(tmp_path, function_resource())
    catalog = LocaleCatalog(tmp_path, function_records=lambda: [function_record()])
    assert catalog.problems == []
    title, title_resolution = catalog.resource(
        "functions.ocf-emo-003.title", "en-US", domain="ui", fallback=False
    )
    assert title.text == "Empathize" and title_resolution.origin_locale == "en-US"
    description, _ = catalog.resource(
        "functions.ocf-emo-003.short-description", "en-US", domain="ui", fallback=False
    )
    assert description.text == "Develops understanding through awareness."
    display, _ = catalog.resource(
        f"commands.{COMMAND_ID.lower()}.display-cue",
        "en-US",
        domain="ui",
        fallback=False,
    )
    assert display.text == "PLUS-EMPATHIZE"
    spoken, spoken_resolution = catalog.resource(
        f"commands.{COMMAND_ID.lower()}.spoken-cue",
        "en-US",
        domain="narration",
        fallback=False,
    )
    assert spoken.text == "Plus Empathize" and spoken.status == "reviewed"
    assert (
        catalog.resource(
            "hplus.function.ocf-emo-003.opener", "en-US", domain="narration", fallback=False
        )[0].text
        == "An unchanged opener."
    )
    localized, resolution = catalog.localized_function(FUNCTION_ID, "en-US", fallback=False)
    assert localized["function_id"] == FUNCTION_ID and resolution.fallback is False
    validation = validate_locale_packs(catalog)
    assert not validation.errors and not validation.warnings


def test_function_filename_compatibility_uses_stable_id_not_title(tmp_path):
    root = tmp_path / "locales"
    write_pack(root, function_resource())
    catalog = LocaleCatalog(root, function_records=lambda: [function_record()])
    data, _ = catalog.localized_function(FUNCTION_ID, "en-US")
    assert data["function_id"] == FUNCTION_ID
    assert "Empathize" not in catalog.packs["en-US"].localized_functions.keys()


def test_repository_empathize_resource_uses_stable_filename_and_preserves_cues():
    catalog = LocaleCatalog(REPO_ROOT / "locales")
    assert catalog.problems == []
    assert catalog.packs["en-US"].localized_function_files[FUNCTION_ID] == (
        "OCF-EMO-003-Empathize.yaml"
    )
    assert "hplus-OCF-EMO-003.yaml" not in {
        resource["file"] for resource in catalog.packs["en-US"].manifest["resources"]
    }
    assert (
        catalog.resource(
            f"commands.{COMMAND_ID.lower()}.display-cue",
            "en-US",
            domain="ui",
            fallback=False,
        )[0].text
        == "PLUS-EMPATHIZE"
    )
    spoken = catalog.resource(
        f"commands.{COMMAND_ID.lower()}.spoken-cue",
        "en-US",
        domain="narration",
        fallback=False,
    )[0]
    assert spoken.text == "Plus Empathize" and spoken.status == "reviewed"


def test_noncanonical_locale_root_loads_its_sibling_function_registry(tmp_path):
    root = tmp_path / "locales"
    write_pack(root, function_resource())
    source = REPO_ROOT / "functions/emotion/empathizing.yaml"
    target = tmp_path / "functions/emotion/empathizing.yaml"
    target.parent.mkdir(parents=True)
    shutil.copyfile(source, target)
    (tmp_path / "functions/notes.txt").write_text("not a function", encoding="utf-8")

    catalog = LocaleCatalog(root)
    localized, resolution = catalog.localized_function(FUNCTION_ID, "en-US", fallback=False)
    assert localized["function_id"] == FUNCTION_ID
    assert resolution.origin_locale == "en-US"
    assert catalog.problems == []


def test_function_metadata_alias_collision_is_reported_instead_of_shadowed(tmp_path):
    locale = write_pack(tmp_path, function_resource())
    (locale / "legacy.yaml").write_text(
        "schema_version: '1.0'\nlocale: en-US\ndomain: ui\nentries:\n"
        "  functions.ocf-emo-003.title:\n    text: Legacy title\n    status: canonical\n    version: 1.0.0\n",
        encoding="utf-8",
    )
    manifest = locale / "manifest.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "- file: legacy.yaml\n  domain: ui\n",
        encoding="utf-8",
    )
    catalog = LocaleCatalog(tmp_path, function_records=lambda: [function_record()])
    assert any(
        "duplicates active resource functions.ocf-emo-003.title" in x for x in catalog.problems
    )
