"""Localized structural projections fail closed without mutating historical ledgers."""

import hashlib
import json

import pytest
from ocf_tools import locale_history as history
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def fixture_ledger(tmp_path, monkeypatch):
    active = tmp_path / "locales/en-US/OCF-EMO-003-Empathize.yaml"
    active.parent.mkdir(parents=True)
    active.write_text("exact active narration\n", encoding="utf-8")
    before = "historical manifest\n"
    after = "active manifest\n"
    data = {
        "files": {
            "locales/en-US/manifest.yaml": {
                "before": before,
                "before_sha256": history._sha(before),
                "after_sha256": history._sha(after),
            }
        },
        "active_resources": {
            str(active.relative_to(tmp_path)): hashlib.sha256(active.read_bytes()).hexdigest()
        },
    }
    path = tmp_path / history.LEDGER
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(history, "LEDGER_SHA256", history._sha(path.read_text()))
    return path, active, before, after


def test_exact_predecessor_and_successor_are_idempotent(tmp_path, monkeypatch):
    _, _, before, after = fixture_ledger(tmp_path, monkeypatch)
    name = "locales/en-US/manifest.yaml"
    assert history.predecessor(tmp_path, name, after) == before
    assert history.predecessor(tmp_path, name, before) == before
    assert history.predecessor(tmp_path, "unrelated.yaml", "untouched") == "untouched"


def test_mutated_active_narration_cannot_be_projected_as_history(tmp_path, monkeypatch):
    _, active, _, after = fixture_ledger(tmp_path, monkeypatch)
    active.write_text("unauthorized edit", encoding="utf-8")
    with pytest.raises(OCFError, match="active source drift"):
        history.predecessor(tmp_path, "locales/en-US/manifest.yaml", after)


def test_unknown_manifest_and_mutated_ledger_are_rejected(tmp_path, monkeypatch):
    path, _, _, after = fixture_ledger(tmp_path, monkeypatch)
    with pytest.raises(OCFError, match="successor source drift"):
        history.predecessor(tmp_path, "locales/en-US/manifest.yaml", "unknown")
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(OCFError, match="immutable .* ledger drift"):
        history.predecessor(tmp_path, "locales/en-US/manifest.yaml", after)


def test_missing_successor_is_not_silently_replaced_by_history(tmp_path, monkeypatch):
    _, active, _, after = fixture_ledger(tmp_path, monkeypatch)
    active.unlink()
    with pytest.raises(OCFError, match="missing or unsafe"):
        history.predecessor(tmp_path, "locales/en-US/manifest.yaml", after)


def test_active_resource_hash_preserves_crlf_bytes_on_every_platform(tmp_path, monkeypatch):
    path, active, before, after = fixture_ledger(tmp_path, monkeypatch)
    active.write_bytes(b"exact active narration\r\n")
    data = json.loads(path.read_text())
    name = next(iter(data["active_resources"]))
    data["active_resources"][name] = hashlib.sha256(active.read_bytes()).hexdigest()
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(history, "LEDGER_SHA256", history._sha(path.read_text()))
    assert history.predecessor(tmp_path, "locales/en-US/manifest.yaml", after) == before


def test_checkout_without_migration_record_is_unchanged(tmp_path):
    assert history.predecessor(tmp_path, "locales/en-US/manifest.yaml", "original") == "original"


def test_consolidation_retains_exact_original_and_rechecks_cached_ledger(tmp_path, monkeypatch):
    name = "locales/en-US/hplus-OCF-FND-001.yaml"
    before = "entries:\n  fixture.optional:\n    text: Exact speech.\n"
    after = "function_id: OCF-FND-001\n" + before
    data = {
        "files": {
            name: {
                "before": before,
                "before_sha256": history._sha(before),
                "after_sha256": history._sha(after),
            }
        }
    }
    path = tmp_path / history.CONSOLIDATION
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data))
    monkeypatch.setattr(history, "CONSOLIDATION_SHA256", history._sha(path.read_text()))
    assert history.before_consolidation(tmp_path, name, after) == before
    assert history.before_consolidation(tmp_path, name, before) == before
    assert history.before_consolidation(tmp_path, "unrelated.yaml", "unchanged") == "unchanged"
    with pytest.raises(OCFError, match="successor source drift"):
        history.before_consolidation(tmp_path, name, after + "unknown edit")
    data["files"][name]["before"] = "tampered predecessor"
    path.write_text(json.dumps(data))
    with pytest.raises(OCFError, match="immutable localized consolidation ledger drift"):
        history.before_consolidation(tmp_path, name, after)


def test_structural_replay_accepts_only_exact_independently_pinned_predecessors(
    tmp_path, monkeypatch
):
    name = "locales/en-US/commands.yaml"
    archive = tmp_path / "function-content/editorial/historical-locales/004/en-US/commands.yaml"
    archive.parent.mkdir(parents=True)
    archive.write_text("pre-retirement bytes\n", encoding="utf-8", newline="\n")
    current = "word-free historical reference\n"
    earlier = "older independently verified predecessor\n"
    retired = {
        "files": {
            name: {
                "archive": archive.relative_to(tmp_path).as_posix(),
                "before_sha256": history._sha(archive.read_text()),
                "after_sha256": history._sha(current),
            }
        }
    }
    retirement = tmp_path / history.RETIREMENT
    retirement.parent.mkdir(parents=True, exist_ok=True)
    retirement.write_text(json.dumps(retired))
    monkeypatch.setattr(history, "RETIREMENT_SHA256", history._sha(retirement.read_text()))
    old = tmp_path / history.LEDGER
    old.write_text(
        json.dumps({"files": {name: {"before": earlier, "before_sha256": history._sha(earlier)}}})
    )
    monkeypatch.setattr(history, "LEDGER_SHA256", history._sha(old.read_text()))
    assert history.before_structural(tmp_path, name, current) == archive.read_text()
    assert history.before_structural(tmp_path, name, earlier) == earlier
    with pytest.raises(OCFError, match="successor source drift"):
        history.before_structural(tmp_path, name, "arbitrary changed text")
    old.write_text("tampered older ledger")
    with pytest.raises(OCFError, match="immutable"):
        history.before_structural(tmp_path, name, earlier)
