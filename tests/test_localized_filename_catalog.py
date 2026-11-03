"""Catalog-wide L4 execution on an isolated fixture, never the active source."""

import json
import shutil

import pytest
from ocf_tools import audio_defaults, locale_history
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocaleCatalog
from ocf_tools.localized_filenames import apply_filenames
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration


def test_execute_all_58_preserves_speech_and_hplus015_logical_identities(tmp_path, monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    records = load_all_functions()
    shutil.copytree(REPO_ROOT / "functions", tmp_path / "functions")
    shutil.copytree(REPO_ROOT / "locales", tmp_path / "locales")
    # Reconstruct the exact pre-L4 fixture from the checked path map, rather
    # than expecting the now-renamed active source to still use old filenames.
    predecessor_map = json.loads((REPO_ROOT / locale_history.FILENAMES).read_text())
    for name, row in predecessor_map["files"].items():
        (tmp_path / name).write_bytes((REPO_ROOT / row["archive"]).read_bytes())
    for name in predecessor_map["created_resources"]:
        if name not in predecessor_map["files"]:
            (tmp_path / name).unlink()
    editorial = tmp_path / "function-content/editorial"
    editorial.mkdir(parents=True)
    for name in (
        locale_history.LEDGER,
        locale_history.CONSOLIDATION,
        locale_history.AUTHORITY,
        locale_history.RETIREMENT,
    ):
        target = tmp_path / name
        target.write_bytes((REPO_ROOT / name).read_bytes())
    shutil.copytree(
        REPO_ROOT / "function-content/editorial/historical-locales/004",
        editorial / "historical-locales/004",
    )
    # Copy only the declared engineering dependencies, not generated audio,
    # caches, recordings, references or private assets.
    for lock_file in (REPO_ROOT / "audio/defaults").glob("*.json"):
        target = tmp_path / lock_file.relative_to(REPO_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(lock_file.read_bytes())
    lock = json.loads((tmp_path / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-015.json").read_text())
    for name in lock["files"]:
        target = tmp_path / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(locale_history.read_logical(REPO_ROOT, name).encode("utf-8"))
    before = LocaleCatalog(tmp_path / "locales", function_records=lambda: records)
    assert before.problems == []
    raw = {
        key: (entry.text, entry.version, entry.status)
        for key, entry in before.require("en-US").entries.items()
    }
    speech = {
        key: before.resource(key, "en-US", domain="narration", fallback=False)[0].text
        for key, entry in before.require("en-US").entries.items()
        if entry.domain == "narration"
    }
    receipt = apply_filenames(tmp_path)
    assert receipt["count"] == 58 and receipt["historical_destinations_reused"] == 1
    monkeypatch.setattr(locale_history, "FILENAMES_SHA256", receipt["ledger_sha256"])
    after = LocaleCatalog(tmp_path / "locales", function_records=lambda: records)
    assert after.problems == []
    assert len(after.require("en-US").localized_function_files) == 58
    assert all(
        filename.startswith(identity + "-")
        for identity, filename in after.require("en-US").localized_function_files.items()
    )
    assert raw == {
        key: (entry.text, entry.version, entry.status)
        for key, entry in after.require("en-US").entries.items()
    }
    assert speech == {
        key: after.resource(key, "en-US", domain="narration", fallback=False)[0].text
        for key in speech
    }
    monkeypatch.setattr(audio_defaults, "REPO_ROOT", tmp_path)
    assert (
        audio_defaults.check_lock(tmp_path / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-015.json")
        == lock
    )
    ledger = json.loads((tmp_path / locale_history.FILENAMES).read_text())
    for row in ledger["mapping"]:
        assert locale_history.before_structural(
            tmp_path, row["old_path"], (tmp_path / row["old_path"]).read_text()
        )
    assert apply_filenames(tmp_path)["status"] == "already-renamed; no writes"
