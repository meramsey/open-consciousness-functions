"""Isolated invalid-input boundaries; no synthesis or renderer rewrite."""

import pytest
from ocf_tools import complete_session, narration_first, semantic_dsp, session, session_overrides
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def planning(monkeypatch, template, options):
    monkeypatch.setattr(narration_first, "plan_narration", lambda *a, **k: {})
    monkeypatch.setattr(complete_session, "load_layers", lambda *a: {})
    monkeypatch.setattr(complete_session, "_resolve_template", lambda *a: (template, {}))
    monkeypatch.setattr(session_overrides, "resolve", lambda *a: (options, {}))
    monkeypatch.setattr(semantic_dsp, "load_profile", lambda *a: {})


def test_unpaced_complete_template_reports_actionable_error_before_apply(monkeypatch):
    planning(monkeypatch, {"id": "test", "dsp_profile": "dsp"}, {})
    monkeypatch.setattr(session_overrides, "apply", lambda *a: pytest.fail("must preflight pacing"))
    with pytest.raises(OCFError, match="test has no explicit pacing profile"):
        complete_session.build_complete_session_plan("test")


@pytest.mark.parametrize(
    "base,override,expected",
    [(None, "override", "override"), ("base", "override", "override"), ("base", None, "base")],
)
def test_explicit_pacing_override_is_honored_even_without_template_pacing(
    monkeypatch, base, override, expected
):
    template = {"id": "test", "dsp_profile": "dsp"}
    if base:
        template["pacing_profile"] = base
    planning(monkeypatch, template, {"pacing_profile": override} if override else {})
    monkeypatch.setattr(session, "load_pacing_profile", lambda key: {"selected": key})

    class ReachedApply(Exception):
        pass

    def apply(template_arg, pacing, dsp, options):
        assert pacing == {"selected": expected}
        assert template_arg == template
        raise ReachedApply

    monkeypatch.setattr(session_overrides, "apply", apply)
    with pytest.raises(ReachedApply):
        complete_session.build_complete_session_plan("test")


@pytest.mark.parametrize("dry_run", [True, False])
def test_missing_tts_voice_is_allowed_for_planning_but_fails_before_output(
    monkeypatch, tmp_path, dry_run
):
    monkeypatch.setattr(complete_session, "_resolve_template", lambda *a: ({"id": "test"}, {}))
    monkeypatch.setattr(session_overrides, "resolve", lambda *a: ({}, {}))
    monkeypatch.setattr(
        complete_session, "build_complete_session_plan", lambda *a, **k: {"voice_selection": {}}
    )
    monkeypatch.setattr(
        complete_session,
        "workspace_temp_directory",
        lambda **k: pytest.fail("no render scratch before voice validation"),
    )
    output = tmp_path / "audition"
    if dry_run:
        assert complete_session.render_complete_session("test", output=output, dry_run=True)[
            "dry_run"
        ]
    else:
        with pytest.raises(OCFError, match="requires a voice profile"):
            complete_session.render_complete_session("test", output=output)
    assert not output.exists()


@pytest.mark.parametrize("source_mode", [None, "recording", "hybrid"])
def test_build_boundary_preserves_source_voice_and_plain_tts_kwargs(
    monkeypatch, tmp_path, source_mode
):
    from ocf_tools import audio_build, narration_sources

    monkeypatch.setattr(complete_session, "LocaleCatalog", lambda: object())

    monkeypatch.setattr(
        complete_session,
        "_resolve_template",
        lambda *a: ({"id": "template", "voice_profile": "inherited"}, {}),
    )
    monkeypatch.setattr(session_overrides, "resolve", lambda *a: ({}, {}))
    plan = {
        "voice_selection": {},
        "locale": "en-US",
        "template": {},
        "template_plan": {},
        "tts_plan": {
            "requested_locale": "en-US",
            "voice_profile": {"id": "explicit"},
            "title": "Example",
            "pacing": {"speech_rate_scale": 1},
        },
        "resolved_dsp_profile": {"id": "dsp"},
        "resolved_pacing_profile": {},
    }
    monkeypatch.setattr(complete_session, "build_complete_session_plan", lambda *a, **k: plan)
    monkeypatch.setattr(narration_sources, "preview_sources", lambda *a, **k: {"mode": source_mode})
    monkeypatch.setattr(narration_first, "_voice_profile", lambda *a: ({}, {}))
    monkeypatch.setattr(narration_first, "_adjusted_profile", lambda *a: "adjusted")

    class ReachedBuild(Exception):
        pass

    def build(*args, **kwargs):
        if source_mode:
            assert kwargs["source_fallback_voice"] == "inherited"
            assert kwargs["voice"] == "explicit"
            assert kwargs["narration_source"] == source_mode
        else:
            assert "source_fallback_voice" not in kwargs
            assert "narration_sources" not in kwargs
            assert kwargs["voice"] == "adjusted"
        raise ReachedBuild

    monkeypatch.setattr(audio_build, "build", build)
    with pytest.raises(ReachedBuild):
        complete_session.render_complete_session(
            "test",
            voice="explicit",
            output=tmp_path / "out",
            narration_sources=tmp_path / "sources.json" if source_mode else None,
            narration_source=source_mode,
        )
    assert not (tmp_path / "out").exists()
