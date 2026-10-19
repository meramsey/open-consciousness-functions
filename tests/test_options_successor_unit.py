"""Isolated successor replay: synthetic files, no repository or subprocess work."""

import json
from copy import deepcopy

import pytest
import yaml
from ocf_tools import options_successor as subject
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    from tools import check_hplus_narration_integrity as integrity

    def write(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = value if isinstance(value, str) else json.dumps(value)
        path.write_text(text, encoding="utf-8")
        return text

    before = {
        "commands": [
            {
                "id": "primary",
                "observed_phrase": {},
                "localization": {},
                "procedure": {"preserve": True},
            },
            {"id": "legacy", "documentation": {}},
        ],
        "aliases": {},
        "lifecycle": {"persistence": "unchanged"},
    }
    narration = {
        "entries": {
            f"hplus.function.ocf-cog-005.{role}": {
                "text": " / ".join([subject.OLD] * count),
                "version": "1.0.0",
                "status": "reviewed",
            }
            for role, count in (("function-body", 2), ("closer", 1))
        }
    }
    current = deepcopy(narration)
    texts, speech = {}, {}
    for key, entry in narration["entries"].items():
        identity = subject.NARRATION + "::" + key
        old = entry["text"]
        new = old.replace(subject.OLD, subject.NEW)
        raw = old.replace(subject.OLD, "{{ cue.primary }}")
        current["entries"][key].update(
            text=raw,
            version="1.1.0",
            cue_template={"function_id": subject.OWNER, "allowed": ["cue.primary"]},
        )
        texts[identity] = new
        speech[identity] = {
            "before": old,
            "after": new,
            "before_sha256": subject.sha(old),
            "after_sha256": subject.sha(new),
            "raw_template_sha256": subject.sha(raw),
        }
    files = {}
    for name, old, new in (
        (subject.FUNCTION, before, subject.approved_function(before)),
        (subject.NARRATION, narration, current),
    ):
        old_text = yaml.safe_dump(old)
        new_text = write(name, yaml.safe_dump(new))
        files[name] = {
            "before": old_text,
            "before_sha256": subject.sha(old_text),
            "after_sha256": subject.sha(new_text),
        }
    previous = {identity: row["before_sha256"] for identity, row in speech.items()}
    raw = write("previous.json", previous)
    write(subject.BASELINE, integrity.text_fingerprints(texts))
    lock = {
        "id": "old",
        "version": "1",
        "profiles": {"dsp": "unchanged"},
        "files": {subject.NARRATION: "old"},
    }
    write("old-lock.json", lock)
    lock.update(id="new", version="2")
    lock["files"][subject.NARRATION] = files[subject.NARRATION]["after_sha256"]
    write("new-lock.json", lock)
    data = {
        "approval": {
            "function_id": subject.OWNER,
            "display": "PLUS-OPTIONS",
            "before": subject.OLD,
            "after": subject.NEW,
        },
        "speech": speech,
        "files": files,
        "previous_baseline": "previous.json",
        "previous_baseline_sha256": subject.sha(raw),
        "previous_lock": "old-lock.json",
        "lock": "new-lock.json",
    }

    def save():
        monkeypatch.setattr(subject, "LEDGER_SHA256", subject.sha(write(subject.LEDGER, data)))

    save()
    monkeypatch.setattr(integrity, "narration_texts", lambda root: dict(texts))
    return tmp_path, data, texts, write, save


def test_checked_replay_and_no_in_place_mutation(evidence):
    root, data, texts, _, _ = evidence
    assert subject.verify(root) == []
    before = deepcopy(texts)
    result = subject.before_texts(root, texts)
    assert texts == before
    assert result == {key: row["before"] for key, row in data["speech"].items()}
    assert subject.predecessor(root, "unrelated", "untouched") == "untouched"


def test_absent_successor_is_explicit(tmp_path):
    assert subject.record(tmp_path) is None
    assert subject.verify(tmp_path) == ["Options successor missing"]
    assert subject.predecessor(tmp_path, "any", "text") == "text"
    assert subject.before_texts(tmp_path, {"key": "text"}) == {"key": "text"}


def test_approved_spoken_change_selects_new_cache_identity(tmp_path, monkeypatch):
    import hashlib
    import io
    import wave

    from ocf_tools import speech_cache

    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        writer.writeframes(b"\x00\x00" * 100)
    pcm = output.getvalue()
    calls = []
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: {"synthetic": True})
    monkeypatch.setattr(speech_cache, "work_path", lambda *parts: tmp_path.joinpath(*parts))

    def publish(root, key, data):
        root.mkdir(parents=True)
        (root / "speech.wav").write_bytes(data)
        (root / "manifest.json").write_text(
            json.dumps({"key": key, "sha256": hashlib.sha256(data).hexdigest()})
        )

    monkeypatch.setattr(speech_cache, "_publish", publish)

    def synthesize():
        calls.append(True)
        return pcm

    with speech_cache.enabled():
        for text in (subject.OLD, subject.NEW, subject.NEW):
            assert speech_cache.cached_cue({"locale": "en-US"}, text, synthesize) == pcm
    assert len(calls) == 2
    assert len(list((tmp_path / "cache/tts").glob("*/speech.wav"))) == 2


@pytest.mark.parametrize(
    "case", ["approval", "scope", "count", "after", "before_hash", "after_hash", "pin"]
)
def test_record_rejects_forged_evidence(evidence, case):
    root, data, _, write, save = evidence
    row = next(iter(data["speech"].values()))
    if case == "approval":
        data["approval"]["display"] = "WRONG"
    elif case == "scope":
        data["speech"]["outside"] = row
    elif case == "count":
        row["before"] += subject.OLD
    elif case == "after":
        row["after"] += " unauthorized"
    elif case.endswith("_hash"):
        row[case.replace("_hash", "_sha256")] = "bad"
    else:
        write(subject.LEDGER, "{}")
    if case != "pin":
        save()
    with pytest.raises(OCFError):
        subject.record(root)


@pytest.mark.parametrize(
    "case",
    [
        "current_file",
        "predecessor_file",
        "resolved",
        "previous_baseline",
        "unrelated_speech",
        "baseline",
        "behavior",
        "raw",
        "binding",
        "metadata",
        "engineering",
    ],
)
def test_verifier_rejects_scope_drift_even_with_current_file_witness(evidence, case):
    root, data, texts, write, save = evidence
    if case == "current_file":
        write(subject.FUNCTION, "changed")
    elif case == "predecessor_file":
        data["files"][subject.FUNCTION]["before"] += " "
    elif case == "resolved":
        texts[next(iter(texts))] += " changed"
    elif case == "previous_baseline":
        write("previous.json", {})
    elif case == "unrelated_speech":
        texts["unrelated"] = "new text"
    elif case == "baseline":
        write(subject.BASELINE, {})
    elif case == "engineering":
        lock = json.loads((root / "new-lock.json").read_text())
        lock["profiles"]["dsp"] = "retuned"
        write("new-lock.json", lock)
    else:
        name = subject.FUNCTION if case == "behavior" else subject.NARRATION
        value = yaml.safe_load((root / name).read_text())
        if case == "behavior":
            value["lifecycle"]["persistence"] = "changed"
        else:
            entry = next(iter(value["entries"].values()))
            if case == "raw":
                entry["text"] += " changed"
            elif case == "binding":
                entry["cue_template"]["function_id"] = "OTHER"
            else:
                entry["status"] = "draft"
        data["files"][name]["after_sha256"] = subject.sha(write(name, yaml.safe_dump(value)))
    save()
    with pytest.raises(OCFError):
        subject.verify(root)
