"""Harness safety/reporting tests; real external-stage measurements use the CLI."""

import json
import sys
import wave
from types import SimpleNamespace

import pytest
from ocf_tools.utils import OCFError
from tools import benchmark_synthetic_audio as bench

pytestmark = pytest.mark.unit


@pytest.fixture
def fixtures(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("OCF_WORK_DIR", str(work))

    def bed(path, seconds):
        bench.audio_build._write_wav(path, [100, -100] * 16, 22050, channels=2, overwrite=True)

    def narration(doc, path, **kwargs):
        bench.voice._write_wav(path, [0, -32768, 32767, 42] * 4, 22050, overwrite=True)

    def encode(source, fmt, target):
        target.write_bytes(source.read_bytes())

    def decode(argv, **kwargs):
        with wave.open(argv[argv.index("-i") + 1]) as reader:
            data = reader.readframes(reader.getnframes())
        return SimpleNamespace(returncode=0, stdout=data)

    monkeypatch.setattr(bench, "make_bed", bed)
    monkeypatch.setattr(bench.voice, "render_narration", narration)
    monkeypatch.setattr(bench.audio_build, "_encode", encode)
    monkeypatch.setattr(bench, "workspace_run", decode)
    monkeypatch.setattr(bench.shutil, "which", lambda _: sys.executable)
    monkeypatch.setattr(bench, "_batch_resource_state", lambda count: {"selected_workers": count})
    monkeypatch.setattr(bench.platform, "platform", lambda: "synthetic-test-platform")
    return work


def test_real_pcm_and_atomic_fixture_receipts_cover_warm_resume_recovery_and_workers(fixtures):
    original = str(fixtures)
    result = bench.benchmark(
        fixtures / "audio", sessions=2, seconds=6, worker_counts=[1, 2], source_sha="a" * 40
    )
    assert bench.os.environ["OCF_WORK_DIR"] == original
    assert result["retained_fixture_bytes"] > 0
    for case in result["cases"]:
        assert case["all_artifacts_byte_exact"]
        assert all(row["reused"] for row in case["verified_resume"]["rows"])
        assert sum(row["reused"] for row in case["recovery"]["rows"]) == 1
        assert case["injected_interruption"]["rows"][0]["injected_failure"]
    # Subsequent invocation keeps the old marked family intact and creates a
    # separate run, never reuses a partially warm run as a new cold measurement.
    again = bench.benchmark(
        fixtures / "audio", sessions=1, seconds=6, worker_counts=[1], source_sha="a" * 40
    )
    assert again["cases"][0]["all_artifacts_byte_exact"]


def test_output_boundary_and_unmarked_directory_preserved(fixtures):
    for output in [fixtures, fixtures.parent / "outside"]:
        with pytest.raises(OCFError, match="dedicated directory"):
            bench.benchmark(output, sessions=1, seconds=6, worker_counts=[1], source_sha="a")
    existing = fixtures / "unmarked"
    existing.mkdir()
    with pytest.raises(OCFError, match="unmarked"):
        bench.benchmark(existing, sessions=1, seconds=6, worker_counts=[1], source_sha="a")
    assert list(existing.iterdir()) == []


def test_tool_scratch_is_independent_of_long_artifact_paths(fixtures, monkeypatch):
    output = fixtures / ("long-artifact-path-" * 5)
    seen = []
    original = bench.voice.render_narration

    def checked(*args, **kwargs):
        from pathlib import Path

        scratch = Path(bench.os.environ["OCF_WORK_DIR"])
        assert not scratch.is_relative_to(output)
        assert (scratch.parent / ".ocf-owned").is_file()
        assert len(str(scratch)) < len(str(output))
        seen.append(scratch)
        return original(*args, **kwargs)

    monkeypatch.setattr(bench.voice, "render_narration", checked)
    bench.benchmark(output, sessions=1, seconds=6, worker_counts=[1], source_sha="a")
    assert seen and bench.os.environ["OCF_WORK_DIR"] == str(fixtures)


def test_fixture_identity_collision_and_corrupt_resume_fail_closed(fixtures):
    root = fixtures / "fixture"
    root.mkdir()
    bench.make_bed(root / "bed.wav", 6)
    config = {"seconds": 6, "source_sha": "a"}
    bench.render_fixture(root, 0, config)
    with pytest.raises(OCFError, match="identity collision"):
        bench.render_fixture(root, 0, {**config, "seconds": 7})
    target = root / "fixture-000/master.flac"
    target.write_bytes(b"corrupted")
    with pytest.raises(OCFError, match="resume integrity"):
        bench.render_fixture(root, 0, config)
    assert target.read_bytes() == b"corrupted"


def test_lossless_decode_validation_and_unexpected_failure_are_not_hidden(fixtures, monkeypatch):
    root = fixtures / "fixture"
    root.mkdir()
    bench.make_bed(root / "bed.wav", 6)
    monkeypatch.setattr(
        bench,
        "workspace_run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout=b"wrong samples"),
    )
    with pytest.raises(OCFError, match="changed PCM"):
        bench.batch(root, {"seconds": 6}, 1, 1, fail_id=None)
    assert not (root / "fixture-000/receipt.json").exists()
    assert bench.os.environ["OCF_WORK_DIR"] == str(fixtures)


@pytest.mark.parametrize(
    "extra",
    [
        ["--sessions", "0"],
        ["--seconds", "121"],
        ["--workers", "3"],
        ["--workers", "1", "1"],
        ["--profile", "--workers", "2"],
    ],
)
def test_cli_bounds_prevent_unbounded_work(monkeypatch, fixtures, extra):
    monkeypatch.setattr(sys, "argv", ["benchmark", "--output", str(fixtures / "audio"), *extra])
    with pytest.raises(SystemExit) as error:
        bench.main()
    assert error.value.code == 2


@pytest.mark.parametrize("profile", [False, True])
def test_cli_fingerprints_source_and_distinguishes_profile_overhead(
    monkeypatch, fixtures, capsys, profile
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark",
            "--output",
            str(fixtures / "audio"),
            "--workers",
            "1",
            *(["--profile"] if profile else []),
        ],
    )
    monkeypatch.setattr(
        bench.subprocess, "check_output", lambda argv, **kw: "a" * 40 if "rev-parse" in argv else ""
    )
    bench.main()
    report = json.loads(capsys.readouterr().out)
    assert report["profiled"] is profile
    assert report["source_sha"] == "a" * 40


def test_cli_refuses_dirty_measurement(monkeypatch, fixtures):
    monkeypatch.setattr(sys, "argv", ["benchmark", "--output", str(fixtures / "audio")])
    monkeypatch.setattr(bench.subprocess, "check_output", lambda *a, **kw: "dirty")
    with pytest.raises(OCFError, match="commit"):
        bench.main()


def test_synthetic_bed_uses_real_external_boundary_and_checks_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(bench.shutil, "which", lambda _: None)
    with pytest.raises(OCFError, match="requires ffmpeg"):
        bench.make_bed(tmp_path / "bed.wav", 6)
    monkeypatch.setattr(bench.shutil, "which", lambda _: "ffmpeg")
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=len(calls) - 1)

    monkeypatch.setattr(bench, "workspace_run", run)
    bench.make_bed(tmp_path / "bed.wav", 6)
    assert "lavfi" in calls[0] and "pcm_s16le" in calls[0]
    with pytest.raises(OCFError, match="generation failed"):
        bench.make_bed(tmp_path / "bed.wav", 6)
