"""Public core tests use synthetic revision/preset wording, never private supplied text."""

import os
import shutil
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from ocf_tools import locale as locales
from ocf_tools.locale import LocaleCatalog, LocalizationError, iter_events, resolve_document
from ocf_tools.session import compose, load_template, run_compose
from ocf_tools.utils import OCFError, yaml_safe_dump, yaml_safe_load

REVISION = "TEST-REV"
SYNTHETIC = {
    "fixture.line": "Revised fixture words.",
    "hplus.optional.affirmation.begin": "Synthetic introduction.",
    "hplus.optional.affirmation.gateway": "Synthetic Gateway fixture.",
    "hplus.optional.affirmation.synccreation": "Synthetic SyncCreation fixture.",
    "hplus.optional.affirmation.ocf": "Synthetic OCF fixture.",
    "hplus.optional.affirmation.complete": "Synthetic conclusion.",
}


def write_revision(pack):
    manifest = yaml_safe_load((pack / "manifest.yaml").read_text())
    manifest["resources"].append(
        {"file": "fixture-revision.yaml", "domain": "narration", "revision": REVISION}
    )
    (pack / "manifest.yaml").write_text(yaml_safe_dump(manifest), encoding="utf-8")
    data = {
        "schema_version": "1.0",
        "locale": "en-US",
        "domain": "narration",
        "entries": {
            key: {"text": text, "status": "reviewed", "version": "1.0.0"}
            for key, text in SYNTHETIC.items()
        },
    }
    (pack / "fixture-revision.yaml").write_text(yaml_safe_dump(data), encoding="utf-8")


@pytest.fixture
def catalog(tmp_path):
    pack = tmp_path / "en-US"
    pack.mkdir()
    (pack / "manifest.yaml").write_text(
        yaml_safe_dump(
            {"locale": "en-US", "resources": [{"file": "base.yaml", "domain": "narration"}]}
        ),
        encoding="utf-8",
    )
    (pack / "base.yaml").write_text(
        "locale: en-US\ndomain: narration\nentries:\n  fixture.line: Original fixture.\n",
        encoding="utf-8",
    )
    write_revision(pack)
    return LocaleCatalog(tmp_path, function_records=lambda: [])


@pytest.mark.unit
def test_revision_is_explicit_nonmutating_and_survives_reresolution(catalog):
    doc = {
        "narration_revision": REVISION,
        "sections": [{"timeline": [{"id": "line", "narration_key": "fixture.line"}]}],
    }
    revised = resolve_document(doc, "en-US", catalog=catalog)
    assert next(iter_events(revised))["text"] == SYNTHETIC["fixture.line"]
    assert resolve_document(revised, "en-US", catalog=catalog) == revised
    assert catalog.canonical.get("fixture.line").text == "Original fixture."
    assert "text" not in next(iter_events(doc))
    with pytest.raises(LocalizationError):
        catalog.with_revision(REVISION, "es")
    with pytest.raises(LocalizationError, match="unavailable"):
        catalog.with_revision("UNKNOWN", "en-US")
    assert catalog.with_revision(None, "en-US") is catalog


@pytest.mark.unit
@pytest.mark.parametrize("saved", [True, False])
def test_revision_uses_unsaved_editor_reader_and_exists_callbacks(catalog, saved):
    target = catalog.root / "en-US/fixture-revision.yaml"
    if not saved:
        target.unlink()
    unsaved = {
        "locale": "en-US",
        "domain": "narration",
        "entries": {"fixture.line": "Unsaved fixture wording."},
    }

    def reader(path):
        return deepcopy(unsaved) if path == target else yaml_safe_load(path.read_text())

    view = LocaleCatalog(
        catalog.root,
        reader=reader,
        exists=lambda path: path == target or path.is_file(),
        function_records=lambda: [],
    )
    selected = view.with_revision(REVISION, "en-US")
    assert selected.canonical.get("fixture.line").text == "Unsaved fixture wording."
    assert view.canonical.get("fixture.line").text == "Original fixture."


@pytest.mark.unit
def test_pathless_pack_revision_has_a_resource_diagnostic():
    pack = locales.LocalePack(
        {
            "locale": "en-US",
            "resources": [{"file": "revision.yaml", "domain": "narration", "revision": REVISION}],
        },
        {},
        None,
    )
    with pytest.raises(LocalizationError, match="no resource path"):
        LocaleCatalog.from_packs([("en-US", pack)]).with_revision(REVISION, "en-US")


@pytest.mark.unit
def test_unselected_revision_cannot_bypass_resource_path_containment(catalog):
    manifest_path = catalog.root / "en-US/manifest.yaml"
    manifest = yaml_safe_load(manifest_path.read_text())
    manifest["resources"][-1]["file"] = "../outside.yaml"
    manifest_path.write_text(yaml_safe_dump(manifest), encoding="utf-8")
    outside = catalog.root / "outside.yaml"
    outside.write_text("entries: {}\n", encoding="utf-8")
    reads = []

    def reader(path):
        reads.append(path)
        return yaml_safe_load(path.read_text())

    rejected = LocaleCatalog(catalog.root, reader=reader, function_records=lambda: [])
    assert rejected.problems
    assert outside not in reads


@pytest.mark.integration
def test_malformed_unselected_revision_returns_locale_diagnostics(catalog):
    from ocf_tools.validators import validate_locale_packs

    (catalog.root / "en-US/fixture-revision.yaml").write_text(
        "entries: [unterminated", encoding="utf-8"
    )
    assert catalog.canonical.get("fixture.line").text == "Original fixture."
    result = validate_locale_packs(catalog)
    assert "locale-resource-read" in {issue.code for issue in result.errors}


@pytest.mark.integration
@pytest.mark.parametrize("problem", ["unavailable", "empty", "malformed"])
def test_revision_selection_errors_are_validator_diagnostics(catalog, problem):
    from ocf_tools.validators import (
        _load_schema,
        validate_against_schema,
        validate_timed_transcript,
    )

    if problem != "unavailable":
        content = (
            "locale: en-US\ndomain: narration\nentries: {}\n"
            if problem == "empty"
            else "entries: [unterminated"
        )
        (catalog.root / "en-US/fixture-revision.yaml").write_text(content, encoding="utf-8")
    doc = {
        "schema_version": "1.0",
        "title": "Synthetic revision fixture",
        "locale": "en-US",
        "narration_revision": "UNKNOWN" if problem == "unavailable" else REVISION,
        "timeline": [{"id": "line", "at": "00:00:00.000", "narration_key": "fixture.line"}],
    }
    assert validate_against_schema(doc, _load_schema("timed-transcript.schema.json")) == []
    result = validate_timed_transcript(doc, Path("fixture.yaml"), catalog=catalog, records=[])
    assert "narration-revision" in {issue.code for issue in result.errors}


@pytest.mark.unit
@pytest.mark.parametrize("entries", ["", "entries: null\n", "entries: {}\n"])
def test_empty_revision_fails_closed(catalog, entries):
    (catalog.root / "en-US/fixture-revision.yaml").write_text(
        "locale: en-US\ndomain: narration\n" + entries, encoding="utf-8"
    )
    with pytest.raises(LocalizationError, match="nonempty entries"):
        catalog.with_revision(REVISION, "en-US")


@pytest.mark.unit
@pytest.mark.parametrize("domain", ["ui", "function"])
def test_revision_cannot_project_another_domain(catalog, domain):
    pack = catalog.root / "en-US"
    manifest = yaml_safe_load((pack / "manifest.yaml").read_text())
    manifest["resources"][-1]["domain"] = domain
    (pack / "manifest.yaml").write_text(yaml_safe_dump(manifest), encoding="utf-8")
    with pytest.raises(LocalizationError, match="require narration resources"):
        LocaleCatalog(catalog.root, function_records=lambda: []).with_revision(REVISION, "en-US")


@pytest.mark.unit
def test_yaml_duplicate_rejection_preserves_explicit_merge_overrides():
    with pytest.raises(yaml.constructor.ConstructorError, match="duplicate key"):
        yaml_safe_load("entries:\n  fixture.line: first\n  fixture.line: second\n")
    with pytest.raises(yaml.constructor.ConstructorError, match="unhashable"):
        yaml_safe_load("? [invalid, key]\n: value\n")
    assert (
        yaml_safe_load("base: &base {value: 1}\nchild: {<<: *base, value: 2}\n")["child"]["value"]
        == 2
    )


@pytest.mark.unit
def test_test_harness_scratch_uses_resolved_workspace(tmp_path, monkeypatch):
    import conftest
    from ocf_tools import paths

    target = tmp_path / "canonical-workspace"
    monkeypatch.setattr(paths, "work_root", lambda: target)
    monkeypatch.setenv("OCF_WORK_DIR", "restore-after-test")
    config = SimpleNamespace(option=SimpleNamespace(basetemp=None))
    conftest.pytest_configure(config)
    assert Path(config.option.basetemp).parent == target / "tmp"
    assert os.environ["OCF_WORK_DIR"] == str(Path(config.option.basetemp) / "ocf-serial")


@pytest.mark.unit
def test_explicit_affirmation_cannot_request_fallback():
    with pytest.raises(OCFError, match="strict locale"):
        run_compose(SimpleNamespace(affirmation="none", allow_fallback=True))


@pytest.mark.unit
def test_custom_literal_exception_keeps_other_hygiene_guards():
    from ocf_tools.validators import validate_narration_hygiene

    event = {
        "id": "affirmation.practice",
        "at": 0,
        "text": "Synthetic {{literal}}.",
        "timing": {"pause_after": -1},
    }
    doc = {"affirmation_selection": "custom", "timeline": [event]}
    codes = {issue.code for issue in validate_narration_hygiene(doc).errors}
    assert "narration-variable" not in codes and "narration-pause" in codes
    event["id"] = "another.event"
    assert "narration-variable" in {issue.code for issue in validate_narration_hygiene(doc).errors}
    event["id"] = "affirmation.practice"
    event["narration_key"] = "fixture.line"
    assert "narration-variable" in {issue.code for issue in validate_narration_hygiene(doc).errors}


@pytest.fixture
def routine(tmp_path):
    from ocf_tools.indexes import load_all_functions
    from ocf_tools.paths import LOCALES_DIR

    # Repository-backed composition stays integration; revision words are synthetic.
    shutil.copytree(LOCALES_DIR / "en-US", tmp_path / "en-US")
    write_revision(tmp_path / "en-US")
    template = load_template("OCF-TPL-SESSION-HPLUS-LOCKED-005")
    template["narration_revision"] = REVISION
    slots = {
        "opener": "Synthetic opener.",
        "function_body": "Synthetic body.",
        "closer": "Synthetic closer.",
    }
    return template, slots, LocaleCatalog(tmp_path, function_records=load_all_functions)


@pytest.mark.integration
def test_locale_validation_uses_unsaved_revision_resources(routine):
    from ocf_tools.indexes import load_all_functions
    from ocf_tools.validators import validate_locale_packs

    _template, _slots, catalog = routine
    target = catalog.root / "en-US/fixture-revision.yaml"
    payload = yaml_safe_load(target.read_text())
    target.unlink()

    def reader(path):
        return deepcopy(payload) if path == target else locales.load_yaml_file(path)

    view = LocaleCatalog(
        catalog.root,
        reader=reader,
        exists=lambda path: path == target or path.is_file(),
        function_records=load_all_functions,
    )
    assert validate_locale_packs(view).errors == []


@pytest.mark.integration
@pytest.mark.parametrize("choice", ["none", "Gateway", "SyncCreation", "OCF", "custom"])
def test_affirmation_selector_matrix_without_supplied_wording(routine, choice):
    template, slots, catalog = routine
    if choice == "custom":
        slots["affirmation"] = "Synthetic {{literal data}} only."
    doc = compose(
        template,
        slots,
        title="Fixture",
        affirmation=choice,
        function_id="OCF-SEN-001",
        locale="en-US",
    )
    resolved = resolve_document(doc, "en-US", catalog=catalog)
    events = [event for event in iter_events(resolved) if event["id"].startswith("affirmation.")]
    if choice == "none":
        assert events == [] and not any(
            section["id"] == "affirmation" for section in doc["sections"]
        )
    else:
        assert [event["id"] for event in events] == [
            "affirmation.begin",
            "affirmation.practice",
            "affirmation.complete",
        ]
        assert events[0]["text"] == SYNTHETIC["hplus.optional.affirmation.begin"]
        assert events[-1]["text"] == SYNTHETIC["hplus.optional.affirmation.complete"]
        assert events[1]["text"] == (
            slots["affirmation"]
            if choice == "custom"
            else SYNTHETIC["hplus.optional.affirmation." + choice.lower()]
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "choice,text,locale",
    [
        ("unknown", None, None),
        ([], None, None),
        ("custom", None, None),
        ("custom", " ", None),
        ("Gateway", "conflict", None),
        ("none", "conflict", None),
        ("custom", "Fixture.", "es"),
    ],
)
def test_invalid_or_conflicting_input_fails_before_synthesis(routine, choice, text, locale):
    template, slots, _catalog = routine
    if text is not None:
        slots["affirmation"] = text
    with pytest.raises(OCFError):
        compose(
            template,
            slots,
            title="Fixture",
            affirmation=choice,
            custom_affirmation_locale=locale,
            locale="en-US",
        )


@pytest.mark.integration
def test_legacy_enabled_behavior_and_new_default_off_are_distinct(routine):
    template, slots, _catalog = routine
    revised = compose(template, slots, title="Revised", enabled_stages=["affirmation"])
    assert not any(event["id"].startswith("affirmation.") for event in iter_events(revised))
    old = deepcopy(template)
    old.pop("narration_revision")
    replay = compose(old, slots, title="Original", enabled_stages=["affirmation"])
    assert (
        len([event for event in iter_events(replay) if event["id"].startswith("affirmation.")]) == 3
    )
    custom = compose(
        old,
        {**slots, "affirmation": "Explicit legacy fixture."},
        title="Legacy",
        enabled_stages=["affirmation"],
    )
    assert (
        next(event for event in iter_events(custom) if event["id"] == "affirmation.practice")[
            "text"
        ]
        == "Explicit legacy fixture."
    )


@pytest.fixture
def scoped_planner(routine, monkeypatch):
    from ocf_tools import complete_session, validators
    from ocf_tools.content import load_layers

    template, _slots, catalog = routine
    monkeypatch.setattr(
        complete_session,
        "_resolve_template",
        lambda owner, requested: (deepcopy(template), load_layers(owner)["bindings"]),
    )
    monkeypatch.setattr(locales, "LocaleCatalog", lambda: catalog)
    monkeypatch.setattr(complete_session, "LocaleCatalog", lambda: catalog)
    monkeypatch.setattr(validators, "LocaleCatalog", lambda: catalog)
    return complete_session, catalog


@pytest.mark.integration
def test_complete_session_custom_exception_uses_the_same_strict_revision(scoped_planner):
    complete_session, catalog = scoped_planner
    plan = complete_session.build_complete_session_plan(
        "OCF-SEN-001",
        overrides={
            "affirmation": "custom",
            "custom_affirmation": "Synthetic {{literal}} custom.",
            "custom_affirmation_locale": "en-US",
        },
    )
    doc = resolve_document(plan["template_plan"], "en-US", catalog=catalog)
    assert (
        next(event for event in iter_events(doc) if event["id"] == "affirmation.practice")["text"]
        == "Synthetic {{literal}} custom."
    )


@pytest.mark.integration
def test_custom_selection_does_not_allow_another_inline_event(scoped_planner, monkeypatch):
    from ocf_tools import session

    complete_session, _catalog = scoped_planner
    original = session.compose

    def unexpected_inline(*args, **kwargs):
        doc = original(*args, **kwargs)
        timeline = doc["sections"][-1]["timeline"]
        timeline.append(
            {
                "id": "another.inline",
                "after": timeline[-1]["id"],
                "offset": 0,
                "timing": {"anchor": "event-end"},
                "text": "Synthetic unrelated inline.",
            }
        )
        return doc

    monkeypatch.setattr(session, "compose", unexpected_inline)
    with pytest.raises(OCFError, match="inline text"):
        complete_session.build_complete_session_plan(
            "OCF-SEN-001",
            overrides={"affirmation": "custom", "custom_affirmation": "Synthetic explicit custom."},
        )


@pytest.mark.integration
def test_unbound_template_remains_rejected():
    from ocf_tools.complete_session import build_complete_session_plan

    with pytest.raises(OCFError, match="not bound"):
        build_complete_session_plan("OCF-SEN-001", template="OCF-TPL-SESSION-NOT-BOUND-001")
