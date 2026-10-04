"""Pure command/collection rules, semantic binding and measured-clock contracts."""

from copy import deepcopy
from pathlib import Path

import pytest
from ocf_tools import bootstrap, semantics
from ocf_tools import validators as v
from ocf_tools.models import function_from_dict
from ocf_tools.timing import schedule_timeline
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def record(primary="PLUS-FOCUS", modes=None, legacy=None, status="unchanged", compatibility=None):
    data = {
        "id": "OCF-FND-999",
        "slug": "fixture",
        "canonical": {"command": {"primary": primary, "modes": modes or []}},
        "legacy": {
            "commands": legacy or [],
            "command_status": status,
            "source_availability": "available",
        },
        "ocf": {"reimplementation_status": "planned"},
    }
    if compatibility is not None:
        data["compatibility"] = compatibility
    return function_from_dict(data, Path("fixture.yaml"))


def codes(result):
    return {issue.code for issue in result.issues}


def test_issue_severity_format_and_aggregate_error_state():
    with pytest.raises(ValueError, match="unknown severity"):
        v.Issue("bad", "code", "message")
    result = v.ValidationResult()
    result.add("warning", "review", "Needs review", "Fixture")
    assert result.ok and result.warnings[0].format() == "[WARNING] review: Needs review (Fixture)"
    other = v.ValidationResult()
    other.add("error", "invalid", "Invalid input")
    result.extend(other)
    assert not result.ok and result.errors[0].format() == "[ERROR] invalid: Invalid input"


@pytest.mark.parametrize(
    "primary,modes,legacy,expected",
    [
        (None, [""], [""], set()),
        ("FOCUS", [], [], {"plus-prefix"}),
        ("PLUS-SEE MORE", [], [], {"asymmetric-more-less"}),
        ("PLUS-SEE LESS", [], [], {"asymmetric-more-less"}),
        ("PLUS-SEE MORE", ["PLUS-SEE LESS"], [], set()),
        (
            "PLUS-SENSE GREATER",
            ["PLUS-SENSE LESSER", "PLUS-SENSE ACCELERATE"],
            [],
            {"deprecated-magnitude-vocab"},
        ),
        (
            "PLUS-ONE TWO THREE FOUR",
            [],
            ["PLUS-ONE TWO THREE FOUR"],
            {"too-many-words", "legacy-too-many-words"},
        ),
    ],
)
def test_command_rule_success_and_failure_categories(primary, modes, legacy, expected):
    item = record(primary, modes, legacy)
    assert codes(v.validate_command_rules(item)) == expected
    assert v.count_commands(item, legacy=True) == sum(v.spoken_word_count(c) for c in legacy)
    assert v.count_commands(item) == sum(v.spoken_word_count(c) for c in [primary, *modes] if c)
    assert v.spoken_word_count("PLUS-TWO%TWO, THREE") == 3


@pytest.mark.parametrize(
    "compatibility,expected",
    [
        (None, "no-compatibility-metadata"),
        ({"state": "alias-listed"}, "no-change-rationale"),
        ({"rationale": "Changed", "state": "none"}, "no-compatibility-state"),
        ({"rationale": "Changed", "state": "bridge-trainable"}, None),
    ],
)
def test_changed_commands_need_rationale_and_compatibility(compatibility, expected):
    item = record("PLUS-SEE MORE", ["PLUS-SEE LESS"], ["PLUS-SEE"], "normalized", compatibility)
    found = codes(v.validate_command_rules(item))
    assert "replacement-longer-than-legacy" in found
    assert (expected in found) if expected else found == {"replacement-longer-than-legacy"}
    item.data["canonical"]["command"]["primary"] = None
    item.data["legacy"]["commands"] = []
    assert "replacement-longer-than-legacy" not in codes(v.validate_command_rules(item))


def test_collection_duplicate_ids_primary_aliases_and_reusable_modes(monkeypatch):
    first, second, blank = record(), record(), record(None, [""])
    second.data["aliases"] = {"commands": ["PLUS-FOCUS", "PLUS-OLD"]}
    monkeypatch.setattr(v, "load_all_functions", lambda: [first, second, blank])
    assert codes(v.validate_collection()) == {
        "duplicate-id",
        "duplicate-command",
        "alias-equals-canonical",
    }
    first.id, second.id, blank.id = "OCF-FND-001", "OCF-FND-002", "OCF-FND-003"
    second.data["canonical"]["command"]["primary"] = "PLUS-OTHER"
    first.data["canonical"]["command"]["modes"] = ["PLUS-SHARED"]
    second.data["canonical"]["command"]["modes"] = ["PLUS-SHARED"]
    assert v.validate_collection().ok
    second.data["legacy"]["source_availability"] = "unavailable"
    assert "reimplementation-target" not in codes(v.validate_legacy_invariants())
    second.data["ocf"]["reimplementation_status"] = "complete"
    assert "reimplementation-target" in codes(v.validate_legacy_invariants())


@pytest.mark.parametrize(
    "at,match",
    [
        (None, "no timestamp"),
        (-1, "invalid resolved"),
        (float("nan"), "invalid resolved"),
        (float("inf"), "invalid resolved"),
    ],
)
def test_invalid_resolved_clock_fails(at, match):
    with pytest.raises(OCFError, match=match):
        schedule_timeline({"timeline": [{"id": "a", "at": at}]}, {})


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf")])
def test_invalid_measured_duration_never_creates_bad_render_ledger(duration):
    with pytest.raises(OCFError, match="invalid measured speech duration"):
        schedule_timeline({"timeline": [{"id": "a", "at": 0}]}, {"a": duration})


def test_cycle_unknown_dependency_and_explicit_maximum_fail():
    for events in (
        [{"id": "a", "after": "missing"}],
        [{"id": "a", "after": "b"}, {"id": "b", "after": "a"}],
    ):
        with pytest.raises(OCFError, match="timeline problems"):
            schedule_timeline({"timeline": events}, {})
    with pytest.raises(OCFError, match="maximum_duration"):
        schedule_timeline(
            {"timeline": [{"id": "a", "at": 0, "timing": {"maximum_duration": 1}}]}, {"a": 2}
        )


def test_stage_namespace_is_nonmutating_and_rejects_unknown_anchors():
    stage = {"id": "fixture", "events": [{"id": "a", "at": 1}, {"id": "b", "after": "a"}]}
    before = deepcopy(stage)
    events = semantics.stage_events(stage, "example", after="$previous", previous="outer.end")
    assert events[0]["after"] == "outer.end" and events[0]["offset"] == 1
    assert events[1]["after"] == "example.a" and stage == before
    with pytest.raises(OCFError, match="no previous"):
        semantics.stage_events(stage, "example", after="$previous")
    stage["events"][1]["after"] = "missing"
    with pytest.raises(OCFError, match="unknown local"):
        semantics.stage_events(stage, "example")


def test_cue_binding_failure_paths_and_copy_isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(semantics, "REPO_ROOT", tmp_path)
    profile = {
        "id": "fixture",
        "bindings": {
            "focus.ten.enter": {"mode": "disabled"},
            "custom.cue": {"mode": "asset", "file": "cue.wav"},
        },
    }
    wrong = {
        "timeline": [{"id": "a", "auditory_cue": "focus.ten.enter", "semantic": "explain.ten"}]
    }
    with pytest.raises(OCFError, match="matching semantic"):
        semantics.bind_document_cues(wrong, profile)
    with pytest.raises(OCFError, match="unbound"):
        semantics.bind_document_cues(
            {"timeline": [{"id": "a", "auditory_cue": "unknown"}]}, profile
        )
    request = {"timeline": [{"id": "a", "auditory_cue": "custom.cue"}]}
    with pytest.raises(OCFError, match="asset not found"):
        semantics.bind_document_cues(request, profile)
    (tmp_path / "cue.wav").write_bytes(b"fixture asset, never played")
    bindings = semantics.bind_document_cues(request, profile)
    bindings[0]["binding"]["file"] = "different.wav"
    assert profile["bindings"]["custom.cue"]["file"] == "cue.wav"


def test_bootstrap_requires_checkout_supported_runtime_and_reports_step_failure(
    monkeypatch, tmp_path
):
    with pytest.raises(ValueError, match="source checkout"):
        bootstrap.setup_plan(tmp_path / "venv", root=tmp_path)
    plan = {"commands": [["python", "doctor"]], "reuse": False}
    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 10))
    with pytest.raises(ValueError, match="Python>=3.11"):
        bootstrap.apply_setup(plan, runner=lambda *a, **kw: pytest.fail("must not run"))
    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 12))
    with pytest.raises(RuntimeError, match="setup step failed"):
        bootstrap.apply_setup(
            plan,
            runner=lambda *a, **kw: type(
                "Result", (), {"returncode": 1, "stderr": "synthetic failure"}
            )(),
        )
