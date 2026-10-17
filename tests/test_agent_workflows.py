"""Temporary source-tree workflow using the real wizard builder and composer."""

from dataclasses import replace

import pytest
from ocf_tools import (
    complete_session,
    content,
    eligibility,
    indexes,
    locale,
    narration_first,
    session_plans,
    validators,
)
from ocf_tools.audio_defaults import TEMPLATE_ID
from ocf_tools.prompts import build_function_yaml
from ocf_tools.utils import write_text_atomic, yaml_safe_dump


@pytest.mark.parametrize("existing_plan", [False, True])
def test_new_temporary_function_validates_and_generates_complete_plan(
    monkeypatch, tmp_path, existing_plan
):
    owner = "OCF-FND-999"
    record = build_function_yaml(
        function_id=owner,
        slug="temporary-fixture",
        name="Temporary fixture",
        primary_domain="foundation",
        secondary_domains=[],
        purpose="Synthetic test fixture.",
        canonical_command="PLUS-FIXTURE",
        modes=[],
        legacy_name="",
        legacy_commands=[],
        command_status="unchanged",
        rationale="Test only",
        compat_state="unchanged",
        source_availability="pending-source-review",
        reimplementation_status="planned",
        persistence="temporary",
        activation="manual",
        release_required=False,
        release_command=None,
        companions=[],
        incompatible=[],
        chains=[],
        safety_level="general",
        medical_relevance=False,
        safety_notes=[],
        evidence="unverified",
        applications=[],
        contributor_name="Fixture",
        contributor_contact="",
        source_files=[],
        source_urls=[],
        community_notes=[],
        testing_status="not-tested",
        audio_status="planned",
        background_status="optional",
        notes="Synthetic fixture only",
    )
    record["audio"]["script_status"] = "approved"  # fixture-only review metadata
    functions = tmp_path / "functions"
    write_text_atomic(functions / "fixture.yaml", yaml_safe_dump(record))
    monkeypatch.setattr(indexes, "FUNCTIONS_DIR", functions)
    assert validators.validate_function_schema(indexes.load_function_by_id(owner)).ok
    root = tmp_path / "content"
    monkeypatch.setattr(content, "CONTENT_DIR", root)
    monkeypatch.setattr(eligibility, "CONTENT_DIR", root)
    monkeypatch.setattr(session_plans, "CONTENT_DIR", root)
    catalog = locale.LocaleCatalog()
    for role in ("opener", "function-body", "closer"):
        original = catalog.canonical.entries[f"hplus.function.ocf-fnd-002.{role}"]
        key = f"hplus.function.{owner.lower()}.{role}"
        catalog.canonical.entries[key] = replace(
            original, key=key, text="Synthetic fixture narration.", notes="Test only."
        )
    for module in (
        locale,
        content,
        eligibility,
        complete_session,
        narration_first,
        session_plans,
        validators,
    ):
        if hasattr(module, "LocaleCatalog"):
            monkeypatch.setattr(module, "LocaleCatalog", lambda: catalog)
    if existing_plan:
        binding = {
            "schema_version": "1.0",
            "function_id": owner,
            "session_templates": [TEMPLATE_ID],
            "default_session_template": TEMPLATE_ID,
            "narration_resources": [],
            "voice_sources": ["tts"],
            "duration": None,
            "narration_plan": {
                "sequence": [
                    {
                        "key": f"hplus.function.{owner.lower()}.{role}",
                        "role": role,
                        "repetitions": 4 if role == "function-body" else 1,
                    }
                    for role in ("opener", "function-body", "closer")
                ]
            },
        }
        path = root / "bindings" / f"{owner}.yaml"
        write_text_atomic(path, yaml_safe_dump(binding))
        before = path.read_bytes(), (functions / "fixture.yaml").read_bytes()
        from ocf_tools.utils import OCFError

        with pytest.raises(OCFError, match="conflicts with authoritative"):
            content.load_layers(owner)
        eligibility.migrate_bindings([owner], dry_run=True)
        assert before == (path.read_bytes(), (functions / "fixture.yaml").read_bytes())
    eligibility.migrate_bindings([owner], dry_run=False)
    assert content.load_layers(owner)["bindings"]["default_session_template"] == TEMPLATE_ID
    assert (
        indexes.load_function_by_id(owner).data["narration"]
        == content.load_layers(owner)["bindings"]["narration_plan"]
    )
    result = session_plans.generate_plans([owner], output=tmp_path / "plans")
    assert result["validated"] == 1
    assert (
        session_plans.generate_plans([owner], output=tmp_path / "plans", check=True)["stale"] == []
    )
    if existing_plan:
        changed = indexes.load_function_by_id(owner).data
        changed["narration"]["sequence"].reverse()
        write_text_atomic(functions / "fixture.yaml", yaml_safe_dump(changed))
        before = path.read_bytes(), (functions / "fixture.yaml").read_bytes()
        with pytest.raises(OCFError, match="conflicts with authoritative"):
            eligibility.migrate_bindings([owner], dry_run=False)
        assert before == (path.read_bytes(), (functions / "fixture.yaml").read_bytes())
