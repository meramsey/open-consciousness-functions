"""Virtual historical paths fail closed without requiring active-looking stubs."""

import hashlib
import json

import pytest
from ocf_tools import locale_history as history
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_record(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return digest(path.read_bytes())


@pytest.fixture
def virtual(tmp_path, monkeypatch):
    name = "locales/en-US/hplus-OCF-COG-001.yaml"
    archive = "function-content/editorial/historical-locales/005/en-US/old.yaml"
    raw = b"locale: en-US\r\nentries:\r\n  example.body: Exact old bytes\r\n"
    path = tmp_path / archive
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    row = {"archive": archive, "before_sha256": digest(raw), "after_sha256": digest(b"stub")}
    checksum = write_record(tmp_path, history.FILENAMES, {"files": {name: row}})
    monkeypatch.setattr(history, "FILENAMES_SHA256", checksum)
    data = {
        "files": {
            name: {
                "ledger": history.FILENAMES,
                "archive": archive,
                "sha256": digest(raw),
                "stub_sha256": digest(b"stub"),
            }
        }
    }
    checksum = write_record(tmp_path, history.RESOURCE_MAP, data)
    monkeypatch.setattr(history, "RESOURCE_MAP_SHA256", checksum)
    return tmp_path, name, archive, raw, data


def test_replay_without_physical_stub_preserves_crlf(virtual):
    root, name, archive, raw, _ = virtual
    assert not (root / name).exists()
    text = history.read_logical(root, name)
    assert text.encode() == raw
    assert history.before_structural(root, name, text).encode() == raw
    assert (root / archive).read_bytes() == raw


def test_modified_archive_and_present_modified_stub_are_rejected(virtual):
    root, name, archive, raw, _ = virtual
    (root / archive).write_bytes(raw + b"drift")
    with pytest.raises(OCFError, match="archive drift"):
        history.read_logical(root, name)
    (root / archive).write_bytes(raw)
    (root / name).parent.mkdir(parents=True)
    (root / name).write_bytes(b"drift")
    with pytest.raises(OCFError, match="successor source drift"):
        history.read_logical(root, name)
    (root / name).write_bytes(b"stub")
    assert history.read_logical(root, name).encode() == raw


@pytest.mark.parametrize(
    "name", ["../outside", "/absolute", "a/../b", "a//b", "a/./b", "C:/escape", "a\\b", ""]
)
def test_unsafe_logical_paths_rejected(virtual, name):
    with pytest.raises(OCFError, match="unsafe"):
        history.read_logical(virtual[0], name)


def test_unknown_missing_path_and_missing_archive_rejected(virtual):
    root, name, archive, _, _ = virtual
    with pytest.raises(OCFError, match="unknown"):
        history.read_logical(root, "locales/en-US/unknown.yaml")
    (root / archive).unlink()
    with pytest.raises(OCFError, match="missing historical"):
        history.read_logical(root, name)


def test_map_and_ledger_drift_rejected_even_after_cache_warmup(virtual):
    root, name, _, _, _ = virtual
    history.read_logical(root, name)
    path = root / history.FILENAMES
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(OCFError, match="ledger drift"):
        history.read_logical(root, name)
    path.write_bytes(original)
    path = root / history.RESOURCE_MAP
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(OCFError, match="ledger drift"):
        history.read_logical(root, name)


def test_archive_collision_and_identity_mismatch_rejected(virtual, monkeypatch):
    root, name, _, _, data = virtual
    data["files"]["locales/en-US/duplicate.yaml"] = data["files"][name].copy()
    monkeypatch.setattr(
        history, "RESOURCE_MAP_SHA256", write_record(root, history.RESOURCE_MAP, data)
    )
    with pytest.raises(OCFError, match="collision"):
        history.read_logical(root, name)
    del data["files"]["locales/en-US/duplicate.yaml"]
    data["files"][name]["sha256"] = "0" * 64
    monkeypatch.setattr(
        history, "RESOURCE_MAP_SHA256", write_record(root, history.RESOURCE_MAP, data)
    )
    with pytest.raises(OCFError, match="identity mismatch"):
        history.read_logical(root, name)


def test_archive_parent_symlink_and_logical_parent_symlink_rejected(virtual):
    root, name, archive, _, _ = virtual
    parent = (root / archive).parent
    moved = parent.with_name("moved")
    parent.rename(moved)
    try:
        parent.symlink_to(moved, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    with pytest.raises(OCFError, match="symlink"):
        history.read_logical(root, name)
    parent.unlink()
    moved.rename(parent)
    (root / "locales").symlink_to(moved, target_is_directory=True)
    with pytest.raises(OCFError, match="symlink"):
        history.read_logical(root, name)
