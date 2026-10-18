"""Plain-editor previews preserve authored bytes and immutable predecessors."""

import json

import pytest
from ocf_tools import cue_completion, cue_headers
from ocf_tools.utils import OCFError
from test_cue_templates import fixture


@pytest.mark.unit
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_header_is_comment_only_and_preserves_body(newline):
    body = "# Author's note\ntext: |\n  Keep  whitespace.\n".replace("\n", newline)
    prefix = (cue_headers.START + "# cue: 雲\n" + cue_headers.END).replace("\n", newline)
    assert cue_headers.split_header(prefix + body) == (prefix, body)
    assert cue_headers.split_header(body) == ("", body)


@pytest.mark.unit
@pytest.mark.parametrize("first,last", [("\r\n", "\n"), ("\n", "\r\n")])
def test_mixed_header_newlines_never_consume_authored_bytes(first, last):
    prefix = cue_headers.START.rstrip() + first + "# preview\n" + cue_headers.END.rstrip() + last
    body = "text: |\r\n  Exact  content.\n"
    assert cue_headers.split_header(prefix + body) == (prefix, body)


@pytest.mark.unit
def test_refresh_requires_each_file_witness_before_any_write(monkeypatch, tmp_path):
    ledger = tmp_path / cue_headers.LEDGER
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"files": {"first.yaml": {}}}), encoding="utf-8")
    first = tmp_path / "first.yaml"
    first.write_bytes(b"preserve this")
    monkeypatch.setattr(cue_headers, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        cue_headers, "plans", lambda: {"first.yaml": "changed", "unlisted.yaml": "new"}
    )
    with pytest.raises(OCFError, match="every preview write"):
        cue_headers.main(["--write"])
    assert first.read_bytes() == b"preserve this"
    assert not (tmp_path / "unlisted.yaml").exists()


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        cue_headers.END,
        cue_headers.START,
        "text: value\n" + cue_headers.START + cue_headers.END,
        cue_headers.START + "text: hidden-authority\n" + cue_headers.END,
        (cue_headers.START + cue_headers.END) * 2,
    ],
)
def test_malformed_headers_fail_closed(text):
    with pytest.raises(OCFError):
        cue_headers.split_header(text)


@pytest.mark.unit
def test_preview_uses_authority_and_marks_missing_locale_cues(tmp_path):
    owner, _, catalog = fixture(tmp_path)
    text = cue_headers.header(owner, "en-US", catalog, tmp_path)
    assert '"symbol": "cue.primary"' in text
    assert '"spoken": "Plus Example"' in text
    assert "English authority: function.yaml" in text
    other, _, translated = fixture(tmp_path, locale="es-ES", speech="Ejemplo")
    localized = cue_headers.header(other, "es-ES", translated, tmp_path)
    assert '"spoken": "Ejemplo"' in localized
    assert "Plus Example" not in localized
    assert cue_headers.header(owner, "en-US", catalog, tmp_path) == text
    other.data["commands"][0]["localization"]["spoken_cue_key"] = "missing"
    missing = cue_headers.header(other, "es-ES", translated, tmp_path)
    assert '"binding_status": "unavailable"' in missing
    assert "Plus Example" not in missing


@pytest.mark.unit
def test_successor_rejects_changed_body_and_changed_preview(tmp_path):
    body = "text: Exact speech\n"
    text = cue_headers.START + "# cue\n" + cue_headers.END + body
    ledger = tmp_path / cue_headers.LEDGER
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        json.dumps(
            {
                "files": {
                    "locale.yaml": {
                        "before_sha256": cue_headers.sha(body),
                        "after_sha256": cue_headers.sha(text),
                        "predecessor": body,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    assert cue_headers.predecessor(tmp_path, "locale.yaml", text) == body
    for changed in (text.replace("Exact", "Changed"), text.replace("# cue", "# stale cue")):
        with pytest.raises(OCFError, match="source drift"):
            cue_headers.predecessor(tmp_path, "locale.yaml", changed)


@pytest.mark.integration
def test_all_55_previews_and_177_resolved_entries_are_current():
    assert len(cue_headers.plans()) == 55
    assert cue_headers.check() == []
    assert cue_headers.verify() == []
    ledger = json.loads((cue_headers.REPO_ROOT / cue_headers.LEDGER).read_text(encoding="utf-8"))
    assert len(ledger["resolved_text_sha256"]) == 177
    assert len(ledger["plans"]) == 56


@pytest.mark.integration
def test_completion_covers_primary_and_secondary_without_resolved_drift():
    assert cue_completion.verify() == []
    data = json.loads((cue_headers.REPO_ROOT / cue_completion.LEDGER).read_text(encoding="utf-8"))
    entries = [entry for row in data["files"].values() for entry in row["entries"]]
    spans = [span for entry in entries for span in entry["spans"]]
    assert len(entries) == 51
    assert len(spans) == 90
    assert any(span["symbol"].startswith("cue.id.") for span in spans)
    assert any(span["symbol"] == "cue.primary" for span in spans)
    assert any(entry["key"].endswith("closer") for entry in entries)
    assert any(entry["key"].endswith("function-body") for entry in entries)
    assert len(data["resolved_text_sha256"]) == 177


@pytest.mark.unit
def test_completion_rejects_behavior_change_even_with_updated_file_hash(tmp_path):
    before = "entries:\n  example:\n    text: Say Plus Example.\n    status: reviewed\n"
    template = "Say {{ cue.primary }}."
    after = (
        'entries:\n  example:\n    text: "' + template + '"\n'
        "    status: changed\n    cue_template: {function_id: OCF-COG-999, allowed: [cue.primary]}\n"
    )
    name = "locales/en-US/hplus-OCF-COG-999.yaml"
    row = {
        "before_sha256": cue_headers.sha(before),
        "after_sha256": cue_headers.sha(after),
        "predecessor": before,
        "entries": [
            {
                "key": "example",
                "spans": [
                    {"start": 4, "end": 16, "spoken": "Plus Example", "symbol": "cue.primary"}
                ],
                "raw_template_sha256": cue_headers.sha(template),
                "contract": {"function_id": "OCF-COG-999", "allowed": ["cue.primary"]},
            }
        ],
    }
    ledger = tmp_path / cue_completion.LEDGER
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"files": {name: row}}), encoding="utf-8")
    with pytest.raises(OCFError, match="non-cue data"):
        cue_completion.predecessor(tmp_path, name, after)


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["literal", "overlap", "hash"])
def test_completion_rejects_invalid_replay_evidence(tmp_path, mutation):
    import yaml

    before = {"entries": {"example": {"text": "Say Plus Example."}}}
    span = {"start": 4, "end": 16, "spoken": "Plus Example", "symbol": "cue.primary"}
    template = "Say {{ cue.primary }}."
    contract = {"function_id": "OCF-COG-999", "allowed": ["cue.primary"]}
    after = {"entries": {"example": {"text": template, "cue_template": contract}}}
    old, new = yaml.safe_dump(before), yaml.safe_dump(after)
    evidence = {
        "key": "example",
        "spans": [span],
        "contract": contract,
        "raw_template_sha256": cue_headers.sha(template),
    }
    if mutation == "literal":
        span["spoken"] = "Incorrect cue"
    elif mutation == "overlap":
        evidence["spans"].append(dict(span))
    else:
        evidence["raw_template_sha256"] = "invalid"
    name = "locales/en-US/hplus-OCF-COG-999.yaml"
    row = {
        "before_sha256": cue_headers.sha(old),
        "after_sha256": cue_headers.sha(new),
        "predecessor": old,
        "entries": [evidence],
    }
    ledger = tmp_path / cue_completion.LEDGER
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"files": {name: row}}), encoding="utf-8")
    with pytest.raises(OCFError, match="span overlap/mismatch|template fingerprint drift"):
        cue_completion.predecessor(tmp_path, name, new)


@pytest.mark.unit
def test_completion_does_not_allow_timing_changes_in_plan(tmp_path):
    before = {"defaults": {"sha256": "old"}, "resources": [], "timing": "original"}
    after = {"defaults": {"sha256": "new"}, "resources": [], "timing": "retuned"}
    old, new = json.dumps(before), json.dumps(after)
    name = "audio/session-plans/en-US/OCF-COG-999.json"
    row = {
        "before_sha256": cue_headers.sha(old),
        "after_sha256": cue_headers.sha(new),
        "predecessor": old,
        "entries": [],
    }
    ledger = tmp_path / cue_completion.LEDGER
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"files": {name: row}}), encoding="utf-8")
    with pytest.raises(OCFError, match="non-cue data"):
        cue_completion.predecessor(tmp_path, name, new)
