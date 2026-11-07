"""Draft output boundaries are independent of historical source filenames."""

import json

import pytest
from ocf_tools import editorial
from ocf_tools.utils import OCFError
from tools import audit_function_authority

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "directory",
    [
        "brand",
        "audio/scripts",
        "audio/stages",
        "locales/en-US",
        "schemas",
        "templates",
        "function-content",
    ],
)
def test_editorial_rejects_all_packaged_and_audio_roots(tmp_path, monkeypatch, directory):
    monkeypatch.setattr(editorial, "REPO_ROOT", tmp_path)
    with pytest.raises(OCFError, match="packaged runtime"):
        editorial.require_local_output(tmp_path / directory / "draft.yaml")
    with pytest.raises(OCFError, match="packaged runtime"):
        editorial.save(tmp_path / directory / "draft.yaml", {"draft": True})
    with pytest.raises(OCFError, match="packaged runtime"):
        editorial.require_local_output(tmp_path)


def test_editorial_refuses_symlink_promotion_before_any_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(editorial, "REPO_ROOT", tmp_path / "repo")
    destination = tmp_path / "repo/locales/en-US"
    destination.mkdir(parents=True)
    draft = tmp_path / "private"
    draft.mkdir()
    (draft / "functions").symlink_to(destination, target_is_directory=True)
    from types import SimpleNamespace

    record = SimpleNamespace(
        id="OCF-TST-001", source_availability="unavailable", data={"content": {}}
    )
    with pytest.raises(OCFError, match="packaged runtime"):
        editorial.skeletonize(tmp_path / "source", draft, [record], tmp_path / "unused")
    assert not list(destination.iterdir())


@pytest.mark.parametrize(
    "data",
    [
        {"domain": "function", "function_id": "OCF-TST-001"},
        {"id": "OCF-TST-001", "canonical": {}, "lifecycle": {}},
        {
            "domain": "narration",
            "entries": {"hplus.function.ocf-tst-001.opener": {"text": "Draft"}},
        },
    ],
)
def test_structural_audit_catches_new_authority_under_any_filename(tmp_path, monkeypatch, data):
    path = tmp_path / "innocent.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(
        audit_function_authority.subprocess, "check_output", lambda *a, **k: b"innocent.json\0"
    )
    monkeypatch.setattr(audit_function_authority, "resources", lambda *a: [])
    assert (
        "noncanonical function authority: innocent.json"
        in audit_function_authority.audit(tmp_path)["problems"]
    )
