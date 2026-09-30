"""Tests for the audio build toolchain: reference-master bed rendering and
the background engine-resolution used by `ocf audio build`.

The reference-master engine composites a bed from an operator-supplied
reference file plus spliced excerpts (access-channel windows) without any
synthesis backend. These tests are hermetic: PCM decode is stubbed so no
ffmpeg or audio fixtures are required.
"""

from __future__ import annotations

import wave
from array import array

import pytest

from ocf_tools import audio_build as ab
from ocf_tools.utils import OCFError


def _constant_stereo_bytes(seconds: float, level: int, rate: int) -> bytes:
    """Raw s16le interleaved stereo: ``level`` on every frame."""
    raw = array("h")
    for _ in range(int(seconds * rate)):
        raw.extend([level, level])
    return raw.tobytes()


def _left_channel(raw: bytes, start_s: float, span_s: float, rate: int) -> array:
    lo = int(start_s * rate) * 4
    hi = int((start_s + span_s) * rate) * 4
    chunks = array("h")
    chunks.frombytes(raw[lo:hi])
    return chunks[::2]


def _make_sources(tmp_path):
    """Create throwaway source files (decode is stubbed; only existence matters)."""
    ref = tmp_path / "ref.flac"
    seg = tmp_path / "seg.flac"
    ref.touch()
    seg.touch()
    return str(ref), str(seg)


class TestReferenceMasterRender:
    def _stub_resolver(self, monkeypatch, manifest):
        monkeypatch.setattr(ab, "_resolve_background_manifest", lambda preset: manifest)
        monkeypatch.setattr(ab.shutil, "which", lambda name: "ffmpeg" if name == "ffmpeg" else None)

    def test_composites_spliced_window_gain_matched(self, monkeypatch, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        ref_path, seg_path = _make_sources(tmp_path)
        manifest = {
            "id": "OCF-BG-T",
            "name": "Test reference bed",
            "engine": "reference-master",
            "reference": {
                "source": ref_path,
                "splices": [
                    {
                        "source": seg_path,
                        "slice_start": 0,
                        "slice_length": 1,
                        "target_start": 1,
                        "crossfade": 0.25,
                        "note": "access window",
                    }
                ],
            },
        }
        self._stub_resolver(monkeypatch, manifest)

        def fake_decode(path, *, start=None, seconds=None, sample_rate=None):
            length = seconds if seconds is not None else 3.0
            level = 8000 if str(path) == ref_path else 4000
            return _constant_stereo_bytes(length, level, rate)

        monkeypatch.setattr(ab, "_decode_to_s16le", fake_decode)

        out, note = ab._render_reference_master("OCF-BG-T", "optional", max_seconds=3.0)
        assert note == "reference-master"
        with wave.open(str(out)) as reader:
            assert reader.getnchannels() == 2
            assert reader.getframerate() == rate
            raw = reader.readframes(reader.getnframes())

        # Outside the splice the reference level (8000) is untouched.
        outside = _left_channel(raw, 0.30, 0.40, rate)
        assert all(abs(v) == 8000 for v in outside)
        # The splice is gain-matched (~2x, 4000 -> 8000) so its interior also
        # reads ~8000; the window runs 1.0..2.0 s with 0.25 s crossfades.
        spliced = _left_channel(raw, 1.30, 0.40, rate)
        assert all(7000 <= abs(v) <= 9000 for v in spliced)

    def test_second_channel_matches_first(self, monkeypatch, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        ref_path, _ = _make_sources(tmp_path)
        manifest = {
            "id": "OCF-BG-T",
            "name": "Test reference bed",
            "engine": "reference-master",
            "reference": {"source": ref_path, "splices": []},
        }
        self._stub_resolver(monkeypatch, manifest)
        monkeypatch.setattr(
            ab,
            "_decode_to_s16le",
            lambda path, start=None, seconds=None: _constant_stereo_bytes(2.0, 5000, rate),
        )
        out, note = ab._render_reference_master("OCF-BG-T", "optional", max_seconds=2.0)
        assert note == "reference-master"
        with wave.open(str(out)) as reader:
            raw = reader.readframes(reader.getnframes())
        left = _left_channel(raw, 0.5, 0.5, rate)
        right = array("h")
        lo = int(0.5 * rate) * 4
        hi = int(1.0 * rate) * 4
        right.frombytes(raw[lo:hi])
        right = right[1::2]
        assert left.tolist() == right.tolist()

    def test_missing_reference_degrades_gracefully(self, monkeypatch):
        manifest = {
            "id": "OCF-BG-T",
            "name": "Test reference bed",
            "engine": "reference-master",
            "reference": {"source": "does-not-exist.flac", "splices": []},
        }
        self._stub_resolver(monkeypatch, manifest)
        out, note = ab._render_reference_master("OCF-BG-T", "optional")
        assert out is None
        assert note == "reference-master-unavailable (narration only)"

    def test_missing_reference_required_raises(self, monkeypatch):
        manifest = {
            "id": "OCF-BG-T",
            "name": "Test reference bed",
            "engine": "reference-master",
            "reference": {"source": "does-not-exist.flac", "splices": []},
        }
        self._stub_resolver(monkeypatch, manifest)
        with pytest.raises(OCFError):
            ab._render_reference_master("OCF-BG-T", "required")

    def test_manifest_without_reference_block_degrades(self, monkeypatch):
        manifest = {"id": "OCF-BG-T", "name": "Test reference bed", "engine": "reference-master"}
        monkeypatch.setattr(ab, "_resolve_background_manifest", lambda preset: manifest)
        monkeypatch.setattr(ab.shutil, "which", lambda name: "ffmpeg" if name == "ffmpeg" else None)
        out, note = ab._render_reference_master("OCF-BG-T", "optional")
        assert out is None
        assert note == "reference-master-unavailable (narration only)"

    def test_truncates_bed_to_narration_length(self, monkeypatch, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        ref_path, _ = _make_sources(tmp_path)
        manifest = {
            "id": "OCF-BG-T",
            "name": "Test reference bed",
            "engine": "reference-master",
            "reference": {"source": ref_path, "splices": []},
        }
        self._stub_resolver(monkeypatch, manifest)
        monkeypatch.setattr(
            ab,
            "_decode_to_s16le",
            lambda path, start=None, seconds=None: _constant_stereo_bytes(seconds or 60.0, 5000, rate),
        )
        out, note = ab._render_reference_master("OCF-BG-T", "optional", max_seconds=2.0)
        assert note == "reference-master"
        with wave.open(str(out)) as reader:
            assert round(reader.getnframes() / reader.getframerate(), 3) == 2.0


class TestBackgroundEngineResolution:
    def test_manifest_engine_wins_over_auto_farfield(self, monkeypatch):
        manifest = {"id": "OCF-BG-X", "name": "x", "engine": "sbagenx"}
        monkeypatch.setattr(ab, "_resolve_background_manifest", lambda preset: manifest)
        monkeypatch.setattr(ab, "_render_sbagenx", lambda preset, strategy: ("bed.wav", "sbagenx"))
        out, note = ab._render_background("OCF-BG-X", "optional", engine="farfield")
        assert (out, note) == ("bed.wav", "sbagenx")

    def test_explicit_engine_requested_overrides_manifest(self, monkeypatch):
        manifest = {"id": "OCF-BG-X", "name": "x", "engine": "reference-master"}
        monkeypatch.setattr(ab, "_resolve_background_manifest", lambda preset: manifest)
        monkeypatch.setattr(ab, "_render_sbagenx", lambda preset, strategy: ("sb.bed", "sbagenx"))
        # The ``farfield`` default acts as "auto"; an explicit non-default
        # engine request overrides the manifest's engine.
        out, note = ab._render_background("OCF-BG-X", "optional", engine="sbagenx")
        assert (out, note) == ("sb.bed", "sbagenx")

    def test_reference_master_dispatch(self, monkeypatch, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        ref_path, _ = _make_sources(tmp_path)
        manifest = {
            "id": "OCF-BG-X",
            "name": "x",
            "engine": "reference-master",
            "reference": {"source": ref_path, "splices": []},
        }
        monkeypatch.setattr(ab, "_resolve_background_manifest", lambda preset: manifest)
        monkeypatch.setattr(ab.shutil, "which", lambda name: "ffmpeg")
        monkeypatch.setattr(
            ab,
            "_decode_to_s16le",
            lambda path, start=None, seconds=None: _constant_stereo_bytes(1.0, 5000, rate),
        )
        out, note = ab._render_background("OCF-BG-X", "optional", engine="farfield")
        assert note == "reference-master"
        assert out is not None

    def test_no_preset_is_none(self):
        out, note = ab._render_background(None, "optional")
        assert (out, note) == (None, "none")


class TestNarrationGainWindows:
    def test_db_gain_factor(self):
        assert ab._db_gain_factor(0.0) == pytest.approx(1.0)
        assert ab._db_gain_factor(-24.0) == pytest.approx(0.0631, abs=1e-4)
        assert ab._db_gain_factor(-6.0) == pytest.approx(0.5012, abs=1e-4)

    def test_window_spans_section_until_next_section(self):
        doc = {
            "sections": [
                {"id": "opening", "timeline": [{"at": "0:00.00", "text": "hello"}]},
                {
                    "id": "sleep20",
                    "gain_db": -24.0,
                    "timeline": [
                        {"at": "19:16.40", "text": "resting"},
                        {"at": "21:38.48", "text": "deeper"},
                    ],
                },
                {"id": "return", "timeline": [{"at": "26:22.64", "text": "return"}]},
            ]
        }
        assert ab._narration_gain_windows(doc, 1800.0) == [(1156.4, 1582.64, -24.0)]

    def test_window_falls_back_to_duration_for_last_section(self):
        doc = {
            "sections": [
                {
                    "id": "closing",
                    "gain_db": -12.0,
                    "timeline": [{"at": 1700.0, "text": "bye"}],
                }
            ]
        }
        assert ab._narration_gain_windows(doc, 1763.6) == [(1700.0, 1763.6, -12.0)]

    def test_no_gain_db_means_no_windows(self):
        doc = {"sections": [{"id": "opening", "timeline": [{"at": 0.0, "text": "hi"}]}]}
        assert ab._narration_gain_windows(doc, 60.0) == []

    def test_mix_attenuates_only_the_window(self, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        speech = tmp_path / "speech.wav"
        with wave.open(str(speech), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(rate)
            for _ in range(rate * 4):  # constant tone for 4 s
                writer.writeframes(array("h", [10000]).tobytes())
        out = tmp_path / "mixed.wav"
        ab.mix(speech, None, out, speech_gain_windows=[(1.0, 2.0, -24.0)])
        with wave.open(str(out)) as reader:
            raw = reader.readframes(reader.getnframes())
        samples = array("h")
        samples.frombytes(raw)
        loud = samples[0:1000]
        quiet = samples[rate: rate + 1000]
        assert abs(loud[0]) == pytest.approx(10000, abs=2)
        assert abs(quiet[0]) == pytest.approx(631, abs=5)

    def test_ffmpeg_filter_graph_chains_are_terminated(self, monkeypatch, tmp_path):
        """Regression: the narration chain label needs ``;`` before the next
        input pad, and the label must not be comma-joined into the chain."""
        captured: dict[str, list[str]] = {}

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, *args, **kwargs):
            captured["cmd"] = cmd
            return _Result()

        monkeypatch.setattr(ab.shutil, "which", lambda name: "ffmpeg")
        monkeypatch.setattr(ab.subprocess, "run", fake_run)
        ab._mix_master_ffmpeg(
            tmp_path / "speech.wav",
            tmp_path / "bed.wav",
            tmp_path / "out.wav",
            speech_gain_windows=[(1156.4, 1582.64, -24.0)],
        )
        graph = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
        assert "volume=0.063096:enable='between(t,1156.400,1582.640)'" in graph
        assert ",[n]" not in graph
        assert "[n];" in graph
        assert graph.count("[n]") == 2

    def test_original_doc_detection(self):
        from_template = {
            "template": {"id": "OCF-TPL-SESSION-ATTENTION-001", "origin": "original-ocf"}
        }
        manual = {"source": {"format": "manual", "filename": None}}
        imported = {
            "source": {
                "format": "lrc",
                "filename": "Attention.lrc",
                "snapshot": "[00:00.00]verbatim imported line",
            },
            "template": {"id": "OCF-TPL-SESSION-LEARN-001", "origin": "ocf-shell"},
        }
        assert ab._doc_is_original(from_template) is True
        assert ab._doc_is_original(manual) is True
        assert ab._doc_is_original(imported) is False
        # Conservative default: no provenance means citation-only.
        assert ab._doc_is_original({}) is False
        assert ab._doc_is_original({"source": {"format": "lrc", "filename": "a.lrc"}}) is False