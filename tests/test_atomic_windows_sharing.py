"""Atomic publication retries preserve complete bytes and exclusive output rules."""

import errno

import pytest
from ocf_tools import utils

pytestmark = pytest.mark.unit


def sharing_error(code):
    error = PermissionError(errno.EACCES, "synthetic Windows sharing denial")
    error.winerror = code
    return error


@pytest.mark.parametrize("code", [5, 32, 33])
def test_transient_windows_sharing_retries_same_complete_source(tmp_path, monkeypatch, code):
    source, target = tmp_path / "complete.tmp", tmp_path / "state.json"
    source.write_bytes(b'{"state":"canceled"}\n')
    target.write_bytes(b'{"state":"running"}\n')
    calls, sleeps = [], []

    def publish(src, dst):
        calls.append((src, dst))
        assert src.read_bytes() == b'{"state":"canceled"}\n'
        if len(calls) < 3:
            assert dst.read_bytes() == b'{"state":"running"}\n'
            raise sharing_error(code)
        src.replace(dst)

    monkeypatch.setattr(utils.time, "sleep", sleeps.append)
    utils._publish_complete(publish, source, target, overwrite=True)
    assert len(calls) == 3 and sleeps == [0.01, 0.02]
    assert target.read_bytes() == b'{"state":"canceled"}\n'


def test_permanent_windows_denial_is_bounded_and_preserves_error(monkeypatch):
    error = sharing_error(5)
    calls, sleeps = [], []

    def denied(*args):
        calls.append(args)
        raise error

    monkeypatch.setattr(utils.time, "sleep", sleeps.append)
    with pytest.raises(PermissionError) as caught:
        utils._publish_complete(denied, "source", "target", overwrite=True)
    assert caught.value is error
    assert len(calls) == 8 and len(sleeps) == 7 and sum(sleeps) < 1


@pytest.mark.parametrize(
    "overwrite,error",
    [
        (False, sharing_error(5)),
        (False, FileExistsError()),
        (True, PermissionError(errno.EACCES, "ordinary permission denial")),
        (True, OSError(errno.EXDEV, "different filesystem")),
    ],
)
def test_exclusive_outputs_and_nonsharing_errors_are_never_retried(monkeypatch, overwrite, error):
    calls = []

    def denied(*args):
        calls.append(args)
        raise error

    monkeypatch.setattr(utils.time, "sleep", lambda _: pytest.fail("must not retry"))
    with pytest.raises(OSError) as caught:
        utils._publish_complete(denied, "source", "target", overwrite=overwrite)
    assert caught.value is error and len(calls) == 1
