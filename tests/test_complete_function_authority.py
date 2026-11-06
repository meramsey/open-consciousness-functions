"""Complete per-locale schema, structural identity and zero-word-drift migration."""

from copy import deepcopy

import pytest
from ocf_tools.function_catalog import completeness, contract_hash, structural_contract


def fixture():
    data = {
        "function_id": "OCF-COG-001",
        "classification": {"primary_domain": "cognition", "secondary_domains": []},
        "title": {"text": "Fixture"},
        "description": {"text": "Description"},
        "lifecycle": {
            "activation": "manual",
            "persistence": "temporary",
            "release": {"required": False, "command": None},
        },
        "activation": {
            "command_id": "OCF-CMD-COG-001-PRIMARY",
            "display_cue": {"text": "PLUS-FIXTURE"},
            "spoken_cue": {"text": "Plus Fixture", "status": "reviewed"},
            "control": {"designation": "primary", "phrase_ref": {"source": "canonical-primary"}},
        },
        "secondary_commands": [],
        "relationships": {"related_functions": [], "complementary_functions": []},
        "narration": {
            "sequence": [{"key": "fixture.body", "role": "function-body", "repetitions": 4}]
        },
        "entries": {"fixture.body": {"text": "Exact local speech", "status": "reviewed"}},
    }
    data["localization"] = {"status": "complete", "contract_sha256": contract_hash(data)}
    return data


@pytest.mark.unit
def test_contract_ignores_local_words_but_protects_operations_and_repetition():
    canonical = fixture()
    translated = deepcopy(canonical)
    translated["title"]["text"] = "Título"
    translated["activation"]["spoken_cue"]["text"] = "Palabras locales"
    translated["entries"]["fixture.body"]["text"] = "Texto local"
    assert structural_contract(translated) == structural_contract(canonical)
    assert completeness(translated, canonical)["status"] == "complete"
    translated["narration"]["sequence"][0]["repetitions"] = 3
    assert contract_hash(translated) != contract_hash(canonical)


@pytest.mark.unit
def test_partial_missing_and_stale_locales_never_inherit_speech():
    canonical = fixture()
    local = deepcopy(canonical)
    del local["entries"]["fixture.body"]
    local["activation"].pop("spoken_cue")
    result = completeness(local, canonical)
    assert result["status"] == "partial"
    assert result["missing"] == ["OCF-CMD-COG-001-PRIMARY/spoken_cue", "fixture.body"]
    assert completeness(None, canonical)["status"] == "missing"
    local["localization"]["contract_sha256"] = "0" * 64
    assert completeness(local, canonical)["status"] == "needs-review"
    assert "fixture.body" not in local["entries"]


@pytest.mark.integration
def test_all_58_dry_run_resources_preserve_behavior_and_validate():
    from ocf_tools.indexes import load_all_functions
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.paths import REPO_ROOT
    from ocf_tools.validators import _load_schema, validate_against_schema

    resources = LocaleCatalog().require("en-US").localized_functions
    records = load_all_functions()
    assert len(resources) == len(records) == 58
    for record in records:
        data = resources[record.id]
        assert not validate_against_schema(data, _load_schema("localized-function.schema.json"))
        assert completeness(data, data)["status"] == "complete"
        assert data["record_metadata"] and isinstance(data["content"], dict)
        raw = record.path.read_bytes()
        assert not raw.startswith(b"\n")
    assert not (REPO_ROOT / "functions").exists()


@pytest.mark.integration
def test_all_functions_load_without_any_physical_global_registry(tmp_path):
    import shutil

    from ocf_tools.commands import localized_cue
    from ocf_tools.function_catalog import load_functions
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.paths import REPO_ROOT

    shutil.copytree(REPO_ROOT / "locales", tmp_path / "locales")
    shutil.copytree(REPO_ROOT / "schemas", tmp_path / "schemas")
    assert not (tmp_path / "functions").exists()
    assert not (tmp_path / "function-content").exists()
    records = load_functions(tmp_path)
    catalog = LocaleCatalog(tmp_path / "locales")
    assert not catalog.problems
    assert len(records) == 58
    from ocf_tools.authoring import AuthoringService, schema_name

    service = AuthoringService(tmp_path)
    assert len(service.records()) == 58
    first = records[0]
    data = catalog.require("en-US").localized_functions[first.id]
    assert schema_name(first.path, data, tmp_path) == "localized-function.schema.json"
    assert all(
        definition.path.is_relative_to(tmp_path / "locales/en-US")
        for definition in service.definitions[first.id]
    )
    assert all(record.path.is_relative_to(tmp_path / "locales/en-US") for record in records)
    assert {row["status"] for row in catalog.function_completeness("es").values()} == {"missing"}
    for record in records:
        for command in record.command_records:
            if command.data.get("availability", "active") == "active" and command.data.get(
                "spoken"
            ):
                cue = localized_cue(record, command, catalog=catalog, strict=True)
                assert cue["spoken_cue"] == command.data["spoken"]
    assert all("content" in record.data for record in records)
    assert len(list((tmp_path / "locales/en-US").glob("OCF-*.yaml"))) == 58


@pytest.mark.unit
def test_manifest_discovery_rejects_unknown_locale_and_duplicate_id(tmp_path):
    import yaml
    from ocf_tools.function_catalog import resources
    from ocf_tools.utils import OCFError

    with pytest.raises(OCFError, match="unsafe"):
        resources(tmp_path, "../en-US")
    directory = tmp_path / "locales/en-US"
    directory.mkdir(parents=True)
    (directory / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "resources": [
                    {"file": "first.yaml", "domain": "function"},
                    {"file": "second.yaml", "domain": "function"},
                ]
            }
        )
    )
    for name in ("first.yaml", "second.yaml"):
        (directory / name).write_text(
            yaml.safe_dump({"function_id": "OCF-COG-001", "locale": "en-US"})
        )
    with pytest.raises(OCFError, match="duplicate"):
        resources(tmp_path)


@pytest.mark.integration
def test_new_function_draft_is_local_self_contained_and_unrenderable():
    from ocf_tools.function_catalog import draft_resource, project
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.models import function_from_dict
    from ocf_tools.paths import REPO_ROOT
    from ocf_tools.prompts import build_function_yaml
    from ocf_tools.validators import _load_schema, validate_against_schema

    source = build_function_yaml(
        function_id="OCF-COG-999",
        slug="fixture",
        name="Fixture",
        primary_domain="cognition",
        canonical_command="PLUS-FIXTURE",
        short_name="Synthetic authoring fixture",
    )
    record = function_from_dict(source, REPO_ROOT / "locales/en-US/OCF-COG-999-Fixture.yaml")
    data = draft_resource(record, LocaleCatalog())
    assert not validate_against_schema(data, _load_schema("localized-function.schema.json"))
    assert data["entries"] == {} and data["localization"]["status"] == "partial"
    assert data["record_metadata"] and isinstance(data["content"], dict)
    projected = project(data, REPO_ROOT / "locales/en-US/OCF-COG-999-Fixture.yaml", REPO_ROOT)
    assert projected.id == record.id
    assert projected.command_records[0].data["spoken"] is None


@pytest.mark.integration
def test_new_draft_projects_localized_command_procedure_steps():
    from ocf_tools.function_catalog import draft_resource
    from ocf_tools.indexes import load_function_by_id
    from ocf_tools.locale import LocaleCatalog

    record = load_function_by_id("OCF-AUT-001")
    draft = draft_resource(record, LocaleCatalog())
    procedure = next(
        row["procedure_steps"]
        for row in [draft["activation"], *draft["secondary_commands"]]
        if row["command_id"] == "OCF-CMD-AUT-001-PRIMARY"
    )

    assert procedure
    assert procedure[0]["operation"] == "select-activity"
    assert procedure[0]["instruction"]["text"]
    assert procedure[0]["instruction"]["status"] == "canonical"

    metadata_record = load_function_by_id("OCF-EXP-002")
    metadata_draft = draft_resource(metadata_record, LocaleCatalog())
    assert (
        metadata_draft["record_metadata"]["command_phrases"]
        == metadata_record.data["command_phrases"]
    )


@pytest.mark.unit
def test_new_draft_resolves_procedure_operation_fallback_key(monkeypatch):
    from types import SimpleNamespace

    from ocf_tools import commands
    from ocf_tools.function_catalog import draft_resource
    from ocf_tools.indexes import load_function_by_id

    monkeypatch.setattr(
        commands,
        "command_view",
        lambda *args, **kwargs: {
            "resolved_procedure_steps": [{"id": "select", "operation": "select-activity"}]
        },
    )

    class Catalog:
        def __init__(self):
            self.keys = []

        def raw_resource(self, key, locale, **kwargs):
            self.keys.append((key, locale, kwargs))
            return SimpleNamespace(text="Choose an activity", status=None, version="1.0.0"), None

    catalog = Catalog()
    draft = draft_resource(load_function_by_id("OCF-AUT-001"), catalog)
    step = draft["activation"]["procedure_steps"][0]

    assert catalog.keys[0][0] == "command.procedure.select-activity"
    assert step["instruction"] == {"text": "Choose an activity", "version": "1.0.0"}


@pytest.mark.unit
def test_active_checkout_retires_the_legacy_function_registry():
    from ocf_tools.function_catalog import load_functions
    from ocf_tools.paths import REPO_ROOT

    assert not (REPO_ROOT / "functions").exists()
    records = load_functions(REPO_ROOT)
    assert len(records) == 58
    assert all(record.path.is_relative_to(REPO_ROOT / "locales/en-US") for record in records)
