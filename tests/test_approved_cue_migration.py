"""Explicit editorial scope, immutable predecessors, and current integrated teaching."""

from __future__ import annotations

import io
import json
import wave
from types import SimpleNamespace

import pytest
import yaml
from ocf_tools import commands, cue_migration, speech_cache
from ocf_tools.artifact_names import ArtifactNamer
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocaleCatalog
from ocf_tools.utils import OCFError
from tools import approved_cue_migration as author
from tools import check_hplus_narration_integrity as integrity

EXPECTED = {
    "OCF-EXP-001": ("Manifest", "PLUS-MANIFEST", "Plus Manifest"),
    "OCF-SLP-005": ("Sleep Easy", "PLUS-SLEEP EASY", "Plus Sleep Easy"),
    "OCF-BOD-001": ("Brain Flow", "PLUS-BRAIN FLOW", "Plus Brain Flow"),
    "OCF-BOD-009": ("Breathe Better", "PLUS-BREATHE BETTER", "Plus Breathe Better"),
    "OCF-EMO-002": ("Offload", "PLUS-OFFLOAD", "Plus Offload"),
    "OCF-EMO-003": ("Empathize", "PLUS-EMPATHIZE", "Plus Empathize"),
    "OCF-EXP-002": ("Insulate", "PLUS-INSULATE", "Plus Insulate"),
    "OCF-SLP-004": ("Sleep Insight", "PLUS-SLEEP INSIGHT", "Plus Sleep Insight"),
    "OCF-PRF-002": ("Inner Power", "PLUS-INNER POWER", "Plus Inner Power"),
    "OCF-BOD-004": ("Detox", "PLUS-DETOX", "Plus Detox"),
    "OCF-BOD-006": ("Heart: Repairs & Maintenance", "PLUS-HEART-BETTER", "Plus Heart Better"),
}


def synthetic_predecessor(monkeypatch, tmp_path):
    owner = "OCF-BOD-006"
    old = "Plus Heart Better Better"
    primary_id = "OCF-CMD-BOD-006-PRIMARY"
    old_id = "OCF-CMD-BOD-006-LEGACY-01"
    doc = {
        "id": owner,
        "canonical": {
            "name": "Heart: Repairs & Maintenance",
            "command": {"primary": "PLUS-HEART, BETTER, BETTER", "modes": []},
        },
        "commands": [
            {
                "id": primary_id,
                "designation": "primary",
                "role": "activation",
                "localization": {},
                "procedure": {"ref": "unchanged"},
            },
            {
                "id": old_id,
                "designation": "secondary",
                "role": "legacy-alias",
                "documentation": {"visible": True},
            },
            {
                "id": "control",
                "designation": "special",
                "role": "release",
                "documentation": {"visible": True},
            },
        ],
        "aliases": {"commands": ["OLD"], "command_ids": [old_id], "names": ["Old Heart"]},
        "purpose": {},
        "lifecycle": {"persistence": "permanent"},
    }
    function = tmp_path / "functions/heart.yaml"
    function.parent.mkdir(parents=True)
    # Model Git's committed UTF-8/LF bytes, independently of the host newline.
    function.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8", newline="\n")
    nar = tmp_path / "locales/en-US/hplus-OCF-BOD-006.yaml"
    nar.parent.mkdir(parents=True)
    nar.write_text(
        'entries:\n  fixture.opener:\n    version: 1.0.0\n    text: |-\n      Original opening.\n  fixture.function-body:\n    version: 1.0.0\n    notes: historical Plus Heart Better Better remains quoted here\n    text: |-\n      Inhale and hold. Think "Plus Heart Better Better." Then exhale.\n      Think Plus Release only for the selected application.\n  fixture.closer:\n    version: 1.0.0\n    text: |-\n      Remember Plus Heart Better Better.\n',
        encoding="utf-8",
        newline="\n",
    )

    def texts(root=tmp_path):
        return {
            nar.relative_to(tmp_path).as_posix() + "::" + key: value["text"]
            for key, value in yaml.safe_load(nar.read_text(encoding="utf-8"))["entries"].items()
        }

    baseline = tmp_path / author.BASELINE
    baseline.parent.mkdir(parents=True)
    baseline.write_text(
        json.dumps(integrity.text_fingerprints(texts())), encoding="utf-8", newline="\n"
    )
    ui = {
        f"functions.{owner.lower()}.{suffix}": "Old description"
        for suffix in ("title", "purpose", "short-description")
    }
    ui["commands.ocf-cmd-exp-002-release.usage"] = (
        "Places Zoning on hold; Cancel ends the adjustment."
    )
    (nar.parent / "commands.yaml").write_text(
        yaml.safe_dump({"entries": ui}, sort_keys=False), encoding="utf-8", newline="\n"
    )
    (nar.parent / "manifest.yaml").write_text(
        "semantic_version: 1.6.0\nresources:\n- file: commands.yaml\n  domain: ui\n",
        encoding="utf-8",
        newline="\n",
    )
    lock = tmp_path / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-001.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(
        json.dumps(
            {
                "id": "OCF-AUDIO-DEFAULTS-HPLUS-001",
                "version": "1.0.0",
                "profiles": {"dsp": {"id": "unchanged"}},
                "files": {
                    nar.relative_to(tmp_path).as_posix(): author.digest(nar.read_text()),
                    "engineering.yaml": "unchanged-hash",
                },
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    record = SimpleNamespace(
        id=owner,
        path=function,
        canonical_name=doc["canonical"]["name"],
        canonical_command=doc["canonical"]["command"]["primary"],
    )
    monkeypatch.setattr(author, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(author, "load_all_functions", lambda: [record])
    monkeypatch.setattr(
        author,
        "APPROVED",
        {owner: (None, "PLUS-HEART-BETTER", "Plus Heart Better", old, "Heart maintenance.")},
    )
    monkeypatch.setattr(author, "SELF_REFERENCES", {})
    monkeypatch.setattr(author, "narration_texts", texts)
    monkeypatch.setattr(integrity, "narration_texts", texts)
    original_sources = {
        path.relative_to(tmp_path).as_posix(): path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(author, "source_text", lambda name: original_sources[name])
    return texts, function, nar, lock


@pytest.mark.unit
def test_bounded_authoring_plan_preserves_procedures_history_and_nonspoken_notes(
    monkeypatch, tmp_path
):
    texts, function, nar, lock = synthetic_predecessor(monkeypatch, tmp_path)
    original = {p: p.read_bytes() for p in (function, nar, lock)}
    data, files = author.plan()
    assert all(path.read_bytes() == content for path, content in original.items())
    assert len(data["allowed_text_changes"]) == 2
    assert data["decisions"][0]["title_status"] == "TENTATIVE TITLE"
    assert data["decisions"][0]["pending_title"] == "Heart Flow"
    new = yaml.safe_load(files["functions/heart.yaml"])
    assert new["canonical"]["name"] == "Heart: Repairs & Maintenance"
    assert new["commands"][0]["procedure"] == {"ref": "unchanged"}
    assert new["commands"][1]["availability"] == "historical-lookup"
    assert "availability" not in new["commands"][2]
    assert new["aliases"]["commands"] == []
    changed = yaml.safe_load(files[nar.relative_to(tmp_path).as_posix()])["entries"]
    assert changed["fixture.opener"]["text"] == "Original opening."
    assert changed["fixture.function-body"]["notes"].endswith(
        "Plus Heart Better Better remains quoted here"
    )
    assert 'Think "Plus Heart Better." Then exhale.' in changed["fixture.function-body"]["text"]
    assert (
        "Think Plus Release only for the selected application."
        in changed["fixture.function-body"]["text"]
    )
    assert author.main(["--apply", "--report", str(tmp_path / "preflight.json")]) == 0
    assert cue_migration.verify_migration(tmp_path) == []
    with pytest.raises(OCFError, match="already recorded"):
        author.plan()


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["baseline", "identity", "source", "unknown-owner"])
def test_authoring_rejects_predecessor_drift_before_any_write(monkeypatch, tmp_path, mutation):
    texts, function, nar, lock = synthetic_predecessor(monkeypatch, tmp_path)
    if mutation == "baseline":
        (tmp_path / author.BASELINE).write_text("{}")
    elif mutation == "identity":
        function.write_text(
            function.read_text().replace("OCF-CMD-BOD-006-PRIMARY", "wrong-primary")
        )
    elif mutation == "source":
        monkeypatch.setattr(author, "source_text", lambda name: "different predecessor")
    else:
        monkeypatch.setattr(author, "load_all_functions", lambda: [])
    before = function.read_bytes(), nar.read_bytes()
    with pytest.raises(OCFError):
        author.plan()
    assert before == (function.read_bytes(), nar.read_bytes())
    assert not (tmp_path / author.MANIFEST).exists()


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["old-lock", "coordinated-text-baseline"])
def test_preexisting_predecessor_edits_cannot_be_blessed_by_new_hashes(
    monkeypatch, tmp_path, mutation
):
    texts, function, nar, lock = synthetic_predecessor(monkeypatch, tmp_path)
    if mutation == "old-lock":
        lock.write_text(lock.read_text() + "\n")
    else:
        nar.write_text(nar.read_text().replace("Original opening.", "Unapproved prior wording."))
        (tmp_path / author.BASELINE).write_text(json.dumps(integrity.text_fingerprints(texts())))
    before = function.read_bytes(), nar.read_bytes(), lock.read_bytes()
    with pytest.raises(OCFError, match="predecessor differs from pinned"):
        author.plan()
    assert before == (function.read_bytes(), nar.read_bytes(), lock.read_bytes())


@pytest.mark.unit
def test_pinned_source_byte_guard_rejects_newline_only_drift(monkeypatch, tmp_path):
    synthetic_predecessor(monkeypatch, tmp_path)
    path = tmp_path / "locales/en-US/commands.yaml"
    committed = path.read_bytes()
    assert b"\r\n" not in committed and b"\n" in committed
    edited = committed.replace(b"\n", b"\r\n")
    path.write_bytes(edited)
    with pytest.raises(OCFError, match="predecessor differs from pinned source"):
        author.plan()
    assert path.read_bytes() == edited
    assert not (tmp_path / author.MANIFEST).exists()


@pytest.mark.unit
def test_migration_preserves_preexisting_and_racing_successor_artifacts(monkeypatch, tmp_path):
    texts, function, nar, lock = synthetic_predecessor(monkeypatch, tmp_path)
    target = lock.with_name("OCF-AUDIO-DEFAULTS-HPLUS-002.json")
    target.write_text("existing successor\n")
    before = function.read_bytes(), nar.read_bytes()
    with pytest.raises(OCFError, match="existing successor artifact"):
        author.plan()
    assert target.read_text() == "existing successor\n"
    # Remove only this test-owned synthetic file to exercise a different race.
    target.unlink()
    writer = author.write_text_atomic

    def racing_writer(path, text, **kwargs):
        if path == target:
            path.write_text("concurrent successor\n")
        return writer(path, text, **kwargs)

    monkeypatch.setattr(author, "write_text_atomic", racing_writer)
    assert author.main(["--apply"]) == 1
    assert target.read_text() == "concurrent successor\n"
    assert before == (function.read_bytes(), nar.read_bytes())


@pytest.mark.unit
def test_unaffected_unicode_input_uses_explicit_utf8_and_retains_identity(monkeypatch, tmp_path):
    synthetic_predecessor(monkeypatch, tmp_path)
    path = tmp_path / "functions/unaffected.yaml"
    text = "id: OCF-FND-999\npurpose: Énergie 見る\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    records = author.load_all_functions()
    monkeypatch.setattr(
        author,
        "load_all_functions",
        lambda: records + [SimpleNamespace(id="OCF-FND-999", path=path)],
    )
    original_source = author.source_text
    monkeypatch.setattr(
        author,
        "source_text",
        lambda name: text if name == "functions/unaffected.yaml" else original_source(name),
    )
    original_reader = type(path).read_text

    def explicit_reader(self, *args, **kwargs):
        if self == path:
            assert kwargs.get("encoding") == "utf-8"
        return original_reader(self, *args, **kwargs)

    monkeypatch.setattr(type(path), "read_text", explicit_reader)
    data, files = author.plan()
    assert data["unaffected_function_sha256"]["functions/unaffected.yaml"] == author.digest(text)
    assert "functions/unaffected.yaml" not in files


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["narration-file", "source-hash"])
def test_malformed_nested_manifest_is_a_schema_error_not_a_traceback(
    monkeypatch, tmp_path, capsys, mutation
):
    synthetic_predecessor(monkeypatch, tmp_path)
    assert author.main(["--apply"]) == 0
    data = json.loads((tmp_path / author.MANIFEST).read_text())
    if mutation == "narration-file":
        del data["decisions"][0]["narration_file"]
    else:
        del next(iter(data["source_files"].values()))["after_sha256"]
    monkeypatch.setattr(cue_migration, "decision_record", lambda root=None: data)
    assert author.main(["--check"]) == 1
    assert "invalid editorial migration" in capsys.readouterr().err


@pytest.mark.unit
def test_integrity_cli_translates_expected_migration_errors(monkeypatch, capsys):
    def invalid(**kwargs):
        raise OCFError("invalid editorial migration fixture")

    monkeypatch.setattr(integrity, "check", invalid)
    assert integrity.main([]) == 2
    assert "invalid editorial migration fixture" in capsys.readouterr().err


@pytest.mark.unit
def test_an_edited_manifest_cannot_authorize_extra_programming_changes(monkeypatch, tmp_path):
    texts, function, nar, lock = synthetic_predecessor(monkeypatch, tmp_path)
    assert author.main(["--apply"]) == 0
    path = tmp_path / author.MANIFEST
    data = json.loads(path.read_text())
    row = next(
        item for item in data["allowed_text_changes"] if item["identity"].endswith("function-body")
    )
    changed = cue_migration.replay_change(row).replace(
        "Inhale and hold.", "Skip the breath entirely."
    )
    row["substitutions"].append(
        {"before": "Inhale and hold.", "after": "Skip the breath entirely.", "count": 1}
    )
    row["after_sha256"] = author.digest(changed)
    path.write_text(json.dumps(data))
    with pytest.raises(OCFError, match="non-allowlisted change"):
        cue_migration.verify_migration(tmp_path)


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutation",
    [
        "unaffected-text",
        "cue",
        "old-baseline",
        "source-hash",
        "engineering",
        "membership",
        "old-lock",
        "unknown-key",
        "identity-set",
    ],
)
def test_integrity_successor_rejects_unapproved_or_corrupt_changes(monkeypatch, tmp_path, mutation):
    synthetic_predecessor(monkeypatch, tmp_path)
    assert author.main(["--apply"]) == 0
    nar = tmp_path / "locales/en-US/hplus-OCF-BOD-006.yaml"
    record = tmp_path / author.MANIFEST
    if mutation in {"unaffected-text", "cue"}:
        old, new = (
            ("Original opening.", "Unauthorized mechanism.")
            if mutation == "unaffected-text"
            else ("Plus Heart Better.", "Plus Heart Better Better.")
        )
        nar.write_text(nar.read_text().replace(old, new))
    elif mutation == "old-baseline":
        baseline = tmp_path / author.BASELINE
        baseline.write_text(baseline.read_text() + "\n")
    elif mutation == "source-hash":
        path = tmp_path / "functions/heart.yaml"
        path.write_text(path.read_text() + "# unexpected edit\n")
    elif mutation in {"engineering", "membership"}:
        path = tmp_path / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json"
        data = json.loads(path.read_text())
        if mutation == "engineering":
            data["files"]["engineering.yaml"] = "changed"
        else:
            del data["files"]["engineering.yaml"]
        path.write_text(json.dumps(data))
    elif mutation == "old-lock":
        path = tmp_path / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-001.json"
        path.write_text(path.read_text() + "\n")
    elif mutation == "unknown-key":
        data = json.loads(record.read_text())
        data["allowed_text_changes"][0]["identity"] += ".unknown"
        record.write_text(json.dumps(data))
    else:
        data = yaml.safe_load(nar.read_text())
        data["entries"]["extra"] = {"text": "Extra protected identity."}
        nar.write_text(yaml.safe_dump(data))
    assert cue_migration.verify_migration(tmp_path)


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["before", "after", "count"])
def test_replay_refuses_blessing_changed_text_or_occurrence_counts(mutation):
    row = {
        "before_text": "Plus Old.",
        "before_sha256": author.digest("Plus Old."),
        "after_sha256": author.digest("Plus New."),
        "substitutions": [{"before": "Plus Old", "after": "Plus New", "count": 1}],
    }
    if mutation == "count":
        row["substitutions"][0]["count"] = 2
    else:
        row[mutation + "_sha256"] = "0" * 64
    with pytest.raises(OCFError):
        cue_migration.replay_change(row)


@pytest.mark.unit
@pytest.mark.parametrize("name", ["../outside.json", "/outside.json", "C:\\private\\source.json"])
def test_migration_dependency_containment(tmp_path, name):
    with pytest.raises(OCFError, match="escapes checkout"):
        cue_migration.contained(tmp_path, name)


@pytest.mark.unit
def test_cue_change_misses_cache_while_identical_shared_speech_reuses_it(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: {"backend": "synthetic"})
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setparams((1, 2, 8000, 0, "NONE", ""))
        writer.writeframes(b"\0\0" * 80)
    seen = []

    def render():
        seen.append(1)
        return buffer.getvalue()

    with speech_cache.enabled():
        for text in (
            "Shared preparation.",
            "Plus Quiet Sleep.",
            "Plus Sleep Easy.",
            "Shared preparation.",
            "Plus Sleep Easy.",
        ):
            speech_cache.cached_cue({}, text, render)
    assert len(seen) == 3


@pytest.mark.integration
def test_exact_user_decisions_integrity_and_unaffected_active_vocabulary():
    data = cue_migration.decision_record()
    assert cue_migration.verify_migration() == []
    assert len(data["allowed_text_changes"]) == 21
    old = json.loads((author.REPO_ROOT / author.BASELINE).read_text())
    from ocf_tools.editorial_successors import before_texts

    current = integrity.text_fingerprints(
        before_texts(author.REPO_ROOT, integrity.narration_texts())
    )
    assert len(old) == len(current) == 177
    assert sum(old[key] != current[key] for key in old) == 21
    catalog = LocaleCatalog()
    records = {record.id: record for record in load_all_functions()}
    assert set(EXPECTED) == set(author.APPROVED)
    for owner, (title, display, speech) in EXPECTED.items():
        record = records[owner]
        primary = next(row for row in record.command_records if row.designation == "primary")
        assert (record.canonical_name, record.canonical_command) == (title, display)
        view = commands.cue_presentation(record, "en-US", catalog=catalog, strict=True)
        assert view["display_cue"] == display and view["spoken_cue"] == speech
        assert view["spoken_locale"] == view["display_locale"] == "en-US"
        assert primary.id == f"OCF-CMD-{owner[4:]}-PRIMARY"
        name = ArtifactNamer().filename(owner, title, "en-US", "wav")
        assert owner in name and title.replace(":", "-").split()[0] in name
        before = yaml.safe_load(
            author.source_text(record.path.relative_to(author.REPO_ROOT).as_posix())
        )
        assert record.data["legacy"] == before["legacy"]
        assert record.data["lifecycle"] == before["lifecycle"]
        for command in record.command_records:
            old = next(row for row in before["commands"] if row["id"] == command.id)
            assert command.data.get("procedure") == old.get("procedure")
            assert command.data.get("relationships") == old.get("relationships")
        if owner == "OCF-BOD-006":
            assert record.data["purpose"] == before["purpose"]
    assert records["OCF-BOD-006"].canonical_name != "Heart Flow"
    assert not {"Heart Renewal", "Body Cleansing", "Body Cleanse"} & {
        row.canonical_name for row in records.values()
    }
    active = [
        row
        for record in records.values()
        for row in record.command_records
        if commands.is_active(row)
    ]
    assert len(active) == 88  # Comfort and Regenerate retire their superseded primary aliases.
    assert len({row.id for row in active if row.designation == "primary"}) == 55


@pytest.mark.integration
@pytest.mark.parametrize("owner", list(EXPECTED))
def test_all_four_body_passes_and_closer_resolve_the_approved_cue(owner):
    from ocf_tools.narration_first import plan_narration

    plan = plan_narration(owner, locale="en-US")
    cue = EXPECTED[owner][2]
    body = [row for row in plan["segments"] if row["role"] == "function-body"]
    assert {row["playback"] for row in body} == {1, 2, 3, 4}
    for playback in range(1, 5):
        text = "\n\n".join(row["canonical_text"] for row in body if row["playback"] == playback)
        assert '"' + cue + '."' in text
        previous = author.APPROVED[owner][3]
        if previous != cue:
            assert previous not in text
    closer = "\n\n".join(
        row["canonical_text"] for row in plan["segments"] if row["role"] == "closer"
    )
    assert '"' + cue + '."' in closer


@pytest.mark.integration
def test_historical_lookup_returns_current_cues_without_reviving_aliases():
    from ocf_tools.vocabulary import lookup

    data = cue_migration.decision_record()
    for decision in data["decisions"]:
        for query in (
            decision["previous"]["title"],
            decision["previous"]["display_cue"],
            decision["previous"]["spoken_cue"],
        ):
            rows = lookup(query)
            match = next(row for row in rows if row["function_id"] == decision["function_id"])
            assert match["title"] == decision["current_title"]
            assert match["cue"]["spoken_cue"] == decision["spoken_cue"]
            assert match["activation_selected"] is False
    insulate = next(row for row in load_all_functions() if row.id == "OCF-EXP-002")
    assert {row.role for row in insulate.command_records if commands.is_active(row)} == {
        "activation",
        "cancel",
        "release",
    }
    assert insulate.command_modes == ["PLUS-CANCEL"]
    assert commands.cue_presentation(insulate, "es")["binding_status"] == "requires-locale-review"
    control = next(row for row in lookup("Plus Release") if row["function_id"] == "OCF-EXP-002")
    assert any(
        match.get("role") == "release" and not match["historical"] and match["active_record"]
        for match in control["matches"]
    )


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["recording", "hybrid"])
def test_old_selected_recording_is_stale_without_automatic_tts_fallback(tmp_path, mode):
    from ocf_tools.narration_sources import SourceResolver
    from test_narration_sources import fixture

    document, config, path = fixture(tmp_path, mode=mode)
    migration = cue_migration.decision_record()
    row = next(
        item
        for item in migration["allowed_text_changes"]
        if item["identity"].endswith("hplus.function.ocf-slp-005.function-body")
    )
    current = LocaleCatalog().resource(
        "hplus.function.ocf-slp-005.function-body", "en-US", domain="narration", fallback=False
    )[0]
    document["timeline"] = [{"id": "first", "at": 0, "text": current.text}]
    config["recordings"]["take"]["text_sha256"] = row["before_sha256"]
    config["fallback"] = "tts"
    path.write_text(json.dumps(config))
    original = (tmp_path / "take.wav").read_bytes()
    manifest_bytes = path.read_bytes()
    with pytest.raises(OCFError, match="fingerprint"):
        SourceResolver(document, path)
    assert path.read_bytes() == manifest_bytes
    assert (tmp_path / "take.wav").read_bytes() == original


@pytest.mark.unit
@pytest.mark.parametrize("owner", list(EXPECTED))
def test_each_approved_spoken_change_has_correct_cache_identity_behavior(
    monkeypatch, tmp_path, owner
):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: {"fixed": True})
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setparams((1, 2, 8000, 0, "NONE", ""))
        writer.writeframes(b"\0\0" * 80)
    calls = []

    def render():
        calls.append(1)
        return buffer.getvalue()

    before, after = author.APPROVED[owner][3], EXPECTED[owner][2]
    with speech_cache.enabled():
        speech_cache.cached_cue({}, before, render)
        speech_cache.cached_cue({}, after, render)
        speech_cache.cached_cue({}, after, render)
    assert len(calls) == (1 if before == after else 2)
