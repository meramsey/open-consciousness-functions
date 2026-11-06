"""Read-only editorial previews resolve exclusively from canonical resources."""

import json

import pytest
from ocf_tools.agent_api import dispatch
from ocf_tools.cli import main
from ocf_tools.editorial_candidates import CANDIDATES, context, review, verify_approvals
from ocf_tools.editorial_review import OUTPUT, render
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration


def test_cli_and_agent_preview_use_the_approved_canonical_resource(capsys):
    assert main(["functions", "candidates"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["candidates"]) == 4
    assert all(row["editorial_status"] == "approved and implemented" for row in data["candidates"])
    assert all(not row["pending_approval"] for row in data["candidates"])

    preview = dispatch("ocf_inspect_candidates", {"candidate": "intuition", "preview": True})
    assert preview["registration"] == "registered"
    assert preview["production_authorized"] and not preview["release_ready"]
    assert not preview["listening_approval"]
    assert len(preview["entries"]) == 3
    assert preview["authority"] == preview["narration_authority"]
    assert "entries" not in dispatch("ocf_inspect_candidates", {"candidate": "dissolve"})


def test_all_embedded_approval_hashes_match_current_canonical_narration():
    assert verify_approvals() == []
    for name in CANDIDATES:
        preview = review(name)
        assert preview["editorial_status"] == "approved and implemented"
        assert not preview["pending_approval"]
        assert not preview["release_ready"]
        assert preview["authority"] == preview["narration_authority"]
        assert all(entry["status"] in {"reviewed", "canonical"} for entry in preview["entries"])


def test_cue_headers_no_longer_generate_duplicate_candidate_files():
    from ocf_tools import cue_headers

    assert cue_headers.plans() == {}
    assert cue_headers.draft_plans() == {}
    assert cue_headers.check() == []


def test_canonical_editorial_summary_is_deterministic_and_does_not_copy_narration():
    text = render()
    assert text == render() == (REPO_ROOT / OUTPUT).read_text(encoding="utf-8")
    assert "canonical locale resource" in text
    assert "```text" not in text
    for identity in CANDIDATES.values():
        record, _catalog = context(
            next(name for name, fid in CANDIDATES.items() if fid == identity)
        )
        assert record.id == identity
        assert f"`{identity}`" in text


def test_canonical_preview_supports_newline_safe_generic_header_parser():
    from ocf_tools.cue_headers import END, START, split_header

    source = START + "# generated comment\r\n" + END.replace("\n", "\r\n") + "authored\n"
    prefix, body = split_header(source)
    assert prefix + body == source
    assert body == "authored\n"
