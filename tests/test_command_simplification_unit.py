"""Isolated one-shot migration, authorization and failure-path contracts."""

import json
from copy import deepcopy

import pytest
import yaml
from ocf_tools import audio_defaults, cue_headers, session_plans
from ocf_tools import command_simplification as subject
from ocf_tools.utils import OCFError
from tools import check_hplus_narration_integrity as integrity
from tools import create_command_simplification as driver

pytestmark = pytest.mark.unit


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def function(owner):
    title, display, old, _ = subject.PAIRS[owner]
    return {
        "id": owner,
        "canonical": {
            "name": "Attention" if owner == "OCF-FND-002" else title,
            "command": {
                "primary": display if owner == "OCF-FND-002" else "OLD-DISPLAY",
                "modes": ["UNCHANGED-CONTROL"],
            },
        },
        "commands": [
            {
                "id": "OCF-CMD-" + owner[4:] + "-PRIMARY",
                "designation": "primary",
                "spoken": old,
                "spoken_review": "reviewed",
                "localization": {},
                "procedure": {"ref": "test-procedure", "steps": ["preserve exact steps"]},
            }
        ],
        "purpose": "Synthetic wellness exercise — café; no real claims.",
        "legacy": {"name": "historical", "commands": ["OLD-DISPLAY"]},
        "lifecycle": {"activation": "manual", "persistence": "temporary"},
    }


@pytest.fixture
def migration(tmp_path, monkeypatch):
    root = tmp_path
    monkeypatch.setattr(driver, "REPO_ROOT", root)
    monkeypatch.setattr(driver.sys, "argv", ["migration"])
    lock = root / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-011.json"
    monkeypatch.setattr(audio_defaults, "LOCK_PATH", lock)
    resources = []
    for owner in subject.PAIRS:
        put(
            root,
            "functions/test/" + owner + ".yaml",
            yaml.safe_dump(function(owner), allow_unicode=True, sort_keys=False),
        )
        entries = {}
        for role in ("opener", "function-body", "closer"):
            text = "Synthetic narration — café."
            if role != "opener":
                text += " Say {{ cue.primary }}."
            if owner == "OCF-FND-002" and role == "closer":
                text += " This concludes your OCF Attention exercise."
            entries[f"hplus.function.{owner.lower()}.{role}"] = {
                "status": "reviewed",
                "version": "1.0.0",
                "text": text,
                "notes": "Immutable source provenance — synthetic fixture.",
            }
        name = f"locales/en-US/hplus-{owner}.yaml"
        resources.append(name)
        # Literal blocks mirror authored files without resolving speech in the driver.
        text = "schema_version: '1.0'\nlocale: en-US\ndomain: narration\nentries:\n"
        for key, entry in entries.items():
            text += f"  {key}:\n    version: '1.0.0'\n    status: reviewed\n    notes: {entry['notes']}\n    text: |-\n      {entry['text']}\n"
        put(root, name, text)
    put(root, "functions/test/unaffected.yaml", "id: OCF-TST-999\n")
    put(root, "audio/session-plans/en-US/fixture.json", {"before": True})
    put(
        root,
        "locales/en-US/commands.yaml",
        "domain: ui\nentries:\n  functions.ocf-fnd-002.title:\n    text: Attention\n    version: 1.0.0\n",
    )
    put(
        root,
        "locales/en-US/activation-cues.yaml",
        "domain: narration\nentries:\n  test.keep: Unchanged\n",
    )
    ui = {
        "domain": "ui",
        "entries": {
            f"functions.{owner.lower()}.artwork-description": {
                "text": "Previous private artwork",
                "status": "draft",
                "version": "1.0.0",
            }
            for owner in subject.ARTWORK
        },
    }
    put(root, "locales/en-US/ui.yaml", yaml.safe_dump(ui, sort_keys=False))
    put(root, "locales/en-US/manifest.yaml", "unchanged locale registry\n")
    put(root, "function-content/editorial/previous.json", {"immutable": True})
    old_lock = {
        "id": "old",
        "version": "10.0.0",
        "profiles": {"dsp": "unchanged"},
        "files": {
            name: subject.sha((root / name).read_text(encoding="utf-8")) for name in resources
        },
    }
    put(root, subject.PREVIOUS_LOCK, old_lock)

    def texts(_root):
        result = {}
        for owner in subject.PAIRS:
            doc = yaml.safe_load(
                (root / ("functions/test/" + owner + ".yaml")).read_text(encoding="utf-8")
            )
            name = f"locales/en-US/hplus-{owner}.yaml"
            data = yaml.safe_load((root / name).read_text(encoding="utf-8"))
            for key, entry in data["entries"].items():
                result[name + "::" + key] = entry["text"].replace(
                    "{{ cue.primary }}", doc["commands"][0]["spoken"]
                )
        return result

    monkeypatch.setattr(integrity, "narration_texts", texts)
    put(root, subject.PREVIOUS_BASELINE, integrity.text_fingerprints(texts(root)))
    frozen = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file()
    }

    def git_show(command, *, cwd):
        assert command[:2] == ["git", "show"] and cwd == root
        revision, name = command[2].split(":", 1)
        assert revision == subject.SOURCE
        return frozen[name].encode("utf-8")

    monkeypatch.setattr(driver.subprocess, "check_output", git_show)
    calls = []

    def create_lock(*, dependency_names):
        assert set(dependency_names) == set(resources)
        new = deepcopy(old_lock)
        new.update(id="new", version="11.0.0")
        new["files"] = {
            name: subject.sha((root / name).read_text(encoding="utf-8"))
            for name in dependency_names
        }
        put(root, lock.relative_to(root), new)
        calls.append("create-lock")

    monkeypatch.setattr(audio_defaults, "create_lock", create_lock)
    monkeypatch.setattr(audio_defaults, "check_lock", lambda: calls.append("check-lock"))
    monkeypatch.setattr(
        cue_headers,
        "plans",
        lambda _root: {
            resources[0]: "# generated preview\n"
            + (root / resources[0]).read_text(encoding="utf-8"),
            "unrelated": "never written",
        },
    )

    def plans(*, locale):
        assert locale == "en-US"
        put(root, "audio/session-plans/en-US/fixture.json", {"generated": True})
        calls.append("plans")

    monkeypatch.setattr(session_plans, "generate_plans", plans)
    return root, lock, frozen, calls


@pytest.mark.parametrize("mode", ["fresh", "recover-new-lock", "recover-existing-lock"])
def test_one_shot_records_exact_changes_and_preserves_predecessors(migration, monkeypatch, mode):
    root, lock, frozen, calls = migration
    if mode.startswith("recover"):
        monkeypatch.setattr(driver.sys, "argv", ["migration", "--recover-incomplete"])
    if mode == "recover-existing-lock":
        # The application lock validator is independently tested; here only prove
        # that an interrupted driver invokes it and does not recreate the lock.
        put(root, lock.relative_to(root), {"existing": True})
    driver.main()
    ledger_text = (root / subject.LEDGER).read_text(encoding="utf-8")
    data = json.loads(ledger_text)
    assert len(data["speech"]) == 15
    assert data["confirmation"] == "Confirm implementation"
    assert data["source_commit"] == subject.SOURCE
    assert (
        data["files"]["audio/session-plans/en-US/fixture.json"]["before"]
        == frozen["audio/session-plans/en-US/fixture.json"]
    )
    for name, row in data["files"].items():
        assert row["before"] == frozen[name]
        assert row["before_sha256"] == subject.sha(frozen[name])
        assert row["after_sha256"] == subject.sha((root / name).read_text(encoding="utf-8"))
    for name in (
        subject.PREVIOUS_BASELINE,
        subject.PREVIOUS_LOCK,
        "locales/en-US/manifest.yaml",
        "functions/test/unaffected.yaml",
    ):
        assert (root / name).read_text(encoding="utf-8") == frozen[name]
    assert not (root / "unrelated").exists()
    assert calls == (
        ["check-lock", "plans"] if mode == "recover-existing-lock" else ["create-lock", "plans"]
    )
    if mode != "recover-existing-lock":
        monkeypatch.setattr(subject, "LEDGER_SHA256", subject.sha(ledger_text))
        assert subject.verify(root) == []
    with pytest.raises(OCFError, match="never overwrite"):
        driver.main()


@pytest.mark.parametrize(
    "failure",
    ["unknown-flag", "ledger", "baseline", "lock", "scope", "input-drift", "recovery-baseline"],
)
def test_driver_refuses_unauthorized_inputs_or_evidence_replacement(
    migration, monkeypatch, failure
):
    root, lock, frozen, _ = migration
    expected = {
        "unknown-flag": "only --recover-incomplete",
        "ledger": "never overwrite",
        "baseline": "never overwrite",
        "lock": "never overwrite",
        "scope": "scope is incomplete",
        "input-drift": "differs from approved",
        "recovery-baseline": "cannot prove",
    }[failure]
    if failure == "unknown-flag":
        monkeypatch.setattr(driver.sys, "argv", ["migration", "--force"])
    elif failure in ("ledger", "baseline", "lock"):
        name = {
            "ledger": subject.LEDGER,
            "baseline": subject.BASELINE,
            "lock": lock.relative_to(root),
        }[failure]
        put(root, name, "do not overwrite")
    elif failure == "scope":
        (root / "functions/test/OCF-BOD-002.yaml").unlink()
    elif failure == "input-drift":
        put(
            root,
            "locales/en-US/commands.yaml",
            frozen["locales/en-US/commands.yaml"] + "# external edit\n",
        )
    else:
        monkeypatch.setattr(driver.sys, "argv", ["migration", "--recover-incomplete"])
        put(root, subject.PREVIOUS_BASELINE, {})
    with pytest.raises(OCFError, match=expected):
        driver.main()


@pytest.mark.parametrize(
    "entry",
    [
        "  selected.value: Old bare cue\n",
        "  selected.value:\n    text: Old structured cue\n    version: 1.2.0\n",
        "",
    ],
)
def test_locale_entry_update_never_duplicates_inline_values_or_changes_neighbors(entry):
    prefix, suffix = "entries:\n", "  untouched.value: Keep these exact bytes\n"
    text = prefix + entry + suffix
    updated = driver.replace_entry(
        text, "selected.value", lambda row: row.update(text="Reviewed cue", version="2.0.0")
    )
    assert updated.startswith(prefix) and updated.endswith(suffix)
    assert updated.count("  selected.value:") == 1
    assert yaml.safe_load(updated)["entries"]["selected.value"]["text"] == "Reviewed cue"
    assert driver.bump("1.2.99") == "1.3.0"


def test_authorization_and_history_are_fail_closed(tmp_path, monkeypatch):
    assert subject.record(tmp_path) is None
    assert subject.predecessor(tmp_path, "other", "original") == "original"
    assert subject.before_texts(tmp_path, {"key": "original"}) == {"key": "original"}
    assert subject.verify(tmp_path) == ["command simplification successor missing"]
    data = {
        "id": subject.ID,
        "source_commit": subject.SOURCE,
        "confirmation": "Confirm implementation",
        "files": {
            "file": {
                "before": "old",
                "before_sha256": subject.sha("old"),
                "after_sha256": subject.sha("new"),
            }
        },
        "speech": {"key": {"before": "old", "after": "new"}},
    }

    def pin():
        path = put(tmp_path, subject.LEDGER, data)
        monkeypatch.setattr(subject, "LEDGER_SHA256", subject.sha(path.read_text(encoding="utf-8")))

    pin()
    assert subject.predecessor(tmp_path, "file", "new") == "old"
    assert subject.before_texts(tmp_path, {"key": "new"}) == {"key": "old"}
    with pytest.raises(OCFError, match="source drift"):
        subject.predecessor(tmp_path, "file", "unapproved")
    with pytest.raises(OCFError, match="resolved speech drift"):
        subject.before_texts(tmp_path, {"key": "unapproved"})
    data["files"]["file"]["before"] = "tampered predecessor"
    pin()
    with pytest.raises(OCFError, match="source drift"):
        subject.predecessor(tmp_path, "file", "new")
    data["confirmation"] = "invented approval"
    pin()
    with pytest.raises(OCFError, match="authorization drift"):
        subject.record(tmp_path)
    put(tmp_path, subject.LEDGER, "unapproved bytes")
    with pytest.raises(OCFError, match="immutable"):
        subject.record(tmp_path)


def test_function_transform_rejects_wrong_predecessor_and_retains_observed_binding():
    before = function("OCF-BOD-002")
    before["commands"][0]["observed_phrase"] = {
        "text": "Plus Flow Smooth",
        "relationship": "historical",
        "narration_key": "unchanged.key",
    }
    after = subject.approved_function(before)
    assert after["commands"][0]["observed_phrase"] == {
        "text": "Plus Circulate",
        "relationship": "canonical-match",
        "narration_key": "unchanged.key",
    }
    assert after["purpose"] == before["purpose"]
    before["commands"][0]["spoken"] = "wrong predecessor"
    with pytest.raises(OCFError, match="predecessor cue"):
        subject.approved_function(before)
