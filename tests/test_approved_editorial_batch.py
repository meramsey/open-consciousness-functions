"""Exact finite owner-approved source batch; no listening/publication approval."""

import json
from pathlib import Path

import pytest
import yaml
from ocf_tools.locale import LocaleCatalog
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration
APPROVAL = json.loads(
    (Path(__file__).parent / "fixtures/approved-editorial-batch-20261114.json").read_text()
)


@pytest.mark.parametrize("identity", sorted(APPROVAL["functions"]))
def test_exact_resolved_approved_content_and_repeat_contract(identity):
    approved = APPROVAL["functions"][identity]
    catalog = LocaleCatalog()
    data = catalog.require("en-US").localized_functions[identity]
    assert data["description"]["text"] == approved["description"]
    assert [(r["role"], r["repetitions"]) for r in data["narration"]["sequence"]] == [
        ("opener", 1),
        ("function-body", 4),
        ("closer", 1),
    ]
    for role, expected in approved["texts"].items():
        key = f"hplus.function.{identity.lower()}.{role}"
        actual = catalog.resource(key, "en-US", domain="narration", fallback=False)[0].text
        assert actual == expected
        assert "{{" not in actual
        if role != "opener":
            assert "{{ cue.primary }}" in data["entries"][key]["text"]
            assert data["entries"][key]["cue_template"]["allowed"] == ["cue.primary"]


def _data(identity):
    path = next((REPO_ROOT / "locales/en-US").glob(identity + "-*.yaml"))
    return yaml.safe_load(path.read_text())


def test_sleep_has_one_hold_command_and_no_purpose_or_exhale_command():
    data = _data("OCF-SLP-002")
    assert data["activation"]["control"]["procedure"]["before_steps"] == []
    assert [s["operation"] for s in data["activation"]["procedure_steps"]] == [
        "close-eyes",
        "inhale",
        "hold-breath",
        "think-or-say-command",
        "exhale",
        "breathe-normally",
    ]
    assert data["activation"]["control"]["procedure"]["ref"] != "OCF-PROC-SLEEP-EXHALE"


@pytest.mark.parametrize(
    "identity",
    ["OCF-BOD-001", "OCF-BOD-002", "OCF-BOD-004", "OCF-BOD-006", "OCF-BOD-007", "OCF-BOD-009"],
)
def test_specific_body_function_does_not_require_target_selection(identity):
    assert not any(
        s["operation"] in ("focus-target", "select-target-area", "select-purpose")
        for s in _data(identity)["activation"]["procedure_steps"]
    )


def test_comfort_selects_once_and_restoration_is_optional():
    steps = _data("OCF-BOD-003")["activation"]["procedure_steps"]
    assert [s["operation"] for s in steps[:3]] == ["close-eyes", "focus-target", "inhale"]
    assert sum(s["operation"] == "focus-target" for s in steps) == 1
    steps = _data("OCF-SLP-001")["activation"]["procedure_steps"]
    assert "optionally" in steps[0]["instruction"]["text"]
    assert steps[1]["operation"] == "close-eyes"


@pytest.mark.parametrize("identity", ["OCF-BOD-008", "OCF-BOD-009"])
def test_breath_and_immune_no_eye_or_target_requirement(identity):
    assert [s["operation"] for s in _data(identity)["activation"]["procedure_steps"]] == [
        "inhale",
        "hold-breath",
        "think-or-say-command",
        "exhale",
    ]
