"""Integration: editorial surfaces share authority and never authorize production."""

import json

import pytest
from ocf_tools import cue_headers
from ocf_tools.agent_api import dispatch
from ocf_tools.cli import main
from ocf_tools.editorial_candidates import CANDIDATES, context, review
from ocf_tools.editorial_review import OUTPUT, render
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration


def test_cli_and_agent_candidate_discovery_and_explicit_preview(capsys):
    assert main(["functions", "candidates"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["candidates"]) == 4
    assert all(row["pending_approval"] for row in data["candidates"])
    data = dispatch("ocf_inspect_candidates", {"candidate": "intuition", "preview": True})
    assert data["registration"] == "staged proposal"
    assert not data["production_authorized"]
    assert len(data["entries"]) == 3
    assert "entries" not in dispatch("ocf_inspect_candidates", {"candidate": "dissolve"})


def test_draft_headers_preserve_snapshot_and_resolve_staged_authority():
    assert cue_headers.check() == []
    plans = cue_headers.draft_plans()
    assert len(plans) == 4
    for name, text in plans.items():
        header, body = cue_headers.split_header(text)
        snapshot = REPO_ROOT / name.replace("/working/", "/")
        assert body == cue_headers.split_header(snapshot.read_text(encoding="utf-8"))[1]
        assert "draft awaiting explicit review" in header
        assert '"spoken": "Plus ' in header
        assert "unavailable" not in header
    assert "intuition.function.yaml" in next(
        text for name, text in plans.items() if "intuition" in name
    )


def test_draft_header_missing_cue_diagnostic():
    owner, catalog = context("dissolve")
    owner.data["commands"][0]["spoken"] = None
    result = cue_headers.header(owner, "en-US", catalog, REPO_ROOT, draft_review=True)
    assert '"binding_status": "unavailable"' in result


def test_full_review_is_deterministic_and_contains_every_authored_and_resolved_entry():
    text = render()
    assert text == render() == (REPO_ROOT / OUTPUT).read_text(encoding="utf-8")
    for name in CANDIDATES:
        for entry in review(name)["entries"]:
            assert entry["raw_template"] in text
            assert entry["text"] in text
    assert "Approved current wording | Proposed revised wording" in text
    assert "newly AI-authored and unreviewed" in text


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_draft_header_split_preserves_spoken_bytes(newline):
    text = next(iter(cue_headers.draft_plans().values())).replace("\n", newline)
    header, body = cue_headers.split_header(text)
    assert header + body == text
    assert body.startswith("#")


def test_lsp_candidate_source_navigation():
    from ocf_tools.authoring import AuthoringService

    workspace = AuthoringService(REPO_ROOT)
    for name in ("intuition", "clear-zone"):
        path = REPO_ROOT / f"function-content/editorial/candidates/working/{name}.en-US.yaml"
        text = path.read_text()
        _, _, definitions = workspace.definitions_at(
            path.as_uri(), text.index("{{ cue.primary }}") + 5
        )
        assert definitions
        assert definitions[0].path == REPO_ROOT / review(name)["authority"]
        assert "draft awaiting review" in definitions[0].description


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_refresh_refuses_edited_generated_view(tmp_path, monkeypatch, newline):
    from ocf_tools import editorial_candidates
    from ocf_tools.utils import OCFError

    directory = tmp_path / "function-content/editorial/candidates"
    (directory / "working").mkdir(parents=True)
    source = directory / "dissolve.en-US.yaml"
    source.write_bytes(("# snapshot\ntext: original\n".replace("\n", newline)).encode())
    target = directory / "working/dissolve.en-US.yaml"
    target.write_bytes(b"# authored edit\r\ntext: human wording\n")
    original = source.read_bytes(), target.read_bytes()
    monkeypatch.setattr(editorial_candidates, "context", lambda *a, **k: (None, None))
    monkeypatch.setattr(cue_headers, "header", lambda *a, **k: cue_headers.START + cue_headers.END)
    with pytest.raises(OCFError, match="edited generated candidate view"):
        cue_headers.draft_plans(tmp_path)
    assert original == (source.read_bytes(), target.read_bytes())


@pytest.mark.parametrize(
    "error",
    [ValueError("invalid staged definition"), FileNotFoundError("missing staged definition")],
)
def test_lsp_unavailable_staged_authority_returns_no_definition(monkeypatch, error):
    from ocf_tools import editorial_candidates
    from ocf_tools.authoring import AuthoringService

    def unavailable(*args, **kwargs):
        raise error

    monkeypatch.setattr(editorial_candidates, "context", unavailable)
    path = REPO_ROOT / "function-content/editorial/candidates/working/intuition.en-US.yaml"
    text = path.read_text()
    _, _, definitions = AuthoringService(REPO_ROOT).definitions_at(
        path.as_uri(), text.index("{{ cue.primary }}") + 5
    )
    assert definitions == []
