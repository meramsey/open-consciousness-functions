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


def test_physical_text_and_explicit_byte_fingerprint_read_modes(virtual):
    root = virtual[0]
    name = "functions/cognition/current.yaml"
    path = root / name
    path.parent.mkdir(parents=True)
    path.write_bytes(b"exact text\r\n")
    assert history.read_logical(root, name) == "exact text\n"
    assert history.read_logical(root, name, preserve_newlines=True).encode() == b"exact text\r\n"


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


@pytest.fixture
def overlay(virtual, monkeypatch):
    import yaml

    root, _, _, _, data = virtual
    name = "locales/en-US/OCF-EMO-003-Empathize.yaml"
    archive = "function-content/editorial/historical-locales/006/en-US/snapshot.yaml"
    original = {
        "title": {"text": "Fixture", "status": "canonical"},
        "description": {"text": "Approved fixture description.", "status": "reviewed"},
        "activation": {"command_id": "fixture", "spoken_cue": {"text": "Exact cue"}},
        "entries": {"fixture.body": {"text": "Exact narration.\n"}},
        "tags": [],
        "common_uses": [],
        "relationships": {
            "related_functions": [
                {"function_id": "target", "description": {"text": "Exact approved rationale."}}
            ],
            "complementary_functions": [],
        },
    }
    raw = yaml.safe_dump(original).replace("\n", "\r\n").encode()
    target = root / archive
    target.parent.mkdir(parents=True)
    target.write_bytes(raw)
    data["discovery_overlays"] = {name: {"archive": archive, "sha256": digest(raw)}}
    monkeypatch.setattr(
        history, "RESOURCE_MAP_SHA256", write_record(root, history.RESOURCE_MAP, data)
    )
    return root, name, target, raw, original


def test_discovery_only_overlay_replays_exact_bytes_and_rejects_archive_drift(overlay):
    import yaml

    root, name, archive, raw, source = overlay
    source["tags"] = [{"text": "draft-tag", "status": "draft"}]
    source["common_uses"] = [{"text": "Draft use.", "status": "draft"}]
    source["relationships"]["proposals"] = [{"status": "draft"}]
    text = yaml.safe_dump(source)
    assert history.before_structural(root, name, text).encode() == raw
    archive.write_bytes(raw + b"drift")
    with pytest.raises(OCFError, match="archive drift"):
        history.before_structural(root, name, text)


@pytest.mark.parametrize(
    "field",
    [
        "narration",
        "title-status",
        "description-status",
        "activation",
        "approved-link",
        "malformed",
        "null-relationships",
        "list-relationships",
    ],
)
def test_overlay_cannot_hide_protected_changes_or_malformed_sources(overlay, field):
    import yaml

    root, name, _, _, source = overlay
    if field == "narration":
        source["entries"]["fixture.body"]["text"] += " changed"
    elif field == "title-status":
        source["title"]["status"] = "draft"
    elif field == "description-status":
        source["description"]["status"] = "draft"
    elif field == "activation":
        source["activation"]["spoken_cue"]["text"] = "Changed cue"
    elif field == "approved-link":
        source["relationships"]["related_functions"][0]["description"]["text"] = "Changed rationale"
    elif field == "null-relationships":
        source["relationships"] = None
    elif field == "list-relationships":
        source["relationships"] = []
    text = "[invalid YAML" if field == "malformed" else yaml.safe_dump(source)
    with pytest.raises(OCFError, match="discovery successor"):
        history.before_structural(root, name, text)
