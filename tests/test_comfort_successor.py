"""Scoped approved successor, immutable predecessor views and failure boundaries."""

import json
from copy import deepcopy

import pytest
import yaml
from ocf_tools import editorial_successors as successors
from ocf_tools.utils import OCFError

OWNER = "OCF-BOD-003"
PRIMARY = "OCF-CMD-BOD-003-PRIMARY"
ALIAS = "OCF-CMD-BOD-003-LEGACY-01"
FUNCTION = "functions/body/de-discomfort.yaml"
NAR = "locales/en-US/hplus-OCF-BOD-003.yaml"
OLD = "Plus Five Five Five One Five"
NEW = "Plus Comfort"


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    path.write_bytes(text.encode("utf-8"))
    return text


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    from tools import check_hplus_narration_integrity as integrity

    monkeypatch.setattr(successors, "REGISTERED", (successors.REGISTERED[0],))
    old_function = {
        "id": OWNER,
        "canonical": {"name": "De-Discomfort", "command": {"primary": "PLUS-COMFORT", "modes": []}},
        "commands": [
            {
                "id": PRIMARY,
                "role": "activation",
                "designation": "primary",
                "localization": {},
                "procedure": {"steps": ["inhale", "hold", "cue", "exhale"]},
                "spoken": None,
                "spoken_review": "unresolved",
            },
            {"id": ALIAS, "role": "legacy-alias", "documentation": {"visible": True}},
        ],
        "aliases": {"names": ["De-Discomfort"], "commands": ["PLUS-55515"], "command_ids": [ALIAS]},
        "ocf": {"command_review": "review-required"},
        "purpose": {
            "summary": "Comfort; proposed concise cue PLUS-COMFORT.",
            "community_description": "Comfort; proposed concise cue PLUS-COMFORT.",
        },
        "compatibility": {"state": "bridge-trainable", "rationale": "old"},
        "lifecycle": {"persistence": "temporary"},
        "legacy": {"commands": ["PLUS-55515"]},
    }
    current = deepcopy(old_function)
    current["canonical"]["name"] = "Comfort"
    primary = current["commands"][0]
    primary.update(
        spoken=NEW,
        spoken_review="reviewed",
        observed_phrase={
            "text": NEW,
            "narration_key": "hplus.function.ocf-bod-003.function-body",
            "relationship": "canonical-match",
        },
    )
    primary["localization"] = {
        "spoken_cue_key": "commands.ocf-cmd-bod-003-primary.spoken-cue",
        "display_cue_key": "commands.ocf-cmd-bod-003-primary.display-cue",
    }
    current["commands"][1]["availability"] = "historical-lookup"
    current["commands"][1]["documentation"]["visible"] = False
    current["aliases"].update(commands=[], command_ids=[])
    current["ocf"]["command_review"] = "approved"
    current["purpose"] = {
        key: value.replace("proposed concise cue", "activation cue")
        for key, value in current["purpose"].items()
    }
    current["historical_lookup"] = [{"text": OLD, "kind": "former-teaching"}]
    current["compatibility"] = {"state": "historical-lookup", "rationale": "explicit user approval"}
    changes, old_entries, new_entries, before_texts, after_texts = [], {}, {}, {}, {}
    for role in ("function-body", "closer"):
        key = "hplus.function.ocf-bod-003." + role
        identity = NAR + "::" + key
        text = 'Select target; inhale and hold. Think "' + OLD + '." Exhale.\n'
        after = text.replace(OLD, NEW)
        template = after.replace(NEW, "{{ cue.primary }}")
        old_entries[key] = {
            "text": text,
            "notes": "Historical wording preserved",
            "version": "1.0.0",
        }
        new_entries[key] = {
            **old_entries[key],
            "text": template,
            "version": "1.0.1",
            "cue_template": {"function_id": OWNER, "allowed": ["cue.primary"]},
        }
        before_texts[identity], after_texts[identity] = text, after
        changes.append(
            {
                "identity": identity,
                "function_id": OWNER,
                "before_text": text,
                "before_sha256": successors.sha(text),
                "after_sha256": successors.sha(after),
                "raw_template_sha256": successors.sha(template),
                "substitutions": [{"before": OLD, "after": NEW, "count": 1}],
                "diff": "approved cue only",
            }
        )
    monkeypatch.setattr(integrity, "narration_texts", lambda root: dict(after_texts))
    prior_files = {
        FUNCTION: yaml.safe_dump(old_function),
        NAR: yaml.safe_dump({"entries": old_entries}),
    }
    files = {
        FUNCTION: write(tmp_path, FUNCTION, yaml.safe_dump(current)),
        NAR: write(tmp_path, NAR, yaml.safe_dump({"entries": new_entries})),
    }
    previous_baseline = "tests/fixtures/hplus-narration-text-baseline-002.json"
    baseline = "tests/fixtures/hplus-narration-text-baseline-003.json"
    old_baseline = write(
        tmp_path,
        previous_baseline,
        {key: successors.sha(value) for key, value in before_texts.items()},
    )
    files[baseline] = write(
        tmp_path, baseline, {key: successors.sha(value) for key, value in after_texts.items()}
    )
    old_lock_name = "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-003.json"
    new_lock_name = "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-004.json"
    lock = {
        "profiles": {"dsp": "unchanged"},
        "files": {NAR: successors.sha(prior_files[NAR]), "engineering.yaml": "0" * 64},
    }
    old_lock = write(tmp_path, old_lock_name, lock)
    lock["files"][NAR] = successors.sha(files[NAR])
    files[new_lock_name] = write(tmp_path, new_lock_name, lock)
    decision = {
        "function_id": OWNER,
        "primary_command_id": PRIMARY,
        "previous": {"title": "De-Discomfort", "display_cue": "PLUS-COMFORT", "spoken_cue": OLD},
        "current_title": "Comfort",
        "display_cue": "PLUS-COMFORT",
        "spoken_cue": NEW,
        "title_status": "APPROVED AND IMPLEMENTED",
        "cue_status": "APPROVED AND IMPLEMENTED",
        "narration_keys_changed": list(old_entries),
        "narration_file": NAR,
        "function_file": FUNCTION,
        "historical_command_ids": [ALIAS],
        "translator_notes": "Retain procedures",
    }
    record = {
        "schema_version": "1.0",
        "id": "OCF-EDITORIAL-TITLE-CUES-002",
        "source_commit": "a" * 40,
        "decision_source": "User response 1",
        "approval_scope": "One title and cue",
        "decisions": [decision],
        "allowed_text_changes": changes,
        "predecessor_files": prior_files,
        "previous_integrity_baseline": previous_baseline,
        "integrity_baseline": baseline,
        "previous_baseline_sha256": successors.sha(old_baseline),
        "previous_defaults_lock": old_lock_name,
        "defaults_lock": new_lock_name,
        "previous_defaults_sha256": successors.sha(old_lock),
        "source_files": {
            name: {
                "before_sha256": successors.sha(prior_files[name]) if name in prior_files else None,
                "after_sha256": successors.sha(text),
            }
            for name, text in files.items()
        },
        "unaffected_function_sha256": {},
        "pending": [],
        "rejected_or_superseded": [],
        "locales_requiring_review": ["es"],
    }
    write(tmp_path, successors.REGISTERED[0], record)
    return tmp_path, record, before_texts, after_texts, old_function, current


@pytest.mark.unit
def test_successor_verifies_current_and_preserves_exact_predecessor_view(fixture):
    root, data, before, after, old, current = fixture
    assert successors.verify(root) == []
    assert successors.before_texts(root, after) == before
    assert yaml.safe_load(successors.before_file(root, FUNCTION)) == old
    source = root / successors.REGISTERED[0]
    original = source.read_bytes()
    assert (
        successors.before_file(root, data["previous_defaults_lock"])
        == (root / data["previous_defaults_lock"]).read_text()
    )
    assert source.read_bytes() == original


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutation",
    [
        "pair",
        "unknown-id",
        "duplicate-decision",
        "substitution",
        "owner",
        "extra-key",
        "missing-predecessors",
    ],
)
def test_approval_scope_cannot_be_expanded_by_manifest_edits(fixture, mutation):
    root, data, *_ = fixture
    if mutation == "pair":
        data["decisions"][0]["current_title"] = "Unauthorized"
    elif mutation == "unknown-id":
        data["id"] = "OCF-EDITORIAL-TITLE-CUES-999"
    elif mutation == "duplicate-decision":
        data["decisions"].append(deepcopy(data["decisions"][0]))
    elif mutation == "substitution":
        data["allowed_text_changes"][0]["substitutions"].append(
            {"before": "inhale", "after": "do not inhale", "count": 1}
        )
    elif mutation == "owner":
        data["allowed_text_changes"][0]["function_id"] = "OCF-BOD-004"
    elif mutation == "extra-key":
        data["allowed_text_changes"][0]["identity"] += ".unapproved"
    else:
        data.pop("predecessor_files")
    write(root, successors.REGISTERED[0], data)
    with pytest.raises(OCFError):
        successors.records(root)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["title", "display_cue", "spoken_cue"])
def test_predecessor_wording_cannot_authorize_procedure_replacement(fixture, field):
    root, data, _, after, *_ = fixture
    data["decisions"][0]["previous"][field] = "inhale"
    if field == "spoken_cue":
        for row in data["allowed_text_changes"]:
            changed = row["before_text"].replace("inhale", NEW)
            row["substitutions"] = [{"before": "inhale", "after": NEW, "count": 1}]
            row["after_sha256"] = successors.sha(changed)
            row["raw_template_sha256"] = successors.sha(changed.replace(NEW, "{{ cue.primary }}"))
            after[row["identity"]] = changed
    write(root, successors.REGISTERED[0], data)
    # Reject authorization itself, before accepting even self-consistent replay hashes.
    with pytest.raises(OCFError, match="predecessor wording"):
        successors.before_texts(root, after)
    with pytest.raises(OCFError, match="predecessor wording"):
        successors.before_file(root, FUNCTION)


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutation",
    [
        "lifecycle",
        "procedure",
        "title",
        "spoken",
        "observed",
        "binding",
        "identity-count",
        "legacy",
        "alias-active",
    ],
)
def test_matching_file_hash_does_not_authorize_changed_behavior(fixture, mutation):
    root, data, before, after, old, current = fixture
    if mutation == "lifecycle":
        current["lifecycle"]["persistence"] = "permanent"
    elif mutation == "procedure":
        current["commands"][0]["procedure"]["steps"] = ["skip targeting"]
    elif mutation == "title":
        current["canonical"]["name"] = "Unauthorized"
    elif mutation == "spoken":
        current["commands"][0]["spoken"] = "Plus Other"
    elif mutation == "observed":
        current["commands"][0]["observed_phrase"]["text"] = OLD
    elif mutation == "binding":
        current["commands"][0]["localization"]["spoken_cue_key"] = "cue.unrelated"
    elif mutation == "identity-count":
        current["commands"].pop()
    elif mutation == "legacy":
        current["legacy"]["commands"] = []
    else:
        current["commands"][1]["availability"] = "active"
    raw = write(root, FUNCTION, yaml.safe_dump(current))
    data["source_files"][FUNCTION]["after_sha256"] = successors.sha(raw)
    write(root, successors.REGISTERED[0], data)
    with pytest.raises(OCFError):
        successors.verify(root)


@pytest.mark.unit
def test_stale_current_or_predecessor_bytes_fail_before_projection(fixture):
    root, data, before, after, *_ = fixture
    changed = dict(after)
    changed[next(iter(changed))] += " Extra."
    with pytest.raises(OCFError, match="speech drift"):
        successors.before_texts(root, changed)
    path = root / FUNCTION
    path.write_bytes(path.read_bytes() + b"# drift\n")
    with pytest.raises(OCFError, match="file drift"):
        successors.before_file(root, FUNCTION)
    data["source_files"][FUNCTION]["after_sha256"] = successors.sha(path.read_text())
    data["predecessor_files"][FUNCTION] += "# forged prior\n"
    write(root, successors.REGISTERED[0], data)
    with pytest.raises(OCFError, match="predecessor file"):
        successors.before_file(root, FUNCTION)


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutation",
    ["baseline", "old-lock", "profile", "engineering", "raw-template", "notes", "unaffected"],
)
def test_successor_reports_baseline_engineering_and_provenance_drift(fixture, mutation):
    root, data, before, after, *_ = fixture
    if mutation == "baseline":
        write(root, data["integrity_baseline"], {})
    elif mutation == "old-lock":
        path = root / data["previous_defaults_lock"]
        path.write_bytes(path.read_bytes() + b"\n")
    elif mutation in {"profile", "engineering"}:
        lock = json.loads((root / data["defaults_lock"]).read_text())
        if mutation == "profile":
            lock["profiles"]["dsp"] = "different"
        else:
            lock["files"]["engineering.yaml"] = "1" * 64
        write(root, data["defaults_lock"], lock)
    elif mutation in {"raw-template", "notes"}:
        narration = yaml.safe_load((root / NAR).read_text())
        entry = next(iter(narration["entries"].values()))
        entry["text" if mutation == "raw-template" else "notes"] += " extra"
        write(root, NAR, yaml.safe_dump(narration))
    else:
        write(root, "functions/unaffected.yaml", "changed")
        data["unaffected_function_sha256"]["functions/unaffected.yaml"] = successors.sha("prior")
        write(root, successors.REGISTERED[0], data)
    assert successors.verify(root)


@pytest.mark.unit
def test_missing_registered_successor_is_not_silently_accepted(tmp_path):
    assert successors.records(tmp_path) == []
    with pytest.raises(OCFError, match="missing"):
        successors.records(tmp_path, required=True)


@pytest.mark.integration
def test_comfort_decision_four_passes_controls_and_other_175_entries_preserved():
    from ocf_tools.commands import cue_presentation, is_active
    from ocf_tools.indexes import load_all_functions, load_function_by_id
    from ocf_tools.narration_first import plan_narration
    from ocf_tools.paths import REPO_ROOT
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    assert successors.verify() == []
    data = successors.records()[0]
    from ocf_tools.options_successor import before_texts

    current = text_fingerprints(before_texts(REPO_ROOT, narration_texts()))
    # Check Comfort's historical revision after authenticating later successors.
    for later in reversed(successors.records()[1:]):
        for change in later["allowed_text_changes"]:
            assert current[change["identity"]] == change["after_sha256"]
            current[change["identity"]] = change["before_sha256"]
    previous = json.loads((REPO_ROOT / data["previous_integrity_baseline"]).read_text())
    assert len(current) == len(previous) == 177
    assert {key for key in current if current[key] != previous[key]} == {
        row["identity"] for row in data["allowed_text_changes"]
    }
    assert len(data["allowed_text_changes"]) == 2
    record = load_function_by_id(OWNER)
    assert record.canonical_name == "Comfort" and record.canonical_command == "PLUS-COMFORT"
    assert cue_presentation(record, strict=True)["spoken_cue"] == NEW
    assert record.persistence == "temporary" and record.command_modes == []
    assert record.legacy_commands == ["PLUS-55515"]
    assert {row.id for row in record.command_records if is_active(row)} == {PRIMARY}
    all_records = [
        row
        for row in load_all_functions()
        if row.data["legacy"]["source_system"] == "Monroe H-PLUS"
    ]
    assert len(all_records) == 55 and sum(len(row.command_records) for row in all_records) == 97
    assert sum(is_active(command) for row in all_records for command in row.command_records) == 78
    plan = plan_narration(OWNER, locale="en-US")
    for playback in range(1, 5):
        text = "\n\n".join(
            row["canonical_text"]
            for row in plan["segments"]
            if row["role"] == "function-body" and row["playback"] == playback
        )
        assert text.count(NEW) == 3 and OLD not in text and "{{" not in text
    closer = "\n\n".join(
        row["canonical_text"] for row in plan["segments"] if row["role"] == "closer"
    )
    assert NEW in closer and "OCF Comfort exercise" in closer and OLD not in closer


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["recording", "hybrid"])
def test_numeric_recording_remains_stale_even_with_hybrid_tts_fallback(tmp_path, mode):
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.narration_sources import SourceResolver
    from test_narration_sources import fixture as recording_fixture

    doc, config, path = recording_fixture(tmp_path, mode=mode)
    row = next(
        item
        for item in successors.records()[0]["allowed_text_changes"]
        if item["identity"].endswith("function-body")
    )
    entry, _ = LocaleCatalog().resource(
        "hplus.function.ocf-bod-003.function-body", "en-US", domain="narration", fallback=False
    )
    doc["timeline"] = [{"id": "first", "at": 0, "text": entry.text}]
    config["recordings"]["take"]["text_sha256"] = row["before_sha256"]
    config["fallback"] = "tts"
    path.write_text(json.dumps(config), encoding="utf-8")
    original = path.read_bytes(), (tmp_path / "take.wav").read_bytes()
    with pytest.raises(OCFError, match="fingerprint"):
        SourceResolver(doc, path)
    assert original == (path.read_bytes(), (tmp_path / "take.wav").read_bytes())


@pytest.mark.unit
def test_new_cue_invalidates_speech_but_identical_shared_text_is_reused(tmp_path, monkeypatch):
    from ocf_tools import speech_cache
    from test_bulk_render import pcm

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: {"voice": "same-fixture"})
    calls = []

    def synthesize():
        calls.append(1)
        return pcm()

    with speech_cache.enabled():
        for text in ("Shared preparation", OLD, NEW, "Shared preparation", NEW):
            speech_cache.cached_cue({}, text, synthesize)
    assert len(calls) == 3


@pytest.mark.integration
def test_historical_discovery_and_future_artifact_names_use_comfort():
    from ocf_tools.artifact_names import ArtifactNamer
    from ocf_tools.vocabulary import lookup

    for query in ("De-Discomfort", "PLUS-55515", OLD):
        row = next(item for item in lookup(query) if item["function_id"] == OWNER)
        assert row["title"] == "Comfort" and row["cue"]["spoken_cue"] == NEW
        assert row["activation_selected"] is False
        assert all(match["historical"] for match in row["matches"])
    assert (
        ArtifactNamer().filename(OWNER, "Comfort", "en-US", "wav")
        == "OCF-BOD-003 - Comfort - en-US.wav"
    )
