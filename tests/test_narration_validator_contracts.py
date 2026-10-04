"""Isolated narration/locale validation with synthetic catalog and record boundaries."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from ocf_tools import validators as v
from ocf_tools.locale import LocalizationError
from ocf_tools.models import function_from_dict

pytestmark = pytest.mark.unit


def entry(text="Words", **extra):
    return NS(
        text=text,
        domain="narration",
        file="words.yaml",
        variables=set(),
        requires_events=[],
        required_pronunciation=[],
        pronunciation={},
        check_contract=lambda: [],
        **extra,
    )


class Catalog:
    canonical_locale = "en-US"
    root = Path("synthetic-locales")
    problems = []

    def __init__(self):
        self.entries = {"fixture.key": entry()}
        self.canonical = NS(
            locale="en-US", semantic_version="2.0.0", get=lambda key: self.entries.get(key)
        )
        self.available = True
        self.missing = []
        self.packs = {}

    def spoken_chain(self, tag):
        if not self.available:
            raise LocalizationError("missing pack")
        return [tag]

    def resource(self, key, tag, **kw):
        if key not in self.entries:
            raise LocalizationError("missing resource")
        return self.entries[key], None

    def locales(self):
        return list(self.packs)

    def require(self, tag):
        return self.packs[tag]

    def missing_keys(self, tag):
        return self.missing

    def unknown_keys(self, tag):
        return []

    def stale_translations(self, tag):
        return False

    def stale_keys(self, tag):
        return []


def codes(result):
    return {issue.code for issue in result.issues}


@pytest.fixture
def catalog(monkeypatch):
    catalog = Catalog()
    record = function_from_dict(
        {
            "id": "OCF-FND-999",
            "slug": "fixture",
            "canonical": {
                "command": {"primary": "PLUS-FOCUS", "modes": ["PLUS-SEE MORE", "PLUS-SEE LESS"]}
            },
            "lifecycle": {"release": {"command": "PLUS-END"}},
        },
        Path("fixture"),
    )
    blank = function_from_dict(
        {"id": "OCF-FND-998", "slug": "blank", "canonical": {"command": {"modes": [""]}}},
        Path("blank"),
    )
    monkeypatch.setattr(v, "load_all_functions", lambda: [record, blank])
    monkeypatch.setattr(v, "LocaleCatalog", lambda: catalog)
    monkeypatch.setattr(v, "missing_narration_keys", lambda *a: catalog.missing)
    return catalog


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"narration_required": True}, "narration-required"),
        ({"text": None}, "narration-empty"),
        ({"text": "Unresolved {person}"}, "narration-variable"),
        ({"text": "TODO words"}, "narration-placeholder"),
        ({"text": "[pause 3]"}, "narration-pause"),
        ({"timing": [1]}, "narration-timing"),
        ({"timing": []}, "narration-timing"),
        ({"timing": {"preferred_duration": 0}}, "narration-timing"),
        ({"timing": {"maximum_duration": float("nan")}}, "narration-timing"),
        ({"timing": {"pause_after": True}}, "narration-pause"),
        ({"timing": {"pause_after": float("inf")}}, "narration-pause"),
        ({"timing": {"anchor": "speech-end"}}, "semantic-anchor"),
        ({"semantic": []}, "semantic-identity"),
        ({"auditory_cue": "Bad Identity"}, "semantic-identity"),
        ({"variables": []}, "narration-variables"),
        ({"variables": {1: "not a named variable"}}, "narration-variables"),
        ({"after": []}, "semantic-anchor"),
        ({"at": {}}, "semantic-anchor"),
        ({"semantic": "explain.ten", "auditory_cue": "focus.ten.enter"}, "semantic-cue-operation"),
    ],
)
def test_hygiene_diagnostics_preserve_invalid_input_without_crashing(change, expected):
    event = {"id": "a", "at": 0, **change}
    doc = {"timeline": [event]}
    before = deepcopy(doc)
    assert expected in codes(v.validate_narration_hygiene(doc))
    # NaN does not compare equal to itself, so compare the unmodified object
    # representation rather than automatically cleaning any source value.
    assert repr(doc) == repr(before)


def test_duplicate_rules_and_required_resource_events_are_not_automatic_rewrites(catalog):
    event = {
        "id": "a",
        "at": 0,
        "text": "Same words",
        "semantic": "custom.cue",
        "auditory_cue": "custom.cue",
    }
    doc = {"timeline": [event, {**event, "id": "b"}]}
    assert {"narration-duplicate", "semantic-cue-duplicate"} <= codes(
        v.validate_narration_hygiene(doc)
    )
    doc["timeline"][1]["intentional_repeat"] = True
    assert not v.validate_narration_hygiene(doc).errors
    catalog.entries["fixture.key"].requires_events = ["missing.event"]
    keyed = {"timeline": [{"id": "a", "at": 0, "narration_key": "fixture.key"}]}
    assert "narration-event-reference" in codes(
        v.validate_narration_hygiene(keyed, catalog=catalog)
    )
    keyed["timeline"].append({"id": "marker", "at": 1, "semantic": "missing.event"})
    assert not v.validate_narration_hygiene(keyed, catalog=catalog).errors
    keyed["timeline"][0]["narration_key"] = "absent.key"
    assert "narration-resource" in codes(v.validate_narration_hygiene(keyed, catalog=catalog))


def test_command_ownership_release_literal_modes_and_wrong_types(catalog):
    assert v.known_commands() == {"PLUS-FOCUS", "PLUS-SEE MORE", "PLUS-SEE LESS", "PLUS-END"}
    doc = {
        "function_id": "OCF-FND-999",
        "timeline": [
            {"id": "a", "at": 0, "text": "Use PLUS-SEE MORE."},
            {
                "id": "b",
                "at": 1,
                "narration_key": "function.release.command",
                "variables": {"release_command": "PLUS-END"},
            },
        ],
    }
    assert not v.validate_command_ownership(doc, Path("fixture")).errors
    doc["timeline"][1]["variables"]["release_command"] = "PLUS-FOCUS"
    assert "narration-command-owner" in codes(v.validate_command_ownership(doc, Path("fixture")))
    doc["function_id"] = []
    assert "narration-command-owner" in codes(v.validate_command_ownership(doc, Path("fixture")))
    doc = {"timeline": [{"id": "a", "narration_key": "fixture.key", "variables": {"command": []}}]}
    assert "narration-command-invalid" in codes(
        v.validate_narration_usage(doc, Path("fixture"), catalog)
    )
    catalog.entries["fixture.key"].text = "Use PLUS-FOCUS."
    doc["timeline"][0]["variables"] = {}
    assert "narration-command-owner" in codes(v.validate_command_ownership(doc, Path("fixture")))


def test_usage_missing_pack_unknown_key_inline_and_missing_resources(catalog):
    assert not v.validate_narration_usage(
        {"timeline": [{"id": "plain", "text": "Plain words"}]}, Path("fixture"), catalog
    ).errors
    doc = {
        "timeline": [
            {"id": "a", "narration_key": "absent.key", "text": "Inline words"},
            {"id": "marker", "semantic": "fixture.marker"},
        ]
    }
    assert {"narration-inline-text", "narration-unknown-key"} <= codes(
        v.validate_narration_usage(doc, Path("fixture"), catalog)
    )
    catalog.available = False
    assert "locale-unavailable" in codes(v.validate_narration_usage(doc, Path("fixture"), catalog))
    catalog.available = True
    catalog.missing = ["fixture.key"]
    assert "narration-missing-key" in codes(
        v.validate_narration_usage(doc, Path("fixture"), catalog)
    )


def pack(tag, entries, **extra):
    canonical = tag == "en-US"
    return NS(
        locale=tag,
        path=None,
        manifest={"status": "canonical" if canonical else "draft", "resources": []},
        is_canonical=canonical,
        translation={}
        if canonical
        else {"source_locale": "en-US", "source_semantic_version": "1.0.0"},
        direction="ltr",
        semantic_version="2.0.0",
        entries=entries,
        get=lambda key: entries.get(key),
        **extra,
    )


@pytest.fixture
def packs(catalog, monkeypatch):
    monkeypatch.setattr(v, "_load_schema", lambda name: {})
    monkeypatch.setattr(v, "validate_against_schema", lambda data, schema: [])
    canonical = pack("en-US", catalog.entries)
    translated = pack("fr", {"fixture.key": entry("Use PLUS-SEE MORE; then PLUS-SEE LESS.")})
    catalog.canonical = canonical
    catalog.packs = {"en-US": canonical, "fr": translated}
    return catalog, translated


def test_full_mode_commands_are_valid_in_translated_resources(packs):
    catalog, translated = packs
    assert "locale-command-invalid" not in codes(v.validate_locale_packs(catalog))
    translated.entries["fixture.key"].text = "Use PLUS-FOCUSING and PLUS-UNKNOWN."
    assert "locale-command-invalid" in codes(v.validate_locale_packs(catalog))


def test_locale_contracts_provenance_unknown_stale_and_direction(packs, monkeypatch):
    catalog, translated = packs
    translated.translation = {"source_locale": "fr"}
    translated.direction = "rtl"
    translated.entries["fixture.key"].requires_events = ["different.event"]
    translated.entries["fixture.key"].required_pronunciation = ["different-token"]
    translated.entries["fixture.key"].variables = {"extra"}
    catalog.entries["fixture.key"].variables = {"missing"}
    catalog.missing = [f"missing.{i}" for i in range(10)]
    monkeypatch.setattr(catalog, "unknown_keys", lambda tag: ["unknown.key"])
    monkeypatch.setattr(catalog, "stale_translations", lambda tag: True)
    monkeypatch.setattr(catalog, "stale_keys", lambda tag: ["fixture.key"])
    expected = {
        "locale-provenance-self",
        "locale-direction",
        "locale-event-contract",
        "locale-pronunciation-contract",
        "locale-variable-mismatch",
        "locale-partial",
        "locale-unknown-keys",
        "locale-stale",
        "locale-entry-stale",
    }
    result = v.validate_locale_packs(catalog)
    assert expected <= codes(result)
    assert any("+2 more" in issue.message for issue in result.warnings)
    translated.translation = {}
    assert "locale-provenance-missing" in codes(v.validate_locale_packs(catalog))


def test_locale_malformed_empty_placeholder_syntax_and_schema(packs, monkeypatch, tmp_path):
    catalog, translated = packs
    catalog.problems = ["malformed pack"]
    translated.path = tmp_path
    translated.manifest["resources"] = [{"file": "words.yaml"}]
    monkeypatch.setattr(v, "load_yaml_file", lambda path: {"fixture": True})
    monkeypatch.setattr(v, "validate_against_schema", lambda *a: ["schema issue"])
    translated.entries = {
        "blank": entry(""),
        "placeholder": entry("TODO"),
        "bad": entry("{bad, nope, a}"),
        "unused": entry("Plain words"),
        "variable": entry("{command}"),
    }
    translated.entries["unused"].pronunciation = {"absent": {"espeak-ng": "hint"}}
    translated.entries["variable"].variables = {"command"}
    translated.entries["blank"].check_contract = lambda: ["contract mismatch"]
    expected = {
        "locale-pack-malformed",
        "locale-manifest-schema",
        "locale-resource-schema",
        "locale-empty",
        "locale-placeholder",
        "locale-message-syntax",
        "locale-pronunciation-unused",
        "locale-variable-contract",
        "locale-command-placeholder",
    }
    assert expected <= codes(v.validate_locale_packs(catalog))
    catalog.packs = {}
    assert "locale-pack-none" in codes(v.validate_locale_packs(catalog))


@pytest.mark.parametrize("source_vars,target_vars", [({"missing"}, set()), (set(), {"extra"})])
def test_translation_variable_loss_and_addition_are_separate_failures(
    packs, source_vars, target_vars
):
    catalog, translated = packs
    catalog.entries["fixture.key"].variables = source_vars
    translated.entries["fixture.key"].variables = target_vars
    assert "locale-variable-mismatch" in codes(v.validate_locale_packs(catalog))


def test_small_partial_pack_and_used_pronunciation_hints(packs):
    catalog, translated = packs
    catalog.missing = ["missing.key"]
    translated.entries["fixture.key"].text = "Use PLUS-FOCUS."
    translated.entries["fixture.key"].pronunciation = {"PLUS-FOCUS": {"espeak-ng": "hint"}}
    result = v.validate_locale_packs(catalog)
    assert "locale-partial" in codes(result)
    assert "locale-pronunciation-unused" not in codes(result)
    assert not any("more" in issue.message for issue in result.warnings)
    catalog.missing = []
    doc = {
        "function_id": "OCF-FND-999",
        "timeline": [
            {
                "id": "a",
                "narration_key": "fixture.key",
                "variables": {"command": "PLUS-FOCUS", "name": "Fixture"},
            }
        ],
    }
    assert not v.validate_narration_usage(doc, Path("fixture"), catalog).errors


def test_command_token_boundaries_do_not_match_inside_longer_identifiers(packs):
    catalog, translated = packs
    translated.entries["fixture.key"].text = "XPLUS-FOCUS pre-PLUS-FOCUS PLUS-FOCUSING"
    result = v.validate_locale_packs(catalog)
    invalid = [issue for issue in result.errors if issue.code == "locale-command-invalid"]
    assert len(invalid) == 1 and "PLUS-FOCUSING" in invalid[0].message
