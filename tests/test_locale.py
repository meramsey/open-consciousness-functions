"""Localization: locale packs, BCP-47 fallback, strict spoken narration, pseudo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from ocf_tools.locale import (
    CANONICAL_LOCALE,
    LocaleCatalog,
    LocalizationError,
    build_pseudo_pack,
    document_key_usage,
    fallback_chain,
    format_message,
    format_number,
    iter_events,
    load_pack,
    locale_direction,
    message_variables,
    normalize_tag,
    plural_category,
    resolve_document,
)
from ocf_tools.paths import LOCALES_DIR, REPO_ROOT
from ocf_tools.validators import validate_locale_packs

# ---------------------------------------------------------------------------
# BCP-47
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("en_us", "en-US"),
        ("ES-mx", "es-MX"),
        ("fr", "fr"),
        ("zh-hans-cn", "zh-Hans-CN"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_tag(value, expected):
    assert normalize_tag(value) == expected


def test_malformed_tag_is_reported_not_guessed():
    with pytest.raises(LocalizationError):
        normalize_tag("x")


def test_fallback_chain_orders_parents_before_canonical():
    assert fallback_chain("es-MX") == ["es-MX", "es", "en-US"]
    assert fallback_chain("en-US") == ["en-US", "en"]
    assert fallback_chain(None) == [CANONICAL_LOCALE, "en"]


def test_locale_direction_is_script_derived():
    assert locale_direction("es") == "ltr"
    assert locale_direction("ar") == "rtl"
    assert locale_direction("he-IL") == "rtl"
    assert locale_direction("en-US") == "ltr"


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------


def test_format_message_simple_and_quote():
    assert format_message("Hello, {name}.", {"name": "Ana"}) == "Hello, Ana."
    # ICU quoting: '\'{...}\' protects the braces from the parser.
    assert format_message("Use '{lit}' and {x}", {"x": "y"}) == "Use {lit} and y"
    # An apostrophe not followed by a syntax character stays a literal.
    assert format_message("Don't stop, {name}.", {"name": "Ana"}) == "Don't stop, Ana."


def test_plural_and_selectordinal():
    message = "{count, plural, one {# rep} other {# reps}}"
    assert format_message(message, {"count": 1}) == "1 rep"
    assert format_message(message, {"count": 4}) == "4 reps"
    ordinal = "{n, selectordinal, one {#st} two {#nd} few {#rd} other {#th}}"
    assert format_message(ordinal, {"n": 2}) == "2nd"
    assert format_message(ordinal, {"n": 11}) == "11th"


def test_plural_offset_uses_offset_value():
    message = "{count, plural, offset:1 =0 {nobody} one {you and # other} other {you and # others}}"
    assert format_message(message, {"count": 0}) == "nobody"
    # CLDR selects the branch for (count - offset), and '#' prints that value.
    assert format_message(message, {"count": 1}) == "you and 0 others"
    assert format_message(message, {"count": 2}) == "you and 1 other"
    assert format_message(message, {"count": 3}) == "you and 2 others"


def test_select_branches_and_escaped_hash():
    message = "{gender, select, female {her} other {his}} note \\#tag"
    assert format_message(message, {"gender": "female"}) == "her note #tag"


def test_plural_category_uses_locale_rules():
    assert plural_category(1, "en-US") == "one"
    assert plural_category(2, "en-US") == "other"
    assert plural_category(1, "ru") == "one"
    assert plural_category(3, "ru") == "few"
    assert plural_category(1, "ar") == "one"
    assert plural_category(11, "ar") == "many"


def test_plural_rules_run_in_a_sandbox():
    # A pack-supplied rule is data, never code: anything but the tiny allowed
    # grammar is refused instead of executed.
    from ocf_tools.locale import _eval_rule

    assert _eval_rule("n % 10 == 1 and n % 100 != 11", 21.0) is True
    with pytest.raises(LocalizationError):
        _eval_rule("__import__('os').system('true')", 1.0)


def test_format_number_uses_locale_separators():
    assert format_number(1234567.5, "en-US") == "1,234,567.5"
    assert format_number(1234567.5, "de-DE") == "1.234.567,5"
    assert format_number(1234567, "hi") == "12,34,567"
    assert format_number(-9876543.25, "en-US") == "-9,876,543.25"
    assert format_number(7, "en-US") == "7"


# ---------------------------------------------------------------------------
# Packs on disk
# ---------------------------------------------------------------------------


def test_repository_packs_load_and_declare_domains():
    catalog = LocaleCatalog()
    assert CANONICAL_LOCALE in catalog.locales()
    for locale in catalog.locales():
        pack = catalog.require(locale)
        assert pack.entries, f"{locale} pack has no entries"
        for entry in pack.entries.values():
            assert entry.domain in {"ui", "narration"}


def test_canonical_pack_carries_original_ocf_narration():
    pack = LocaleCatalog().require(CANONICAL_LOCALE)
    assert pack.is_canonical
    for key in (
        "session.focus-cycle.opener",
        "session.focus-cycle.tenth-state.enter",
        "session.focus-cycle.eleventh-state.enter",
        "session.focus-cycle.instruction",
    ):
        assert pack.entries[key].text.strip()


def test_es_pack_is_labelled_as_a_test_fixture():
    pack = LocaleCatalog().require("es")
    assert pack.status in {"machine", "draft"}
    assert pack.translation["source_locale"] == CANONICAL_LOCALE
    assert "test" in json.dumps(pack.manifest).lower()


def test_resource_variables_are_declared_and_used():
    catalog = LocaleCatalog()
    for locale in catalog.locales():
        pack = catalog.require(locale)
        for entry in pack.entries.values():
            assert entry.check_contract() == []
            entry.render(entry.sample_variables(), plural_rules=pack.plural_rules())


def test_pseudo_pack_preserves_icu_syntax_and_shape():
    catalog = LocaleCatalog()
    source = catalog.require(CANONICAL_LOCALE)
    pseudo = build_pseudo_pack(catalog, CANONICAL_LOCALE)
    assert pseudo.locale == "en-XA"
    assert set(pseudo.entries) == set(source.entries)
    for key, entry in pseudo.entries.items():
        original = source.entries[key]
        assert entry.domain == original.domain
        assert sorted(entry.variables) == sorted(original.variables)
        assert message_variables(entry.text) == message_variables(original.text)
        if entry.text == original.text:
            # Variable-only or numeral-only content has no letters to accent.
            rendered = original.render({name: "" for name in original.variables})
            assert rendered == "" or rendered.isdecimal()
    assert build_pseudo_pack(catalog, CANONICAL_LOCALE, locale="en-XB").locale == "en-XB"


def test_pseudo_pack_files_round_trip(tmp_path: Path):
    catalog = LocaleCatalog()
    pseudo = build_pseudo_pack(catalog, CANONICAL_LOCALE)
    root = tmp_path / "en-XA"
    root.mkdir()
    (root / "manifest.yaml").write_text(yaml.safe_dump(pseudo.manifest), encoding="utf-8")
    for filename in sorted({e.file for e in pseudo.entries.values() if e.file}):
        file_entries = {
            key: entry for key, entry in pseudo.entries.items() if entry.file == filename
        }
        domains = {entry.domain for entry in file_entries.values()}
        assert len(domains) == 1
        payload = {
            "schema_version": "1.0",
            "locale": pseudo.locale,
            "domain": domains.pop(),
            "entries": {key: entry.text for key, entry in file_entries.items()},
        }
        (root / filename).write_text(yaml.safe_dump(payload), encoding="utf-8")
    reloaded = load_pack(root)
    assert reloaded.locale == "en-XA"
    assert len(reloaded.entries) == len(pseudo.entries)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def test_spoken_resolution_prefers_the_requested_locale():
    catalog = LocaleCatalog()
    opener = catalog.spoken("session.focus-cycle.opener", "es")
    canonical = catalog.spoken("session.focus-cycle.opener", "en-US")
    assert opener != canonical


def test_strict_spoken_refuses_canonical_fallback():
    catalog = LocaleCatalog()
    missing = "focus.eleven.hold"  # deliberately absent from the es fixture
    with pytest.raises(LocalizationError):
        catalog.spoken(missing, "es")
    fallback = catalog.spoken(missing, "es", strict=False)
    assert fallback == catalog.spoken(missing, "en-US")


def test_regional_tag_is_served_by_installed_parent():
    catalog = LocaleCatalog()
    assert catalog.spoken("session.focus-cycle.opener", "es-MX") == catalog.spoken(
        "session.focus-cycle.opener", "es"
    )
    assert catalog.text("locale.list.header", "es-MX") == catalog.text("locale.list.header", "es")


def test_strict_spoken_without_any_pack_names_the_override():
    catalog = LocaleCatalog()
    with pytest.raises(LocalizationError) as excinfo:
        catalog.spoken("session.focus-cycle.opener", "de")
    message = str(excinfo.value)
    assert "de" in message and "fallback" in message


def test_ui_may_fall_back_to_canonical():
    catalog = LocaleCatalog()
    assert catalog.text("locale.list.header", "fr") == catalog.text("locale.list.header", "en-US")


def test_resolve_document_keeps_keys_and_records_provenance():
    doc = {
        "schema_version": "1.0",
        "title": "Keyed",
        "timeline": [
            {
                "id": "e1",
                "at": 0.0,
                "narration_key": "session.focus-cycle.opener",
            },
            {"id": "e2", "at": 2.0, "text": "inline narration stays put"},
        ],
    }
    resolved = resolve_document(doc, "es", strict=False)
    events = list(iter_events(resolved))
    assert events[0]["narration_key"] == "session.focus-cycle.opener"
    assert events[0]["text"]
    assert events[1]["text"] == "inline narration stays put"
    assert resolved["narration"]["locale"] == "es"
    assert resolved["narration"]["inline_events"] == 1
    assert resolved["narration"]["resolved"][0]["locale"] == "es"


def test_resolve_document_strict_failure_lists_every_event():
    doc = {
        "schema_version": "1.0",
        "title": "Partial",
        "timeline": [
            {"id": "a", "at": 0.0, "narration_key": "focus.eleven.hold"},
            {"id": "b", "at": 1.0, "narration_key": "focus.eleven.release"},
        ],
    }
    with pytest.raises(LocalizationError) as excinfo:
        resolve_document(doc, "es")
    assert "a" in str(excinfo.value) and "b" in str(excinfo.value)


def test_document_key_usage_counts_keyed_and_inline():
    doc = {
        "timeline": [
            {"id": "a", "narration_key": "session.focus-cycle.opener"},
            {"id": "b", "text": "inline"},
        ]
    }
    usage = document_key_usage(doc)
    assert usage["keyed"] == 1
    assert usage["inline"] == 1
    assert usage["both"] == 0
    assert usage["keys"] == ["session.focus-cycle.opener"]


def test_resolve_document_does_not_mutate_input():
    doc = {
        "schema_version": "1.0",
        "title": "T",
        "timeline": [{"id": "a", "at": 0.0, "narration_key": "session.focus-cycle.opener"}],
    }
    resolve_document(doc, "en-US")
    assert "text" not in doc["timeline"][0]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_repository_locale_packs_validate_without_errors():
    result = validate_locale_packs(LocaleCatalog())
    assert result.errors == []


def test_partial_pack_is_reported_not_silently_accepted():
    result = validate_locale_packs(LocaleCatalog())
    texts = " ".join(i.message for i in result.issues)
    assert "missing" in texts
    assert "focus.eleven.hold" in LocaleCatalog().missing_keys("es")


def test_locale_dir_is_repository_relative():
    assert LOCALES_DIR == REPO_ROOT / "locales"
