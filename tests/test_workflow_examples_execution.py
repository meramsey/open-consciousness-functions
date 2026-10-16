"""Execute documented wizard workflow through real composition in fixture output."""

import json

import pytest
from ocf_tools import cli, prompts, session_plans
from ocf_tools.indexes import load_function_by_id
from ocf_tools.validators import _load_schema, validate_against_schema

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("confirm", ["yes", "no"])
def test_session_plan_wizard_executes_real_generator(monkeypatch, tmp_path, confirm):
    answers = iter(["1", "en-US", confirm])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(prompts, "load_all_functions", lambda: [load_function_by_id("OCF-FND-002")])
    monkeypatch.setattr(session_plans, "PLAN_DIR", tmp_path)
    assert cli.main(["new", "session-plan"]) == 0
    if confirm == "no":
        assert list(tmp_path.iterdir()) == []
        return
    root = tmp_path / "en-US"
    assert sorted(p.name for p in root.iterdir()) == ["OCF-FND-002.json", "_shared.json"]
    plan = json.loads((root / "OCF-FND-002.json").read_text())
    shared = json.loads((root / "_shared.json").read_text())
    assert validate_against_schema(plan, _load_schema("session-plan.schema.json")) == []
    assert plan["defaults"]["sha256"] == session_plans.digest(shared)
    assert plan["approval"]["release_ready"] is False
    assert plan["locale"] == "en-US"


def test_session_plan_wizard_preserves_manually_owned_destination(monkeypatch, tmp_path, capsys):
    root = tmp_path / "en-US"
    root.mkdir()
    manual = root / "OCF-FND-002.json"
    manual.write_text('{"owner":"human"}\n')
    answers = iter(["1", "en-US", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(prompts, "load_all_functions", lambda: [load_function_by_id("OCF-FND-002")])
    monkeypatch.setattr(session_plans, "PLAN_DIR", tmp_path)
    # Wizard reports errors at the shared CLI boundary; it must never partially publish.
    assert cli.main(["new", "session-plan"]) == 1
    assert "manually maintained" in capsys.readouterr().err
    assert manual.read_text() == '{"owner":"human"}\n'
    assert sorted(p.name for p in root.iterdir()) == ["OCF-FND-002.json"]
