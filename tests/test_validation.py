"""Schema validation and collection-rule tests."""

from __future__ import annotations

import json

from ocf_tools.indexes import load_all_functions, load_yaml_file
from ocf_tools.models import FunctionRecord
from ocf_tools.utils import (
    OCFFileExistsError,
    sha256_of_file,
    write_text_atomic,
)
from ocf_tools.validators import (
    spoken_word_count,
    validate_against_schema,
    validate_collection,
    validate_command_rules,
    validate_function_schema,
)


def _schema() -> dict:
    with open("schemas/function.schema.json", encoding="utf-8") as handle:
        return json.load(handle)


def test_sample_function_is_schema_valid(sample_function_path):
    data = load_yaml_file(sample_function_path)
    errors = validate_against_schema(data, _schema())
    assert errors == []


def test_every_function_is_schema_valid():
    schema = _schema()
    for record in load_all_functions():
        errors = validate_against_schema(record.data, schema)
        assert errors == [], f"{record.id}: {errors}"


def test_no_duplicate_ids():
    ids = [r.id for r in load_all_functions()]
    assert len(ids) == len(set(ids))


def test_no_duplicate_primary_commands():
    commands = [r.canonical_command for r in load_all_functions()]
    assert len(commands) == len(set(commands))


def test_fifty_five_legacy_functions():
    assert len(load_all_functions()) == 55


def test_collection_duplicate_id_detection(monkeypatch):
    fake = [
        FunctionRecord(id="OCF-FND-099", slug="a", path=__file__, data={}),
        FunctionRecord(id="OCF-FND-099", slug="b", path=__file__, data={}),
    ]
    monkeypatch.setattr("ocf_tools.validators.load_all_functions", lambda: fake)
    result = validate_collection()
    assert any(i.code == "duplicate-id" for i in result.errors)


def test_collection_duplicate_command_detection(monkeypatch):
    data_a = {
        "canonical": {"command": {"primary": "PLUS-TEST", "modes": []}},
        "aliases": {"commands": []},
    }
    data_b = {
        "canonical": {"command": {"primary": "PLUS-TEST", "modes": []}},
        "aliases": {"commands": []},
    }
    fake = [
        FunctionRecord(id="OCF-FND-097", slug="a", path=__file__, data=data_a),
        FunctionRecord(id="OCF-FND-098", slug="b", path=__file__, data=data_b),
    ]
    monkeypatch.setattr("ocf_tools.validators.load_all_functions", lambda: fake)
    result = validate_collection()
    assert any(i.code == "duplicate-command" for i in result.errors)


def test_spoken_word_count_commas_split_hyphens_do_not():
    assert spoken_word_count("PLUS-FOCUS") == 1
    assert spoken_word_count("PLUS-DO-THIS-NOW") == 1
    assert spoken_word_count("PLUS-CONTROL, BALANCE, RESTORE") == 3
    assert spoken_word_count("PLUS-NO MORE, NO MORE") == 4


def test_missing_plus_prefix_is_error():
    data = {
        "canonical": {"command": {"primary": "FOCUS", "modes": []}},
        "legacy": {"commands": [], "command_status": "unchanged"},
        "aliases": {"commands": []},
        "id": "OCF-FND-001",
        "slug": "x",
    }
    record = FunctionRecord(id=data["id"], slug=data["slug"], path=__file__, data=data)
    result = validate_command_rules(record)
    assert any(i.code == "plus-prefix" and i.severity == "error" for i in result.issues)


def test_changed_command_without_rationale_is_warning():
    data = {
        "id": "OCF-FND-001",
        "slug": "x",
        "canonical": {"command": {"primary": "PLUS-NEW CUE", "modes": []}},
        "legacy": {
            "commands": ["PLUS-OLD"],
            "command_status": "proposed",
            "source_availability": "available",
            "source_system": "x",
            "name": "x",
        },
        "aliases": {"commands": []},
        "ocf": {"command_review": "review-required"},
        "compatibility": {"state": "alias-listed"},
    }
    record = FunctionRecord(id=data["id"], slug=data["slug"], path=__file__, data=data)
    result = validate_command_rules(record)
    assert any(i.code == "no-change-rationale" for i in result.warnings)


def test_atomic_write_and_overwrite_protection(tmp_path):
    target = tmp_path / "sub" / "record.yaml"
    write_text_atomic(target, "a: 1\n")
    assert target.read_text(encoding="utf-8") == "a: 1\n"
    try:
        write_text_atomic(target, "b: 2\n", overwrite=False)
        raise AssertionError("expected OCFFileExistsError")
    except OCFFileExistsError:
        pass
    assert target.read_text(encoding="utf-8") == "a: 1\n"


def test_source_path_with_spaces(tmp_path):
    hashed = tmp_path / "my source file.pdf"
    hashed.write_bytes(b"reference-content")
    digest = sha256_of_file(hashed)
    import hashlib

    assert digest == hashlib.sha256(b"reference-content").hexdigest()


def test_unknown_fields_placeholder_not_required(tmp_path):
    # placeholder values are accepted by the schema rather than breaking it
    data = {
        "schema_version": "1.0",
        "id": "OCF-FND-100",
        "slug": "placeholder-ok",
        "canonical": {"name": "Placeholder", "command": {"primary": None, "modes": []}},
        "legacy": {
            "source_system": "x",
            "name": "",
            "commands": [],
            "command_status": "unchanged",
            "source_availability": "pending-source-review",
        },
        "ocf": {"reimplementation_status": "planned", "command_review": "pending"},
        "aliases": {"names": [], "commands": []},
        "classification": {"primary_domain": "foundation", "secondary_domains": []},
        "compatibility": {"state": "unchanged", "rationale": "x", "legacy_commands": ["x"]},
        "status": {
            "maturity": "community-proposed",
            "implementation": "specification-only",
            "evidence": "unverified",
        },
        "lifecycle": {
            "persistence": "temporary",
            "activation": "manual",
            "release": {"required": False, "command": None},
        },
        "purpose": {"summary": "x", "source_description": None, "community_description": ""},
        "safety": {"level": "general", "notes": [], "medical_relevance": False},
        "claims": {"intended_effects": [], "prohibited_claims": []},
        "audio": {
            "script_status": "not-started",
            "implementation_status": "not-started",
            "background_audio": {"strategy": "none", "engine": None, "preset": None},
        },
        "sources": [],
        "attribution": {"original_authors": [], "ocf_contributors": []},
        "version": {"current": "0.1.0", "created": "2026-01-01", "updated": "2026-01-01"},
        "history": [],
    }
    errors = validate_against_schema(data, _schema())
    assert errors == [], errors


def test_validate_function_schema_passes_for_record(sample_function_path):
    data = load_yaml_file(sample_function_path)
    record = FunctionRecord(id=data["id"], slug=data["slug"], path=sample_function_path, data=data)
    result = validate_function_schema(record)
    assert result.ok
