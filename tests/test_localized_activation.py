"""L2 application safety without production data, audio or subprocesses."""

import json

import pytest
from ocf_tools.localized_activation import LEDGER, activate, digest
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def fixture_plan(tmp_path):
    name = "locales/en-US/hplus-OCF-AAA-001.yaml"
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    path.write_text("exact predecessor\n", encoding="utf-8")
    (tmp_path / LEDGER).parent.mkdir(parents=True)
    return path, {"count": 1, "outputs": {name: "exact successor\n"}, "compatibility": {}}


def test_activation_preserves_preimage_and_is_idempotent(tmp_path):
    path, preview = fixture_plan(tmp_path)
    old = tmp_path / "locales/en-US/old-metadata.yaml"
    old.write_text("preserve compatibility source")
    receipt = activate(preview, tmp_path)
    ledger = json.loads((tmp_path / LEDGER).read_text())
    row = ledger["files"][path.relative_to(tmp_path).as_posix()]
    assert row["before"] == "exact predecessor\n"
    assert row["before_sha256"] == digest(row["before"])
    assert path.read_text() == "exact successor\n"
    assert old.read_text() == "preserve compatibility source"
    assert receipt["count"] == 1
    assert activate(preview, tmp_path)["status"] == "already-active; no writes"


def test_reactivation_never_absorbs_or_overwrites_unknown_edit(tmp_path):
    path, preview = fixture_plan(tmp_path)
    activate(preview, tmp_path)
    ledger_before = (tmp_path / LEDGER).read_bytes()
    path.write_text("human edit; preserve")
    with pytest.raises(OCFError, match="changed source"):
        activate(preview, tmp_path)
    assert path.read_text() == "human edit; preserve"
    assert (tmp_path / LEDGER).read_bytes() == ledger_before


def test_activation_rejects_escape_before_any_write(tmp_path):
    path, preview = fixture_plan(tmp_path)
    preview["outputs"]["outside.yaml"] = "not authorized"
    with pytest.raises(OCFError, match="unsafe localized activation target"):
        activate(preview, tmp_path)
    assert path.read_text() == "exact predecessor\n"
    assert not (tmp_path / "outside.yaml").exists()
    assert not (tmp_path / LEDGER).exists()
