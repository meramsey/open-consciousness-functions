"""Isolated invalid-input boundaries; no synthesis or renderer rewrite."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event

import pytest
from ocf_tools import (
    complete_session,
    dev_jobs,
    narration_first,
    semantic_dsp,
    session,
    session_overrides,
)
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


def test_duplicate_explicit_render_destination_fails_before_rendering(monkeypatch, tmp_path):
    output = tmp_path / "private-session"
    locks = []

    @contextmanager
    def busy(name, *, wait=False, timeout=10):
        locks.append((name, wait, timeout))
        yield False

    monkeypatch.setattr(dev_jobs, "lock", busy)
    monkeypatch.setattr(
        complete_session,
        "_render_complete_session_unlocked",
        lambda *args, **kwargs: pytest.fail("duplicate render must fail before synthesis/render"),
    )
    with pytest.raises(OCFError, match="already being rendered"):
        complete_session.render_complete_session("OCF-SEN-001", output=output)
    assert len(locks) == 1 and locks[0][1] is False
    assert not output.exists()


def _verified_session_fixture(output, identity="a" * 64):
    output.mkdir()
    artifacts = {}
    for name, key in (
        ("master.wav", "wav"),
        ("background.wav", "background_stem"),
        ("transcript.txt", "transcript"),
    ):
        data = f"verified {key}".encode()
        (output / name).write_bytes(data)
        artifacts[key] = {
            "path": name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    (output / "session-report.json").write_text(
        json.dumps({"render_identity_sha256": identity, "artifacts": artifacts})
    )


def test_complete_session_identity_is_deterministic_and_binds_mix_and_source_hashes(tmp_path):
    plan = {
        "locale": "en-US",
        "voice_selection": {"profile_id": "OCF-VOICE-TEST"},
        "template": {"id": "template", "version": "1"},
        "resolved_dsp_profile": {"id": "dsp", "version": "1"},
        "narration_resources": [{"key": "fixture", "resolved_text_sha256": "abc"}],
    }
    source = tmp_path / "sources.json"
    source.write_text('{"mode":"recording"}')
    base = {
        "locale": "en-US",
        "voice": "OCF-VOICE-TEST",
        "pacing": "sleep",
        "dsp_profile": tmp_path / "profile.yaml",
        "sample_rate": 44100,
        "narration_sources": source,
    }
    identity = complete_session._complete_session_identity("fixture", plan, None, **base)
    assert identity == complete_session._complete_session_identity("fixture", plan, None, **base)
    assert identity != complete_session._complete_session_identity(
        "fixture", plan, {"profile_id": "different"}, **base
    )
    source.write_text('{"mode":"different"}')
    assert identity != complete_session._complete_session_identity("fixture", plan, None, **base)


def test_complete_session_identity_binds_private_voice_profile_revision(monkeypatch):
    from ocf_tools import indexes

    plan = {"tts_plan": {"voice_profile": {"id": "OCF-VOICE-TEST"}}}
    request = {"voice": "OCF-VOICE-TEST"}
    profile = {"id": "OCF-VOICE-TEST", "reference_audio": {"sha256": "a" * 64}}
    monkeypatch.setattr(indexes, "load_voice_profiles", lambda: [profile])
    original = complete_session._complete_session_identity("fixture", plan, None, **request)
    profile["reference_audio"]["sha256"] = "b" * 64
    revised = complete_session._complete_session_identity("fixture", plan, None, **request)
    assert original != revised


def test_verified_matching_output_is_reused_without_rendering(monkeypatch, tmp_path):
    output = tmp_path / "verified-output"
    _verified_session_fixture(output)

    @contextmanager
    def owned(*args, **kwargs):
        yield True

    def dry_run(*args, **kwargs):
        assert kwargs["dry_run"] is True
        return {"dry_run": True, "render_identity_sha256": "a" * 64}

    monkeypatch.setattr(dev_jobs, "lock", owned)
    monkeypatch.setattr(complete_session, "_render_complete_session_unlocked", dry_run)
    result = complete_session.render_complete_session("fixture", output=output)
    assert result["reused"] is True
    assert result["output_directory"] == str(output.resolve())
    assert (output / "master.wav").is_file()


@pytest.mark.parametrize("mutation", ["different-identity", "missing-report", "corrupt-artifact"])
def test_existing_partial_or_unmatched_output_is_preserved_and_refused(
    monkeypatch, tmp_path, mutation
):
    output = tmp_path / "existing-output"
    _verified_session_fixture(output)
    if mutation == "different-identity":
        (output / "session-report.json").write_text(
            json.dumps({"render_identity_sha256": "b" * 64, "artifacts": {}})
        )
    elif mutation == "missing-report":
        (output / "session-report.json").unlink()
    else:
        (output / "master.wav").write_bytes(b"tampered")

    @contextmanager
    def owned(*args, **kwargs):
        yield True

    monkeypatch.setattr(dev_jobs, "lock", owned)
    monkeypatch.setattr(
        complete_session,
        "_render_complete_session_unlocked",
        lambda *a, **k: {"dry_run": True, "render_identity_sha256": "a" * 64},
    )
    with pytest.raises(OCFError, match="existing complete-session"):
        complete_session.render_complete_session("fixture", output=output)
    assert output.is_dir()
    assert (output / "master.wav").is_file()


def test_concurrent_identical_destination_has_one_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    output = tmp_path / "concurrent-output"
    entered, release = Event(), Event()
    calls = []

    def render(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return {"dry_run": False, "output_directory": str(output)}

    monkeypatch.setattr(complete_session, "_render_complete_session_unlocked", render)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(complete_session.render_complete_session, "fixture", output=output)
        assert entered.wait(5)
        with pytest.raises(OCFError, match="already being rendered"):
            complete_session.render_complete_session("fixture", output=output)
        release.set()
        assert first.result(timeout=5)["output_directory"] == str(output)
    assert calls == [1]


def test_output_lock_is_released_after_interrupted_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    output = tmp_path / "reentry-output"
    calls = []

    def render(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("simulated interrupted render")
        return {"dry_run": False, "output_directory": str(output)}

    monkeypatch.setattr(complete_session, "_render_complete_session_unlocked", render)
    with pytest.raises(RuntimeError, match="simulated interrupted"):
        complete_session.render_complete_session("fixture", output=output)
    assert complete_session.render_complete_session("fixture", output=output)[
        "output_directory"
    ] == str(output)
    assert calls == [1, 1]


def test_stale_pid_text_does_not_impersonate_kernel_lock_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    lock_path = tmp_path / "work/logs/jobs/complete-session-output-fixture.lock"
    lock_path.parent.mkdir(parents=True)
    stale = b'{"pid": 2147483647, "started_at": "before-reboot"}\n'
    lock_path.write_bytes(stale)
    with dev_jobs.lock("complete-session-output-fixture", wait=False) as acquired:
        assert acquired
    assert lock_path.read_bytes() == stale


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
