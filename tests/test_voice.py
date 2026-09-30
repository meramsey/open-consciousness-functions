"""Tests for the narration voice backend and audio build toolchain.

Backends are optional external binaries; tests never shell out to a real TTS.
A deterministic ``render_cue`` hook stands in for invocation so placement,
overlap, mixing, and manifest logic are exercised without binaries being
present.
"""

from __future__ import annotations

import io
import math
import wave

import pytest
from ocf_tools import audio_build as build_mod
from ocf_tools import voice as voice_mod
from ocf_tools.cli import main as cli_main
from ocf_tools.utils import OCFError, yaml_safe_dump
from ocf_tools.voice import render_narration


def make_wav_bytes(rate: int, samples: list[int], channels: int = 1) -> bytes:
    """Encode int16 PCM samples into WAV bytes."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        frames = bytearray()
        for sample in samples:
            frames.extend(int(max(-32768, min(32767, sample))).to_bytes(2, "little", signed=True))
        writer.writeframes(bytes(frames))
    return buffer.getvalue()


def tone_samples(rate: int, seconds: float, freq: int = 440, amp: int = 8000) -> list[int]:
    count = int(rate * seconds)
    return [int(amp * math.sin(2 * math.pi * freq * i / rate)) for i in range(count)]


def simple_timed_doc(at_values: list[float]) -> dict:
    events = []
    for index, at in enumerate(at_values):
        events.append(
            {
                "id": f"EV-{index + 1:03d}",
                "type": "cue",
                "at": at,
                "text": f"cue number {index + 1}",
            }
        )
    return {
        "schema_version": "1.0",
        "id": "OCF-TEST-DOC",
        "source": {"kind": "file", "path": "test.lrc", "author": "test"},
        "timeline": events,
        "state_profile": None,
        "language": "en",
        "analysis": None,
    }


def fixed_length_cue(length_ms: int, rate: int = 44100) -> callable:
    def render(text: str) -> bytes:
        return make_wav_bytes(rate, [9500] * int(rate * length_ms / 1000))

    return render


FAKE_BACKEND = {
    "name": "espeak-ng",
    "binary": "espeak-ng",
    "language": "en",
    "wpm": 100,
}


@pytest.fixture(autouse=True)
def hide_real_backends(monkeypatch) -> None:
    """Assert tests never find a real TTS binary on this machine."""
    monkeypatch.setattr(voice_mod.shutil, "which", lambda _name: None)


def _read_samples(path) -> tuple[int, list[int]]:
    if isinstance(path, bytes):
        data = path
    else:
        data = path.read_bytes()
    import io as _io

    with wave.open(_io.BytesIO(data), "rb") as reader:
        frames = reader.readframes(reader.getnframes())
        rate = reader.getframerate()
    return rate, [
        int.from_bytes(frames[i * 2 : i * 2 + 2], "little", signed=True)
        for i in range(len(frames) // 2)
    ]


class TestBackendDetection:
    def test_detects_none_when_binaries_missing(self):
        entries = voice_mod.detect_backends()
        assert len(entries) == 3
        assert all(not e["available"] for e in entries)
        assert voice_mod.first_available_backend() is None

    def test_detects_first_available_backend(self, monkeypatch):
        def fake_which(name):
            return "/usr/bin/" + name if name == "espeak-ng" else None

        monkeypatch.setattr(voice_mod.shutil, "which", fake_which)
        by_name = {e["name"]: e for e in voice_mod.detect_backends()}
        assert by_name["espeak-ng"]["available"] is True
        assert by_name["espeak"]["available"] is False
        assert voice_mod.first_available_backend() == "espeak-ng"


class TestModelPathExpansion:
    """Committed voice profiles must stay portable: a machine-specific absolute
    model path must never be required."""

    def test_expands_tilde_and_env(self, monkeypatch):
        monkeypatch.setenv("OCF_PIPER_DIR", "/opt/piper")
        assert voice_mod._expand_model_path("~/.ocf/piper/m.onnx").endswith(
            "/.ocf/piper/m.onnx"
        )
        assert not voice_mod._expand_model_path("~/.ocf/piper/m.onnx").startswith("~")
        assert voice_mod._expand_model_path("$OCF_PIPER_DIR/m.onnx") == "/opt/piper/m.onnx"

    def test_empty_and_null_stay_none(self):
        assert voice_mod._expand_model_path(None) is None
        assert voice_mod._expand_model_path("") is None

    def test_committed_profile_has_no_machine_path(self):
        for profile in voice_mod.load_voice_profiles():
            model = profile.get("piper_model")
            if not model:
                continue
            assert not model.startswith("/home/"), profile["id"]
            assert model.startswith("~") or "$" in model, profile["id"]


class TestRenderNarration:
    def test_raises_when_no_backend(self, tmp_path):
        with pytest.raises(OCFError, match="No text-to-speech backend"):
            render_narration(
                simple_timed_doc([0.0]),
                tmp_path / "out.wav",
                render_cue=fixed_length_cue(100),
            )

    def test_raises_on_untimed_events(self, tmp_path):
        with pytest.raises(OCFError, match="no timestamp"):
            render_narration(
                simple_timed_doc([None]),
                tmp_path / "out.wav",
                backend=FAKE_BACKEND,
                render_cue=fixed_length_cue(100),
            )

    def test_places_cues_at_timestamps(self, tmp_path):
        rate = 44100
        out = tmp_path / "narration.wav"
        metadata = render_narration(
            simple_timed_doc([0.0, 2.0]),
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
        )
        assert metadata["cues"] == 2
        assert metadata["channels"] == 1
        assert metadata["overlap_mode"] == "cut-at-cue-start"

        out_rate, samples = _read_samples(out)
        assert out_rate == rate

        cue_len = int(rate * 0.1)
        expected_frames = int(2.0 * rate) + cue_len + int(1.0 * rate)
        assert len(samples) == expected_frames
        assert max(samples[: int(0.05 * rate)]) == 9500
        assert max(samples[int(0.5 * rate) : int(1.9 * rate)]) == 0
        assert max(samples[int(2.0 * rate) : int(2.05 * rate)]) == 9500


class TestOverlapPolicy:
    def test_cut_at_cue_start(self, tmp_path):
        rate = 44100
        out = tmp_path / "cut.wav"
        metadata = render_narration(
            simple_timed_doc([0.0, 0.05]),
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
        )
        assert metadata["cue_stats"][0]["cut_previous"] is False
        assert metadata["cue_stats"][1]["cut_previous"] is True

        _, samples = _read_samples(out)
        start_two = int(0.05 * rate)
        cue_len = int(rate * 0.1)
        assert samples[start_two] == 9500
        assert samples[start_two + cue_len - 1] == 9500
        assert max(samples[:start_two]) == 9500


class TestAdaptiveFit:
    def test_fit_stretches_short_flow_slot(self, tmp_path):
        rate = 44100
        out = tmp_path / "fit.wav"
        metadata = render_narration(
            simple_timed_doc([0.0, 0.25]),
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
            fit=True,
        )
        assert metadata["timing_mode"] == "fit-soft"
        _, samples = _read_samples(out)
        # 100 ms tone stretched toward its 250 ms slot (FIT_MIN_AIR=120 ms
        # trailing air): speech now spans ~130 ms instead of 100 ms, then air.
        assert max(samples[int(0.115 * rate) : int(0.125 * rate)]) > 9000
        assert max(samples[int(0.14 * rate) : int(0.25 * rate)]) == 0

    def test_fit_reports_default_mode_when_off(self, tmp_path):
        rate = 44100
        out = tmp_path / "plain.wav"
        metadata = render_narration(
            simple_timed_doc([0.0, 0.25]),
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
        )
        assert metadata["timing_mode"] == "explicit-at-timestamps"

    def test_fit_preserves_deliberate_long_slot(self, tmp_path):
        rate = 44100
        out = tmp_path / "long.wav"
        render_narration(
            simple_timed_doc([0.0, 5.0]),
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
            fit=True,
        )
        _, samples = _read_samples(out)
        # A 5 s slot far exceeds FIT_MAX_SCALE: the 100 ms cue must not be
        # stretched at all, so its speech ends right after ~100 ms.
        assert max(samples[int(0.21 * rate) : int(1.0 * rate)]) == 0


class TestFlowMerge:
    def _doc_with_text(self, items: list[tuple[float, str]]) -> dict:
        events = []
        for index, (at, text) in enumerate(items):
            events.append({"id": f"C-{index + 1:03d}", "type": "cue", "at": at, "text": text})
        return {
            "schema_version": "1.0",
            "id": "OCF-TEST-FLOW",
            "source": {"kind": "file", "path": "flow.lrc", "author": "test"},
            "timeline": events,
            "state_profile": None,
            "language": "en",
            "analysis": None,
        }

    def test_flow_merges_sentence_fragments(self, tmp_path):
        rate = 44100
        out = tmp_path / "flow.wav"
        doc = self._doc_with_text(
            [
                (0.0, "This is"),
                (0.5, "your H plus exercise"),
                (1.0, "to focus your attention."),
            ]
        )
        metadata = render_narration(
            doc,
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
            flow=True,
        )
        assert metadata["timing_mode"] == "natural"
        assert metadata["cues"] == 1  # three fragments -> one utterance
        assert metadata["cue_stats"][0]["id"] == "C-001+C-002+C-003"

    def test_flow_stops_at_sentence_final_line(self, tmp_path):
        rate = 44100
        out = tmp_path / "flow-stop.wav"
        doc = self._doc_with_text(
            [
                (0.0, "First complete sentence."),
                (1.0, "Second sentence"),
                (2.0, "still continuing"),
            ]
        )
        metadata = render_narration(
            doc,
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
            flow=True,
        )
        # First line is sentence-final; lines 2-3 merge.
        assert metadata["cues"] == 2
        assert metadata["cue_stats"][0]["id"] == "C-001"
        assert metadata["cue_stats"][1]["id"] == "C-002+C-003"

    def test_flow_keeps_count_markers_separate(self, tmp_path):
        rate = 44100
        out = tmp_path / "flow-count.wav"
        doc = self._doc_with_text(
            [(0.0, "Move to the 10th state"), (1.0, "as I guide you."), (2.0, "2"), (3.0, "3")]
        )
        metadata = render_narration(
            doc,
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
            flow=True,
        )
        # "Move to the 10th state" is a fragment; "as I guide you." ends the
        # sentence; "2"/"3" are countdown markers kept as their own cues.
        assert [s["id"] for s in metadata["cue_stats"]] == ["C-001+C-002", "C-003", "C-004"]

    def test_flow_disabled_keeps_every_line(self, tmp_path):
        rate = 44100
        out = tmp_path / "no-flow.wav"
        doc = self._doc_with_text([(0.0, "This is"), (1.0, "your H plus exercise.")])
        metadata = render_narration(
            doc,
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
        )
        assert metadata["timing_mode"] == "explicit-at-timestamps"
        assert metadata["cues"] == 2


class TestEvenCounts:
    def _doc_with_text(self, items: list[tuple[float, str]]) -> dict:
        events = []
        for index, (at, text) in enumerate(items):
            events.append({"id": f"C-{index + 1:03d}", "type": "cue", "at": at, "text": text})
        return {
            "schema_version": "1.0",
            "id": "OCF-TEST-COUNTS",
            "source": {"kind": "file", "path": "counts.lrc", "author": "test"},
            "timeline": events,
            "state_profile": None,
            "language": "en",
            "analysis": None,
        }

    def _render(self, doc, out, *, rate=44100, **kwargs):
        return render_narration(
            doc,
            out,
            backend=FAKE_BACKEND,
            sample_rate=rate,
            render_cue=fixed_length_cue(100, rate),
            **kwargs,
        )

    def test_even_counts_smooths_jittered_digits(self, tmp_path):
        rate = 44100
        out = tmp_path / "counts.wav"
        doc = self._doc_with_text(
            [
                (0.0, "2"),
                (0.1, "3"),
                (2.0, "4"),
                (5.0, "Relax calmly and serenely."),
            ]
        )
        metadata = self._render(doc, out, rate=rate, even_counts=True)
        assert metadata["timing_mode"] == "explicit-at-timestamps+even-counts"
        # Digits 2..4 form one pure-count run (0.0 -> 2.0): gap becomes 1.0 s.
        ats = [s["at"] for s in metadata["cue_stats"]]
        assert ats[:3] == [0.0, 1.0, 2.0]
        assert ats[3] == 5.0  # phrase line keeps its authored time
        assert metadata["even_counts"]["runs"][0]["gap"] == 1.0
        assert metadata["even_counts"]["runs"][0]["values"] == [2, 3, 4]

    def test_even_counts_splits_multi_number_cues(self, tmp_path):
        rate = 44100
        out = tmp_path / "split.wav"
        doc = self._doc_with_text(
            [
                (10.0, "Twelve. Thirteen."),
                (30.0, "Fourteen."),
            ]
        )
        metadata = self._render(doc, out, rate=rate, even_counts=True)
        # Three spoken numbers across 10.0..30.0 -> counts land at 10/20/30.
        assert [s["id"] for s in metadata["cue_stats"]] == ["C-001#1", "C-001#2", "C-002"]
        assert [s["at"] for s in metadata["cue_stats"]] == [10.0, 20.0, 30.0]
        assert metadata["cue_stats"][0]["text"] == "Twelve."

    def test_even_counts_stops_at_phrase_line(self, tmp_path):
        rate = 44100
        out = tmp_path / "stop.wav"
        doc = self._doc_with_text(
            [
                (0.0, "I'm going to count now. Ten. Eleven."),
                (5.0, "Twelve."),
                (6.0, "Thirteen."),
                (30.0, "Rest deeply."),
            ]
        )
        metadata = self._render(doc, out, rate=rate, even_counts=True)
        # Only the pure-count run (Twelve/Thirteen) is re-timed; the phrase
        # boundary cue keeps its authored timestamp and wording.
        assert metadata["cue_stats"][0]["id"] == "C-001"
        assert metadata["cue_stats"][0]["at"] == 0.0
        ats = [s["at"] for s in metadata["cue_stats"]]
        assert ats[1:3] == [5.0, 6.0]

    def test_even_counts_noop_when_disabled(self, tmp_path):
        rate = 44100
        out = tmp_path / "off.wav"
        doc = self._doc_with_text([(0.0, "2"), (0.1, "3"), (2.0, "4")])
        metadata = self._render(doc, out, rate=rate)
        assert metadata["timing_mode"] == "explicit-at-timestamps"
        assert metadata["even_counts"] is None
        assert [s["at"] for s in metadata["cue_stats"]] == [0.0, 0.1, 2.0]

    def test_even_counts_composes_with_flow(self, tmp_path):
        rate = 44100
        out = tmp_path / "flow-counts.wav"
        doc = self._doc_with_text(
            [
                (0.0, "Move now to the"),
                (0.5, "10th state"),
                (1.0, "as I guide you."),
                (4.0, "2"),
                (5.0, "3"),
            ]
        )
        metadata = self._render(doc, out, rate=rate, flow=True, even_counts=True)
        assert metadata["timing_mode"] == "natural+even-counts"
        # Fragments merge; the two countdown markers stay separate and are
        # re-timed evenly across 4.0..5.0 (no intervening counts).
        assert [s["id"] for s in metadata["cue_stats"]] == [
            "C-001+C-002+C-003",
            "C-004",
            "C-005",
        ]
        assert metadata["cue_stats"][1]["at"] == 4.0
        assert metadata["cue_stats"][2]["at"] == 5.0


class TestAudioBuild:
    def test_mix_extends_to_longest_track(self, tmp_path):
        rate = 44100
        speech = tmp_path / "speech.wav"
        background = tmp_path / "bg.wav"
        out = tmp_path / "mix.wav"
        speech.write_bytes(make_wav_bytes(rate, tone_samples(rate, 1.0)))
        background.write_bytes(make_wav_bytes(rate, tone_samples(rate, 3.0)))
        info = build_mod.mix(speech, background, out, background_gain=0.5)
        assert info["duration"] == pytest.approx(3.0, abs=0.01)
        with wave.open(str(out), "rb") as reader:
            assert reader.getnframes() == int(3.0 * rate)

    def test_mix_without_background(self, tmp_path):
        rate = 44100
        speech = tmp_path / "speech.wav"
        out = tmp_path / "mix.wav"
        speech.write_bytes(make_wav_bytes(rate, tone_samples(rate, 2.0)))
        info = build_mod.mix(speech, None, out, background_gain=0.5)
        assert info["duration"] == pytest.approx(2.0, abs=0.01)

    def test_build_end_to_end(self, tmp_path):
        rate = 44100
        script = tmp_path / "script.yaml"
        script.write_bytes(yaml_safe_dump(simple_timed_doc([0.0, 1.5])).encode("utf-8"))
        manifest = tmp_path / "audio-manifest.yaml"
        manifest.write_bytes(
            yaml_safe_dump(
                {
                    "schema_version": "1.0",
                    "id": "OCF-AUDIO-9999",
                    "function_id": "OCF-FND-002",
                    "title": "Test build",
                    "version": "0.1.0",
                    "contributor": "tester",
                    "narrator": None,
                    "language": "en",
                    "license": "pending-source-review",
                    "training_type": "experimental",
                    "duration_minutes": 0.2,
                    "induction": "n/a",
                    "command_rehearsal": "n/a",
                    "legacy_bridge": None,
                    "mode_rehearsal": None,
                    "release_rehearsal": None,
                    "safety_intro": None,
                    "transcript_path": str(script),
                    "background_audio": {"strategy": "none", "preset": None},
                    "technical": {"sample_rate": rate, "channels": 1, "format": "wav"},
                    "testing_notes": "test-only",
                    "review_state": "experimental",
                }
            ).encode("utf-8")
        )
        out_root = tmp_path / "rendered"
        result = build_mod.build(
            str(manifest),
            out_root=out_root,
            fmt="wav",
            voice=FAKE_BACKEND,
            render_cue=fixed_length_cue(80, rate),
        )
        master = out_root / "OCF-AUDIO-9999-master.wav"
        assert master.is_file()
        assert result["master"]["checksum_sha256"]
        render_manifest = out_root / "OCF-RENDER-9999.yaml"
        assert render_manifest.is_file()
        assert "citation-only" in render_manifest.read_text()
        info = build_mod.inspect(master)
        assert info["format"] == "WAV (PCM)"
        assert info["sample_rate"] == rate
        assert info["duration"] == pytest.approx(result["master"]["duration"], abs=0.05)

    def test_build_requires_transcript(self, tmp_path):
        manifest = tmp_path / "audio-manifest.yaml"
        manifest.write_bytes(
            yaml_safe_dump(
                {
                    "schema_version": "1.0",
                    "id": "OCF-AUDIO-9998",
                    "function_id": "OCF-FND-002",
                    "title": "No transcript",
                    "version": "0.1.0",
                    "contributor": "tester",
                    "narrator": None,
                    "language": "en",
                    "license": "pending-source-review",
                    "training_type": "experimental",
                    "duration_minutes": None,
                    "induction": "n/a",
                    "command_rehearsal": "n/a",
                    "legacy_bridge": None,
                    "mode_rehearsal": None,
                    "release_rehearsal": None,
                    "safety_intro": None,
                    "transcript_path": None,
                    "background_audio": {"strategy": "none", "preset": None},
                    "technical": {"sample_rate": None, "channels": None, "format": "wav"},
                    "testing_notes": "test-only",
                    "review_state": "experimental",
                }
            ).encode("utf-8")
        )
        with pytest.raises(OCFError, match="transcript_path"):
            build_mod.build(str(manifest), out_root=tmp_path / "out", voice=FAKE_BACKEND)

    def test_build_multi_format_and_tags(self, tmp_path, monkeypatch):
        rate = 44100
        script = tmp_path / "script.yaml"
        script.write_bytes(yaml_safe_dump(simple_timed_doc([0.0])).encode("utf-8"))
        manifest = tmp_path / "audio-manifest.yaml"
        manifest.write_bytes(
            yaml_safe_dump(
                {
                    "schema_version": "1.0",
                    "id": "OCF-AUDIO-9997",
                    "function_id": "OCF-FND-002",
                    "title": "Multi-format build",
                    "version": "0.5.1",
                    "contributor": "tester",
                    "narrator": None,
                    "language": "en",
                    "license": "pending-source-review",
                    "training_type": "experimental",
                    "duration_minutes": 0.2,
                    "induction": "n/a",
                    "command_rehearsal": "n/a",
                    "legacy_bridge": None,
                    "mode_rehearsal": None,
                    "release_rehearsal": None,
                    "safety_intro": None,
                    "transcript_path": str(script),
                    "background_audio": {"strategy": "none", "preset": None},
                    "technical": {"sample_rate": rate, "channels": 1, "format": "wav"},
                    "testing_notes": "test-only",
                    "review_state": "experimental",
                }
            ).encode("utf-8")
        )

        calls: list[dict] = []

        def fake_encode(intermediate, fmt, out_path, tags=None):
            out_path.write_bytes(intermediate.read_bytes())
            calls.append({"fmt": fmt, "tags": tags})
            return "ffmpeg"

        monkeypatch.setattr(build_mod, "_encode", fake_encode)
        out_root = tmp_path / "rendered"
        result = build_mod.build(
            str(manifest),
            out_root=out_root,
            formats=("wav", "flac", "mp3"),
            tag_overrides={"artist": "Override Artist"},
            voice=FAKE_BACKEND,
            render_cue=fixed_length_cue(80, rate),
        )
        assert (out_root / "OCF-AUDIO-9997-master.wav").is_file()
        assert (out_root / "OCF-AUDIO-9997-master.flac").is_file()
        assert (out_root / "OCF-AUDIO-9997-master.mp3").is_file()
        assert result["formats"] == ["wav", "flac", "mp3"]
        assert [o["format"] for o in result["outputs"]] == ["wav", "flac", "mp3"]
        flac_tagset = calls[0]["tags"]
        assert flac_tagset["title"] == "Multi-format build"
        assert flac_tagset["artist"] == "Override Artist"
        assert flac_tagset["album"] == "Attention"
        assert flac_tagset["OCF_FUNCTION"] == "Attention"
        assert "OCF_AUDIO_ID" in flac_tagset
        assert "OCF_AUDIO_VERSION" in flac_tagset
        assert "citation-only" in flac_tagset["comment"]
        assert calls[1]["tags"] == flac_tagset
        body = (out_root / "OCF-RENDER-9997.yaml").read_text()
        assert "formats:" in body
        assert "outputs:" in body
        assert "Override Artist" in body

    def test_encode_embeds_metadata_flags(self, tmp_path, monkeypatch):
        rate = 44100
        wav = tmp_path / "master.wav"
        wav.write_bytes(make_wav_bytes(rate, tone_samples(rate, 0.2)))
        out_mp3 = tmp_path / "master.mp3"
        cmd: list[str] = []

        def fake_run(command, *args, **kwargs):
            cmd.extend(command)
            return type("R", (), {"returncode": 0, "stderr": ""})()

        monkeypatch.setattr(build_mod.shutil, "which", lambda name: "/usr/bin/ffmpeg")
        monkeypatch.setattr(build_mod.subprocess, "run", fake_run)
        encoder = build_mod._encode(
            wav,
            "mp3",
            out_mp3,
            tags={"title": "Attention", "OCF_AUDIO_ID": "OCF-AUDIO-0001"},
        )
        assert encoder == "ffmpeg"
        assert "-metadata" in cmd
        assert "title=Attention" in cmd
        assert "OCF_AUDIO_ID=OCF-AUDIO-0001" in cmd
        assert "-id3v2_version" in cmd and "3" in cmd
        assert "-write_id3v1" in cmd and "1" in cmd

    def test_resolve_tags_derives_function_metadata(self, tmp_path, monkeypatch):
        class FakeRecord:
            canonical_name = "Attention"
            canonical_command = "PLUS-FOCUS"

        monkeypatch.setattr(build_mod, "load_function_by_id", lambda fid: FakeRecord())
        doc = {
            "schema_version": "1.0",
            "title": "t",
            "sections": [],
            "template": {"id": "OCF-TPL-SESSION-LEARN-001", "version": "1.0", "origin": "original-ocf"},
        }
        tags = build_mod._resolve_tags(
            {
                "id": "OCF-AUDIO-0001",
                "function_id": "OCF-FND-002",
                "title": "Attention",
                "version": "0.5.1",
                "narrator": "piper",
            },
            doc,
            {"timing_mode": "natural+even-counts"},
        )
        assert tags["album"] == "Attention"
        assert tags["track"] == "0001"
        assert tags["OCF_COMMAND"] == "PLUS-FOCUS"
        assert tags["OCF_FUNCTION"] == "Attention"
        assert tags["OCF_SESSION_TEMPLATE"] == "OCF-TPL-SESSION-LEARN-001"
        assert tags["OCF_NARRATOR"] == "piper"


class TestCli:
    def test_voice_list_backends(self, capsys):
        assert cli_main(["voice", "list-backends"]) == 0
        assert "espeak" in capsys.readouterr().out

    def test_voice_doctor_missing_backend(self, capsys):
        assert cli_main(["voice", "doctor"]) == 1
        assert "not on PATH" in capsys.readouterr().out

    def test_voice_render_missing_backend_fails(self, tmp_path):
        script = tmp_path / "script.yaml"
        script.write_bytes(yaml_safe_dump(simple_timed_doc([0.0])).encode("utf-8"))
        rc = cli_main(["voice", "render", str(script), "--output", str(tmp_path / "out.wav")])
        assert rc == 1

    def test_audio_inspect_cli(self, tmp_path):
        rate = 44100
        path = tmp_path / "tone.wav"
        path.write_bytes(make_wav_bytes(rate, tone_samples(rate, 0.1)))
        assert cli_main(["audio", "inspect", str(path)]) == 0
