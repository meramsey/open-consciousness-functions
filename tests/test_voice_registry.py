"""Downloadability, engine license and model/voice rights are distinct facts."""

from copy import deepcopy

from conftest import REPO_ROOT
from ocf_tools.indexes import load_yaml_file
from ocf_tools.validators import _load_schema, validate_against_schema
from ocf_tools.voice_registry import load_registry


def test_unknown_terms_remain_unknown_and_cannot_be_bundled():
    data = load_yaml_file(REPO_ROOT / "templates/community-voice.yaml")
    schema = _load_schema("community-voice.schema.json")
    assert validate_against_schema(data, schema) == []
    assert load_registry() == []
    bad = deepcopy(data)
    bad["bundled"] = True
    bad["redistribution_permission"] = False
    assert validate_against_schema(bad, schema)
    bad = deepcopy(data)
    bad["install_status"] = "bundled"
    assert validate_against_schema(bad, schema)
    data["software_license"] = {
        "status": "recorded",
        "reference": "engine-license",
        "description": "Engine license only",
    }
    assert (
        data["model_license"]["status"] == "unknown" and data["voice_rights"]["status"] == "unknown"
    )
