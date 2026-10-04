"""TTS/PCM contracts with synthetic bytes and stubbed native execution."""

import io
import json
import os
import subprocess
import wave
from pathlib import Path

import pytest
from ocf_tools import voice as v
from ocf_tools.locale import LocalizationError
from ocf_tools.transcript import ResolvedEvent
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def wav(samples, rate=100, channels=1, width=2):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(
            b"".join(int(value).to_bytes(width, "little", signed=width != 1) for value in samples)
        )
    return stream.getvalue()


@pytest.mark.parametrize(
    "token,value",
    [
        ("", None),
        ("word", None),
        ("1.5", None),
        ("1,5", None),
        ("10th", 10),
        ("-2", -2),
        ("Nineteen.", 19),
    ],
)
def test_count_tokens_are_textual_hints_not_state_identity(token, value):
    assert v._token_value(token) == value
    assert v._count_token_texts("one hello") == []


def test_count_grids_and_flow_groups_preserve_source_text():
    rows = [
        ResolvedEvent("a", "One. Two.", 0),
        ResolvedEvent("b", "Three.", 6),
        ResolvedEvent("c", "words", 10),
        ResolvedEvent("d", "Ten.", 11),
    ]
    adjusted, stats = v._even_counts(rows)
    assert [event.at for event in adjusted[:3]] == [0, 3, 6]
    assert [event.text for event in adjusted[:3]] == ["One.", "Two.", "Three."]
    assert rows[0].text == "One. Two." and rows[1].at == 6
    assert stats["runs"][0]["values"] == [1, 2, 3]
    assert v._even_counts([ResolvedEvent("none", "plain", 0)])[1] == {"runs": []}
    fragments = [
        ResolvedEvent("a", "first", 0),
        ResolvedEvent("b", "second.", 1),
        ResolvedEvent("c", "Ten.", 2),
        ResolvedEvent("d", "last", 3),
    ]
    assert [[e.id for e in group] for group in v._flow_groups(fragments)] == [
        ["a", "b"],
        ["c"],
        ["d"],
    ]
    assert v._flow_groups([]) == []


def test_request_pronunciation_only_changes_backend_input():
    request = v.NarrationRequest(
        "en-US",
        "PLUS-FOCUS stays",
        "espeak-ng",
        pronunciation={"PLUS-FOCUS": {"espeak-ng": "[[hint]]"}},
    )
    assert request.backend_text() == "[[hint]] stays"
    assert request.backend_text("piper") == request.text == "PLUS-FOCUS stays"
    assert request.as_metadata()["pronunciation_hints"] == ["PLUS-FOCUS"]
    assert (
        v.apply_pronunciation("plain", {"absent": {"espeak-ng": "hint"}, "plain": {}}, "espeak-ng")
        == "plain"
    )


def test_backend_profile_precedence_detection_and_model_expansion(monkeypatch, tmp_path):
    monkeypatch.setattr(v.shutil, "which", lambda name: "engine" if name == "espeak" else None)
    assert v.first_available_backend() == "espeak"
    assert [item["name"] for item in v.detect_backends()] == ["espeak-ng", "espeak", "piper"]
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    assert v._expand_model_path("$MODEL_DIR/voice.onnx") == str(tmp_path / "voice.onnx")
    assert v._expand_model_path(1) is None
    profile = {"id": "fixture", "slug": "profile", "name": "Name", "backend": "espeak"}
    for reference in ("fixture", "profile", "Name", profile):
        assert v.resolve_backend(reference, [profile])["profile_id"] == "fixture"
    assert v.resolve_backend(None, [profile])["name"] == "espeak"
    with pytest.raises(OCFError, match="unknown voice"):
        v.resolve_backend("unknown", [])
    with pytest.raises(OCFError, match="not supported"):
        v.resolve_backend({"backend": "unknown"}, [])
    monkeypatch.setattr(v.shutil, "which", lambda name: None)
    with pytest.raises(OCFError, match="No text-to-speech"):
        v.resolve_backend(None, [])
    assert v._locale_voice_name("espeak", "fr-CA") == "fr"
    assert v._locale_voice_name("espeak-ng", "fr-CA") == "fr-ca"
    assert v._locale_voice_name("piper", "fr") is None
    assert v._locale_voice_name("espeak", None) is None
    assert v.backend_locale_support("piper")["locale_style"] == "model-bound"


@pytest.mark.parametrize("metadata", ["{bad", "[]", '{"language":"fr"}', '{"language":{"code":2}}'])
def test_malformed_piper_metadata_fails_clearly(monkeypatch, tmp_path, metadata):
    model = tmp_path / "voice.onnx"
    Path(str(model) + ".json").write_text(metadata)
    with pytest.raises(LocalizationError, match="cannot read Piper model locale"):
        v.resolve_backend(
            {"backend": "piper", "language": "en_US", "piper_model": str(model)}, [], locale="en-US"
        )


def test_piper_sidecar_locale_overrides_mislabelled_profile(tmp_path):
    model = tmp_path / "voice.onnx"
    Path(str(model) + ".json").write_text(json.dumps({"language": {"code": "fr_FR"}}))
    profile = {"backend": "piper", "language": "en_US", "piper_model": str(model)}
    assert v.resolve_backend(profile, [], locale="fr-CA")["language"] == "fr_FR"
    with pytest.raises(LocalizationError, match="cannot render"):
        v.resolve_backend(profile, [], locale="en-US")


@pytest.mark.parametrize("case", ["missing", "unsupported", "ok"])
def test_language_probe_plans_command_and_rejects_unsupported(monkeypatch, case):
    spec = {"name": "espeak", "binary": "espeak", "locale": "fr", "language": "fr"}
    monkeypatch.setattr(v.shutil, "which", lambda name: None if case == "missing" else "engine")
    calls = []
    monkeypatch.setattr(
        v.subprocess,
        "run",
        lambda argv, **kw: (
            calls.append((argv, kw))
            or subprocess.CompletedProcess(
                argv, 1 if case == "unsupported" else 0, "header\nvoice", ""
            )
        ),
    )
    if case == "ok":
        v.check_backend_locale(spec)
        assert calls == [
            (["engine", "--voices=fr"], {"capture_output": True, "text": True, "timeout": 15})
        ]
    else:
        with pytest.raises(OCFError):
            v.check_backend_locale(spec)
    v.check_backend_locale({"name": "piper", "locale": "fr"})
    v.check_backend_locale({"name": "espeak"})


@pytest.mark.parametrize("backend", ["espeak-ng", "espeak", "piper"])
@pytest.mark.parametrize(
    "case", ["ok", "missing", "oserror", "timeout", "nonzero", "empty", "deleted"]
)
def test_native_cue_boundary_closes_descriptor_and_cleans_every_outcome(
    monkeypatch, tmp_path, backend, case
):
    spec = v.resolve_backend({"backend": backend, "piper_model": "model.onnx"}, [])
    monkeypatch.setattr(v.shutil, "which", lambda name: None if case == "missing" else "engine")
    original_mkstemp, original_close = v.tempfile.mkstemp, os.close
    closed, allocated, calls = [], [], []

    def allocate(**kw):
        fd, path = original_mkstemp(dir=tmp_path, **kw)
        allocated.append((fd, Path(path)))
        return fd, path

    def close(fd):
        closed.append(fd)
        original_close(fd)

    monkeypatch.setattr(v.tempfile, "mkstemp", allocate)
    monkeypatch.setattr(v.os, "close", close)
    payload = wav([100, -100])

    def run(argv, **kw):
        calls.append((argv, kw))
        assert closed == [allocated[0][0]]
        if case == "oserror":
            raise OSError("missing engine")
        if case == "timeout":
            raise subprocess.TimeoutExpired(argv, 10)
        if case == "deleted":
            allocated[0][1].unlink()
        if case == "ok":
            allocated[0][1].write_bytes(payload)
        return subprocess.CompletedProcess(
            argv, 2 if case == "nonzero" else 0, b"", b"error" if case == "nonzero" else b""
        )

    monkeypatch.setattr(v.subprocess, "run", run)
    if case == "ok":
        assert v.render_cue_wav(spec, "Café", timeout=10) == payload
        assert calls[0][1] == {"input": "Café".encode(), "capture_output": True, "timeout": 10}
        assert "engine" == calls[0][0][0]
    else:
        with pytest.raises(OCFError):
            v.render_cue_wav(spec, "Café", timeout=10)
    assert list(tmp_path.iterdir()) == []
    if case == "missing":
        assert not calls and not allocated


def test_pcm_width_channels_corruption_and_linear_resampling():
    assert v._read_pcm_from_bytes(wav([100, 300, -100, -300], channels=2)) == (100, [200, -200])
    for payload, message in [
        (b"not wav", "unreadable"),
        (wav([1, 2], width=1), "expected 16-bit"),
        (wav([1, 2, 3], channels=3), "channel count"),
    ]:
        with pytest.raises(OCFError, match=message):
            v._read_pcm_from_bytes(payload)
    assert v._resample([0, 1000], 100, 200) == [0, 500, 1000, 1000]
    assert v._resample([0], 0, 100) == [0]
    assert v._resample([], 100, 200) == []
    assert v._active_bounds([0] * 10, 100) == (0, 0)
    assert v._active_bounds([0, 1000, 1000, 0], 100) == (1, 3)
    assert v._fit_line([0] * 10, 1, 100) == [0] * 10
    assert v._fit_line([1000] * 10, 0, 100) == [1000] * 10
    fitted = v._fit_line([0] * 10 + [1000] * 100 + [0] * 10, 1.1 + v.FIT_MIN_AIR, 100)
    assert 105 <= len(fitted) <= 115 and fitted[0] == fitted[-1] == 1000


def test_voice_status_commands_have_no_execution_or_downloads(monkeypatch, capsys):
    monkeypatch.setattr(v.shutil, "which", lambda name: None)
    monkeypatch.setattr(v, "load_voice_profiles", lambda: [])
    assert v.voice_doctor() == 1
    assert v.list_profiles_cmd() == 0 and v.list_backends_cmd() == 0
    assert "No voice profiles" in capsys.readouterr().out
    monkeypatch.setattr(v.shutil, "which", lambda name: "engine")
    monkeypatch.setattr(
        v, "load_voice_profiles", lambda: [{"id": "profile", "slug": "voice", "backend": "espeak"}]
    )
    assert v.voice_doctor() == 0 and v.list_profiles_cmd() == 0
    assert "profile" in capsys.readouterr().out


@pytest.mark.parametrize("case", ["ok", "empty", "nonzero", "oserror", "timeout"])
def test_stdout_backend_protocol_has_no_file_or_stdin(monkeypatch, case):
    monkeypatch.setitem(
        v.BACKENDS,
        "fixture",
        {"mode": "stdout", "render": lambda exe, voice, wpm, model, text, out: [exe, text]},
    )
    monkeypatch.setattr(v.shutil, "which", lambda name: "engine")
    payload = wav([100, 100])

    def run(argv, **kw):
        assert argv == ["engine", "Café"] and kw["input"] is None
        if case == "oserror":
            raise OSError("gone")
        if case == "timeout":
            raise subprocess.TimeoutExpired(argv, 60)
        return subprocess.CompletedProcess(
            argv, 1 if case == "nonzero" else 0, payload if case == "ok" else b"", b""
        )

    monkeypatch.setattr(v.subprocess, "run", run)
    spec = {"name": "fixture", "binary": "fixture", "language": "en", "wpm": 100}
    if case == "ok":
        assert v.render_cue_wav(spec, "Café") == payload
    else:
        with pytest.raises(OCFError):
            v.render_cue_wav(spec, "Café")


def test_pronunciation_requirements_and_resource_origin_are_explicit():
    from types import SimpleNamespace as NS

    calls = []
    entry = NS(
        required_pronunciation=["command"],
        pronunciation={"PLUS-FOCUS": {"espeak-ng": "[[hint]]"}},
        hint_for=lambda backend, token: "[[hint]]" if backend == "espeak-ng" else None,
    )
    catalog = NS(resource=lambda key, tag, **kw: calls.append((key, tag, kw)) or (entry, None))
    doc = {
        "timeline": [
            {"id": "a", "narration_key": "fixture.key", "variables": {"command": "PLUS-FOCUS"}}
        ],
        "narration": {"resolved": [{"id": "a", "locale": "fr"}]},
    }
    assert v._pronunciation_hints(doc, None, catalog, "espeak-ng") == {}
    assert v._pronunciation_hints(doc, "en-US", catalog, "espeak-ng")["a"] == entry.pronunciation
    assert calls[-1][1] == "fr" and calls[-1][2]["fallback"] is False
    with pytest.raises(OCFError, match="required pronunciation"):
        v._pronunciation_hints(doc, "en-US", catalog, "piper")
    entry.required_pronunciation = []
    entry.pronunciation = {}
    assert v._pronunciation_hints(doc, "en-US", catalog, "espeak-ng") == {}
    assert v.apply_pronunciation("plain", None, "espeak-ng") == "plain"


def test_backend_locale_notes_and_invalid_tags_are_not_silent(monkeypatch):
    from types import SimpleNamespace as NS

    result = v.resolve_backend({"backend": "espeak"}, [], locale="fr", catalog=NS(packs={}))
    assert result["language"] == "fr" and any("no locale pack" in note for note in result["notes"])
    with pytest.raises(LocalizationError):
        v.resolve_backend({"backend": "espeak"}, [], locale="bad!tag")


@pytest.fixture
def narration_boundary(monkeypatch):
    from ocf_tools import semantics, validators

    monkeypatch.setattr(
        v,
        "resolve_backend",
        lambda *a, **kw: {"name": "espeak-ng", "language": "en-us", "notes": []},
    )
    monkeypatch.setattr(v, "check_backend_locale", lambda spec: None)
    monkeypatch.setattr(semantics, "bind_document_cues", lambda doc: [])
    monkeypatch.setattr(
        validators, "validate_command_ownership", lambda *a: validators.ValidationResult()
    )
    monkeypatch.setattr(
        validators, "validate_narration_hygiene", lambda *a: validators.ValidationResult()
    )
    return validators, semantics


@pytest.mark.parametrize("case", ["validation", "untimed", "duplicate-id", "disabled-speech"])
def test_narration_preflight_rejects_before_native_render(
    monkeypatch, tmp_path, narration_boundary, case
):
    validators, _ = narration_boundary
    doc = {"timeline": [{"id": "a", "at": 0, "text": "Fixture"}]}
    if case == "validation":
        error = validators.ValidationResult()
        error.add("error", "fixture", "invalid narration")
        monkeypatch.setattr(validators, "validate_narration_hygiene", lambda *a: error)
    elif case == "untimed":
        doc["timeline"][0].pop("at")
    elif case == "duplicate-id":
        doc["timeline"].append({"id": "a", "at": 1, "text": "Duplicate"})
    monkeypatch.setattr(v, "render_cue_wav", lambda *a: pytest.fail("must not synthesize"))
    with pytest.raises(OCFError):
        v.render_narration(
            doc,
            tmp_path / "out.wav",
            backend="disabled" if case == "disabled-speech" else "espeak-ng",
        )
    assert not (tmp_path / "out.wav").exists()


def test_narration_hints_fit_and_semantic_counts_keep_display_text(
    monkeypatch, tmp_path, narration_boundary
):
    doc = {
        "timeline": [
            {"id": "a", "at": 0, "text": "PLUS-FOCUS", "semantic": "fixture.start"},
            {"id": "b", "at": 2, "text": "Other", "semantic": "fixture.continue"},
        ]
    }
    monkeypatch.setattr(
        v, "_pronunciation_hints", lambda *a: {"a": {"PLUS-FOCUS": {"espeak-ng": "[[hint]]"}}}
    )
    rendered = []
    metadata = v.render_narration(
        doc,
        tmp_path / "out.wav",
        backend="espeak-ng",
        sample_rate=100,
        render_cue=lambda text: rendered.append(text) or wav([1000] * 10),
        fit=True,
        flow=True,
        even_counts=True,
    )
    assert rendered == ["[[hint]]", "Other"]
    assert metadata["cue_stats"][0]["display_text"] == "PLUS-FOCUS"
    assert metadata["pronunciation_hints"] == 1
    assert metadata["timing_mode"] == "timeline-shift+even-counts"
    assert metadata["even_counts"]["runs"] == []
    assert [e["id"] for e in metadata["event_timing"]] == ["a", "b"]
    monkeypatch.setattr(v, "render_cue_wav", lambda spec, text: wav([1000] * 10))
    metadata = v.render_narration(
        {"timeline": [{"id": "a", "at": 0, "text": "Native stub"}]},
        tmp_path / "native.wav",
        backend="espeak-ng",
        sample_rate=100,
    )
    assert metadata["cues"] == 1


def test_duplicate_resolved_cues_fail_without_output(tmp_path, narration_boundary, monkeypatch):
    _, semantics = narration_boundary
    doc = {
        "timeline": [
            {"id": "a", "at": 0, "semantic": "fixture.start"},
            {"id": "b", "at": 0, "semantic": "fixture.start"},
        ]
    }
    monkeypatch.setattr(
        semantics,
        "bind_document_cues",
        lambda doc: [
            {"event_id": "a", "identity": "fixture.cue"},
            {"event_id": "b", "identity": "fixture.cue"},
        ],
    )
    with pytest.raises(OCFError, match="duplicate auditory cue"):
        v.render_narration(doc, tmp_path / "out.wav", backend="disabled", sample_rate=100)
    assert not (tmp_path / "out.wav").exists()


def test_render_script_reports_sidecar_and_output_collision(monkeypatch, tmp_path, capsys):
    from ocf_tools.utils import OCFFileExistsError

    monkeypatch.setattr(v, "load_timed_doc", lambda path: {"id": "fixture"})
    out = tmp_path / "speech.wav"
    source = tmp_path / "source.yaml"
    source.write_text("synthetic source")
    sidecar = out.with_suffix(".render.yaml")
    sidecar.write_text("old timing")
    with pytest.raises(OCFError, match="timing manifest"):
        v.render_script(source, out)

    def collision(*a, **kw):
        raise OCFFileExistsError("old audio exists")

    monkeypatch.setattr(v, "render_narration", collision)
    with pytest.raises(OCFError, match="--force"):
        v.render_script(source, out, force=True)

    def render(doc, path, **kw):
        path.write_bytes(wav([1000] * 10))
        return {
            "profile_id": None,
            "backend": "fixture",
            "cues": 1,
            "duration": 0.1,
            "sample_rate": 100,
            "cue_stats": [{"id": "a", "at": 0, "samples": 10}],
            "locale": "fr",
            "voice": "fr",
            "pronunciation_hints": 1,
        }

    monkeypatch.setattr(v, "render_narration", render)
    assert v.render_script(source, out, force=True) == 0
    assert "applied 1 pronunciation" in capsys.readouterr().out
    assert sidecar.read_text() != "old timing"
    with pytest.raises(OCFFileExistsError):
        v._write_wav(out, [0], 100, overwrite=False)


def test_sample_rounding_retains_every_pcm_frame(tmp_path, narration_boundary):
    metadata = v.render_narration(
        {"timeline": [{"id": "a", "at": 0, "text": "Fixture"}]},
        tmp_path / "out.wav",
        backend="espeak-ng",
        render_cue=lambda text: wav([1000] * 21, rate=44100),
        sample_rate=44100,
    )
    with wave.open(str(tmp_path / "out.wav"), "rb") as reader:
        assert reader.getnframes() == 44121
    assert metadata["cue_stats"][0]["samples"] == 21


def test_model_bound_locale_without_sidecar_and_script_without_locale(
    monkeypatch, tmp_path, capsys
):
    assert (
        v.resolve_backend({"backend": "piper", "language": "en_US"}, [], locale="en-US")["language"]
        == "en_US"
    )
    missing_model = tmp_path / "missing.onnx"
    assert (
        v.resolve_backend(
            {"backend": "piper", "language": "en_US", "piper_model": str(missing_model)},
            [],
            locale="en-US",
        )["language"]
        == "en_US"
    )
    source = tmp_path / "source.yaml"
    source.write_text("synthetic source")
    out = tmp_path / "speech.wav"
    monkeypatch.setattr(v, "load_timed_doc", lambda path: {})

    def render(doc, path, **kw):
        path.write_bytes(wav([1000] * 10))
        return {
            "profile_id": "fixture-profile",
            "backend": "fixture",
            "cues": 1,
            "duration": 0.1,
            "sample_rate": 100,
            "cue_stats": [{"id": "a", "at": 0, "samples": 10}],
            "locale": None,
            "voice": None,
            "pronunciation_hints": 0,
        }

    monkeypatch.setattr(v, "render_narration", render)
    assert v.render_script(source, out) == 0
    assert "locale " not in capsys.readouterr().out
