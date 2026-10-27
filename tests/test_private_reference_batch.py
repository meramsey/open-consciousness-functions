import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import tools.render_private_reference_v4 as batch
from ocf_tools import indexes
from ocf_tools.utils import sha256_of_file
from tools.render_private_reference_v4 import _verified_export


@pytest.mark.unit
def test_batch_export_resume_requires_matching_session_report_and_all_hashes(tmp_path):
    source = tmp_path / "session-report.json"
    source.write_text('{"session":1}\n', encoding="utf-8")
    artifact = tmp_path / "verified.mp3"
    artifact.write_bytes(b"private-audio")

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "kind": "private-audition-export",
        "source_report": {"sha256": digest(source)},
        "artifacts": {
            "mp3": {
                "path": artifact.name,
                "size_bytes": artifact.stat().st_size,
                "sha256": digest(artifact),
            }
        },
    }
    output = tmp_path / "export"
    output.mkdir()
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (output / artifact.name).write_bytes(artifact.read_bytes())
    assert _verified_export(output, source)
    artifact_copy = output / artifact.name
    artifact_copy.write_bytes(b"altered")
    assert not _verified_export(output, source)
    artifact_copy.write_bytes(b"private-audio")
    source.write_text('{"session":2}\n', encoding="utf-8")
    assert not _verified_export(output, source)


def _session_fixture(directory: Path, function_id: str, template_id: str) -> Path:
    directory.mkdir(parents=True)
    (directory / "master.wav").write_bytes(b"disposable-wav-fixture")
    report = {
        "function_id": function_id,
        "title": "Disposable private session",
        "template": {"id": template_id},
        "artifacts": {
            "wav": {"path": "master.wav", "sha256": sha256_of_file(directory / "master.wav")}
        },
        "measurements": {
            "duration_seconds": 1,
            "sample_rate": 44100,
            "channels": 2,
            "clipped_sample_count": 0,
            "left_rms_dbfs": -10,
            "right_rms_dbfs": -10,
        },
        "background_continuity": {},
        "state_transitions": [],
        "mix": {"ending_fade_seconds": 1},
        "background_variant": "fixture",
        "dsp_profile": {},
        "narration_resources": [],
        "session_pacing_profile": {},
    }
    path = directory / "session-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _export_fixture(output: Path, source_report: Path) -> dict:
    output.mkdir(parents=True)
    receipts = {}
    for name, data in (
        ("fixture.flac", b"disposable-flac"),
        ("fixture.mp3", b"disposable-mp3"),
        ("timing.json", b"{}\n"),
    ):
        artifact = output / name
        artifact.write_bytes(data)
        receipts[name] = {
            "path": name,
            "size_bytes": artifact.stat().st_size,
            "sha256": sha256_of_file(artifact),
        }
    manifest = {
        "kind": "private-audition-export",
        "source_report": {"sha256": sha256_of_file(source_report)},
        "artifacts": {key: receipts[key] for key in ("fixture.flac", "fixture.mp3")},
        "listener_text": {"artifacts": {}, "timing_receipt": receipts["timing.json"]},
        "function_content": {"primary_command": "PLUS-DISPOSABLE-FIXTURE"},
    }
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


@pytest.mark.unit
def test_run_collection_reuses_verified_session_and_packages_one_new_fixture(monkeypatch, tmp_path):
    root = tmp_path / "private-work"
    continuity = root / "agent-continuity"
    continuity.mkdir(parents=True)
    recovered_id, rendered_id = "OCF-FND-001", "OCF-FND-002"
    recovered_report = _session_fixture(
        tmp_path / "recovered-session", recovered_id, "OCF-TPL-SESSION-HPLUS-LOCKED-004"
    )
    rendered_report = _session_fixture(
        tmp_path / "rendered-session", rendered_id, "fixture-template"
    )
    status_path = continuity / "REFERENCE_V4_V0_3_0_STATUS.json"
    status_path.write_text(
        json.dumps(
            {
                "functions": [
                    {
                        "function_id": recovered_id,
                        "session_report": str(recovered_report),
                        "status": "PENDING",
                    },
                    {"function_id": rendered_id, "session_report": None, "status": "PENDING"},
                ]
            }
        ),
        encoding="utf-8",
    )
    recovered_export = (
        root / "renders/amy-reference-v4-v0.3.0/verified-exports-final" / recovered_id
    )
    _export_fixture(recovered_export, recovered_report)

    monkeypatch.setattr(batch, "work_root", lambda: root)
    rendered_ids = []

    def render_many(function_ids, **kwargs):
        rendered_ids.extend(function_ids)
        kwargs["progress_callback"]({"phase": "function-start", "function_id": rendered_id})
        kwargs["progress_callback"]({"phase": "worker-progress", "function_id": rendered_id})
        kwargs["progress_callback"]({"phase": "function-rendered", "function_id": rendered_id})
        return {
            "results": [
                {
                    "function_id": rendered_id,
                    "status": "rendered",
                    "output_directory": str(rendered_report.parent),
                }
            ],
            "failed": 0,
            "blocked": 0,
        }

    monkeypatch.setattr(batch, "render_many", render_many)
    exported_outputs = []

    def export_audition(session, *, edition, output, **kwargs):
        source = Path(session) / "session-report.json"
        exported_outputs.append(output)
        return {"manifest": _export_fixture(output, source)}

    monkeypatch.setattr(batch, "export_audition", export_audition)
    monkeypatch.setattr(batch, "measure_ebur128", lambda _path: {"fixture": True})
    monkeypatch.setattr(batch, "attach_audio_quality", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(batch, "attach_build_provenance", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        batch, "load_voice_profiles", lambda: [{"id": "OCF-VOICE-FIXTURE", "model": {}}]
    )
    monkeypatch.setattr(
        batch,
        "discover_environment",
        lambda **_kwargs: {
            "tools": {
                "piper": {"runtime": {"python_version": "3.12.3", "package_version": "fixture"}}
            }
        },
    )

    def package_auditions(exports, output, *, resume):
        assert len(exports) == 2 and resume is False
        output.mkdir(parents=True)
        (output / "package.json").write_text("{}\n", encoding="utf-8")
        return {"package_path": str(output)}

    monkeypatch.setattr(batch, "package_auditions", package_auditions)
    monkeypatch.setattr(
        batch,
        "verify_package",
        lambda _path: {
            "artifacts": [{"path": "fixture"}],
            "sessions": [{"function_id": recovered_id}, {"function_id": rendered_id}],
        },
    )
    indexes = []
    monkeypatch.setattr(
        batch,
        "build_private_collection_index",
        lambda package, index, *, progress: indexes.append((package, index, progress)),
    )

    result = batch.run_collection(
        [recovered_id, rendered_id], voice="OCF-VOICE-FIXTURE", profile="fixture.yaml", workers=1
    )

    assert rendered_ids == [rendered_id]
    assert len(exported_outputs) == 1
    assert result["export_count"] == 2 and result["package"] is not None
    assert Path(result["package"]["package_path"], "package.json").is_file()
    assert len(indexes) == 1 and indexes[0][2] == status_path
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert all(
        row["status"] == "TECHNICALLY_VERIFIED_IN_PRIVATE_PACKAGE" for row in status["functions"]
    )
    assert status["verified_count"] == 2
    assert all(
        _verified_export(path, report)
        for path, report in (
            (recovered_export, recovered_report),
            (exported_outputs[0], rendered_report),
        )
    )


@pytest.mark.unit
def test_run_collection_records_failed_render_without_exporting_or_packaging(monkeypatch, tmp_path):
    root = tmp_path / "private-work"
    continuity = root / "agent-continuity"
    continuity.mkdir(parents=True)
    function_id = "OCF-FND-003"
    status_path = continuity / "REFERENCE_V4_V0_3_0_STATUS.json"
    status_path.write_text(
        json.dumps({"functions": [{"function_id": function_id, "status": "PENDING"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(batch, "work_root", lambda: root)
    monkeypatch.setattr(
        batch,
        "render_many",
        lambda _ids, **kwargs: (
            kwargs["progress_callback"](
                {
                    "phase": "function-failed",
                    "function_id": function_id,
                    "detail": "fixture failure",
                }
            )
            or {
                "results": [
                    {"function_id": function_id, "status": "failed", "error": "fixture failure"}
                ],
                "failed": 1,
                "blocked": 0,
            }
        ),
    )
    monkeypatch.setattr(
        batch, "export_audition", lambda *_args, **_kwargs: pytest.fail("no export expected")
    )
    monkeypatch.setattr(
        batch, "package_auditions", lambda *_args, **_kwargs: pytest.fail("no package expected")
    )

    result = batch.run_collection([function_id], voice="fixture", profile="fixture.yaml", workers=1)

    assert result["render"]["failed"] == 1
    assert result["export_count"] == 0 and result["package"] is None
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["functions"][0]["status"] == "FAILED"


@pytest.mark.unit
def test_batch_cli_filters_completed_functions_and_dispatches_only_pending(
    monkeypatch, tmp_path, capsys
):
    root = tmp_path / "private-work"
    continuity = root / "agent-continuity"
    continuity.mkdir(parents=True)
    status_path = continuity / "REFERENCE_V4_V0_3_0_STATUS.json"
    status_path.write_text(
        json.dumps(
            {
                "functions": [
                    {
                        "function_id": "OCF-FND-001",
                        "status": "TECHNICALLY_VERIFIED_IN_PRIVATE_PACKAGE",
                    },
                    {"function_id": "OCF-FND-002", "status": "PENDING"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(batch, "work_root", lambda: root)
    monkeypatch.setattr(
        indexes,
        "load_all_functions",
        lambda: [SimpleNamespace(id="OCF-FND-001"), SimpleNamespace(id="OCF-FND-002")],
    )
    calls = []
    monkeypatch.setattr(
        batch,
        "run_collection",
        lambda ids, **kwargs: (
            calls.append((ids, kwargs))
            or {"render": {"failed": 0, "blocked": 0}, "export_count": 0, "package": None}
        ),
    )

    assert batch.main(["--all", "--profile", "fixture.yaml", "--workers", "1"]) == 0
    assert calls == [
        (
            ["OCF-FND-002"],
            {
                "voice": "OCF-VOICE-9003",
                "profile": "fixture.yaml",
                "version": "0.3.0",
                "workers": 1,
                "fresh_synthesis": False,
            },
        )
    ]
    assert json.loads(capsys.readouterr().out)["render"]["failed"] == 0


@pytest.mark.unit
def test_batch_cli_returns_cleanly_when_every_function_is_complete_and_requires_selection(
    monkeypatch, tmp_path, capsys
):
    root = tmp_path / "private-work"
    continuity = root / "agent-continuity"
    continuity.mkdir(parents=True)
    (continuity / "REFERENCE_V4_V0_3_0_STATUS.json").write_text(
        json.dumps(
            {
                "functions": [
                    {
                        "function_id": "OCF-FND-001",
                        "status": "TECHNICALLY_VERIFIED_IN_PRIVATE_PACKAGE",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(batch, "work_root", lambda: root)
    monkeypatch.setattr(indexes, "load_all_functions", lambda: [SimpleNamespace(id="OCF-FND-001")])
    monkeypatch.setattr(batch, "run_collection", lambda *_a, **_k: pytest.fail("no pending render"))

    assert batch.main(["--all", "--profile", "fixture.yaml"]) == 0
    assert "already technically verified" in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:
        batch.main(["--profile", "fixture.yaml"])
    assert error.value.code == 2
