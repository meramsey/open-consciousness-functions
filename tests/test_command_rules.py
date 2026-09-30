"""Command-design invariant tests from docs/COMMAND_GRAMMAR.md and README."""

from __future__ import annotations

from ocf_tools.indexes import load_all_functions
from ocf_tools.models import FunctionRecord
from ocf_tools.validators import validate_command_rules


def _by_legacy_name(records, name):
    return next(r for r in records if r.legacy_name == name)


def test_think_fast_remains_plus_think():
    record = _by_legacy_name(load_all_functions(), "THINK FAST")
    assert record.canonical_command == "PLUS-THINK"
    assert record.command_status == "unchanged"
    assert record.command_review == "approved"


def test_attention_remains_plus_focus():
    record = _by_legacy_name(load_all_functions(), "ATTENTION")
    assert record.canonical_command == "PLUS-FOCUS"
    assert record.command_status == "unchanged"


def test_directional_sensory_controls_use_more_less():
    for name, primary, modes in [
        ("SENSORY: SEEING", "PLUS-SEE MORE", ["PLUS-SEE LESS"]),
        ("SENSORY: HEARING", "PLUS-HEAR MORE", ["PLUS-HEAR LESS"]),
        ("SENSORY: SMELL", "PLUS-SMELL MORE", ["PLUS-SMELL LESS"]),
        ("SENSORY: TASTE", "PLUS-TASTE MORE", ["PLUS-TASTE LESS"]),
        ("SENSORY: TOUCH", "PLUS-TOUCH MORE", ["PLUS-TOUCH LESS"]),
        ("SEX DRIVE", "PLUS-SEX MORE", ["PLUS-SEX LESS"]),
        ("NUTRICIA", "PLUS-FOOD MORE", ["PLUS-FOOD LESS"]),
    ]:
        record = _by_legacy_name(load_all_functions(), name)
        assert record.canonical_command == primary
        assert record.command_modes == modes


def test_available_count_is_39():
    records = load_all_functions()
    assert len([r for r in records if r.source_availability == "available"]) == 39


def test_unavailable_count_is_16():
    records = load_all_functions()
    assert len([r for r in records if r.source_availability == "unavailable"]) == 16


def test_all_16_unavailable_are_reimplementation_targets():
    for record in load_all_functions():
        if record.source_availability == "unavailable":
            assert record.reimplementation_status == "planned"


def test_16_unavailable_are_in_unified_index():
    from ocf_tools.generators import function_index_json

    payload = function_index_json()
    for suffix in ("OCF-EMG-001", "OCF-EXP-002", "OCF-SLP-006", "OCF-BOD-014"):
        assert suffix in payload


def test_legacy_commands_preserved_when_changed():
    records = [
        r
        for r in load_all_functions()
        if r.command_status in ("proposed", "normalized", "review-required")
    ]
    assert records, "expected at least one changed command"
    for record in records:
        assert record.legacy_commands, f"{record.id} must preserve legacy commands"
        compat = record.data.get("compatibility", {})
        assert compat.get("rationale"), f"{record.id} must carry compatibility rationale"


def test_longer_replacement_triggers_warning():
    data = {
        "id": "OCF-FND-098",
        "slug": "longer",
        "canonical": {"command": {"primary": "PLUS-ONE TWO THREE FOUR", "modes": []}},
        "legacy": {
            "commands": ["PLUSONE"],
            "command_status": "proposed",
            "source_availability": "available",
        },
        "aliases": {"commands": []},
    }
    record = FunctionRecord(id=data["id"], slug=data["slug"], path=__file__, data=data)
    result = validate_command_rules(record)
    assert any(i.code == "replacement-longer-than-legacy" for i in result.warnings)


def test_regenerate_command_is_review_required_not_approved():
    record = _by_legacy_name(load_all_functions(), "REGENERATE")
    assert record.command_review == "review-required"


def test_canonical_commands_fit_word_limits_except_flagged():
    # Only functions explicitly flagged for review may exceed 3 classroom words.
    for record in load_all_functions():
        for text, count in record.spoken_words():
            if count > 3:
                assert record.command_review == "review-required", record.id
                assert record.command_status != "unchanged", record.id
