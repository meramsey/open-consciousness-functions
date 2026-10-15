from types import SimpleNamespace

import pytest
from ocf_tools import prompts, session_plans


@pytest.mark.unit
def test_session_plan_wizard_uses_authoritative_generator(monkeypatch):
    calls = []
    monkeypatch.setattr(prompts, "load_all_functions", lambda: [SimpleNamespace(id="OCF-FND-002")])
    monkeypatch.setattr(prompts, "ask_pick", lambda *a, **k: SimpleNamespace(value="OCF-FND-002"))
    monkeypatch.setattr(prompts, "ask", lambda *a, **k: SimpleNamespace(value="en-US"))
    monkeypatch.setattr(
        prompts, "ask_yes_no", lambda *a, **k: SimpleNamespace(intent="value", value="yes")
    )
    monkeypatch.setattr(
        session_plans, "generate_plans", lambda *a, **k: calls.append((a, k)) or {"validated": 1}
    )
    prompts.run_session_plan_wizard()
    assert calls == [
        ((["OCF-FND-002"],), {"locale": "en-US", "dry_run": True}),
        ((["OCF-FND-002"],), {"locale": "en-US"}),
    ]
