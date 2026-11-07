"""Windows CRT sharing denials must not hide permanent errors or allow duplicates."""

import errno
import json
from types import SimpleNamespace

import pytest
from ocf_tools import dev_jobs as jobs

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("winerror", [None, 5, 32, 33])
def test_windows_state_open_retries_native_and_crt_sharing_errors(monkeypatch, winerror):
    error = PermissionError(errno.EACCES, "state file sharing denial")
    if winerror is not None:
        error.winerror = winerror
    reads, sleeps = [], []

    def read_text(**kwargs):
        reads.append(kwargs)
        if len(reads) <= 2:
            raise error
        return '{"state": "running", "heartbeat": 123}'

    monkeypatch.setattr(jobs, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(jobs.time, "sleep", sleeps.append)
    assert jobs._read_state(SimpleNamespace(read_text=read_text)) == {
        "state": "running",
        "heartbeat": 123,
    }
    assert len(reads) == 3 and sleeps == [0.01, 0.02]


def test_permanent_windows_crt_denial_exhausts_bound_and_propagates_original(monkeypatch):
    error = PermissionError(errno.EACCES, "permanent ACL denial")
    calls, sleeps = [], []

    def denied(**kwargs):
        calls.append(kwargs)
        raise error

    monkeypatch.setattr(jobs, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(jobs.time, "sleep", sleeps.append)
    with pytest.raises(PermissionError) as caught:
        jobs._read_state(SimpleNamespace(read_text=denied))
    assert caught.value is error
    assert len(calls) == 8
    assert sleeps == [0.01, 0.02, 0.04, 0.08, 0.16, 0.25, 0.25]


@pytest.mark.parametrize(
    "platform,code,native",
    [
        ("posix", errno.EACCES, None),
        ("nt", None, None),
        ("nt", errno.EACCES, 87),
    ],
)
def test_unclassified_denial_is_not_retried(monkeypatch, platform, code, native):
    error = PermissionError(code, "not a classified sharing denial")
    if native is not None:
        error.winerror = native
    monkeypatch.setattr(jobs, "os", SimpleNamespace(name=platform))
    monkeypatch.setattr(jobs.time, "sleep", lambda _: pytest.fail("unexpected retry"))

    def denied(**kwargs):
        raise error

    with pytest.raises(PermissionError) as caught:
        jobs._read_state(SimpleNamespace(read_text=denied))
    assert caught.value is error


@pytest.mark.parametrize(
    "error", [FileNotFoundError("missing"), json.JSONDecodeError("invalid", "x", 0)]
)
def test_missing_or_corrupt_state_is_not_retried(monkeypatch, error):
    monkeypatch.setattr(jobs.time, "sleep", lambda _: pytest.fail("unexpected retry"))

    def invalid(**kwargs):
        raise error

    with pytest.raises(type(error)) as caught:
        jobs._read_state(SimpleNamespace(read_text=invalid))
    assert caught.value is error


def test_unreadable_existing_job_fails_closed_before_duplicate_dispatch(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(jobs, "validate_request", lambda operation, args: args)
    monkeypatch.setattr(jobs, "input_identity", lambda *args: {})
    root = jobs.directory("a" * 32)
    root.mkdir(parents=True)
    (root / "request.json").write_text('{"request_hash": "existing"}')
    error = PermissionError(errno.EACCES, "existing state is unreadable")

    def unreadable(identifier):
        raise error

    monkeypatch.setattr(jobs, "status", unreadable)
    with pytest.raises(PermissionError) as caught:
        jobs.start("tests", {"full": True, "paths": []})
    assert caught.value is error
    assert list(root.parent.glob("*/request.json")) == [root / "request.json"]
