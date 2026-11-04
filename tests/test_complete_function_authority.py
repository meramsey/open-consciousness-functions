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
    from ocf_tools.function_authority_migration import build
    from ocf_tools.utils import yaml_safe_load
    from ocf_tools.validators import _load_schema, validate_against_schema

    ledger, writes = build()
    assert len(ledger["files"]) == len(ledger["locale_files"]) == 58
    if not writes:
        return  # Committed successor is checked by build.verify on every call.
    for name, raw in writes.items():
        if not name.startswith("locales/"):
            continue
        data = yaml_safe_load(raw.decode())
        assert not validate_against_schema(data, _load_schema("localized-function.schema.json")), (
            name
        )
        assert completeness(data, data)["status"] == "complete"
        assert not raw.startswith(b"\n")


@pytest.mark.integration
def test_all_functions_load_without_any_physical_global_registry(tmp_path):
    import hashlib
    import shutil

    from ocf_tools.commands import localized_cue
    from ocf_tools.function_catalog import load_functions
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.locale_history import historical_function_resources, read_logical
    from ocf_tools.paths import REPO_ROOT

    shutil.copytree(REPO_ROOT / "locales", tmp_path / "locales")
    shutil.copytree(
        REPO_ROOT / "function-content/editorial", tmp_path / "function-content/editorial"
    )
    assert not (tmp_path / "functions").exists()
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
    for name, row in historical_function_resources(tmp_path).items():
        assert (
            hashlib.sha256(
                read_logical(tmp_path, name, preserve_newlines=True).encode()
            ).hexdigest()
            == row["sha256"]
        )


@pytest.mark.integration
def test_full_migration_resumes_after_publication_interruption_and_is_idempotent(
    tmp_path, monkeypatch
):
    import json
    import shutil

    from ocf_tools import function_authority_migration as migration
    from ocf_tools.paths import REPO_ROOT
    from ocf_tools.utils import OCFError

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    shutil.copytree(REPO_ROOT / "locales", tmp_path / "locales")
    original = json.loads((REPO_ROOT / migration.LEDGER).read_text())
    for name, row in original["files"].items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / row["archive"]).read_bytes())
    for name, row in original["locale_files"].items():
        (tmp_path / name).write_bytes((REPO_ROOT / row["archive"]).read_bytes())
    monkeypatch.setattr(migration, "REPO_ROOT", tmp_path)
    _, planned = migration.build(tmp_path)
    assert len(planned) == 174
    write = migration.write_text_atomic

    def interrupted(path, text, **kwargs):
        if path == tmp_path / migration.LEDGER:
            raise OSError("synthetic interruption before terminal ledger publication")
        return write(path, text, **kwargs)

    monkeypatch.setattr(migration, "write_text_atomic", interrupted)
    with pytest.raises(OSError, match="synthetic interruption"):
        migration.apply(tmp_path)
    assert not (tmp_path / migration.LEDGER).exists()
    monkeypatch.setattr(migration, "write_text_atomic", write)
    receipt = migration.apply(tmp_path)
    assert receipt["functions"] == 58 and receipt["speech_unchanged"]
    assert migration.apply(tmp_path)["status"] == "already-migrated; no writes"
    first = next(iter(original["files"].values()))
    (tmp_path / first["archive"]).write_bytes(b"unauthorized drift")
    with pytest.raises(OCFError, match="archive drift"):
        migration.apply(tmp_path)


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
    record = function_from_dict(source, REPO_ROOT / "functions/cognition/fixture.yaml")
    data = draft_resource(record, LocaleCatalog())
    assert not validate_against_schema(data, _load_schema("localized-function.schema.json"))
    assert data["entries"] == {} and data["localization"]["status"] == "partial"
    assert "historical_record" not in data
    projected = project(data, REPO_ROOT / "locales/en-US/OCF-COG-999-Fixture.yaml", REPO_ROOT)
    assert projected.id == record.id
    assert projected.command_records[0].data["spoken"] is None
