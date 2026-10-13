"""Session composition contracts using synthetic templates and injected resources."""

import json
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
import yaml
from ocf_tools import indexes, locale, semantics
from ocf_tools import session as s
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def test_keyed_stage_slot_keeps_locale_key_instead_of_speaking_it(boundary, monkeypatch):
    monkeypatch.setattr(
        semantics,
        "load_stage",
        lambda ref: {
            "id": "OCF-TPL-STAGE-FIXTURE-001",
            "version": "1.0.0",
            "events": [{"id": "line", "at": 0, "semantic": "function.instruction"}],
        },
    )
    doc = s.compose(
        template(
            [
                {
                    "id": "practice",
                    "stage": "fixture",
                    "start": 0,
                    "narration": {"line": {"slot": "body"}},
                }
            ],
            slots={"required": ["body"], "optional": []},
        ),
        {},
        title="fixture",
        slot_keys={"body": "function.fixture.body"},
    )
    event = doc["sections"][0]["timeline"][0]
    assert event["narration_key"] == "function.fixture.body"
    assert "text" not in event
    assert doc["slots"] == {}


def template(sections=None, **extra):
    return {
        "id": "OCF-TPL-SESSION-FIXTURE-001",
        "origin": "original-ocf",
        "schema_version": "1.0",
        "slots": {"required": [], "optional": []},
        "sections": sections or [],
        **extra,
    }


@pytest.fixture
def boundary(monkeypatch, tmp_path):
    monkeypatch.setattr(s, "TEMPLATES_DIR", tmp_path)
    monkeypatch.setattr(s, "AUDIO_SCRIPTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(s, "_load_schema", lambda name: {})
    monkeypatch.setattr(s, "validate_against_schema", lambda data, schema: [])
    return tmp_path


def test_template_load_errors_listing_and_empty_descriptions(boundary, monkeypatch, capsys):
    root = boundary
    missing = root / "absent.yaml"
    with pytest.raises(OCFError, match="not found"):
        s.load_template(str(missing))
    path = root / "fixture.yaml"
    for text, match in [("[broken", "invalid YAML"), ("- list", "not a mapping")]:
        path.write_text(text)
        with pytest.raises(OCFError, match=match):
            s.load_template(str(path))
    path.write_text(yaml.safe_dump(template()))
    assert s.load_template(str(path))["id"] == "OCF-TPL-SESSION-FIXTURE-001"
    assert s.list_templates()[0]["description"] == ""
    assert s.run_list_templates() == 0
    monkeypatch.setattr(s, "validate_against_schema", lambda *a: ["invalid fixture"])
    with pytest.raises(OCFError, match="fails its schema"):
        s.load_template("fixture")
    assert s.list_templates() == []
    assert s.run_list_templates() == 0 and "No session templates" in capsys.readouterr().out
    monkeypatch.setattr(s, "TEMPLATES_DIR", root / "missing")
    assert s.list_templates() == []


def test_schema_loader_reads_only_selected_local_json(monkeypatch, tmp_path):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps({"type": "object"}))
    monkeypatch.setattr(s, "schema_path", lambda name: path)
    assert s._load_schema("fixture") == {"type": "object"}


def test_slot_scheduling_lrc_and_repeat_markup_are_not_spoken():
    source = "first\n[00:04.00]second\n\nthird"
    assert s._parse_slot(source, section_start=1, section_end=None, line_seconds=2) == [
        (1, "first"),
        (4, "second"),
        (6, "third"),
    ]
    assert s._parse_slot(
        source, section_start=0, section_end=9, line_seconds=2, pace="even-span"
    ) == [(3, "first"), (4, "second"), (6, "third")]
    assert (
        s._parse_slot("", section_start=0, section_end=None, line_seconds=2, pace="even-span") == []
    )
    assert s._parse_slot(
        "plain", section_start=0, section_end=None, line_seconds=2, pace="even-span"
    ) == [(1, "plain")]
    assert [
        text
        for _, text in s._parse_repeated(
            "[00:04]same words\nnext words", section_start=0, section_end=12, repeat=2
        )
    ] == ["same words", "next words", "same words", "next words"]
    assert source == "first\n[00:04.00]second\n\nthird"
    for pace in ("sequential", "even-span"):
        with pytest.raises(OCFError, match="unusable LRC"):
            s._parse_slot("[00:04]", section_start=0, section_end=9, line_seconds=2, pace=pace)


@pytest.mark.parametrize(
    "text,start,end,repeat",
    [("", 0, 1, 1), ("words", 0, 1, 0), ("words", 1, 1, 1), ("[00:02]", 0, 1, 1)],
)
def test_invalid_repeated_slots_fail_explicitly(text, start, end, repeat):
    with pytest.raises(OCFError):
        s._parse_repeated(text, section_start=start, section_end=end, repeat=repeat)


def test_sections_preserve_keys_variables_semantics_and_reused_slots():
    section = {"id": "body", "start": 10, "slot": "main"}
    assert s.resolve_section(section, {"main": "a\nb"}, line_seconds=2) == [(10, "a"), (12, "b")]
    assert s.resolve_section_events(
        {**section, "repeat": 2}, {"main": "a"}, line_seconds=2, section_end=20
    ) == [{"at": 12.5, "text": "a"}, {"at": 17.5, "text": "a"}]
    with pytest.raises(OCFError, match="no section window"):
        s.resolve_section_events({**section, "repeat": 2}, {"main": "a"}, line_seconds=2)
    assert s._slot_text({"id": "reuse", "from_slot": "main"}, {"main": "exact"}) == (None, "exact")
    with pytest.raises(OCFError, match="not supplied"):
        s._slot_text({"id": "reuse", "from_slot": "missing"}, {})
    inline = {
        "id": "inline",
        "start": 0,
        "lines": [
            {
                "id": "a",
                "semantic": "fixture.begin",
                "narration_key": "fixture.key",
                "variables": {"name": "Café"},
            },
            {"id": "b", "after": "a", "semantic": "fixture.end", "text": "words"},
            {"semantic": "fixture.marker"},
        ],
    }
    events = s.resolve_section_events(inline, {}, line_seconds=2)
    assert events[0]["variables"] == {"name": "Café"} and events[0]["semantic"] == "fixture.begin"
    assert events[1]["after"] == "a" and events[1]["offset"] == 0
    assert events[2]["semantic"] == "fixture.marker"


@pytest.mark.parametrize(
    "option,value",
    [
        ("line_seconds", 0),
        ("line_seconds", float("nan")),
        ("duration", -1),
        ("duration", float("inf")),
    ],
)
def test_timing_options_are_not_silently_replaced(boundary, option, value):
    with pytest.raises(OCFError, match="finite"):
        s.compose(template(), {}, title="Fixture", **{option: value})


def test_zero_duration_and_missing_unknown_slots(boundary, capsys):
    root = template(
        [{"id": "late", "start": 1, "type": "freeform", "lines": [{"text": "words"}]}],
        defaults={"duration": 10},
    )
    assert (
        s.compose(root, {}, title="Fixture", duration=0)["sections"][0]["timeline"][0]["at"]
        == "00:00:01.000"
    )
    assert "exceeds template duration 0" in capsys.readouterr().out
    with pytest.raises(OCFError, match="unknown slot"):
        s.compose(root, {"unknown": "words"}, title="Fixture")
    root["slots"]["required"] = ["main"]
    with pytest.raises(OCFError, match="missing required"):
        s.compose(root, {}, title="Fixture")


def stage():
    return {
        "id": "stage",
        "version": "1.0.0",
        "type": "preparation",
        "events": [
            {"id": "begin", "at": 0, "semantic": "fixture.begin", "narration_key": "fixture.begin"},
            {
                "id": "end",
                "after": "begin",
                "timing": {"anchor": "speech-end"},
                "semantic": "fixture.end",
                "text": "old",
            },
        ],
    }


def test_stage_override_provenance_optional_features_and_owner_metadata(boundary, monkeypatch):
    original = stage()
    monkeypatch.setattr(semantics, "load_stage", lambda id: original)
    owner = NS(id="OCF-FND-999", canonical_command="PLUS-FOCUS", canonical_name="Café")
    monkeypatch.setattr(indexes, "load_all_functions", lambda: [owner])
    entry = NS(variables={"command", "function_name", "unrelated"})
    monkeypatch.setattr(
        locale, "LocaleCatalog", lambda: NS(canonical=NS(get=lambda key: entry if key else None))
    )
    root = template(
        [
            {
                "id": "first",
                "stage": "stage",
                "start": 0,
                "role": "learning",
                "gain_db": -6,
                "narration": {
                    "begin": {"text": "new", "locale": "en-US"},
                    "end": {"narration_key": "fixture.end"},
                },
            },
            {"id": "optional", "stage": "stage", "after": "$previous", "enabled_by": "extra"},
            {"id": "last", "stage": "stage", "after": "$previous"},
        ],
        function_id=owner.id,
        cue_profile="disabled",
        locale="en-US",
        source={"format": "manual", "filename": None},
    )
    before = deepcopy(root)
    doc = s.compose(root, {}, title="Fixture", document_id="fixture")
    assert [s["id"] for s in doc["sections"]] == ["first", "last"]
    assert doc["sections"][1]["timeline"][0]["after"] == "first.end"
    assert doc["sections"][0]["timeline"][0]["text"] == "new"
    assert doc["sections"][0]["timeline"][1]["variables"] == {
        "command": "PLUS-FOCUS",
        "function_name": "Café",
    }
    assert doc["stages"][0] == {"id": "stage", "version": "1.0.0", "instance": "first"}
    assert doc["source"] == root["source"] and root == before and original == stage()
    assert len(s.compose(root, {}, title="Fixture", enabled_stages=["extra"])["sections"]) == 3
    with pytest.raises(OCFError, match="unknown optional"):
        s.compose(root, {}, title="Fixture", enabled_stages=["unknown"])
    with pytest.raises(OCFError, match="command owner"):
        s.compose(root, {}, title="Fixture", function_id="OCF-FND-001")
    monkeypatch.setattr(indexes, "load_all_functions", lambda: [])
    with pytest.raises(OCFError, match="unknown function_id"):
        s.compose(root, {}, title="Fixture")


@pytest.mark.parametrize(
    "override,match",
    [
        ({"unknown": {"text": "x"}}, "unknown narration"),
        ({"begin": {"dsp": {}, "text": "x"}}, "cannot alter"),
        ({"begin": {"text": "x", "narration_key": "fixture.key"}}, "exactly one"),
        ({"begin": {}}, "exactly one"),
    ],
)
def test_narration_overrides_cannot_change_semantics(boundary, monkeypatch, override, match):
    monkeypatch.setattr(semantics, "load_stage", lambda id: stage())
    root = template([{"id": "instance", "stage": "stage", "start": 0, "narration": override}])
    with pytest.raises(OCFError, match=match):
        s.compose(root, {}, title="Fixture")


def test_compose_records_used_slots_and_validates_result(boundary, monkeypatch):
    root = template(
        [{"id": "body", "type": "freeform", "start": 0, "slot": "main", "role": "instruction"}],
        slots={"required": ["main"], "optional": []},
    )
    doc = s.compose(root, {"main": "words\nmore words"}, title="Fixture")
    assert doc["slots"] == {"main": ["words", "more words"]}
    monkeypatch.setattr(s, "validate_against_schema", lambda *a: ["invalid result"])
    with pytest.raises(OCFError, match="composed document fails"):
        s.compose(root, {"main": "words"}, title="Fixture")


def test_compose_handler_forwards_slots_locale_and_protects_output(boundary, monkeypatch, capsys):
    root = template(content_status="architecture-draft")
    monkeypatch.setattr(s, "load_template", lambda ref: root)
    monkeypatch.setattr(s, "read_text", lambda path: "words from " + path.name)
    monkeypatch.setattr(
        s,
        "_slot_file_provenance",
        lambda path, text: {"filename": path.name, "text_sha256": "fixture"},
    )
    captured = []
    monkeypatch.setattr(s, "compose", lambda *a, **kw: captured.append((a, kw)) or {"sections": []})
    monkeypatch.setattr(locale, "resolve_document", lambda doc, tag, **kw: {**doc, "locale": tag})
    writes = []
    monkeypatch.setattr(s, "write_text_atomic", lambda *a, **kw: writes.append((a, kw)))
    request = NS(
        template="fixture",
        opener="opening.txt",
        focus11=None,
        sleep20=None,
        closer=None,
        slot=["main=middle.txt"],
        title=None,
        id="fixture",
        line_seconds=2,
        duration=10,
        enable_stage=["extra"],
        function="OCF-FND-999",
        locale="fr",
        allow_fallback=True,
        output=None,
        force=False,
    )
    assert s.run_compose(request) == 0
    assert captured[0][0][1] == {
        "opener": "words from opening.txt",
        "main": "words from middle.txt",
    }
    assert captured[0][1]["function_id"] == "OCF-FND-999"
    assert writes[0][0][0] == boundary / "outputs/fixture.yaml"
    assert "Locale: fr" in capsys.readouterr().out
    request.slot = ["bad"]
    with pytest.raises(OCFError, match="NAME=PATH"):
        s.run_compose(request)
    request.slot = []
    request.output = str(boundary / "existing.yaml")
    (boundary / "existing.yaml").write_text("preserved")
    with pytest.raises(OCFError, match="Refusing to overwrite"):
        s.run_compose(request)
    assert (boundary / "existing.yaml").read_text() == "preserved"


def test_explicit_owner_binding_and_key_without_variables(boundary, monkeypatch):
    owner = NS(id="OCF-FND-999", canonical_command="PLUS-FOCUS", canonical_name="Fixture")
    monkeypatch.setattr(indexes, "load_all_functions", lambda: [owner])
    monkeypatch.setattr(locale, "LocaleCatalog", lambda: NS(canonical=None))
    root = template(
        [
            {
                "id": "body",
                "type": "freeform",
                "start": 0,
                "lines": [{"narration_key": "fixture.key"}],
            }
        ]
    )
    doc = s.compose(root, {}, title="Fixture", function_id=owner.id)
    assert doc["function_id"] == owner.id
    assert doc["sections"][0]["timeline"][0]["narration_key"] == "fixture.key"
    assert "variables" not in doc["sections"][0]["timeline"][0]
    assert [
        text
        for _, text in s._parse_repeated(
            "\nfirst\n\nsecond\n", section_start=0, section_end=3, repeat=1
        )
    ] == ["first", "second"]


def test_unlocalized_handler_and_list_descriptions(boundary, monkeypatch, capsys):
    root = template()
    monkeypatch.setattr(s, "load_template", lambda ref: root)
    monkeypatch.setattr(s, "compose", lambda *a, **kw: {"sections": []})
    writes = []
    monkeypatch.setattr(s, "write_text_atomic", lambda *a, **kw: writes.append(a))
    request = NS(
        template="fixture",
        slot=[],
        title="Fixture",
        id=None,
        output=str(boundary / "new.yaml"),
        force=False,
    )
    assert s.run_compose(request) == 0
    assert writes[0][0] == boundary / "new.yaml"
    assert "Locale:" not in capsys.readouterr().out
    monkeypatch.setattr(
        s,
        "list_templates",
        lambda: [
            {
                "id": "fixture",
                "origin": "original-ocf",
                "name": "Fixture",
                "description": "Short description",
            }
        ],
    )
    assert s.run_list_templates() == 0
    assert "Short description" in capsys.readouterr().out
