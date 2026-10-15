"""Deterministic technical demo preparation/receipts; no engines or full TTS."""

import json
import os
import wave
from copy import deepcopy

import pytest
from ocf_tools import narration_cli
from ocf_tools.narration_sources import SourceResolver, text_fingerprint
from ocf_tools.paths import work_root
from ocf_tools.utils import OCFError, sha256_of_file
from tools import verify_narration_engine2 as demo


@pytest.fixture
def document():
    return {
        "schema_version": "1.0",
        "id": "demo-test",
        "locale": "en-US",
        "function_id": "OCF-SLP-005",
        "semantic_dsp_profile": "test-profile",
        "timeline": [
            {
                "id": "opening",
                "at": 0,
                "text": "Original test opening.",
                "narration_key": "test.opening",
            },
            {
                "id": "enter",
                "after": "opening",
                "timing": {"anchor": "speech-end", "pause_after": 7},
                "text": "Original signal declaration.",
            },
            {
                "id": "transition",
                "after": "enter",
                "timing": {"anchor": "speech-end"},
                "dsp": {"state": {"from": "focus-10", "to": "focus-11"}, "transition_s": 25},
            },
            {
                "id": "ready",
                "after": "transition",
                "timing": {"anchor": "event-end"},
                "text": "Original ready instruction.",
            },
            {"id": "hold", "after": "ready", "timing": {"anchor": "speech-end", "pause_after": 60}},
        ],
    }


@pytest.fixture
def prepared(document, monkeypatch, tmp_path):
    from ocf_tools import voice

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(narration_cli, "session_document", lambda *_: deepcopy(document))
    monkeypatch.setattr(
        demo, "load_profile", lambda *_: {"id": "test-profile", "ignored_state_events": []}
    )
    monkeypatch.setattr(
        voice, "load_voice_profiles", lambda: [{"id": "OCF-VOICE-0002", "backend": "piper"}]
    )
    monkeypatch.setattr(
        demo,
        "plan_program",
        lambda _doc, _ledger, duration, _profile: {"transitions": [], "duration_s": duration},
    )
    # Keep generated unit fixture bytes tiny while preserving their declared seconds.
    original = demo.write_fixture
    monkeypatch.setattr(demo, "write_fixture", lambda *a: original(*a, sample_rate=8000))
    root = work_root() / "new-demo"
    return demo.prepare(root)


@pytest.mark.unit
def test_prepare_exact_event_hashes_single_tts_gain_and_expected_mismatch(prepared, document):
    root, marker, resolved, _profile = demo.load_preparation(prepared["prepared_directory"])
    assert resolved == document
    assert prepared["label"] == demo.LABEL and prepared["listening_approval"] is None
    assert marker["tts_event"] == marker["gain_event"] == "opening"
    reports = {
        key: SourceResolver(document, path).report
        for key, path in prepared["manifest_paths"].items()
        if key != "mismatch"
    }
    assert [row["event_id"] for row in reports["hybrid"]["events"] if row["source"] == "tts"] == [
        "opening"
    ]
    assert reports["hybrid"]["fallback"] == "error"
    assert reports["recorded"]["output_channels"] == 2
    for row in reports["recorded"]["events"]:
        if row["source"] != "recording":
            continue
        event = next(event for event in document["timeline"] if event["id"] == row["event_id"])
        assert row["text_sha256"] == text_fingerprint(event["text"])
        entry = row["recording"]
        assert entry["target"] == {"event_id": event["id"]}
        assert entry["sha256"] == sha256_of_file(root / entry["file"])
        assert entry["rights"]["consent"] == "synthetic-fixture"
        assert entry["approval"] == "pending"
    recorded = json.loads((root / "recorded.json").read_text())
    gain = json.loads((root / "gain.json").read_text())
    gain["id"] = recorded["id"]
    assert gain["events"]["opening"].pop("gain_db") == -6
    assert gain == recorded
    with pytest.raises(OCFError, match="source text fingerprint mismatch"):
        SourceResolver(document, root / "mismatch.json")
    assert "ocf_start_narration_render" in prepared["queue_cli_argv"]["recorded"]
    assert json.loads(prepared["queue_cli_argv"]["hybrid"][-1])["manifest"] == str(
        root / "hybrid.json"
    )


@pytest.mark.unit
def test_explicit_transition_metadata_selects_durations_not_prose(document):
    durations, bindings = demo.fixture_durations(document, {})
    assert durations == {"opening": 2, "enter": 30, "ready": 30}
    assert bindings == [
        {"event_id": "transition", "transition_s": 25, "spoken_fixture_events": ["enter", "ready"]}
    ]
    document["timeline"][0]["text"] = "Focus 11 entering, closing, 25 seconds."
    assert demo.fixture_durations(document, {})[0] == durations
    assert demo.fixture_durations(document, {"ignored_state_events": ["transition"]})[0] == {
        "opening": 2,
        "enter": 2,
        "ready": 2,
    }


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["manifest", "asset", "marker", "canonical"])
def test_preparation_marker_and_diff_detection(prepared, document, monkeypatch, mutation):
    root = work_root() / "new-demo"
    if mutation == "manifest":
        path = root / "gain.json"
        path.write_text(path.read_text() + " ")
    elif mutation == "asset":
        fixture = prepared["fixtures"][0]
        with (root / fixture["file"]).open("ab") as stream:
            stream.write(b"changed")
    elif mutation == "marker":
        path = root / demo.MARKER
        data = json.loads(path.read_text())
        data["label"] = "human narration"
        path.write_text(json.dumps(data))
    else:
        document["timeline"][0]["text"] += " Updated."
        monkeypatch.setattr(narration_cli, "session_document", lambda *_: document)
    with pytest.raises(OCFError, match="changed|marker"):
        demo.load_preparation(root)


@pytest.mark.unit
def test_new_private_directory_does_not_overwrite_or_escape(prepared):
    with pytest.raises(OCFError, match="NEW"):
        demo._new_private_directory(prepared["prepared_directory"])
    with pytest.raises(OCFError, match="inside"):
        demo._new_private_directory(work_root().parent / "escape")
    with pytest.raises(OCFError, match="escapes"):
        demo._contained(work_root(), "../escape")


@pytest.mark.unit
def test_signal_has_ramped_independent_stereo_and_deterministic_bytes(tmp_path):
    first = demo.write_fixture(tmp_path / "one.wav", 0.5, 2, sample_rate=8000)
    second = demo.write_fixture(tmp_path / "two.wav", 0.5, 2, sample_rate=8000)
    assert first["sha256"] == second["sha256"]
    with wave.open(str(tmp_path / "one.wav")) as reader:
        assert reader.getnframes() == 4000 and reader.getnchannels() == 2
        raw = reader.readframes(4000)
    assert raw[:4] == raw[-4:] == b"\0" * 4
    assert raw[0::4] != raw[2::4]
    metrics = demo.recording_audio.inspect_recording(tmp_path / "one.wav")["original"]
    assert 0 < metrics["sample_peak"] < 0.13
    assert abs(metrics["stereo_correlation"]) < 0.01


def comparison_rows():
    base = {
        "variant": "recorded",
        "background_sha256": "background",
        "master_sha256": "recorded-master",
        "gain_receipt_db": 0,
        "preset_fingerprints": {
            "focus-10": {"preset_id": "explicit", "preset_sha256": "fingerprint"}
        },
        "mix": {"voice_gain": 1, "background_gain": 1},
    }
    gain = {
        **deepcopy(base),
        "variant": "gain",
        "master_sha256": "gain-master",
        "gain_receipt_db": -6,
    }
    hybrid = {
        **deepcopy(base),
        "variant": "hybrid",
        "background_sha256": "different-duration-background",
    }
    return [base, gain, hybrid]


@pytest.mark.unit
def test_comparison_preserves_background_bytes_but_hybrid_only_preset_identity():
    rows = comparison_rows()
    assert set(demo.compare_reports(rows)) == {"recorded_gain", "recorded_hybrid"}
    assert demo.compare_reports(rows[:1]) == {}


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["background", "master", "gain", "preset", "mix", "duplicate"])
def test_comparison_detects_regressions(mutation):
    rows = comparison_rows()
    if mutation == "background":
        rows[1]["background_sha256"] = "changed"
    elif mutation == "master":
        rows[1]["master_sha256"] = rows[0]["master_sha256"]
    elif mutation == "gain":
        rows[1]["gain_receipt_db"] = 0
    elif mutation == "preset":
        rows[2]["preset_fingerprints"]["focus-10"]["preset_sha256"] = "changed"
    elif mutation == "mix":
        rows[1]["mix"]["voice_gain"] = 0.5
    else:
        rows.append(rows[0])
    with pytest.raises(OCFError):
        demo.compare_reports(rows)


@pytest.mark.unit
def test_cli_failure_is_json_and_nonzero(capsys):
    assert demo.main(["verify", str(work_root() / "missing")]) == 1
    report = json.loads(capsys.readouterr().err)
    assert report["status"] == "failed" and "--prepared" in report["error"]


@pytest.mark.unit
def test_verify_reports_partial_and_complete_without_audio_engines(prepared, monkeypatch):
    root = work_root() / "new-demo"
    monkeypatch.setattr(
        demo,
        "verify_report",
        lambda directory, _preparation: next(
            row for row in comparison_rows() if row["variant"] == directory.name
        ),
    )
    result = demo.verify([root / "recorded"])
    assert result["status"] == "partial" and result["missing_variants"] == ["gain", "hybrid"]
    result = demo.verify([root / key for key in ("recorded", "gain", "hybrid")])
    assert result["status"] == "passed" and result["mismatch_rejected"]
    assert result["listening_approval"] is None


@pytest.fixture
def report_fixture(prepared, document, monkeypatch):
    """Real source/size/hash/timing validation; stub only DSP planning and audio scans."""
    root = work_root() / "new-demo"
    preparation = demo.load_preparation(root)
    resolver = SourceResolver(document, root / "recorded.json")
    durations = prepared["fixture_durations_s"]
    ledger = demo.schedule_timeline(document, durations)
    total = max(row["end"] for row in ledger) + 1
    transition = next(row for row in ledger if row["id"] == "transition")
    program = {
        "profile_id": "test-profile",
        "profile_version": "1",
        "seed": 0,
        "initial_state": "focus-10",
        "default_background_state": "focus-10",
        "curve": "equal-power",
        "duration_s": total,
        "ending_fade_seconds": 10,
        "selections": {"focus-10": {"preset_id": "declared-preset", "preset_sha256": "original"}},
        "transitions": [
            {
                "event_id": "transition",
                "from": "focus-10",
                "to": "focus-11",
                "start_s": transition["at"],
                "end_s": transition["at"] + 25,
            }
        ],
        "ignored_state_directives": [],
        "stage_backgrounds": {},
    }
    monkeypatch.setattr(demo, "plan_program", lambda *_: deepcopy(program))
    # The test document has original inline fixture prose, no locale catalog entries.
    monkeypatch.setattr(demo, "resolve_document", lambda doc, *_a, **_k: doc)
    directory = root / "rendered"
    directory.mkdir()
    assets = {}
    for key, data in (
        ("wav", b"master"),
        ("background_stem", b"background"),
        ("session_plan", json.dumps(document).encode()),
    ):
        path = directory / key
        path.write_bytes(data)
        assets[key] = {"path": key, "sha256": sha256_of_file(path), "size_bytes": len(data)}
    cues = []
    for row in ledger:
        if row["id"] not in durations:
            continue
        receipt = deepcopy(resolver.rows[row["id"]])
        receipt["preparation"] = {
            "input_sha256": receipt["recording"]["sha256"],
            "original_preserved": True,
            "processed": {"channels": 2},
        }
        cues.append(
            {
                "id": row["id"],
                "at": row["at"],
                "duration": durations[row["id"]],
                "narration_source": receipt,
            }
        )
    report = {
        "render_type": "complete-session-audition",
        "function_id": "OCF-SLP-005",
        "requested_locale": "en-US",
        "narration_source": resolver.report,
        "narration_timing": {"cues": cues},
        "dsp_profile": deepcopy(program),
        "mix": {"ending_fade_seconds": 10},
        "state_transitions": deepcopy(program["transitions"]),
        "stages": [],
        "artifacts": assets,
    }
    scans = []
    monkeypatch.setattr(
        demo.complete_session, "_verify_decode", lambda path: scans.append(("decode", path.name))
    )
    metrics = {
        "frames": round(total * 44100),
        "duration_seconds": total,
        "channels": 2,
        "left_peak_int16": 100,
        "right_peak_int16": 110,
        "different_channel_frames": 100,
        "clipped_sample_count": 0,
    }
    monkeypatch.setattr(
        demo.complete_session, "_stereo_metrics", lambda *_a, **_k: deepcopy(metrics)
    )
    for symbol in (
        "_background_activity",
        "_representative_audio_analysis",
        "_verify_background_continuity",
    ):
        monkeypatch.setattr(
            demo.complete_session,
            symbol,
            lambda *_a, _name=symbol: scans.append((_name, "background")) or [],
        )
    return directory, preparation, report, scans, metrics


@pytest.mark.unit
def test_verify_report_checks_real_artifact_hashes_sources_and_timing(report_fixture):
    directory, preparation, report, scans, _metrics = report_fixture
    (directory / "session-report.json").write_text(json.dumps(report))
    result = demo.verify_report(directory, preparation)
    assert result["status"] == "passed" and result["spoken_cues_checked"] == 3
    assert scans[:2] == [("decode", "wav"), ("decode", "background_stem")]
    assert {row[0] for row in scans[2:]} == {
        "_background_activity",
        "_representative_audio_analysis",
        "_verify_background_continuity",
    }
    assert result["listening_approval"] is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutation,match",
    [
        ("artifact", "hash/size"),
        ("receipt", "source/gain receipt"),
        ("sources", "source event report"),
        ("wait", "timing/waits"),
        ("preset", "fingerprint"),
        ("transition", "canonical anchor"),
        ("fade", "10-second"),
        ("clipping", "clipping"),
        ("frames", "duration mismatch"),
    ],
)
def test_verify_report_rejects_objective_regressions(report_fixture, monkeypatch, mutation, match):
    directory, preparation, report, scans, metrics = report_fixture
    if mutation == "artifact":
        (directory / "wav").write_bytes(b"tampered")
    elif mutation == "receipt":
        report["narration_timing"]["cues"][0]["narration_source"]["gain_db"] = -6
    elif mutation == "sources":
        report["narration_source"]["events"].pop()
    elif mutation == "wait":
        report["narration_timing"]["cues"][-1]["at"] -= 7
    elif mutation == "preset":
        report["dsp_profile"]["selections"]["focus-10"]["preset_sha256"] = "changed"
    elif mutation == "transition":
        report["state_transitions"][0]["start_s"] += 1
        report["dsp_profile"]["transitions"][0]["start_s"] += 1
    elif mutation == "fade":
        report["mix"]["ending_fade_seconds"] = 5
    elif mutation == "clipping":
        metrics["clipped_sample_count"] = 1
    elif mutation == "frames":
        monkeypatch.setattr(
            demo.complete_session,
            "_stereo_metrics",
            lambda path, **_k: {**metrics, "frames": metrics["frames"] + (path.name == "wav")},
        )
    (directory / "session-report.json").write_text(json.dumps(report))
    with pytest.raises(OCFError, match=match):
        demo.verify_report(directory, preparation)
    if mutation in ("artifact", "receipt", "sources", "wait", "preset", "transition", "fade"):
        assert scans == []  # Preflight fails before any expensive audio scans.


@pytest.mark.unit
def test_benchmark_repeated_cache_metadata_identical_bytes_and_environment_restoration(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    previous = os.environ["OCF_WORK_DIR"]
    original_writer = demo.write_fixture
    monkeypatch.setattr(
        demo, "write_fixture", lambda path, *_a: original_writer(path, 0.02, 2, sample_rate=8000)
    )
    seen = {}

    def process(source, **kwargs):
        cache = os.environ["OCF_WORK_DIR"]
        hit = cache in seen
        seen[cache] = seen.get(cache, 0) + 1
        data = source.read_bytes()
        measurements = {"per_channel": [{"peak": 0.1, "rms": 0.05}]}
        return data, {
            "cache_hit": hit,
            "cache_key": "key",
            "processed_sha256": sha256_of_file(source),
            "original": measurements,
            "processed": measurements,
        }

    monkeypatch.setattr(demo.recording_audio, "process_recording", process)
    result = demo.benchmark_recording(work_root() / "benchmark", repeats=2, warm_runs=2)
    assert os.environ["OCF_WORK_DIR"] == previous
    assert len(seen) == 2 and set(seen.values()) == {3}
    assert all(
        [call["cache_hit"] for call in trial["calls"]] == [False, True, True]
        for trial in result["trials"]
    )
    assert result["speed_claim"] is None
    assert set(result["median_wall_seconds"]) == {"cold", "warm"}


@pytest.mark.unit
def test_benchmark_failure_retains_environment_and_rejects_false_warm_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    previous = os.environ["OCF_WORK_DIR"]
    monkeypatch.setattr(demo, "write_fixture", lambda path, *_a: {"sha256": "fixture"})
    monkeypatch.setattr(
        demo.recording_audio, "process_recording", lambda *_a, **_k: (b"bytes", {"cache_hit": True})
    )
    with pytest.raises(OCFError, match="cache-hit"):
        demo.benchmark_recording(work_root() / "failed", repeats=2)
    assert os.environ["OCF_WORK_DIR"] == previous
