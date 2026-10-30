"""Optional mix contracts: mocked unit boundaries and actual stereo FFmpeg DSP."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import wave
from array import array
from types import SimpleNamespace

import pytest
from ocf_tools import audio_build as ab
from ocf_tools import mix_profiles as mp
from ocf_tools.utils import OCFError, sha256_of_file, yaml_safe_load


def _wav(path, samples, rate=ab.DEFAULT_SAMPLE_RATE, channels=2):
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(array("h", samples).tobytes())


def _read(path):
    with wave.open(str(path), "rb") as reader:
        assert reader.getnchannels() == 2
        assert reader.getframerate() == ab.DEFAULT_SAMPLE_RATE
        assert reader.getsampwidth() == 2
        samples = array("h")
        samples.frombytes(reader.readframes(reader.getnframes()))
    return samples


@pytest.mark.unit
class TestProfileContracts:
    def test_defaults_are_conservative_and_detached(self):
        original = {"limiter": {"ceiling": 0.8}}
        profile = mp.load_mix_profile(original)
        assert profile["limiter"] == {
            "enabled": True,
            "ceiling": 0.8,
            "attack_ms": 5,
            "release_ms": 50,
        }
        assert profile["background_ducking"]["enabled"] is False
        assert profile["background_gain_windows"] == []
        assert profile["output_headroom_db"] == profile["fade_in_s"] == profile["fade_out_s"] == 0
        assert profile["measure_loudness"] is False
        profile["limiter"]["ceiling"] = 0.5
        assert original == {"limiter": {"ceiling": 0.8}}
        assert mp.load_mix_profile({})["limiter"]["ceiling"] == 0.97

    @pytest.mark.parametrize(
        "suffix,text",
        [
            (".json", '{"output_headroom_db": 3}'),
            (".yaml", "output_headroom_db: 3\nlimiter:\n  enabled: false\n"),
        ],
    )
    def test_profile_file(self, tmp_path, suffix, text):
        path = tmp_path / ("mix" + suffix)
        path.write_text(text, encoding="utf-8")
        assert mp.load_mix_profile(path)["output_headroom_db"] == 3

    @pytest.mark.parametrize(
        "profile",
        [
            None,
            [],
            True,
            {"unexpected": 1},
            {"schema_version": "2.0"},
            {"background_ducking": {"crossfeed": 0.2}},
            {"limiter": {"level": True}},
            {"limiter": {"enabled": "false"}},
            {"measure_loudness": 1},
            {"limiter": {"ceiling": 1.01}},
            {"limiter": {"ceiling": 0.06}},
            {"limiter": {"attack_ms": 0}},
            {"limiter": {"release_ms": 8001}},
            {"background_ducking": {"threshold_dbfs": -61}},
            {"background_ducking": {"ratio": 21}},
            {"background_ducking": {"attack_ms": 2001}},
            {"background_ducking": {"release_ms": 9001}},
            {"background_ducking": {"knee": 0.9}},
            {
                "background_gain_windows": [
                    {
                        "event_id": "x",
                        "start_s": 1,
                        "end_s": 2,
                        "gain_db": 1,
                        "attack_s": 0,
                        "release_s": 0,
                    }
                ]
            },
            {
                "background_gain_windows": [
                    {
                        "event_id": "x",
                        "start_s": 1,
                        "end_s": 2,
                        "gain_db": -10,
                        "attack_s": -0.1,
                        "release_s": 0,
                    }
                ]
            },
            {"output_headroom_db": -1},
            {"output_headroom_db": 61},
            {"fade_in_s": 31},
            {"fade_out_s": -1},
            {"limiter": {"ceiling": float("nan")}},
            {"background_ducking": {"attack_ms": float("inf")}},
            {"output_headroom_db": float("-inf")},
            {"fade_in_s": True},
        ],
    )
    def test_invalid_profile_rejected_before_build_outputs(self, monkeypatch, tmp_path, profile):
        # None is the build opt-out, but never an explicit profile object.
        with pytest.raises(OCFError):
            mp.load_mix_profile(profile)
        if profile is None:
            return
        monkeypatch.setattr(ab, "find_audio_manifest", lambda _: pytest.fail("too late validation"))
        out = tmp_path / "not-created"
        with pytest.raises(OCFError):
            ab.build("unused", mix_profile=profile, out_root=out)
        assert not out.exists()

    @pytest.mark.parametrize("text", ["[invalid", "limiter: .nan", "limiter: {ceiling: .inf}"])
    def test_malformed_file_is_actionable(self, tmp_path, text):
        path = tmp_path / "mix.yaml"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(OCFError, match="mix profile"):
            mp.load_mix_profile(path)

    def test_missing_file(self, tmp_path):
        with pytest.raises(OCFError, match="cannot read mix profile"):
            mp.load_mix_profile(tmp_path / "absent.yaml")

    def test_exact_legacy_graph_and_output_arguments(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(ab, "_require_ffmpeg", lambda: "ffmpeg")
        monkeypatch.setattr(
            ab,
            "workspace_run",
            lambda argv, **kwargs: calls.append((argv, kwargs)) or SimpleNamespace(returncode=0),
        )
        speech, bed, out = [tmp_path / name for name in ("speech.wav", "bed.wav", "out.wav")]
        result = ab._mix_master_ffmpeg(speech, bed, out, speech_gain_windows=[(1, 2, -6)])
        assert result is None
        assert calls == [
            (
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(speech),
                    "-i",
                    str(bed),
                    "-filter_complex",
                    "[0:a]aformat=channel_layouts=stereo,volume=1.000000,"
                    "volume=0.501187:enable='between(t,1.000,2.000)'[n];"
                    "[1:a]volume=0.250000[b];"
                    "[n][b]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97:level=false[out]",
                    "-map",
                    "[out]",
                    "-ar",
                    str(ab.DEFAULT_SAMPLE_RATE),
                    "-ac",
                    "2",
                    str(out),
                ],
                {"capture_output": True, "timeout": mp.MIX_TIMEOUT_SECONDS},
            )
        ]

    def test_explicit_graph_and_receipt_preserve_gains_windows(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(mp.shutil, "which", lambda _: "ffmpeg")
        monkeypatch.setattr(
            mp,
            "workspace_run",
            lambda argv, **kwargs: calls.append((argv, kwargs)) or SimpleNamespace(returncode=0),
        )
        result = ab._mix_master_ffmpeg(
            tmp_path / "speech.wav",
            tmp_path / "bed.wav",
            tmp_path / "out.wav",
            speech_gain=0.8,
            background_gain=0.2,
            speech_gain_windows=[(1, 2, -24)],
            mix_profile={"background_ducking": {"enabled": True}, "output_headroom_db": 3},
        )
        graph = result["filtergraph"]
        assert result["argv"] == calls[0][0]
        assert calls[0][1] == {
            "timeout": mp.MIX_TIMEOUT_SECONDS,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.PIPE,
        }
        assert "volume=0.800000,volume=0.063096:enable='between(t,1.000,2.000)'[n]" in graph
        assert "[1:a]volume=0.200000[b]" in graph
        assert "[n]asplit=2[voice][sc]" in graph
        assert "[b]apad[duck_bed];[sc]apad[duck_sc];[duck_bed][duck_sc]sidechaincompress=" in graph
        assert graph.count("apad") == 2
        assert ":link=maximum:detection=rms:" in graph
        assert "[voice][d]amix=inputs=2:duration=first:normalize=0,volume=" in graph
        assert "level=false:latency=false" in graph
        assert all(effect not in graph for effect in ("pan=", "loudnorm", "afade", "adelay"))
        assert result["parameters"]["speech_gain_windows"] == [
            {"start": 1, "end": 2, "gain_db": -24}
        ]
        assert result["parameters"]["ducking"]["threshold_linear"] == pytest.approx(
            10 ** (-24 / 20)
        )
        json.dumps(result, allow_nan=False)

    def test_fixed_background_gain_window_is_time_only_and_stereo_linked(
        self, monkeypatch, tmp_path
    ):
        calls = []
        monkeypatch.setattr(mp.shutil, "which", lambda _: "ffmpeg")
        monkeypatch.setattr(
            mp,
            "workspace_run",
            lambda argv, **kwargs: calls.append(argv) or SimpleNamespace(returncode=0),
        )
        speech = tmp_path / "speech.wav"
        _wav(speech, [0] * (4 * ab.DEFAULT_SAMPLE_RATE), channels=1)
        window = {
            "event_id": "focus11-body.pass-2",
            "start_s": 1.0,
            "end_s": 3.0,
            "gain_db": -10.0,
            "attack_s": 0.25,
            "release_s": 0.5,
        }
        result = ab._mix_master_ffmpeg(
            speech,
            tmp_path / "one-farfield-bed.wav",
            tmp_path / "out.wav",
            speech_gain=1.0,
            background_gain=1.0,
            mix_profile={"background_gain_windows": [window], "limiter": {"enabled": False}},
        )
        graph = result["filtergraph"]
        assert "[1:a]volume=1.000000,volume='if(lt(t,1.000000000),1," in graph
        assert (
            "0.316227766017+(1-0.316227766017)*(0.5-0.5*cos(PI*(t-3.000000000)/0.500000000))"
            in graph
        )
        assert ":eval=frame[b]" in graph
        assert "sidechaincompress" not in graph and "loudnorm" not in graph
        assert "amix=inputs=2:duration=first:normalize=0" in graph
        assert graph.count("[1:a]") == 1
        assert result["parameters"]["speech_gain"] == 1.0
        assert result["parameters"]["background_gain_windows"] == [window]
        assert calls and calls[0] == result["argv"]

    def test_background_gain_windows_require_bed_and_ordered_ramp_intervals(self, tmp_path):
        speech = tmp_path / "speech.wav"
        _wav(speech, [0] * (4 * ab.DEFAULT_SAMPLE_RATE), channels=1)
        one = {
            "event_id": "focus11.pass-1",
            "start_s": 1,
            "end_s": 2,
            "gain_db": -10,
            "attack_s": 0.25,
            "release_s": 1,
        }
        with pytest.raises(OCFError, match="requires a background stem"):
            ab._mix_master_ffmpeg(
                speech,
                None,
                tmp_path / "no-bed.wav",
                mix_profile={"background_gain_windows": [one]},
            )
        overlapping = [one, {**one, "event_id": "focus11.pass-2", "start_s": 2.5, "end_s": 3}]
        out = tmp_path / "not-written.wav"
        with pytest.raises(OCFError, match="ordered, nonoverlapping"):
            ab._mix_master_ffmpeg(
                speech,
                tmp_path / "bed.wav",
                out,
                mix_profile={"background_gain_windows": overlapping},
            )
        assert not out.exists()

    def test_ducking_without_background_rejected_before_outputs(self, tmp_path):
        out = tmp_path / "absent" / "out.wav"
        with pytest.raises(OCFError, match="requires a background stem"):
            ab._mix_master_ffmpeg(
                tmp_path / "speech.wav",
                None,
                out,
                mix_profile={"background_ducking": {"enabled": True}},
            )
        assert not out.parent.exists()

    def test_overlapping_fades_rejected_before_outputs(self, tmp_path):
        speech = tmp_path / "speech.wav"
        _wav(speech, [100] * 200, rate=100)
        out = tmp_path / "absent" / "out.wav"
        with pytest.raises(OCFError, match="fades must not overlap"):
            ab._mix_master_ffmpeg(
                speech, None, out, mix_profile={"fade_in_s": 0.6, "fade_out_s": 0.6}
            )
        assert not out.parent.exists()

    def test_missing_ffmpeg_explicit_error_before_output(self, monkeypatch, tmp_path):
        monkeypatch.setattr(mp.shutil, "which", lambda _: None)
        with pytest.raises(OCFError, match="required for an explicit mix profile"):
            ab._mix_master_ffmpeg(
                tmp_path / "speech.wav", None, tmp_path / "absent" / "out.wav", mix_profile={}
            )
        assert not (tmp_path / "absent").exists()

    @pytest.mark.parametrize(
        "failure",
        [
            subprocess.TimeoutExpired("ffmpeg", 3600),
            OSError("cannot execute ffmpeg"),
        ],
    )
    def test_subprocess_failures_actionable(self, monkeypatch, tmp_path, failure):
        monkeypatch.setattr(mp.shutil, "which", lambda _: "ffmpeg")

        def fail(*args, **kwargs):
            raise failure

        monkeypatch.setattr(mp, "workspace_run", fail)
        with pytest.raises(OCFError, match="ffmpeg mix tool failed"):
            ab._mix_master_ffmpeg(tmp_path / "s.wav", None, tmp_path / "o.wav", mix_profile={})

    def test_nonzero_ffmpeg_result(self, monkeypatch, tmp_path):
        monkeypatch.setattr(mp.shutil, "which", lambda _: "ffmpeg")
        monkeypatch.setattr(
            mp,
            "workspace_run",
            lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr=b"bad filter"),
        )
        with pytest.raises(OCFError, match="bad filter"):
            ab._mix_master_ffmpeg(tmp_path / "s.wav", None, tmp_path / "o.wav", mix_profile={})

    @pytest.mark.parametrize("bad_gain", [float("nan"), float("inf"), -0.1, True])
    def test_invalid_existing_gain_not_injected(self, tmp_path, bad_gain):
        with pytest.raises(OCFError, match="mix gains and windows"):
            ab._mix_master_ffmpeg(
                tmp_path / "s.wav", None, tmp_path / "o.wav", speech_gain=bad_gain, mix_profile={}
            )
        assert not (tmp_path / "o.wav").exists()

    @pytest.mark.parametrize(
        "stderr",
        [
            b'prefix\n{"input_i":"-inf","input_tp":"-inf","input_lra":"0","input_thresh":"-70"}\n',
            b'prefix\n{"input_i":"-19.2","input_tp":"-3.4","input_lra":"1.2","input_thresh":"-29.2"}\n',
            b"no metrics",
        ],
    )
    def test_metrics_stream_to_null_and_are_finite(self, monkeypatch, tmp_path, stderr):
        calls = []
        monkeypatch.setattr(
            mp,
            "workspace_run",
            lambda argv, **kw: (
                calls.append((argv, kw)) or SimpleNamespace(returncode=0, stderr=stderr)
            ),
        )
        if stderr == b"no metrics":
            with pytest.raises(OCFError, match="loudness measurements"):
                mp.measure_loudness(tmp_path / "master.wav", ffmpeg="ffmpeg")
        else:
            result = mp.measure_loudness(tmp_path / "master.wav", ffmpeg="ffmpeg")
            assert result["integrated_loudness_lufs"] == (None if b"-inf" in stderr else -19.2)
            json.dumps(result, allow_nan=False)
        argv, kwargs = calls[0]
        assert argv[-3:] == ["-f", "null", "-"]
        assert "-nostats" in argv
        assert kwargs == {
            "timeout": mp.MIX_TIMEOUT_SECONDS,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.PIPE,
        }

    @pytest.mark.parametrize(
        "explicit,background", [(False, False), (False, True), (True, False), (True, True)]
    )
    def test_build_forwarding_default_mock_signature_and_renderdoc(
        self, monkeypatch, tmp_path, explicit, background
    ):
        metadata = {
            "backend": "recording",
            "sample_rate": ab.DEFAULT_SAMPLE_RATE,
            "channels": 1,
            "duration": 1,
            "cues": 0,
            "overlap_mode": "error",
            "event_timing": [],
        }

        def narration(doc, out, **kwargs):
            _wav(out, [0] * ab.DEFAULT_SAMPLE_RATE, channels=1)
            return metadata

        monkeypatch.setattr(ab, "render_narration", narration)
        bed = tmp_path / "bed.wav" if background else None
        monkeypatch.setattr(ab, "_render_background", lambda *args, **kwargs: (bed, "test"))
        receipt = {"parameters": {"profile": mp.load_mix_profile({})}, "filtergraph": "exact graph"}
        calls = []

        def legacy(speech, bg, out, *, background_gain, speech_gain, speech_gain_windows):
            calls.append((background_gain, speech_gain, speech_gain_windows))
            _wav(out, [100] * (2 * ab.DEFAULT_SAMPLE_RATE))

        def profiled(*args, mix_profile, **kwargs):
            assert mix_profile == mp.load_mix_profile({})
            legacy(*args, **kwargs)
            return receipt

        monkeypatch.setattr(ab, "_mix_master_ffmpeg", profiled if explicit else legacy)
        out = tmp_path / "build"
        result = ab.build(
            "test",
            manifest_override={"id": "TEST-001"},
            document_override={},
            out_root=out,
            mix_profile={} if explicit else None,
            voice_gain=0.8,
            background_gain=0.2,
        )
        assert result["mixing"]["voice_gain"] == 0.8
        assert result["mixing"]["background_gain"] == (0.2 if background else 0)
        if explicit:
            assert result["mixing"]["processing"] == receipt
            saved = yaml_safe_load((out / "OCF-RENDER-001.yaml").read_text().split("\n\n", 1)[1])
            assert saved["mixing"]["processing"] == receipt
        else:
            assert "processing" not in result["mixing"]
        assert bool(calls) == (explicit or background)


@pytest.mark.integration
@pytest.mark.audio_integration
@pytest.mark.external_tool
class TestRealFFmpegMix:
    @pytest.fixture(autouse=True)
    def require_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            pytest.skip("optional ffmpeg is not installed")

    def test_independent_stereo_phase_amplitude_and_composed_fade_unchanged(self, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        speech, bed, out = [tmp_path / name for name in ("speech.wav", "bed.wav", "out.wav")]
        # Different frequencies, independent phase, unequal L/R amplitudes and
        # an already-composed ending fade expose downmix/crossfeed/double fades.
        samples = array("h")
        for i in range(rate * 2):
            envelope = min(1, (2 - i / rate) / 0.4)
            samples.extend(
                (
                    round(12000 * math.sin(2 * math.pi * 311 * i / rate + 0.23) * envelope),
                    round(7000 * math.sin(2 * math.pi * 563 * i / rate + 1.07) * envelope),
                )
            )
        _wav(speech, [0] * (rate * 4))
        _wav(bed, samples)
        result = ab._mix_master_ffmpeg(
            speech, bed, out, background_gain=1, mix_profile={"limiter": {"enabled": False}}
        )
        actual = _read(out)
        assert len(actual) == len(samples)
        assert max(abs(a - b) for a, b in zip(actual, samples, strict=True)) <= 1
        assert "sidechaincompress" not in result["filtergraph"]
        assert "apad" not in result["filtergraph"]
        assert "afade" not in result["filtergraph"]

    def test_fixed_time_window_attenuates_bed_in_speech_and_silence_then_recovers(self, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        speech, bed, out = [tmp_path / name for name in ("speech.wav", "bed.wav", "out.wav")]
        frames = rate * 4
        voice = array("h")
        binaural = array("h")
        for frame in range(frames):
            active = frame < rate or rate <= frame < int(1.7 * rate) or frame >= int(3.5 * rate)
            voice.append(round(3000 * math.sin(2 * math.pi * 1000 * frame / rate)) if active else 0)
            binaural.extend(
                (
                    round(7000 * math.sin(2 * math.pi * 311 * frame / rate + 0.23)),
                    round(4200 * math.sin(2 * math.pi * 563 * frame / rate + 1.07)),
                )
            )
        _wav(speech, voice, channels=1)
        _wav(bed, binaural)
        window = {
            "event_id": "focus11-body.pass-2",
            "start_s": 1.0,
            "end_s": 3.0,
            "gain_db": -10.0,
            "attack_s": 0.25,
            "release_s": 0.5,
        }
        receipt = ab._mix_master_ffmpeg(
            speech,
            bed,
            out,
            speech_gain=1.0,
            background_gain=1.0,
            mix_profile={"background_gain_windows": [window], "limiter": {"enabled": False}},
        )
        mixed = _read(out)

        def estimate(start_s, end_s):
            lo, hi = int(start_s * rate), int(end_s * rate)
            result = []
            for channel in range(2):
                source = array("h", binaural[2 * lo + channel : 2 * hi : 2])
                rendered = array("h", mixed[2 * lo + channel : 2 * hi : 2])
                original_voice = array("h", voice[lo:hi])
                denominator = sum(value * value for value in source)
                result.append(
                    sum(
                        (y - v) * x
                        for y, v, x in zip(rendered, original_voice, source, strict=True)
                    )
                    / denominator
                )
            return result

        before = estimate(0.2, 0.8)
        inside_speech = estimate(1.4, 1.6)
        inside_silence = estimate(2.0, 2.4)
        after = estimate(3.7, 3.9)
        expected = 10 ** (-10 / 20)
        assert min(before) > 0.98 and max(before) < 1.02
        assert all(abs(gain - expected) < 0.03 for gain in inside_speech + inside_silence)
        assert min(after) > 0.98 and max(after) < 1.02
        assert abs(inside_speech[0] - inside_speech[1]) < 0.01
        assert "sidechaincompress" not in receipt["filtergraph"]

    @pytest.mark.parametrize("paced_input", [None, "speech", "bed"])
    def test_ducking_shared_envelope_expected_ratio_and_window_detector(
        self, tmp_path, monkeypatch, paced_input
    ):
        if paced_input:
            run = mp._run

            def paced(argv, **kwargs):
                index = argv.index(str(tmp_path / (paced_input + ".wav"))) - 1
                assert argv[index] == "-i"
                argv[index:index] = ["-re"]
                return run(argv, **kwargs)

            monkeypatch.setattr(mp, "_run", paced)
        rate = ab.DEFAULT_SAMPLE_RATE
        speech, bed, out = [tmp_path / name for name in ("speech.wav", "bed.wav", "out.wav")]
        voice = array("h")
        background = array("h")
        for i in range(rate * 5):
            # Stereo detector maximum must follow the louder LEFT channel.
            voice.extend((13107, 1638) if rate <= i < 4 * rate else (0, 0))
            background.extend(
                (
                    round(7000 * math.sin(2 * math.pi * 311 * i / rate + 0.23)),
                    round(4200 * math.sin(2 * math.pi * 563 * i / rate + 1.07)),
                )
            )
        _wav(speech, voice)
        _wav(bed, background)
        threshold_db = 20 * math.log10(0.1)
        receipt = ab._mix_master_ffmpeg(
            speech,
            bed,
            out,
            background_gain=1,
            speech_gain=1,
            speech_gain_windows=[(2.5, 4, -20)],
            mix_profile={
                "limiter": {"enabled": False},
                "background_ducking": {
                    "enabled": True,
                    "threshold_dbfs": threshold_db,
                    "ratio": 4,
                    "knee": 1,
                    "attack_ms": 5,
                    "release_ms": 40,
                },
            },
        )
        actual = _read(out)
        diagnostic = {
            "paced_input": paced_input,
            "ffmpeg_version": subprocess.run(
                [receipt["argv"][0], "-version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ).stdout.splitlines()[0],
            "receipt": receipt,
            "input_sha256": {p.name: sha256_of_file(p) for p in (speech, bed)},
            "output_sha256": sha256_of_file(out),
            "expected_frames": rate * 5,
            "actual_frames": len(actual) // 2,
        }
        details = tmp_path / "ducking-diagnostics.json"
        details.write_text(json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8")
        # Steady compressor law: output/input = (threshold / detector)^(1-1/ratio).
        assert len(actual) == len(background)
        expected = (0.1 / (13107 / 32768)) ** 0.75

        def gains_at(i, gain=1):
            result = []
            for ch in range(2):
                j = i * 2 + ch
                if abs(background[j]) < 1200:
                    return None
                result.append((actual[j] - voice[j] * gain) / background[j])
            return result

        steady = [gains_at(i) for i in range(2 * rate, int(2.4 * rate))]
        steady = [pair for pair in steady if pair]
        assert steady
        assert max(abs(g - expected) for pair in steady for g in pair) < 0.002
        # Check coherence throughout attack AND release, with independent phases.
        transition = [gains_at(i) for i in range(rate, int(1.1 * rate))]
        transition += [gains_at(i, 0.1) for i in range(int(2.6 * rate), 3 * rate)]
        assert max(abs(pair[0] - pair[1]) for pair in transition if pair) < 0.002
        # -20 dB narration window drops the detector below threshold: no duck.
        recovered = [gains_at(i, 0.1) for i in range(int(3.5 * rate), int(3.9 * rate))]
        worst = max(
            (abs(g - 1), int(3.5 * rate) + offset, channel, g)
            for offset, pair in enumerate(recovered)
            if pair
            for channel, g in enumerate(pair)
        )
        diagnostic["worst_recovery"] = dict(
            zip(("absolute_error", "frame", "channel", "signed_gain"), worst, strict=True)
        )
        details.write_text(json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8")
        assert max(abs(g - 1) for pair in recovered if pair for g in pair) < 0.002, diagnostic
        assert all(
            abs(a - b) <= 1 for a, b in zip(actual[: 2 * rate], background[: 2 * rate], strict=True)
        )
        tail = 2 * int(4.2 * rate)
        assert max(abs(a - b) for a, b in zip(actual[tail:], background[tail:], strict=True)) <= 1

    @pytest.mark.parametrize(
        "voice_frames,bed_frames",
        [
            (0, 2 * ab.DEFAULT_SAMPLE_RATE + 37),
            (2 * ab.DEFAULT_SAMPLE_RATE + 37, 0),
            (2 * ab.DEFAULT_SAMPLE_RATE + 37, ab.DEFAULT_SAMPLE_RATE + 11),
            (ab.DEFAULT_SAMPLE_RATE + 11, 2 * ab.DEFAULT_SAMPLE_RATE + 37),
        ],
    )
    def test_ducking_eof_preserves_narration_duration_without_padding_output(
        self, tmp_path, voice_frames, bed_frames
    ):
        speech, bed, out = [tmp_path / name for name in ("speech.wav", "bed.wav", "out.wav")]
        _wav(speech, [0, 0] * voice_frames)
        _wav(bed, [1300, -2100] * bed_frames)
        ab._mix_master_ffmpeg(
            speech,
            bed,
            out,
            background_gain=1,
            mix_profile={
                "limiter": {"enabled": False},
                "background_ducking": {"enabled": True},
            },
        )
        actual = _read(out)
        expected = array(
            "h",
            [1300, -2100] * min(voice_frames, bed_frames)
            + [0, 0] * max(0, voice_frames - bed_frames),
        )
        assert len(actual) == 2 * voice_frames
        assert all(abs(a - b) <= 1 for a, b in zip(actual, expected, strict=True))

    def test_sum_headroom_before_pcm_quantization_avoids_unintended_clipping(self, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        speech, bed, out = [tmp_path / name for name in ("speech.wav", "bed.wav", "out.wav")]
        values = [round(26000 * math.sin(2 * math.pi * 300 * i / rate)) for i in range(rate)]
        stereo = [v for sample in values for v in (sample, -sample)]
        _wav(speech, stereo)
        _wav(bed, stereo)
        ab._mix_master_ffmpeg(
            speech,
            bed,
            out,
            background_gain=1,
            mix_profile={"limiter": {"enabled": False}, "output_headroom_db": 6},
        )
        actual = _read(out)
        factor = 2 * 10 ** (-6 / 20)
        assert max(abs(a - b * factor) for a, b in zip(actual, stereo, strict=True)) < 2
        assert max(abs(v) for v in actual) < 27000

    @pytest.mark.parametrize("level", [3000, 29000])
    def test_limiter_ceiling_and_no_auto_gain(self, tmp_path, level):
        rate = ab.DEFAULT_SAMPLE_RATE
        speech, bed, out = [tmp_path / name for name in ("speech.wav", "bed.wav", "out.wav")]
        values = [round(level * math.sin(2 * math.pi * 300 * i / rate)) for i in range(rate)]
        stereo = [v for sample in values for v in (sample, -sample)]
        _wav(speech, stereo)
        _wav(bed, stereo)
        result = ab._mix_master_ffmpeg(
            speech,
            bed,
            out,
            background_gain=1,
            mix_profile={"limiter": {"ceiling": 0.5, "attack_ms": 2, "release_ms": 80}},
        )
        actual = _read(out)
        assert len(actual) == len(stereo)
        peak = max(abs(v) for v in actual[rate:])
        assert peak <= 16385
        assert peak == pytest.approx(min(2 * level, 16384), abs=4)
        assert result["parameters"]["profile"]["limiter"]["release_ms"] == 80

    def test_narration_only_explicit_gains_windows_and_final_fades(self, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        speech, out = tmp_path / "speech.wav", tmp_path / "out.wav"
        _wav(speech, [10000, -4000] * (rate * 3))
        result = ab._mix_master_ffmpeg(
            speech,
            None,
            out,
            speech_gain=0.8,
            speech_gain_windows=[(1, 2, -6)],
            mix_profile={"limiter": {"enabled": False}, "fade_in_s": 0.5, "fade_out_s": 0.5},
        )
        actual = _read(out)
        for t, factor in [(0.25, 0.5), (0.75, 1), (1.5, 10 ** (-6 / 20)), (2.75, 0.5)]:
            i = int(t * rate) * 2
            assert actual[i] == pytest.approx(8000 * factor, abs=3)
            assert actual[i + 1] == pytest.approx(-3200 * factor, abs=3)
        assert result["filtergraph"].count("afade=") == 2
        assert "afade=t=out:st=2.5:d=0.5" in result["filtergraph"]

    def test_streamed_loudness_measures_master_without_changing_audio(self, tmp_path):
        rate = ab.DEFAULT_SAMPLE_RATE
        speech = tmp_path / "speech.wav"
        values = [round(8000 * math.sin(2 * math.pi * 1000 * i / rate)) for i in range(rate * 4)]
        _wav(speech, [v for sample in values for v in (sample, sample)])
        plain, measured = tmp_path / "plain.wav", tmp_path / "measured.wav"
        ab._mix_master_ffmpeg(speech, None, plain, mix_profile={})
        result = ab._mix_master_ffmpeg(
            speech, None, measured, mix_profile={"measure_loudness": True}
        )
        assert _read(plain) == _read(measured)
        assert -20 < result["loudness"]["integrated_loudness_lufs"] < -10
        assert result["loudness"]["true_peak_dbfs"] == pytest.approx(
            20 * math.log10(8000 / 32768), abs=0.1
        )
        assert "loudnorm" not in result["filtergraph"]
        json.dumps(result, allow_nan=False)


def test_complete_render_cli_forwards_explicit_mix_profile(monkeypatch, tmp_path, capsys):
    from ocf_tools import cli, complete_session

    profile = tmp_path / "mix.json"
    profile.write_text("{}", encoding="utf-8")
    captured = []
    monkeypatch.setattr(
        complete_session,
        "render_complete_session",
        lambda *_a, **kwargs: captured.append(kwargs) or {"dry_run": True},
    )
    assert (
        cli.main(["audio", "render", "OCF-SLP-005", "--mix-profile", str(profile), "--dry-run"])
        == 0
    )
    assert captured[0]["mix_profile"] == profile
    assert '"dry_run": true' in capsys.readouterr().out
