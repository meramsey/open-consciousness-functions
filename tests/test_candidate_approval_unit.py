"""Isolated approval-scope and one-shot authoring contracts; no real subprocesses."""

import json
from copy import deepcopy

import pytest
import yaml
from ocf_tools import candidate_approval as approval
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def test_absent_ledger_does_not_create_approval(tmp_path):
    assert approval.record(tmp_path) is None
    assert approval.predecessor(tmp_path, "unrelated", "original") == "original"
    assert approval.before_texts(tmp_path, {"key": "original"}) == {"key": "original"}
    assert approval.verify(tmp_path) == ["candidate approval ledger missing"]


def test_checked_predecessor_rejects_tampering_and_preserves_new_files(monkeypatch):
    rows = {
        "old": {
            "before": "previous",
            "before_sha256": approval.sha("previous"),
            "after_sha256": approval.sha("current"),
        },
        "new": {"before": None, "before_sha256": None, "after_sha256": approval.sha("new")},
    }
    monkeypatch.setattr(approval, "record", lambda root: {"files": rows})
    assert approval.predecessor(None, "old", "current") == "previous"
    assert approval.predecessor(None, "new", "new") == "new"
    rows["old"]["before"] = "tampered"
    with pytest.raises(OCFError, match="predecessor drift"):
        approval.predecessor(None, "old", "current")


@pytest.mark.parametrize(
    "change", ["source", "confirmation", "missing", "response", "owner", "snapshot"]
)
def test_repinning_cannot_expand_explicit_authorization(tmp_path, monkeypatch, change):
    data = {
        "source_commit": approval.SOURCE,
        "confirmation": "Confirm implementation",
        "approvals": {
            name: {
                "function_id": row[0],
                "user_response": "1",
                "snapshot_sha256": approval.SNAPSHOTS[name],
            }
            for name, row in approval.APPROVED.items()
        },
    }
    if change == "source":
        data["source_commit"] = "0" * 40
    elif change == "confirmation":
        data["confirmation"] = "maybe"
    elif change == "missing":
        data["approvals"].pop("intuition")
    else:
        key = {"response": "user_response", "owner": "function_id", "snapshot": "snapshot_sha256"}[
            change
        ]
        data["approvals"]["intuition"][key] = "unapproved"
    raw = json.dumps(data)
    path = tmp_path / approval.LEDGER
    path.parent.mkdir(parents=True)
    path.write_text(raw, encoding="utf-8")
    monkeypatch.setattr(approval, "LEDGER_SHA256", approval.sha(raw))
    with pytest.raises(OCFError, match="scope drift|user's decision"):
        approval.record(tmp_path)


@pytest.mark.parametrize(
    "case", ["success", "collision", "input", "snapshot", "staged", "new_output", "protected"]
)
def test_one_shot_driver_replays_pinned_inputs_without_audio_or_processes(
    tmp_path, monkeypatch, case
):
    from types import SimpleNamespace

    from ocf_tools import (
        audio_defaults,
        cue_headers,
        editorial_candidates,
        indexes,
        locale,
        session_plans,
    )
    from ocf_tools.models import function_from_dict
    from tools import approve_editorial_candidates as driver
    from tools import check_hplus_narration_integrity as integrity

    # Explicit checked repository evidence supplies the test fixture; all writes
    # and generated outputs are confined to this test's temporary checkout.
    data = approval.record()
    source = approval.REPO_ROOT
    originals = {
        name: row["before"] for name, row in data["files"].items() if row["before"] is not None
    }
    staged_name = "function-content/editorial/candidates/intuition.function.yaml"
    originals[staged_name] = (source / staged_name).read_text(encoding="utf-8")
    for name in approval.APPROVED:
        relative = f"function-content/editorial/candidates/{name}.en-US.yaml"
        originals[relative] = (source / relative).read_text(encoding="utf-8")
    for name in (
        data["previous_lock"],
        data["previous_baseline"],
        "function-content/bindings/OCF-EXP-003.yaml",
        "functions/experimental/mobius-west.yaml",
    ):
        originals[name] = (source / name).read_text(encoding="utf-8")
    for name, text in originals.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    before_bytes = {
        name: (tmp_path / name).read_bytes()
        for name in originals
        if name.startswith("function-content/editorial/candidates/")
    }
    monkeypatch.setattr(driver, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        driver.subprocess,
        "check_output",
        lambda command, **kw: originals[command[2].split(":", 1)[1]].encode("utf-8"),
    )
    lock = tmp_path / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-010.json"
    monkeypatch.setattr(audio_defaults, "LOCK_PATH", lock)

    def functions():
        return [
            function_from_dict(yaml.safe_load(path.read_text(encoding="utf-8")), path)
            for path in (tmp_path / "functions").rglob("*.yaml")
        ]

    monkeypatch.setattr(indexes, "load_all_functions", functions)
    monkeypatch.setattr(
        editorial_candidates,
        "review",
        lambda name: {
            "entries": [
                {"key": key, "resolved_text_sha256": checksum}
                for key, checksum in data["approvals"][name]["resolved_sha256"].items()
            ]
        },
    )
    monkeypatch.setattr(locale, "LocaleCatalog", lambda: SimpleNamespace())
    monkeypatch.setattr(cue_headers, "header", lambda *args, **kw: "# generated cue preview\n")

    def create_lock(**kwargs):
        old = json.loads(originals[data["previous_lock"]])
        assert set(kwargs["dependency_names"]) == set(old["files"])
        old.update(id="OCF-AUDIO-DEFAULTS-HPLUS-010", version="10.0.0")
        old["files"][approval.MANIFEST] = approval.sha(
            (tmp_path / approval.MANIFEST).read_text(encoding="utf-8")
        )
        lock.write_text(json.dumps(old), encoding="utf-8")

    monkeypatch.setattr(audio_defaults, "create_lock", create_lock)

    def plans(**kwargs):
        assert kwargs == {"locale": "en-US"}
        for identifier in ("OCF-EXP-003", "OCF-EXP-005", "OCF-EXP-006"):
            (tmp_path / f"audio/session-plans/en-US/{identifier}.json").write_text(
                "{}\n", encoding="utf-8"
            )

    monkeypatch.setattr(session_plans, "generate_plans", plans)
    old_texts = {identity: row["before"] for identity, row in data["speech"].items()}
    new_texts = {identity: row["after"] for identity, row in data["speech"].items()}
    old_texts["unaffected"] = new_texts["unaffected"] = "unchanged"
    calls = iter([old_texts, new_texts])
    monkeypatch.setattr(integrity, "narration_texts", lambda root: next(calls))
    if case != "success":
        if case == "collision":
            monkeypatch.setattr(
                indexes, "load_all_functions", lambda: [SimpleNamespace(id="OCF-EXP-006")]
            )
        elif case == "input":
            (tmp_path / "locales/en-US/manifest.yaml").write_text("changed", encoding="utf-8")
        elif case == "snapshot":
            (tmp_path / "function-content/editorial/candidates/manifest-v2.en-US.yaml").write_text(
                "changed", encoding="utf-8"
            )
        elif case == "staged":
            (tmp_path / staged_name).write_text("changed", encoding="utf-8")
        elif case == "new_output":
            (tmp_path / "locales/en-US/intuition-ui.yaml").write_text("user work", encoding="utf-8")
        else:
            new_texts["unaffected"] = "unauthorized change"
        with pytest.raises(OCFError):
            driver.main()
        assert not (tmp_path / approval.LEDGER).exists()
        return
    driver.main()
    result = json.loads((tmp_path / approval.LEDGER).read_text(encoding="utf-8"))
    assert result["confirmation"] == "Confirm implementation"
    assert len(result["speech"]) == 3 and result["unchanged_protected"] == {
        "unaffected": approval.sha("unchanged")
    }
    for name, before in before_bytes.items():
        assert (tmp_path / name).read_bytes() == before
    for name, (_, function, resource) in approval.APPROVED.items():
        snapshot = yaml.safe_load(
            originals[f"function-content/editorial/candidates/{name}.en-US.yaml"]
        )
        expected = deepcopy(snapshot)
        for entry in expected["entries"].values():
            entry["status"] = "reviewed"
        assert yaml.safe_load((tmp_path / resource).read_text(encoding="utf-8")) == expected
        assert (
            yaml.safe_load((tmp_path / function).read_text(encoding="utf-8"))["audio"][
                "script_status"
            ]
            == "approved"
        )
    with pytest.raises(OCFError, match="never overwrite"):
        driver.main()


@pytest.fixture
def batch_evidence(tmp_path, monkeypatch):
    """Small synthetic approval bundle, independent of repository rendering."""
    from types import SimpleNamespace

    from ocf_tools import locale
    from tools import check_hplus_narration_integrity as integrity

    def write(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = value if isinstance(value, str) else json.dumps(value)
        path.write_text(text, encoding="utf-8")
        return text

    data = {
        "source_commit": approval.SOURCE,
        "confirmation": "Confirm implementation",
        "approvals": {},
        "files": {},
        "immutable_files": {},
        "speech": {},
        "previous_baseline": "previous.json",
        "previous_lock": "old-lock.json",
        "lock": "new-lock.json",
        "intuition_documentation": {"title_key": "example.title"},
        "intuition_localization": {"spoken_cue_key": "example.cue"},
    }
    texts, resolved, snapshot_hashes = {}, {}, {}

    def witness(name, before, after):
        raw = write(name, after)
        data["files"][name] = {
            "before": before,
            "before_sha256": approval.sha(before) if before else None,
            "after_sha256": approval.sha(raw),
        }

    for name, (identifier, function, resource) in approval.APPROVED.items():
        entries = {
            f"hplus.function.{identifier.lower()}.{role}": {
                "text": f"Approved {name} {role}.",
                "status": "draft",
                "version": "1.0.0",
            }
            for role in ("opener", "function-body", "closer")
        }
        snapshot = {
            "schema_version": "1.0",
            "locale": "en-US",
            "domain": "narration",
            "entries": entries,
        }
        snapshot_hashes[name] = approval.sha(
            write(f"function-content/editorial/candidates/{name}.en-US.yaml", snapshot)
        )
        active = deepcopy(snapshot)
        for key, entry in active["entries"].items():
            entry["status"] = "reviewed"
            resolved[key] = entry["text"]
            if name == "manifest-v2":
                identity = resource + "::" + key
                texts[identity] = entry["text"]
                data["speech"][identity] = {"before": "Old " + key, "after": entry["text"]}
        witness(resource, json.dumps(snapshot), active)
        data["approvals"][name] = {
            "function_id": identifier,
            "user_response": "1",
            "snapshot_sha256": snapshot_hashes[name],
            "resolved_sha256": {key: approval.sha(entry["text"]) for key, entry in entries.items()},
        }
        if name == "manifest-v2":
            continue
        before = {
            "id": identifier,
            "audio": {"script_status": "draft"},
            "status": {},
            "ocf": {},
            "commands": [{"spoken_review": "unresolved", "procedure": {"status": "unresolved"}}],
            "lifecycle": {"persistence": "permanent"},
        }
        after = approval.approved_function(before)
        if name == "intuition":
            staged = "function-content/editorial/candidates/intuition.function.yaml"
            data["immutable_files"][staged] = approval.sha(write(staged, before))
            after["documentation"] = data["intuition_documentation"]
            after["commands"][0]["localization"] = data["intuition_localization"]
        witness(function, None if name == "intuition" else json.dumps(before), after)
    data["immutable_files"]["immutable.txt"] = approval.sha(write("immutable.txt", "frozen"))
    texts["unrelated::protected"] = "untouched"
    previous = {identity: approval.sha(row["before"]) for identity, row in data["speech"].items()}
    previous["unrelated::protected"] = approval.sha("untouched")
    write(data["previous_baseline"], previous)
    write(approval.BASELINE, integrity.text_fingerprints(texts))
    old_lock = {
        "id": "old",
        "version": "1",
        "profiles": {"dsp": "frozen"},
        "files": {approval.MANIFEST: "old"},
    }
    write(data["previous_lock"], old_lock)
    new_lock = deepcopy(old_lock)
    new_lock.update(id="new", version="2")
    new_lock["files"][approval.MANIFEST] = data["files"][approval.MANIFEST]["after_sha256"]
    write(data["lock"], new_lock)
    monkeypatch.setattr(approval, "SNAPSHOTS", snapshot_hashes)
    monkeypatch.setattr(integrity, "narration_texts", lambda root: dict(texts))
    monkeypatch.setattr(
        locale,
        "LocaleCatalog",
        lambda root: SimpleNamespace(
            resource=lambda key, *a, **kw: (SimpleNamespace(text=resolved[key]), None)
        ),
    )

    def save():
        monkeypatch.setattr(approval, "LEDGER_SHA256", approval.sha(write(approval.LEDGER, data)))

    save()
    return tmp_path, data, texts, resolved, write, save


def test_batch_verifier_replays_without_mutating_inputs(batch_evidence):
    root, data, texts, _, _, _ = batch_evidence
    original = deepcopy(texts)
    assert approval.verify(root) == []
    projected = approval.before_texts(root, texts)
    assert texts == original
    assert projected["unrelated::protected"] == "untouched"
    assert all(projected[key] == row["before"] for key, row in data["speech"].items())


@pytest.mark.parametrize(
    "case",
    [
        "source",
        "predecessor",
        "immutable",
        "previous_baseline",
        "baseline",
        "protected_scope",
        "snapshot",
        "resolved",
        "metadata",
        "behavior",
        "engineering",
    ],
)
def test_batch_verifier_rejects_drift_even_with_recomputed_file_witness(batch_evidence, case):
    root, data, texts, resolved, write, save = batch_evidence
    if case == "source":
        write(approval.MANIFEST, "changed")
    elif case == "predecessor":
        data["files"][approval.MANIFEST]["before"] = "changed"
    elif case == "immutable":
        write("immutable.txt", "changed")
    elif case == "previous_baseline":
        write(data["previous_baseline"], {})
    elif case == "baseline":
        write(approval.BASELINE, {})
    elif case == "protected_scope":
        data["speech"]["unrelated::protected"] = {"before": "untouched", "after": "untouched"}
    elif case == "snapshot":
        write("function-content/editorial/candidates/manifest-v2.en-US.yaml", "changed")
    elif case == "resolved":
        resolved[next(iter(resolved))] = "changed"
    elif case == "engineering":
        lock = json.loads((root / data["lock"]).read_text(encoding="utf-8"))
        lock["profiles"]["dsp"] = "retuned"
        write(data["lock"], lock)
    else:
        name = approval.MANIFEST if case == "metadata" else approval.APPROVED["dissolve"][1]
        value = yaml.safe_load((root / name).read_text(encoding="utf-8"))
        if case == "metadata":
            next(iter(value["entries"].values()))["version"] = "unapproved-version"
        else:
            value["lifecycle"]["persistence"] = "changed"
        data["files"][name]["after_sha256"] = approval.sha(write(name, value))
    save()
    with pytest.raises(OCFError):
        approval.verify(root)
