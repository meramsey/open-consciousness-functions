"""Discovery-only history, Unicode equivalence and older metadata compatibility."""

from types import SimpleNamespace

import pytest
from ocf_tools import cli, vocabulary
from ocf_tools.models import FunctionRecord

pytestmark = pytest.mark.unit


def fixture(tmp_path, docs):
    owner = "OCF-EXP-001"
    command = {
        "id": "OCF-CMD-EXP-001-PRIMARY",
        "function_id": owner,
        "phrase_ref": {"source": "canonical-primary"},
        "role": "activation",
        "designation": "primary",
    }
    return FunctionRecord(
        owner,
        "mobius-west",
        tmp_path / "function.yaml",
        {
            "canonical": {"name": "Manifest", "command": {"primary": "PLUS-MANIFEST"}},
            "commands": [command],
            "legacy": {"name": "MOBIUS WEST", "commands": ["PLUS-CHANGE, CHANGE"]},
            "aliases": {"names": ["Mobius West"]},
            "purpose": {"summary": "Selected future condition."},
            "documentation": docs,
            "historical_lookup": [{"text": "Möbius West", "kind": "former-title"}],
        },
    )


@pytest.mark.parametrize("query", ["MÖBIUS WEST", "Mo\u0308bius West", "  Möbius   West  "])
def test_historical_unicode_queries_do_not_select_an_activation(tmp_path, query):
    record = fixture(tmp_path, {"title_key": "title", "purpose_key": "purpose"})
    catalog = SimpleNamespace(
        canonical_locale="en-US",
        lookup=lambda *a, **k: SimpleNamespace(origin_locale="en-US"),
        text=lambda key, *a: "Manifest" if key == "title" else "Selected future condition.",
    )
    rows = vocabulary.lookup(query, records=[record], catalog=catalog)
    assert rows[0]["title"] == "Manifest"
    assert rows[0]["cue"]["display_cue"] == "PLUS-MANIFEST"
    assert rows[0]["cue"]["spoken_cue"] is None
    assert all(row["historical"] for row in rows[0]["matches"])
    assert rows[0]["activation_selected"] is False


def test_unlocalized_legacy_metadata_is_labeled_without_a_second_resolver(tmp_path):
    record = fixture(tmp_path, {})
    catalog = SimpleNamespace(
        canonical_locale="en-US", lookup=lambda *a, **k: pytest.fail("no undeclared title key")
    )
    rows = vocabulary.lookup("Mobius West", records=[record], catalog=catalog)
    assert rows[0]["title"] == "Manifest" and rows[0]["title_locale"] == "canonical-record"
    assert rows[0]["purpose_locale"] == "canonical-record"
    assert vocabulary.lookup("unknown", records=[record], catalog=catalog) == []
    assert vocabulary.lookup(" ", catalog=catalog) == []


@pytest.mark.parametrize("json_output", [True, False])
def test_lookup_cli_uses_shared_service_without_activating_or_mutating(
    monkeypatch, capsys, json_output
):
    seen = []

    def lookup(query, *, locale):
        seen.append((query, locale))
        return [
            {
                "function_id": "OCF-EXP-001",
                "title": "Manifest",
                "cue": {"display_cue": "PLUS-MANIFEST"},
                "matches": [{"kind": "former-title"}],
            }
        ]

    monkeypatch.setattr(vocabulary, "lookup", lookup)
    args = ["functions", "lookup", "Mobius West", "--locale", "en-US"] + (
        ["--json"] if json_output else []
    )
    assert cli.main(args) == 0
    assert seen == [("Mobius West", "en-US")]
    output = capsys.readouterr().out
    assert "Manifest" in output and "PLUS-MANIFEST" in output
    if json_output:
        assert '"activation_selected": false' in output
