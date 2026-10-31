"""Force policy reaches synthesis through the real complete-session call chain."""

import io
import wave

import pytest
from ocf_tools import complete_session, narration_first, speech_cache, voice
from ocf_tools.utils import OCFError


def pcm():
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\xe8\x03" * 80)
    return output.getvalue()


@pytest.mark.unit
def test_nested_disable_is_sticky_and_restores_default_reuse(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: spec)
    calls = []
    monkeypatch.setattr(voice, "_render_cue_wav", lambda *args: calls.append(args) or pcm())
    before = dict(speech_cache.STATS)
    with speech_cache.enabled():
        voice.render_cue_wav({}, "Exact text.")
        voice.render_cue_wav({}, "Exact text.")
        for _ in range(2):
            with speech_cache.enabled(False), speech_cache.enabled(), speech_cache.enabled(True):
                voice.render_cue_wav({}, "Exact text.")
        voice.render_cue_wav({}, "Exact text.")
    with speech_cache.enabled():
        voice.render_cue_wav({}, "Exact text.")
    assert len(calls) == 3
    assert speech_cache.STATS["hit"] - before["hit"] == 3
    assert speech_cache.STATS["bypassed"] - before["bypassed"] == 2
    assert not speech_cache._active.get()


@pytest.mark.unit
def test_require_hit_blocks_missing_speech_without_calling_synthesizer(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: spec)
    calls = []
    monkeypatch.setattr(voice, "_render_cue_wav", lambda *args: calls.append(args) or pcm())
    with speech_cache.policy("require-hit"), speech_cache.policy("auto"), speech_cache.enabled():
        with pytest.raises(OCFError, match="synthesis was blocked"):
            voice.render_cue_wav({"name": "fixture"}, "not cached")
    assert calls == []


@pytest.mark.integration
@pytest.mark.parametrize("force", [False, True])
def test_complete_session_policy_at_actual_synthesis_boundary(monkeypatch, tmp_path, force):
    # Keep composition, audio_build, narration pacing, cue cache and dispatch real;
    # stop at the external synthesizer before producing a full-length session.
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    spec = {"name": "piper", "language": "en_US", "binary": "fixture", "wpm": None}
    profile = {
        "id": "OCF-VOICE-0002",
        "slug": "fixture",
        "name": "Fixture",
        "backend": "piper",
        "piper_length_scale": 1.0,
    }
    monkeypatch.setattr(narration_first, "_voice_profile", lambda *args: (profile, spec))
    monkeypatch.setattr(voice, "resolve_backend", lambda *args, **kwargs: dict(spec))
    monkeypatch.setattr(voice, "check_backend_locale", lambda *args: None)
    monkeypatch.setattr(speech_cache, "voice_identity", lambda selected: selected)
    requests = []

    class SynthesisBoundary(Exception):
        pass

    def stop_at_synthesis(selected, text, timeout):
        requests.append((selected, text))
        raise SynthesisBoundary

    monkeypatch.setattr(voice, "_render_cue_wav", stop_at_synthesis)
    with pytest.raises(SynthesisBoundary):
        complete_session.render_complete_session(
            "OCF-SLP-005", voice="OCF-VOICE-0002", output=tmp_path / "probe"
        )
    first_spec, first_text = requests.pop()
    monkeypatch.setattr(voice, "_render_cue_wav", lambda *args: pcm())
    with speech_cache.enabled():
        voice.render_cue_wav(first_spec, first_text)
    monkeypatch.setattr(voice, "_render_cue_wav", stop_at_synthesis)
    before = dict(speech_cache.STATS)
    with speech_cache.enabled(not force), pytest.raises(SynthesisBoundary):
        complete_session.render_complete_session(
            "OCF-SLP-005", voice="OCF-VOICE-0002", output=tmp_path / "render"
        )
    assert (requests[0] == (first_spec, first_text)) is force
    assert speech_cache.STATS["hit"] - before["hit"] == (0 if force else 1)
    assert speech_cache.STATS["bypassed"] - before["bypassed"] == (1 if force else 0)
    assert not speech_cache._active.get()
