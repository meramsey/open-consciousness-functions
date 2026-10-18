"""Function-scoped persistence is descriptive and separate from invocation."""

import json

import pytest
from ocf_tools.commands import command_view, validate_command_records
from ocf_tools.indexes import load_function_by_id
from ocf_tools.models import FunctionRecord


def fixture_owner(scopes, effect_ref="lifecycle.persistence", invocation_ref=None):
    primary = {
        "id": "OCF-CMD-TST-999-PRIMARY",
        "function_id": "OCF-TST-999",
        "phrase_ref": {"source": "canonical-primary"},
        "role": "activation",
        "designation": "primary",
        "spoken": "Plus Example",
        "spoken_review": "reviewed",
        "effect_scope_ref": effect_ref,
    }
    if invocation_ref is not None:
        primary["invocation_scope_ref"] = invocation_ref
    return FunctionRecord(
        "OCF-TST-999",
        "example",
        __file__,
        {
            "id": "OCF-TST-999",
            "slug": "example",
            "canonical": {
                "name": "Example",
                "command": {"primary": "PLUS-EXAMPLE", "modes": [], "mode_ids": []},
            },
            "commands": [primary],
            "legacy": {"commands": []},
            "aliases": {"commands": []},
            "narration": {"sequence": []},
            "lifecycle": {
                "activation": "manual",
                "persistence": "permanent",
                "release": {"required": False, "command": None},
                "trigger_conditions": [],
                "scopes": scopes,
            },
            "purpose": {"summary": "Example", "community_description": "Example"},
        },
    )


def valid_scopes():
    return {
        "baseline": {
            "persistence": "permanent",
            "activation": "automatic",
            "description": "Learned pattern continues.",
            "description_key": "functions.ocf-tst-999.lifecycle.scopes.baseline.description",
        },
        "application": {
            "persistence": "temporary",
            "activation": "manual",
            "description": "One selected cue invocation.",
            "description_key": "functions.ocf-tst-999.lifecycle.scopes.application.description",
        },
    }


def test_legacy_scope_and_explicit_application_scope_resolve_independently():
    owner = fixture_owner(valid_scopes())
    command = owner.command_records[0]
    assert command_view(owner, command)["effect_scope"] == "permanent"
    command.data["effect_scope_ref"] = "lifecycle.scopes.application.persistence"
    command.data["invocation_scope_ref"] = "lifecycle.scopes.application"
    view = command_view(owner, command)
    assert view["effect_scope"] == "temporary"
    assert view["effect_scope_details"]["activation"] == "manual"
    assert view["invocation_scope"]["persistence"] == "temporary"
    assert not validate_command_records(owner)


@pytest.mark.parametrize(
    "reference",
    [
        "lifecycle.scopes.unknown.persistence",
        "lifecycle.scopes.baseline",
        "",
        "lifecycle.scopes.application.persistence.extra",
    ],
)
def test_unknown_or_malformed_scope_reference_fails_closed(reference):
    owner = fixture_owner(valid_scopes(), effect_ref=reference)
    assert any("lifecycle scope" in error for error in validate_command_records(owner))
    with pytest.raises(Exception):
        command_view(owner, owner.command_records[0])


def test_missing_scope_target_and_nonmanual_invocation_are_errors():
    owner = fixture_owner(
        {},
        effect_ref="lifecycle.scopes.baseline.persistence",
        invocation_ref="lifecycle.scopes.application",
    )
    errors = validate_command_records(owner)
    assert any("missing or invalid lifecycle scope" in error for error in errors)
    owner = fixture_owner(
        {"application": {**valid_scopes()["application"], "activation": "automatic"}},
        invocation_ref="lifecycle.scopes.application",
    )
    assert any(
        "must explicitly remain manual" in error for error in validate_command_records(owner)
    )


@pytest.mark.integration
def test_confirmed_functions_keep_capability_baseline_and_application_scopes_distinct():
    expected = {
        "OCF-COG-004": ("permanent", "permanent", "temporary"),
        "OCF-COG-005": ("permanent", "permanent", "temporary"),
        "OCF-PRF-004": ("permanent", "permanent", "temporary"),
        "OCF-BOD-005": ("permanent", "permanent", "temporary"),
        "OCF-AUT-001": ("permanent", "permanent", "temporary"),
        "OCF-BOD-007": ("permanent", "permanent", "temporary"),
        "OCF-BOD-011": ("permanent", "permanent", "temporary"),
        "OCF-BOD-013": ("permanent", "permanent", "temporary"),
        "OCF-COG-001": ("permanent", "permanent", "temporary"),
        "OCF-LIF-001": ("permanent", "permanent", "temporary"),
        "OCF-EMG-001": ("permanent", None, "temporary"),
        "OCF-EMG-002": ("permanent", None, "temporary"),
    }
    for function_id, (capability, baseline, application) in expected.items():
        owner = load_function_by_id(function_id)
        scopes = owner.data["lifecycle"]["scopes"]
        assert scopes["capability"]["persistence"] == capability
        assert scopes["application"]["persistence"] == application
        if baseline:
            assert scopes["baseline"]["persistence"] == baseline
        else:
            assert scopes["episode"]["persistence"] == "temporary"
            assert scopes["episode"]["trigger_conditions_ref"] == "lifecycle.trigger_conditions"
        assert (
            owner.activation == "manual"
            if function_id not in {"OCF-EMG-001", "OCF-EMG-002"}
            else owner.activation == "conditional"
        )
        expected_function_summary = {
            "OCF-COG-004": "permanent",
            "OCF-COG-005": "temporary",
            "OCF-PRF-004": "permanent",
            "OCF-BOD-005": "permanent",
            "OCF-AUT-001": "permanent",
            "OCF-BOD-007": "permanent",
            "OCF-BOD-011": "permanent",
            "OCF-BOD-013": "permanent",
            "OCF-COG-001": "temporary",
            "OCF-LIF-001": "permanent",
            "OCF-EMG-001": "temporary",
            "OCF-EMG-002": "temporary",
        }
        assert owner.persistence == expected_function_summary[function_id]


@pytest.mark.integration
def test_nutricia_food_less_is_alternative_mode_and_all_resolved_speech_is_exact():
    from ocf_tools.commands import is_active
    from ocf_tools.locale import LocaleCatalog
    from tools.check_hplus_narration_integrity import narration_texts

    owner = load_function_by_id("OCF-BOD-010")
    commands = {item.id: item for item in owner.command_records}
    less = commands["OCF-CMD-BOD-010-FOOD-LESS"]
    assert less.role == "mode" and less.designation == "secondary"
    assert less.relationships["pairs_with"] == ["OCF-CMD-BOD-010-PRIMARY"]
    assert "modifies" not in less.relationships
    assert owner.canonical_command == "PLUS-FOOD MORE"
    assert owner.data["canonical"]["command"]["modes"] == ["PLUS-FOOD LESS"]
    catalog = LocaleCatalog()
    for key in (
        "hplus.function.ocf-bod-010.opener",
        "hplus.function.ocf-bod-010.function-body",
        "hplus.function.ocf-bod-010.closer",
    ):
        entry, _ = catalog.resource(key, "en-US", domain="narration", fallback=False)
        assert entry.text == narration_texts()[f"locales/en-US/hplus-OCF-BOD-010.yaml::{key}"]
    assert all(is_active(item) for item in (commands["OCF-CMD-BOD-010-PRIMARY"], less))


@pytest.mark.integration
def test_scope_only_migration_preserves_plans_timings_and_engineering_locks():
    from ocf_tools.audio_defaults import check_lock
    from ocf_tools.narration_first import plan_narration
    from ocf_tools.paths import REPO_ROOT
    from ocf_tools.session_plans import source_plan

    for function_id in (
        "OCF-COG-004",
        "OCF-COG-005",
        "OCF-BOD-005",
        "OCF-BOD-010",
        "OCF-EMG-001",
        "OCF-EMG-002",
    ):
        canonical = plan_narration(function_id, locale="en-US")
        source, shared, expanded = source_plan(function_id)
        assert source["function_id"] == function_id
        assert source["timing"] == "measured-speech-relative; expand template at render time"
        assert {segment["role"] for segment in canonical["segments"]} >= {"function-body", "closer"}
    old = json.loads((REPO_ROOT / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-006.json").read_text())
    current = check_lock()
    assert current["profiles"] == old["profiles"]
