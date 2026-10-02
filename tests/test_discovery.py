"""Discover only live interfaces and authoritative metadata, not prose guesses."""

import json

from ocf_tools.cli import main
from ocf_tools.validators import _load_schema, validate_against_schema


def test_capabilities_schema_and_live_state_dispatch(capsys):
    assert main(["capabilities", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert not validate_against_schema(data, _load_schema("capabilities.schema.json"))
    commands = [row["path"] for row in data["commands"]]
    assert ["audio", "render-state-program"] in commands
    assert ["corpus", "inventory"] in commands
    assert not any(path[0] == "preparation" for path in commands)


def test_function_discovery_preserves_commands_and_legacy_targets(capsys):
    assert main(["functions", "list", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["functions"]) == 55
    assert (
        sum(row["legacy"]["source_availability"] == "unavailable" for row in data["functions"])
        == 16
    )
    assert main(["functions", "describe", "OCF-FND-002", "--json"]) == 0
    row = json.loads(capsys.readouterr().out)["functions"][0]
    assert row["canonical"]["command"]["primary"] == "PLUS-FOCUS"
    assert main(["functions", "describe", "no-such-function", "--json"]) == 1
    assert main(["functions", "describe", "relax"]) == 0
    assert "PLUS-RELAX" in capsys.readouterr().out
