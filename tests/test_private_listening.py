"""Public synthetic checks for private delivery boundaries."""

import hashlib
import json

import pytest
from ocf_tools.learning_session import plan, verify_timing
from ocf_tools.listening_portal import Library, byte_range, regular_file
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration


def completed(root):
    folder = root / "edition"
    folder.mkdir()
    media = []
    for role, name in [
        ("audio", "audio.mp3"),
        ("master", "master.wav"),
        ("transcript", "text.txt"),
    ]:
        data = (role * 5).encode()
        (folder / name).write_bytes(data)
        media.append(
            {
                "role": role,
                "file": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
        )
    doc = {
        "status": "completed",
        "technical_verified": True,
        "title": "Synthetic",
        "edition": "1",
        "profile": "synthetic",
        "duration_seconds": 12,
        "media": media,
    }
    (folder / "listening.json").write_text(json.dumps(doc))
    return folder, doc


def test_discovery_integrity_and_notes(tmp_path):
    folder, _ = completed(tmp_path)
    library = Library(tmp_path)
    rows, files = library.discover()
    assert len(rows) == 1 and len(files) == 3
    library.save_notes(rows[0]["id"], "Compare closure with previous edition.")
    assert library.discover()[0][0]["notes"].startswith("Compare")
    (folder / "audio.mp3").write_bytes(b"corrupt")
    assert library.discover() == ([], {})


@pytest.mark.parametrize("name", ["../secret", "/secret", "a/b", "a\\b", ".", "..", ""])
def test_reject_arbitrary_paths(tmp_path, name):
    with pytest.raises(ValueError):
        regular_file(tmp_path, name)


def test_incomplete_and_symlink_never_listed(tmp_path):
    folder, doc = completed(tmp_path)
    doc["status"] = "rendering"
    (folder / "listening.json").write_text(json.dumps(doc))
    assert Library(tmp_path).discover() == ([], {})
    doc["status"] = "completed"
    (folder / "listening.json").write_text(json.dumps(doc))
    (folder / "audio.mp3").unlink()
    try:
        (folder / "audio.mp3").symlink_to(folder / "master.wav")
    except OSError:
        pytest.skip("OS does not permit test symlinks")
    assert Library(tmp_path).discover() == ([], {})


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, (0, 99, 200)),
        ("bytes=5-9", (5, 9, 206)),
        ("bytes=95-", (95, 99, 206)),
        ("bytes=-10", (90, 99, 206)),
        ("bytes=0-999", (0, 99, 206)),
    ],
)
def test_ranges(header, expected):
    assert byte_range(header, 100) == expected


@pytest.mark.parametrize(
    "header", ["bytes=100-", "bytes=9-1", "bytes=-0", "bytes=-", "bytes=0-1,4-5", "garbage"]
)
def test_invalid_ranges(header):
    with pytest.raises(ValueError):
        byte_range(header, 100)


def test_learning_is_standalone_with_full_practice():
    planned = plan()
    assert planned["practice_seconds"] == 510
    assert "function_id" not in planned["document"]
    assert set(planned["dsp"]["states"]) == {"focus-10", "focus-11"}
    with pytest.raises(OCFError, match="ledger"):
        verify_timing(planned["document"], {"event_timing": []})


@pytest.mark.parametrize("path_metadata_differs", [False, True])
def test_http_auth_ranges_and_notes(tmp_path, monkeypatch, path_metadata_differs):
    import base64
    import http.client
    import threading
    from http.server import ThreadingHTTPServer

    from ocf_tools.listening_portal import handler

    completed(tmp_path)
    if path_metadata_differs:
        from pathlib import Path
        from types import SimpleNamespace

        original_stat = Path.stat

        def path_stat(path, *args, **kwargs):
            info = original_stat(path, *args, **kwargs)
            if path.suffix == ".mp3":
                fields = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
                fields["st_ctime_ns"] += 100
                return SimpleNamespace(**fields)
            return info

        monkeypatch.setattr(Path, "stat", path_stat)
    auth = "Basic " + base64.b64encode(b"test:synthetic-password-for-tests").decode()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(Library(tmp_path), auth))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        connection.request("GET", "/catalog")
        result = connection.getresponse()
        assert result.status == 401
        result.read()
        connection.request("GET", "/catalog", headers={"Authorization": auth})
        result = connection.getresponse()
        catalog = json.loads(result.read())
        connection.request(
            "GET",
            catalog[0]["media"][0]["url"],
            headers={"Authorization": auth, "Range": "bytes=1-3"},
        )
        result = connection.getresponse()
        assert result.status == 206 and result.read() == b"udi"
        connection.request("GET", "/media/../../secret", headers={"Authorization": auth})
        result = connection.getresponse()
        assert result.status == 404
        result.read()
        connection.request(
            "POST",
            "/notes/" + catalog[0]["id"],
            body=json.dumps({"notes": "review"}),
            headers={"Authorization": auth, "X-OCF-Request": "notes"},
        )
        result = connection.getresponse()
        assert result.status == 200
        result.read()
        assert Library(tmp_path).discover()[0][0]["notes"] == "review"
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_native_speed_is_explicit_and_preserves_public_pacing():
    from ocf_tools.locale import iter_events
    from ocf_tools.narration_pacing import plan_event_pacing

    native = plan(native_speed=True)["document"]
    rates = {
        u["rate_scale"]
        for e in iter_events(native)
        if (p := plan_event_pacing(native, e))
        for u in p["units"]
    }
    assert rates == {1.0}
    normal = plan()["document"]
    assert any(
        u["rate_scale"] < 1
        for e in iter_events(normal)
        if (p := plan_event_pacing(normal, e))
        for u in p["units"]
    )


@pytest.mark.parametrize("malformed", [[], None, 3, "invalid"])
def test_malformed_manifest_does_not_break_discovery(tmp_path, malformed):
    folder, _ = completed(tmp_path)
    (folder / "listening.json").write_text(json.dumps(malformed))
    assert Library(tmp_path).discover() == ([], {})


def test_symlink_ancestor_rejected(tmp_path):
    directory = tmp_path / "real"
    directory.mkdir()
    (directory / "library").mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(directory, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit test symlinks")
    with pytest.raises(ValueError, match="symlink"):
        Library(alias / "library")


def test_malformed_notes_and_stale_temporary_are_recoverable(tmp_path):
    completed(tmp_path)
    library = Library(tmp_path)
    identity = library.discover()[0][0]["id"]
    (tmp_path / ("notes-" + identity + ".json")).write_text("[]")
    (tmp_path / ("notes-" + identity + ".tmp")).write_text("retained interrupted write")
    library.save_notes(identity, "new review")
    assert library.discover()[0][0]["notes"] == "new review"


def test_durable_model_cache_precedence(monkeypatch, tmp_path):
    from ocf_tools.voice_packs import model_cache_root

    monkeypatch.setenv("HF_HOME", str(tmp_path / "durable"))
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    assert model_cache_root() == tmp_path / "durable/hub"
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    assert model_cache_root() == tmp_path / "hub"


def synthetic_learning(document):
    from ocf_tools.locale import iter_events
    from ocf_tools.timing import schedule_timeline

    events = list(iter_events(document))
    durations = {e["id"]: 1.0 for e in events if e.get("text", "").strip()}
    rows = schedule_timeline(document, durations)
    by_id = {r["id"]: r for r in rows}
    return {
        "event_timing": rows,
        "semantic_dsp": {"transitions": [{"to": x} for x in ["focus-11", "focus-10"] * 3]},
        "narration_timing": {
            "measured": True,
            "cues": [
                {
                    "id": e["id"],
                    "source_ids": [e["id"]],
                    "spoken_text": e["text"],
                    "at": by_id[e["id"]]["at"],
                    "duration": 1.0,
                }
                for e in events
                if e.get("text", "").strip()
            ],
        },
    }


def test_learning_rejects_changed_holds_and_words():
    import copy

    document = plan()["document"]
    built = synthetic_learning(document)
    assert verify_timing(document, built)["visits"] == 3
    changed = copy.deepcopy(built)
    changed["event_timing"][3]["end"] += 1
    with pytest.raises(OCFError, match="anchors"):
        verify_timing(document, changed)
    changed = copy.deepcopy(built)
    changed["narration_timing"]["cues"][0]["spoken_text"] = "substituted wording"
    with pytest.raises(OCFError, match="wording"):
        verify_timing(document, changed)
    changed = copy.deepcopy(built)
    changed["semantic_dsp"]["transitions"].pop()
    with pytest.raises(OCFError, match="three complete"):
        verify_timing(document, changed)


def test_learning_publication_and_no_overwrite(tmp_path, monkeypatch):
    from contextlib import nullcontext

    from ocf_tools import learning_session as learning

    calls = []
    monkeypatch.setattr("ocf_tools.voice.resolve_backend", lambda *a, **k: {})
    monkeypatch.setattr("ocf_tools.speech_cache.voice_identity", lambda *a: {"synthetic": True})
    monkeypatch.setattr(
        "ocf_tools.semantic_dsp.dependency_identity", lambda *a: {"synthetic": True}
    )
    monkeypatch.setattr("ocf_tools.voice_packs.persistent_worker", lambda *a: nullcontext())
    monkeypatch.setattr(
        "ocf_tools.complete_session._probe_audio", lambda *a: {"sample_rate": 44100, "channels": 2}
    )
    monkeypatch.setattr(
        "ocf_tools.complete_session._stereo_metrics", lambda *a, **k: {"clipped_sample_count": 0}
    )
    monkeypatch.setattr(
        "ocf_tools.complete_session._verify_decode", lambda path: calls.append(path)
    )

    def build(*a, **kw):
        assert "function_id" not in kw["manifest_override"]
        built = synthetic_learning(kw["document_override"])
        built["master"] = {
            "file": "master.wav",
            "duration": max(row["end"] for row in built["event_timing"]) + 1,
        }
        (kw["out_root"] / "master.wav").write_bytes(b"public synthetic fixture")
        return built

    monkeypatch.setattr(learning.audio_build, "build", build)
    target = tmp_path / "published"
    result = learning.render(output=target, voice="synthetic", mix_profile={})
    assert result["status"] == "completed" and calls
    assert (target / "completion.json").is_file()
    assert all(not name.startswith(".") for name in result["artifacts"])
    for row in result["artifacts"].values():
        assert hashlib.sha256((target / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    with pytest.raises(OCFError, match="already exists"):
        learning.render(output=target, voice="synthetic", mix_profile={})


def test_private_defaults_are_explicit_and_schema_validated(tmp_path):
    from ocf_tools.private_session import load_defaults

    config = tmp_path / "private.json"
    config.write_text(
        json.dumps({"voice": "synthetic", "mix_profile": "mix.yaml", "native_speed": True})
    )
    assert load_defaults(config)["mix_profile"] == str(tmp_path / "mix.yaml")
    config.write_text(
        json.dumps(
            {
                "voice": "synthetic",
                "mix_profile": "mix.yaml",
                "environment": {"UNAUTHORIZED": "value"},
            }
        )
    )
    with pytest.raises(OCFError, match="configuration"):
        load_defaults(config)


def test_portal_reconciliation_preserves_live_ownership(tmp_path, monkeypatch):
    from ocf_tools import listening_portal_worker as worker

    status = tmp_path / "status.json"
    assert worker.reconcile(status)["safe_to_run"]
    identity = {"pid": 123, "start_ticks": "stable"}
    status.write_text(json.dumps({"server_identity": identity}))
    monkeypatch.setattr(worker, "process_identity", lambda pid: identity)
    assert not worker.reconcile(status)["safe_to_run"]
    monkeypatch.setattr(
        worker, "process_identity", lambda pid: {"pid": pid, "start_ticks": "reused"}
    )
    assert worker.reconcile(status)["safe_to_run"]


def test_unhealthy_portal_worker_terminates_child(tmp_path, monkeypatch):
    from ocf_tools import listening_portal_worker as worker

    config = tmp_path / "config.json"
    config.write_text("{}")
    status = tmp_path / "status.json"

    class Child:
        pid = 456
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def wait(self, timeout):
            return self.returncode

    child = Child()
    monkeypatch.setattr(worker.subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(worker, "check_health", lambda config: False)
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(worker, "process_identity", lambda pid: {"pid": pid})
    monkeypatch.setattr(
        worker.sys, "argv", ["worker", "run", "--config", str(config), "--status", str(status)]
    )
    assert worker.main() == 1
    assert child.returncode == -15
    assert json.loads(status.read_text())["sessions"]["portal"]["checks"] == 3


def test_portal_rejects_mutation_during_hash(tmp_path, monkeypatch):
    import os

    from ocf_tools import listening_portal as portal

    folder, _ = completed(tmp_path)
    audio = folder / "audio.mp3"
    original = portal.hashlib.sha256
    changed = False

    class Hash:
        def __init__(self, *args):
            self.inner = original(*args)

        def update(self, block):
            nonlocal changed
            self.inner.update(block)
            if not changed:
                changed = True
                info = audio.stat()
                audio.write_bytes(b"X" * info.st_size)
                os.utime(audio, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000000))

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(portal.hashlib, "sha256", Hash)
    assert Library(tmp_path).discover() == ([], {})
    assert changed


def test_portal_rejects_same_bytes_replacement_after_discovery(tmp_path):
    import base64
    import http.client
    import os
    import threading
    from http.server import ThreadingHTTPServer

    from ocf_tools.listening_portal import handler

    folder, _ = completed(tmp_path)

    class ReplacedLibrary(Library):
        def discover(self):
            rows, files = super().discover()
            source = folder / "audio.mp3"
            replacement = folder / "replacement.mp3"
            replacement.write_bytes(source.read_bytes())
            os.replace(replacement, source)
            return rows, files

    library = ReplacedLibrary(tmp_path)
    auth = "Basic " + base64.b64encode(b"test:synthetic-password-for-tests").decode()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(library, auth))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    connection = http.client.HTTPConnection(*server.server_address, timeout=3)
    try:
        connection.request("GET", "/catalog", headers={"Authorization": auth})
        catalog = json.loads(connection.getresponse().read())
        connection.request(
            "GET",
            catalog[0]["media"][0]["url"],
            headers={"Authorization": auth, "Range": "bytes=1-3"},
        )
        response = connection.getresponse()
        assert response.status == 416
        response.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
