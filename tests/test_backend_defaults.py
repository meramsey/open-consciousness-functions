"""Conditional defaults, explicit precedence and actual session composition."""

import pytest
from ocf_tools import backend_defaults as defaults


@pytest.mark.unit
@pytest.mark.parametrize(
    "backend,engine,enabled,rms,expected",
    [
        ("chatterbox-nano", "farfield", True, -18, True),
        ("piper", "farfield", True, -18, False),
        ("chatterbox-nano", "sbagenx", True, -18, False),
        ("chatterbox-nano", "farfield", False, -18, False),
        ("chatterbox-nano", "farfield", True, -29, False),
        (None, "farfield", True, -18, False),
    ],
)
def test_pair_is_declared_and_original_normalization_is_required(
    monkeypatch, backend, engine, enabled, rms, expected
):
    from ocf_tools import audio_build

    monkeypatch.setattr(
        audio_build, "_resolve_background_manifest", lambda query: {"engine": engine}
    )
    dsp = {
        "target_state_rms_dbfs": rms,
        "states": {
            state: {"mode": "preset", "preset": "fixture"} for state in ["focus-10", "focus-11"]
        },
    }
    assert defaults.eligible(backend, dsp, enabled=enabled) is expected
    assert defaults.eligible(backend, {"states": {}}, enabled=enabled) is False


@pytest.mark.unit
def test_mix_is_detached_and_fixed_not_cumulative():
    a = defaults.mix_profile()
    a["semantic_state_gains_db"]["focus-11"] = -99
    assert defaults.mix_profile()["semantic_state_gains_db"] == {"focus-10": -3, "focus-11": -14}


@pytest.mark.integration
def test_selected_pair_preserves_words_holds_and_explicit_overrides():
    from ocf_tools.complete_session import build_complete_session_plan
    from ocf_tools.locale import iter_events

    args = {"function_id": "OCF-SEN-001", "locale": "en-US"}
    old = build_complete_session_plan(**args)
    new = build_complete_session_plan(**args, declared_voice_backend="chatterbox-nano")

    def words(plan):
        return [
            (e["id"], e.get("text"), e.get("timing")) for e in iter_events(plan["template_plan"])
        ]

    assert words(new) == words(old)
    assert "backend_defaults" not in old
    assert new["default_mix_profile"]["semantic_state_gains_db"] == {
        "focus-10": -3,
        "focus-11": -14,
    }
    policy = new["resolved_pacing_profile"]["narration_pacing"]["profiles"]
    assert policy["preparation"]["group_prose"] is True
    assert all(row["rate_scale"] == 1 for row in policy.values())
    explicit = build_complete_session_plan(
        **args,
        declared_voice_backend="chatterbox-nano",
        overrides={"pacing_profile": old["resolved_pacing_profile"]["id"]},
    )
    assert explicit["resolved_pacing_profile"] == old["resolved_pacing_profile"]
    assert explicit["default_mix_profile"] == new["default_mix_profile"]
    disabled = build_complete_session_plan(
        **args, declared_voice_backend="chatterbox-nano", overrides={"backend_defaults": False}
    )
    assert "default_mix_profile" not in disabled
    assert disabled["resolved_pacing_profile"] == old["resolved_pacing_profile"]


@pytest.mark.integration
def test_learning_defaults_and_empty_mix_override(monkeypatch, tmp_path):
    from ocf_tools import learning_session, semantic_dsp, speech_cache, voice

    monkeypatch.setattr(voice, "resolve_backend", lambda *a, **kw: {"name": "chatterbox-nano"})
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: {"backend": spec["name"]})
    monkeypatch.setattr(semantic_dsp, "dependency_identity", lambda dsp: {"verified": True})
    args = {"output": tmp_path / "unused", "voice": "fixture", "dry_run": True}
    default = learning_session.render(**args)
    explicit = learning_session.render(**args, mix_profile={})
    assert default["practice_seconds"] == explicit["practice_seconds"] == 510
    assert default["mix_profile"]["semantic_state_gains_db"] == {"focus-10": -3, "focus-11": -14}
    assert explicit["mix_profile"]["semantic_state_gains_db"] == {}
    assert default["identity_sha256"] != explicit["identity_sha256"]
    assert not (tmp_path / "unused").exists()


@pytest.mark.integration
def test_public_a6_gain_receipt_matches_actual_pcm(tmp_path):
    import shutil
    import subprocess

    from ocf_tools import semantic_dsp
    from test_semantic_dsp import TIMES, constant_stem, state_doc

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required for actual PCM verification")
    levels = {"focus-10": 3277, "focus-11": 6554}
    stems = {
        state: constant_stem(tmp_path, state, level, duration_s=100)
        for state, level in levels.items()
    }
    output = tmp_path / "bed.wav"
    gains = defaults.mix_profile()["semantic_state_gains_db"]
    result = semantic_dsp.render_program(
        state_doc(),
        TIMES,
        100,
        semantic_dsp.load_profile("OCF-DSP-DEVELOPMENT-V4-001"),
        output,
        render_state=lambda state, selection, seed, duration: stems[state],
        state_gains_db=gains,
    )
    assert result["fixed_state_gains_db"] == gains
    raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", str(output), "-f", "s24le", "-c:a", "pcm_s24le", "-"]
    )
    for at in [20, 35, 42, 48, 52, 58, 65, 80]:
        offset = round(at * 44100) * 6
        actual = int.from_bytes(raw[offset : offset + 3], "little", signed=True)
        expected = round(
            sum(
                level
                * result["selections"][state]["renderer_gain"]
                * semantic_dsp.gain_at(result, state, at)
                * 10 ** (gains[state] / 20)
                * 256
                for state, level in levels.items()
            )
        )
        assert abs(actual - expected) <= 1


@pytest.mark.integration
def test_bulk_candidate_plan_uses_selected_connected_policy(monkeypatch, tmp_path):
    from ocf_tools import bulk_render

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(defaults, "declared_backend", lambda voice: "chatterbox-nano")
    args = {"function_ids": ["OCF-SEN-001"], "voice": "fixture", "dry_run": True}
    selected = bulk_render.render_many(**args)
    legacy = bulk_render.render_many(**args, overrides={"backend_defaults": False})
    assert selected["blocked"] == legacy["blocked"] == 0
    assert (
        selected["speech_plan"]["candidate_unique_spoken_units"]
        < legacy["speech_plan"]["candidate_unique_spoken_units"]
    )
    assert selected["results"][0]["plan_sha256"] != legacy["results"][0]["plan_sha256"]


@pytest.mark.integration
def test_voice_override_preview_and_render_mix_identity(monkeypatch):
    from ocf_tools import complete_session, narration_first

    monkeypatch.setattr(defaults, "declared_backend", lambda query: "chatterbox-nano")
    preview = complete_session.build_complete_session_plan(
        "OCF-SEN-001", overrides={"voice_profile": "OCF-VOICE-9100"}
    )
    assert preview["default_mix_profile"]["semantic_state_gains_db"]["focus-11"] == -14
    monkeypatch.setattr(
        narration_first,
        "_voice_profile",
        lambda *args: (
            {
                "id": "OCF-VOICE-9100",
                "slug": "fixture",
                "name": "Fixture",
                "backend": "chatterbox-nano",
            },
            {"name": "chatterbox-nano", "language": "en-US"},
        ),
    )
    args = {"function_id": "OCF-SEN-001", "voice": "OCF-VOICE-9100", "dry_run": True}
    selected = complete_session.render_complete_session(**args)
    explicit = complete_session.render_complete_session(**args, mix_profile={})
    assert selected["mix_profile"] == preview["default_mix_profile"]
    assert explicit["mix_profile"]["semantic_state_gains_db"] == {}
    assert selected["render_identity_sha256"] != explicit["render_identity_sha256"]
