import hashlib

import pytest
from ocf_tools.paths import REPO_ROOT
from ocf_tools.shared_session_successor import predecessor, record
from ocf_tools.utils import OCFError


@pytest.mark.unit
def test_shared_session_predecessor_keeps_historical_manifest_and_plans_immutable():
    ledger = record()
    assert ledger["base_git_sha"] == "ef5b2821d6d63638588be1855aa3af340be3ca2b"
    for name in (
        "locales/en-US/manifest.yaml",
        "audio/session-plans/en-US/OCF-AUT-001.json",
        "audio/session-plans/en-US/_shared.json",
    ):
        current = (REPO_ROOT / name).read_text(encoding="utf-8")
        previous = predecessor(REPO_ROOT, name, current)
        assert (
            hashlib.sha256(previous.encode()).hexdigest() == ledger["files"][name]["before_sha256"]
        )
        assert predecessor(REPO_ROOT, name, previous) == previous


@pytest.mark.unit
def test_shared_session_predecessor_rejects_unrecorded_mutation():
    with pytest.raises(OCFError, match="successor source drift"):
        predecessor(REPO_ROOT, "locales/en-US/manifest.yaml", "tampered\n")
