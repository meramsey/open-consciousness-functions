import json

import pytest
from ocf_tools.session_plans import generate_plans, source_plan
from ocf_tools.utils import OCFError


def test_all_58_source_plans_are_valid_and_fresh_without_audio_tools(monkeypatch):
    from ocf_tools import narration_first

    def forbidden(*args, **kwargs):
        pytest.fail("source planning must not resolve an installed voice")

    monkeypatch.setattr(narration_first, "_voice_profile", forbidden)
    result = generate_plans(check=True)
    assert result["total"] == result["validated"] == 58


def test_generation_determinism_manual_ownership_and_staleness(tmp_path):
    ids = ["OCF-FND-002", "OCF-SLP-005"]
    first = generate_plans(ids, output=tmp_path)
    second = generate_plans(list(reversed(ids)), output=tmp_path, check=True)
    assert first["files"] == second["files"]
    path = tmp_path / "en-US/OCF-FND-002.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(OCFError, match="stale"):
        generate_plans(ids, output=tmp_path, check=True)
    with pytest.raises(OCFError, match="manually maintained"):
        generate_plans(ids, output=tmp_path)


def test_dry_run_is_read_only_and_relative_timing_has_one_start(tmp_path):
    result = generate_plans(["OCF-FND-002"], output=tmp_path, dry_run=True)
    assert result["total"] == 1 and not list(tmp_path.iterdir())
    compact, shared, expanded = source_plan("OCF-FND-002")
    assert shared["timing"]["body_repetitions"] == {"programming": 2, "sleep": 2}
    assert compact["slots"]["function_body"] == "hplus.function.ocf-fnd-002.function-body"
    assert expanded["voice"] is None
    assert "voice_profile" not in expanded["template_plan"]
    from ocf_tools.locale import iter_events

    events = list(iter_events(expanded["template_plan"]))
    assert len([e for e in events if "at" in e]) == 1
    assert all(
        e.get("after") in {p["id"] for p in events[:i]}
        for i, e in enumerate(events)
        if "after" in e
    )
    assert all(r["locale"] == "en-US" and not r["fallback"] for r in compact["resources"])
    assert "file:///" not in json.dumps(compact)


def test_planning_missing_locale_publishes_nothing(tmp_path):
    with pytest.raises(OCFError, match="planning failed"):
        generate_plans(["OCF-FND-002"], locale="es", output=tmp_path)
    assert not list(tmp_path.iterdir())
