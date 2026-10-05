"""Plans validate concrete capability choices without generating editorial content."""

from copy import deepcopy

import pytest
from ocf_tools.planning import plan
from ocf_tools.utils import OCFError, yaml_safe_dump

REQUEST = {
    "schema_version": "1.0",
    "template": "OCF-TPL-SESSION-PILOT-RELAX-001",
    "locale": "en-US",
    "narration_source": "tts",
    "target_duration_s": 1200,
}


def test_plan_does_not_promote_pilot_or_claim_target_duration():
    original = deepcopy(REQUEST)
    result = plan(REQUEST)
    assert REQUEST == original
    assert (
        result["dry_run"]
        and result["content_status"] == "draft"
        and result["human_review"] == "required"
    )
    assert result["spoken_events"] == 6 and result["target_duration_s"] == 1200
    assert "no automatic stretching" in result["duration_status"]


def test_plan_accepts_profile_covering_all_required_semantic_states():
    result = plan({**REQUEST, "dsp_profile": "OCF-DSP-DEVELOPMENT-V4-001"})
    assert result["valid"]


def test_plan_rejects_missing_translation_wrong_owner_and_missing_dsp():
    with pytest.raises(OCFError):
        plan({**REQUEST, "locale": "es"})
    with pytest.raises(OCFError):
        plan({**REQUEST, "function_id": "OCF-FND-002"})
    with pytest.raises(OCFError, match="lacks required"):
        plan(
            {
                **REQUEST,
                "template": "OCF-TPL-SESSION-PREP-LEARN-001",
                "dsp_profile": "OCF-DSP-DEFAULT-001",
            }
        )
    with pytest.raises(OCFError):
        plan({**REQUEST, "narration_source": "prerecorded-user"})


def test_plan_resolves_optional_voice_and_slot_input(monkeypatch, tmp_path):
    from ocf_tools import planning, voice

    slots = {}
    for name in ("opener", "focus11", "sleep20", "closer"):
        slot = tmp_path / f"{name}.txt"
        slot.write_text(f"Local {name} value", encoding="utf-8")
        slots[name] = slot.name
    observed = {}
    monkeypatch.setattr(
        voice,
        "resolve_backend",
        lambda backend, locale: observed.update(backend=backend, locale=locale),
    )
    result = planning.plan(
        {
            **REQUEST,
            "template": "OCF-TPL-SESSION-LEARN-001",
            "voice": "espeak-ng",
            "slots": slots,
        },
        tmp_path,
    )
    assert result["valid"] and result["dry_run"]
    assert observed == {"backend": "espeak-ng", "locale": "en-US"}


def test_plan_accepts_matching_prerecorded_package_and_rejects_package_mismatch(tmp_path):
    from ocf_tools.planning import plan

    tts_plan = plan(REQUEST)
    package = {
        "schema_version": "1.0",
        "id": "synthetic-package",
        "source_type": "prerecorded-user",
        "locale": "en-US",
        "author": "User",
        "license": "private",
        "redistribution_permission": False,
        "recordings": {
            event["id"]: {"file": f"{event['id']}.wav", "sha256": "a" * 64}
            for event in tts_plan["semantic_events"]
        },
    }
    path = tmp_path / "recordings.yaml"
    path.write_text(yaml_safe_dump(package), encoding="utf-8")
    request = {**REQUEST, "narration_source": "prerecorded-user", "recordings": str(path)}
    result = plan(request, tmp_path)
    assert result["narration_source"] == "prerecorded-user"

    package["recordings"] = {"unexpected-event": {"file": "extra.wav", "sha256": "b" * 64}}
    path.write_text(yaml_safe_dump(package), encoding="utf-8")
    with pytest.raises(OCFError, match="spoken event occurrences"):
        plan(request, tmp_path)

    package["locale"] = "es"
    path.write_text(yaml_safe_dump(package), encoding="utf-8")
    with pytest.raises(OCFError, match="schema/locale"):
        plan(request, tmp_path)
