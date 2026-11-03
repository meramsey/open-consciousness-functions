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
            "spoken_cue": {"text": "Plus Fixture"},
            "control": {"designation": "primary", "phrase_ref": {"source": "canonical-primary"}},
        },
        "secondary_commands": [],
        "relationships": {"related_functions": [], "complementary_functions": []},
        "narration": {
            "sequence": [{"key": "fixture.body", "role": "function-body", "repetitions": 4}]
        },
        "entries": {"fixture.body": {"text": "Exact local speech"}},
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
