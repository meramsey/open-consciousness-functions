"""Exclusive publication must win or fail without exposing partial text."""

import errno
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from ocf_tools import paths, utils

pytestmark = pytest.mark.unit


@pytest.fixture
def target(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    return tmp_path / "output" / "record.txt"


@pytest.mark.parametrize("cross_device", [False, True])
@pytest.mark.parametrize("competing", [False, True])
@pytest.mark.parametrize("binary", [False, True])
def test_exclusive_publication_is_complete_and_preserves_late_creator(
    monkeypatch, target, cross_device, competing, binary
):
    content = "Complete café — 日本語\n" * 100
    payload = b"\xff\x00%PDF binary\n" * 100 if binary else content.encode("utf-8")
    writer = utils.write_bytes_atomic if binary else utils.write_text_atomic
    link = os.link
    calls = []

    def publish(source, destination):
        calls.append(Path(source))
        assert Path(source).read_bytes() == payload
        if cross_device and len(calls) == 1:
            assert not target.exists()
            raise OSError(errno.EXDEV, "different filesystem")
        if cross_device:
            assert Path(source).parent == target.parent
        assert not target.exists()
        if competing:
            target.write_text("concurrent human data\n", encoding="utf-8")
        return link(source, destination)

    monkeypatch.setattr(utils.os, "link", publish)
    if competing:
        with pytest.raises(utils.OCFFileExistsError):
            writer(target, payload if binary else content, overwrite=False)
        assert target.read_text() == "concurrent human data\n"
    else:
        writer(target, payload if binary else content, overwrite=False)
        assert target.read_bytes() == payload
    assert len(calls) == (2 if cross_device else 1)
    assert list(target.parent.iterdir()) == [target]
    assert list(paths.work_path("tmp").iterdir()) == []


def test_competing_creator_after_initial_check_is_never_replaced(monkeypatch, target):
    sync = os.fsync

    def sync_then_compete(descriptor):
        sync(descriptor)
        target.write_text("human version\n")

    monkeypatch.setattr(utils.os, "fsync", sync_then_compete)
    with pytest.raises(utils.OCFFileExistsError):
        utils.write_text_atomic(target, "machine version\n", overwrite=False)
    assert target.read_text() == "human version\n"
    assert list(paths.work_path("tmp").iterdir()) == []


def test_concurrent_exclusive_writers_have_exactly_one_winner(monkeypatch, target):
    barrier = threading.Barrier(8)
    sync = os.fsync

    def synchronize(descriptor):
        sync(descriptor)
        barrier.wait(timeout=10)

    monkeypatch.setattr(utils.os, "fsync", synchronize)

    def write(index):
        text = f"writer {index} — café\n" * 100
        try:
            utils.write_text_atomic(target, text, overwrite=False)
            return text
        except utils.OCFFileExistsError:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        winners = [text for text in executor.map(write, range(8)) if text is not None]
    assert winners == [target.read_text(encoding="utf-8")]
    assert list(paths.work_path("tmp").iterdir()) == []


@pytest.mark.parametrize("code", [errno.EPERM, errno.ENOSYS, errno.EOPNOTSUPP])
def test_unsupported_exclusive_publication_fails_closed_and_cleans(monkeypatch, target, code):
    def unsupported(*args):
        raise OSError(code, "hard links unsupported")

    monkeypatch.setattr(utils.os, "link", unsupported)
    with pytest.raises(utils.OCFError, match="atomic no-overwrite"):
        utils.write_text_atomic(target, "complete\n", overwrite=False)
    assert not target.exists()
    assert list(target.parent.iterdir()) == []
    assert list(paths.work_path("tmp").iterdir()) == []


def test_dangling_symlink_is_also_an_existing_target(target):
    target.parent.mkdir()
    try:
        target.symlink_to(target.parent / "missing")
    except OSError:
        pytest.skip("symlink creation unavailable on this platform")
    with pytest.raises(utils.OCFFileExistsError):
        utils.write_text_atomic(target, "new", overwrite=False)
    assert target.is_symlink()
    assert not target.exists()


def test_overwrite_true_still_replaces_complete_utf8(target):
    utils.write_text_atomic(target, "old\n")
    utils.write_text_atomic(target, "new café\n", overwrite=True)
    assert target.read_bytes() == "new café\n".encode()
    assert list(paths.work_path("tmp").iterdir()) == []


@pytest.mark.parametrize(
    "writer,invalid",
    [
        (utils.write_text_atomic, b"\xff"),
        (utils.write_bytes_atomic, "not bytes"),
    ],
)
def test_text_and_binary_writers_keep_their_input_contract(target, writer, invalid):
    with pytest.raises(TypeError):
        writer(target, invalid, overwrite=False)
    assert not target.exists()
    assert not target.parent.exists()
