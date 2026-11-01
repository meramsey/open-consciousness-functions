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


def test_checkout_without_migration_record_is_unchanged(tmp_path):
    assert history.predecessor(tmp_path, "locales/en-US/manifest.yaml", "original") == "original"
