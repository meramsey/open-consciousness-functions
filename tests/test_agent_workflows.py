"""The public audio planning flow consumes only canonical locale resources."""

import pytest
from ocf_tools import content, eligibility, session_plans
from ocf_tools.audio_defaults import TEMPLATE_ID
from ocf_tools.indexes import load_function_by_id
from ocf_tools.paths import REPO_ROOT


@pytest.mark.integration
def test_canonical_function_to_binding_projection_and_plan_without_sidecars(tmp_path):
    owner = "OCF-FND-002"
    record = load_function_by_id(owner)
    before = record.path.read_bytes()

    layers = content.load_layers(owner)
    binding = layers["bindings"]
    assert binding["narration_plan"] == record.data["narration"]
    assert binding["default_session_template"] == TEMPLATE_ID
    assert not (REPO_ROOT / "function-content/bindings" / f"{owner}.yaml").exists()
    assert not (REPO_ROOT / "functions").exists()

    dry_run = eligibility.migrate_bindings([owner], dry_run=True)
    assert dry_run[0] == {
        "function_id": owner,
        "default_session_template": TEMPLATE_ID,
        "dry_run": True,
    }
    assert record.path.read_bytes() == before

    plans = session_plans.generate_plans([owner], output=tmp_path / "plans")
    assert plans["validated"] == 1
    assert (
        session_plans.generate_plans([owner], output=tmp_path / "plans", check=True)["stale"] == []
    )
