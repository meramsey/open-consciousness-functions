"""Audio planning/provenance contracts and synthetic reference PCM; no native tools."""

import io
import subprocess
import wave
from array import array
from types import SimpleNamespace as NS

import pytest
from ocf_tools import audio_build as ab
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def test_tags_classify_provenance_without_claiming_release_rights(monkeypatch):
    monkeypatch.setattr(
        ab,
        "load_function_by_id",
        lambda id: NS(canonical_name="Café", canonical_command="PLUS-FOCUS"),
    )
    manifest = {
        "id": "OCF-AUDIO-0001",
        "title": "Example",
        "function_id": "OCF-FND-999",
        "narrator": "Human",
    }
    original = {
        "source": {"format": "manual"},
        "template": {"id": "fixture", "origin": "original-ocf"},
    }
    tags = ab._resolve_tags(
        manifest,
        original,
        {"timing_mode": "measured"},
        {"title": "Override"},
        voice_profile_id="OCF-VOICE-9100",
    )
    assert tags["title"] == "Override" and tags["album"] == "Café"
    assert tags["OCF_VOICE_PROFILE"] == "OCF-VOICE-9100"
    assert tags["OCF_COMMAND"] == "PLUS-FOCUS" and tags["OCF_SESSION_TEMPLATE"] == "fixture"
    assert (
        "committable" not in tags["comment"] and "rights clearance are separate" in tags["comment"]
    )
    assert not ab._doc_is_original({"source": {"format": "manual", "snapshot": ""}})
    assert not ab._doc_is_original(None)
    assert (
        "source-derived" in ab._resolve_tags(manifest, {"source": {"format": "lrc"}}, {})["comment"]
    )
    monkeypatch.setattr(ab, "load_function_by_id", lambda id: None)
    assert (
        ab._resolve_tags({"id": "custom", "title": "Title", "function_id": "unknown"}, {}, {})[
            "track"
        ]
        == "1"
    )
    assert ab._resolve_tags({"title": "Title"}, {}, {})["album"] == "Title"


@pytest.mark.parametrize("fmt", ["wav", "flac", "mp3"])
def test_encoding_plans_argv_tags_and_translates_failures(monkeypatch, tmp_path, fmt):
    source, out = tmp_path / "source.wav", tmp_path / f"out.{fmt}"
    source.write_bytes(b"source bytes")
    monkeypatch.setattr(ab.shutil, "which", lambda name: "ffmpeg" if name == "ffmpeg" else None)
    calls = []
    monkeypatch.setattr(
        ab,
        "workspace_run",
        lambda cmd, **kw: calls.append((cmd, kw)) or subprocess.CompletedProcess(cmd, 0, "", ""),
    )
    assert ab._encode(source, fmt, out, {"comment": "a=b"}) == (
        "none" if fmt == "wav" else "ffmpeg"
    )
    if fmt == "wav":
        assert out.read_bytes() == b"source bytes" and not calls
    else:
        assert "comment=a=b" in calls[0][0]
        assert calls[0][1]["capture_output"] is True and calls[0][1]["text"] is True
        assert ("-id3v2_version" in calls[0][0]) is (fmt == "mp3")
        monkeypatch.setattr(
            ab,
            "workspace_run",
            lambda *a, **kw: subprocess.CompletedProcess([], 1, "", "failed encode"),
        )
        with pytest.raises(OCFError, match="ffmpeg encode"):
            ab._encode(source, fmt, out)


@pytest.mark.parametrize("available,code", [(False, 0), (True, 0), (True, 1)])
def test_flac_fallback_and_absence_keep_wav(monkeypatch, tmp_path, available, code):
    source = tmp_path / "source.wav"
    source.write_bytes(b"master")
    monkeypatch.setattr(
        ab.shutil, "which", lambda name: "flac" if name == "flac" and available else None
    )
    calls = []
    monkeypatch.setattr(
        ab,
        "workspace_run",
        lambda cmd, **kw: (
            calls.append(cmd) or subprocess.CompletedProcess(cmd, code, "", "failure")
        ),
    )
    if available and code == 0:
        assert ab._encode(source, "flac", tmp_path / "out.flac", {"title": "Café"}) == "flac"
        assert calls[0][-2:] == ["-T", "title=Café"]
    else:
        with pytest.raises(OCFError, match="master was kept as WAV"):
            ab._encode(source, "flac", tmp_path / "out.flac")
    assert source.read_bytes() == b"master"


def test_decode_and_mix_command_boundaries(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ab.shutil, "which", lambda name: None)
    with pytest.raises(OCFError, match="ffmpeg is required"):
        ab._decode_to_s16le(tmp_path / "input")
    monkeypatch.setattr(ab.shutil, "which", lambda name: "ffmpeg")
    monkeypatch.setattr(
        ab,
        "workspace_run",
        lambda cmd, **kw: (
            calls.append((cmd, kw)) or subprocess.CompletedProcess(cmd, 0, b"pcm", b"")
        ),
    )
    assert ab._decode_to_s16le(tmp_path / "input", start=0, seconds=2, sample_rate=100) == b"pcm"
    assert calls[-1][0][-7:] == ["-ar", "100", "-ac", "2", "-f", "s16le", "-"]
    ab._mix_master_ffmpeg(
        tmp_path / "speech",
        tmp_path / "bed",
        tmp_path / "output/master.wav",
        speech_gain_windows=[(1, 2, -6)],
    )
    graph = calls[-1][0][calls[-1][0].index("-filter_complex") + 1]
    assert "[n];[1:a]" in graph and "between(t,1.000,2.000)" in graph
    assert "alimiter=limit=0.97:level=false" in graph
    monkeypatch.setattr(
        ab, "workspace_run", lambda *a, **kw: subprocess.CompletedProcess([], 1, b"", b"failure")
    )
    with pytest.raises(OCFError, match="decode failed"):
        ab._decode_to_s16le(tmp_path / "input")
    with pytest.raises(OCFError, match="master mix failed"):
        ab._mix_master_ffmpeg(tmp_path / "speech", tmp_path / "bed", tmp_path / "out.wav")


@pytest.mark.parametrize("engine", ["farfield", "sbagenx"])
@pytest.mark.parametrize("case", ["absent", "missing-output", "directory-output", "ok"])
def test_background_native_planning_stays_in_scratch_directory(monkeypatch, tmp_path, engine, case):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    module = ab.farfield_mod if engine == "farfield" else ab.sbagenx_mod
    monkeypatch.setattr(module, "check_" + engine, lambda: NS(available=case != "absent"))
    monkeypatch.setattr(ab, "_farfield_preset_file", lambda *a: "fixture.yaml")
    monkeypatch.setattr(ab, "_sbagenx_sequence_file", lambda *a: "fixture.sbg")
    seen = []

    def render(preset, **kw):
        seen.append((preset, kw))
        if case == "ok":
            kw["output"].write_bytes(b"synthetic output")
        elif case == "directory-output":
            kw["output"].mkdir()
        return "planned"

    monkeypatch.setattr(module, "render_preset", render)
    function = ab._render_farfield if engine == "farfield" else ab._render_sbagenx
    if case == "absent":
        assert function("preset", "optional")[0] is None
        with pytest.raises(OCFError, match="required"):
            function("preset", "required")
    elif case == "ok":
        path, selected = function(str(tmp_path / "source/preset.sbg"), "required")
        assert path.is_relative_to(tmp_path / "ocf-work" / "tmp") and selected == engine
    else:
        with pytest.raises(OCFError, match="produced no file"):
            function("preset", "required")
    if seen:
        assert seen[0][1]["output"].is_relative_to(tmp_path / "ocf-work" / "tmp")


def test_manifest_file_lookup_preserves_declared_paths_and_precedence(monkeypatch, tmp_path):
    monkeypatch.setattr(ab, "REPO_ROOT", tmp_path)
    path = tmp_path / "declared.yaml"
    path.write_text("fixture")
    manifests = [
        {"id": "other"},
        {"id": "preset", "name": "Name", "engine": "farfield", "preset": {"file": "declared.yaml"}},
    ]
    monkeypatch.setattr(ab, "load_background_manifests", lambda: manifests)
    monkeypatch.setattr(ab.farfield_mod, "resolve_preset", lambda name: None)
    assert ab._farfield_preset_file(str(path)) == str(path)
    assert ab._declared_background_file("preset") == str(path)
    assert ab._farfield_preset_file("preset") == str(path)
    assert ab._resolve_background_manifest(None) is None
    assert ab._resolve_background_manifest("Name") == manifests[1]
    assert ab._sbagenx_sequence_file("preset") == "preset"
    manifests[1]["engine"] = "sbagenx"
    assert ab._sbagenx_sequence_file("preset") == str(path)
    assert ab._declared_background_file("preset") is None
    manifests[1]["preset"] = {"file": "missing"}
    assert ab._sbagenx_sequence_file("preset") == "preset"
    assert ab._farfield_preset_file("unknown", "optional") == "unknown"
    with pytest.raises(OCFError):
        ab._farfield_preset_file("unknown", "required")


def test_reference_splice_preserves_the_declared_fade_out(monkeypatch, tmp_path):
    monkeypatch.setattr(ab, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ab, "DEFAULT_SAMPLE_RATE", 10)
    (tmp_path / "base").write_bytes(b"synthetic source")
    (tmp_path / "segment").write_bytes(b"synthetic source")
    manifest = {
        "reference": {
            "source": "base",
            "splices": [
                {
                    "source": "segment",
                    "slice_start": 0,
                    "slice_length": 0.8,
                    "target_start": 0,
                    "crossfade": 0.2,
                }
            ],
        }
    }
    monkeypatch.setattr(ab, "_resolve_background_manifest", lambda preset: manifest)
    monkeypatch.setattr(ab.shutil, "which", lambda name: "ffmpeg")
    base = array("h", [1000] * 20).tobytes()
    segment = array("h", [1000] * 8 + [-1000] * 8).tobytes()
    monkeypatch.setattr(
        ab, "_decode_to_s16le", lambda path, **kw: base if path.name == "base" else segment
    )
    out, engine = ab._render_reference_master("fixture", "required")
    with wave.open(io.BytesIO(out.read_bytes()), "rb") as reader:
        samples = array("h", reader.readframes(reader.getnframes()))
    assert engine == "reference-master"
    assert samples[12:16].tolist() == [-1000, -1000, 0, 0]
    assert samples[16:18].tolist() == [1000, 1000]


@pytest.fixture
def build_boundary(monkeypatch, tmp_path):
    from copy import deepcopy

    import yaml
    from ocf_tools import semantic_dsp

    source = tmp_path / "script.yaml"
    source.write_text("synthetic source reference")
    manifest = {
        "id": "OCF-AUDIO-9999",
        "title": "Fixture",
        "function_id": "OCF-FND-999",
        "transcript_path": "script.yaml",
        "background_audio": {},
    }
    document = {"function_id": "OCF-FND-999", "source": {"format": "manual"}, "timeline": []}
    calls = []
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    monkeypatch.setattr(ab, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ab, "AUDIO_RENDERED_DIR", tmp_path / "outputs")
    monkeypatch.setattr(ab, "find_audio_manifest", lambda query: manifest)
    monkeypatch.setattr(ab, "load_timed_doc", lambda path: deepcopy(document))
    monkeypatch.setattr(
        ab,
        "load_function_by_id",
        lambda id: NS(canonical_name="Fixture", canonical_command="PLUS-TEST"),
    )
    (tmp_path / "ocf-work").mkdir()

    def write_wav(path, rate=100, channels=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as out:
            out.setframerate(rate)
            out.setnchannels(channels)
            out.setsampwidth(2)
            out.writeframes(b"\0\0" * rate * channels)

    def narration(doc, path, **kw):
        calls.append(("narration", doc, kw))
        write_wav(path)
        return {
            "backend": "fixture",
            "sample_rate": 100,
            "channels": 1,
            "duration": 1,
            "cues": 2,
            "overlap_mode": "reject-fixed-overlap",
            "event_timing": [{"id": "a", "at": 0}],
            "cue_stats": [
                {"id": "a", "at": 0, "duration": 0.2},
                {"id": "b", "at": 0.4, "samples": 20},
            ],
        }

    monkeypatch.setattr(ab, "render_narration", narration)

    def mix(speech, bed, path, **kw):
        calls.append(("mix", kw))
        write_wav(path)

    def stereo(speech, bed, path, **kw):
        calls.append(("stereo", kw))
        write_wav(path, rate=200, channels=2)

    monkeypatch.setattr(ab, "mix", mix)
    monkeypatch.setattr(ab, "_mix_master_ffmpeg", stereo)
    monkeypatch.setattr(ab, "_render_background", lambda *a, **kw: (None, "none"))
    monkeypatch.setattr(ab, "_narration_gain_windows", lambda *a: [(0, 0.5, -6)])
    monkeypatch.setattr(semantic_dsp, "load_profile", lambda ref: {"id": ref})

    def program(*args, **kwargs):
        calls.append(("state", args))
        args[-1].write_bytes(b"fixture bed")
        return {"profile_id": args[-2]["id"]}

    monkeypatch.setattr(semantic_dsp, "render_program", program)

    def encode(source, fmt, path, **kw):
        calls.append(("encode", fmt, kw))
        path.write_bytes(b"derived codec bytes")
        return "fixture"

    monkeypatch.setattr(ab, "_encode", encode)
    # Artwork is a separate dependency at this isolated build boundary. Its real
    # pixels, metadata and codec round trips are covered by audition integration.
    from ocf_tools import audition_exports

    cover = tmp_path / "fixture-cover.png"
    cover.write_bytes(b"isolated cover fixture")
    monkeypatch.setattr(
        audition_exports,
        "select_cover",
        lambda *a, **kw: (cover, {"source": "fixture", "publication_approval": False}, None),
    )
    monkeypatch.setattr(
        audition_exports,
        "copy_cover",
        lambda source, target: target.write_bytes(source.read_bytes()),
    )

    def write(path, text, **kw):
        calls.append(("manifest", path, yaml.safe_load(text.split("\n\n", 1)[1])))

    monkeypatch.setattr(ab, "write_text_atomic", write)
    return NS(
        root=tmp_path,
        source=source,
        manifest=manifest,
        document=document,
        calls=calls,
        write_wav=write_wav,
    )


@pytest.mark.parametrize(
    "failure", ["manifest", "no-transcript", "missing-transcript", "wrong-owner", "invalid-format"]
)
def test_build_preflight_errors_precede_rendering(monkeypatch, build_boundary, failure):
    f = build_boundary
    if failure == "manifest":
        monkeypatch.setattr(ab, "find_audio_manifest", lambda query: None)
    elif failure == "no-transcript":
        f.manifest.pop("transcript_path")
    elif failure == "missing-transcript":
        f.manifest["transcript_path"] = "missing.yaml"
    elif failure == "wrong-owner":
        f.document["function_id"] = "OCF-FND-001"
    with pytest.raises(OCFError):
        ab.build("fixture", formats=["invalid"] if failure == "invalid-format" else None)
    assert not f.calls


@pytest.mark.parametrize(
    "occupied", ["OCF-AUDIO-9999-master.wav", "OCF-AUDIO-9999-master.mp3", "OCF-RENDER-9999.yaml"]
)
def test_build_overwrite_false_protects_all_planned_outputs_before_tts(build_boundary, occupied):
    f = build_boundary
    path = f.root / "outputs" / occupied
    path.parent.mkdir()
    path.write_bytes(b"preserved existing artifact")
    with pytest.raises(OCFError, match="refusing to overwrite"):
        ab.build("fixture", formats=["mp3"], overwrite=False)
    assert path.read_bytes() == b"preserved existing artifact" and not f.calls


@pytest.mark.parametrize("formats", [None, ["mp3"], [], ["wav", "wav", "flac"]])
@pytest.mark.parametrize(
    ("voice", "expected_voice"),
    [("profile", "profile"), ({"profile_id": "OCF-VOICE-9100"}, "OCF-VOICE-9100")],
)
def test_build_master_is_wav_independent_of_selected_derivatives(
    build_boundary, formats, voice, expected_voice
):
    f = build_boundary
    result = ab.build(
        "fixture",
        formats=formats,
        voice=voice,
        locale="fr",
        strict=False,
        recordings="recordings.yaml",
        fit=True,
        flow=True,
        even_counts=True,
    )
    assert result["master"]["file"] == "OCF-AUDIO-9999-master.wav"
    assert result["master"]["format"] == "wav" and result["master"]["sample_rate"] == 100
    assert result["master"]["channels"] == 1 and result["master"]["duration"] == 1
    assert result["artwork"]["file"] == "OCF-AUDIO-9999-cover.png"
    assert (f.root / "outputs" / result["artwork"]["file"]).is_file()
    expected = ["wav"] if formats is None else list(dict.fromkeys(formats))
    assert result["formats"] == expected
    assert [cue["duration"] for cue in result["narration_timing"]["cues"]] == [0.2, 0.2]
    kwargs = f.calls[0][2]
    assert (
        kwargs["locale"] == "fr"
        and kwargs["recordings"] == "recordings.yaml"
        and kwargs["strict"] is False
    )
    assert kwargs["fit"] and kwargs["flow"] and kwargs["even_counts"]
    assert f.calls[-1][0] == "manifest"
    assert f.calls[-1][2]["audio_manifest"]["voice_profile"] == expected_voice


def test_failed_derivative_keeps_usable_master_and_manifest(monkeypatch, build_boundary, capsys):
    def failed(*a, **kw):
        raise OCFError("encoder unavailable; WAV kept")

    monkeypatch.setattr(ab, "_encode", failed)
    result = ab.build("fixture", formats=["mp3"])
    assert result["outputs"] == [] and result["master"]["format"] == "wav"
    assert "encoder unavailable" in capsys.readouterr().out


@pytest.mark.parametrize("profile", ["profile-id", {"id": "direct-profile"}])
def test_semantic_profile_override_uses_measured_ledger_not_text(build_boundary, profile):
    f = build_boundary
    f.manifest["background_audio"] = {"preset": "static"}
    result = ab.build("fixture", dsp_profile=profile)
    assert result["background"]["engine"] == "semantic-state-program"
    assert result["master"]["sample_rate"] == 200 and result["master"]["channels"] == 2
    state = next(call[1] for call in f.calls if call[0] == "state")
    assert state[1] == [{"id": "a", "at": 0}] and state[2] == 1
    assert any(call[0] == "stereo" for call in f.calls)


def test_manifest_conflict_degradation_and_unreadable_master_duration(
    monkeypatch, build_boundary, capsys
):
    f = build_boundary
    f.manifest["background_audio"] = {"preset": "static", "semantic_profile": "profile"}
    with pytest.raises(OCFError, match="not both"):
        ab.build("fixture")
    f.manifest["background_audio"] = {}
    monkeypatch.setattr(
        ab, "_render_background", lambda *a, **kw: (None, "farfield-unavailable (narration only)")
    )
    monkeypatch.setattr(ab, "mix", lambda speech, bed, path, **kw: path.write_bytes(b"not wave"))
    result = ab.build("fixture")
    assert result["master"]["duration"] == 1
    assert "farfield-unavailable" in capsys.readouterr().out


def test_inspection_parses_pcm_and_reports_unsupported_input(build_boundary):
    f = build_boundary
    path = f.root / "inspect.wav"
    f.write_wav(path, rate=100, channels=2)
    info = ab.inspect(path)
    assert info["channels"] == 2 and info["frames"] == 100 and info["duration"] == 1
    other = f.root / "other.flac"
    other.write_bytes(b"bytes only")
    assert ab.inspect(other)["format"] == ".FLAC"
    path.write_bytes(b"invalid WAV")
    with pytest.raises(OCFError, match="not a readable WAV"):
        ab.inspect(path)
    with pytest.raises(OCFError, match="file not found"):
        ab.inspect(f.root / "missing")
    assert ab.default_narration_output("script.yaml").endswith("script-narration.wav")


def test_pcm_reader_writer_mix_and_empty_section_gain_contracts(tmp_path):
    path = tmp_path / "stereo.wav"

    def write(samples, channels=2, width=2):
        with wave.open(str(path), "wb") as out:
            out.setframerate(100)
            out.setnchannels(channels)
            out.setsampwidth(width)
            out.writeframes(
                b"".join(int(v).to_bytes(width, "little", signed=width != 1) for v in samples)
            )

    write([100, 300, -100, -300])
    assert ab._read_mono_pcm(path, 200) == (200, [200, 0, -200, -200])
    write([1, 2], width=1)
    with pytest.raises(OCFError, match="expected 16-bit"):
        ab._read_mono_pcm(path)
    write([1, 2, 3], channels=3)
    with pytest.raises(OCFError, match="channel count"):
        ab._read_mono_pcm(path)
    with pytest.raises(OCFError, match="Refusing to overwrite"):
        ab._write_wav(path, [0], 100, overwrite=False)
    ab._write_wav(path, [1000, 1000], 100, overwrite=True)
    bed = tmp_path / "bed.wav"
    ab._write_wav(bed, [100, 100, 100], 100, overwrite=True)
    mixed = tmp_path / "mixed.wav"
    result = ab.mix(path, bed, mixed, speech_gain_windows=[(1, 0, -20)])
    assert result["duration"] == 0.03
    assert ab._read_mono_pcm(mixed)[1] == [1025, 1025, 25]
    doc = {
        "sections": [
            {"id": "empty", "gain_db": -6, "timeline": []},
            {"id": "missing", "timeline": [{"id": "a"}, {"id": "b", "at": 1}]},
        ]
    }
    assert ab._narration_gain_windows(doc, 2) == []


def test_manifest_lookup_no_match_missing_fields_and_override_tier(monkeypatch, tmp_path):
    monkeypatch.setattr(ab, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        ab, "load_background_manifests", lambda: [{"id": "p", "engine": "farfield", "preset": {}}]
    )
    assert ab._declared_background_file("p") is None
    assert ab._resolve_background_manifest("unknown") is None
    assert ab._sbagenx_sequence_file("unknown") == "unknown"
    monkeypatch.setattr(
        ab, "load_background_manifests", lambda: [{"id": "p", "engine": "sbagenx", "preset": {}}]
    )
    assert ab._sbagenx_sequence_file("p") == "p"
    declared = tmp_path / "declared.yaml"
    declared.write_text("fixture")
    monkeypatch.setattr(
        ab,
        "load_background_manifests",
        lambda: [{"id": "p", "engine": "farfield", "preset": {"file": "declared.yaml"}}],
    )
    monkeypatch.setattr(
        ab.farfield_mod, "resolve_preset", lambda name: declared if name == "declared" else None
    )
    assert ab._farfield_preset_file("p") == str(declared)
    declared.unlink()
    assert ab._declared_background_file("p") is None
    monkeypatch.setattr(
        ab, "_resolve_background_manifest", lambda preset: {"engine": "reference-master"}
    )
    calls = []
    monkeypatch.setattr(
        ab, "_render_reference_master", lambda *a, **kw: calls.append((a, kw)) or (None, "fixture")
    )
    assert ab._render_background("preset", "optional", max_seconds=2) == (None, "fixture")
    assert calls[-1] == (("preset", "optional"), {"max_seconds": 2, "scratch_dir": None})
    monkeypatch.setattr(ab.shutil, "which", lambda name: None)
    with pytest.raises(OCFError):
        ab._encode(tmp_path / "unused", "mp3", tmp_path / "out.mp3")


@pytest.mark.parametrize(
    "case",
    [
        "missing-ffmpeg",
        "empty-base",
        "missing-splice",
        "empty-splice",
        "out-of-range",
        "silent-splice",
        "extreme-gain",
        "all-fade",
    ],
)
def test_reference_edge_cases_use_synthetic_stereo_and_explicit_degradation(
    monkeypatch, tmp_path, case, capsys
):
    monkeypatch.setattr(ab, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ab, "DEFAULT_SAMPLE_RATE", 10)
    (tmp_path / "base").write_bytes(b"synthetic source")
    (tmp_path / "segment").write_bytes(b"synthetic source")
    splice = {
        "source": "missing" if case == "missing-splice" else "segment",
        "slice_start": 0,
        "slice_length": 1,
        "target_start": 5 if case == "out-of-range" else 0,
        "crossfade": 1 if case == "all-fade" else 0,
    }
    monkeypatch.setattr(
        ab,
        "_resolve_background_manifest",
        lambda preset: {"reference": {"source": "base", "splices": [splice]}},
    )
    monkeypatch.setattr(
        ab.shutil, "which", lambda name: None if case == "missing-ffmpeg" else "ffmpeg"
    )

    def decode(path, **kw):
        if path.name == "base":
            return b"" if case == "empty-base" else array("h", [1000] * 20).tobytes()
        if case == "empty-splice":
            return b""
        return array(
            "h",
            [0 if case == "silent-splice" else 1 if case == "extreme-gain" else 1000]
            * (4 if case == "all-fade" else 8),
        ).tobytes()

    monkeypatch.setattr(ab, "_decode_to_s16le", decode)
    path, selected = ab._render_reference_master("fixture", "optional")
    if case in ("missing-ffmpeg", "empty-base", "missing-splice"):
        assert path is None and "unavailable" in selected
    else:
        assert path.is_file() and selected == "reference-master"
        if case == "out-of-range":
            assert "outside the rendered bed" in capsys.readouterr().out


def test_build_without_owner_or_format_collisions_preserves_narration_contract(build_boundary):
    f = build_boundary
    f.document.pop("function_id")
    f.manifest.pop("function_id")
    result = ab.build("fixture", out_root=f.root / "chosen", formats=["wav"], overwrite=False)
    assert result["audio_manifest"]["function_id"] is None


def test_background_sbagenx_dispatch_isolated(monkeypatch):
    monkeypatch.setattr(ab, "_resolve_background_manifest", lambda preset: {"engine": "sbagenx"})
    calls = []
    monkeypatch.setattr(
        ab, "_render_sbagenx", lambda *a, **kw: calls.append((a, kw)) or (None, "fixture")
    )
    assert ab._render_background("preset", "optional") == (None, "fixture")
    assert calls == [(("preset", "optional"), {"scratch_dir": None})]
    monkeypatch.setattr(ab, "_resolve_background_manifest", lambda preset: {"engine": "farfield"})
    monkeypatch.setattr(
        ab, "_render_farfield", lambda *a, **kw: calls.append((a, kw)) or (None, "farfield-fixture")
    )
    assert ab._render_background("preset", "optional") == (None, "farfield-fixture")
    assert calls[-1] == (("preset", "optional"), {"scratch_dir": None})
