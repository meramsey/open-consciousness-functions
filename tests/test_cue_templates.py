"""Strict scoped symbols, locale authority, zero-drift and downstream boundaries."""

import hashlib
import json
from copy import deepcopy

import pytest
from ocf_tools.cue_templates import CueTemplateError, choices, expand, preview, scan
from ocf_tools.locale import LocaleCatalog, LocalePack, NarrationResource, resolve_document
from ocf_tools.models import FunctionRecord


def fixture(
    tmp_path, *, locale="en-US", speech="Plus Example", symbol="cue.primary", role="activation"
):
    command = {
        "id": "OCF-CMD-COG-999-PRIMARY",
        "function_id": "OCF-COG-999",
        "phrase_ref": {"source": "canonical-primary"},
        "role": role,
        "designation": "primary",
        "spoken": "Plus Example",
        "spoken_review": "reviewed",
        "localization": {"spoken_cue_key": "cue.example", "display_cue_key": "cue.display"},
    }
    owner = FunctionRecord(
        "OCF-COG-999",
        "example",
        tmp_path / "function.yaml",
        {
            "canonical": {"name": "Example", "command": {"primary": "PLUS-EXAMPLE", "modes": []}},
            "commands": [command],
            "documentation": {"title_key": "function.example"},
            "narration": {
                "sequence": [{"key": "fixture.body", "role": "function-body", "repetitions": 4}]
            },
        },
    )
    entry = NarrationResource(
        "fixture.body",
        locale,
        "narration",
        "Don't change  whitespace.\nThink {{ " + symbol + " }}.\n",
        status="reviewed",
        version="1.0.0",
        cue_template={"function_id": owner.id, "allowed": [symbol]},
    )
    values = {
        entry.key: entry,
        "cue.example": NarrationResource(
            "cue.example", locale, "narration", speech, status="reviewed", version="1.0.0"
        ),
        "cue.display": NarrationResource(
            "cue.display", locale, "ui", "PLUS-EXAMPLE", status="reviewed"
        ),
        "function.example": NarrationResource(
            "function.example", locale, "ui", "Example", status="reviewed"
        ),
    }
    catalog = LocaleCatalog.from_packs(
        [
            (
                locale,
                LocalePack(
                    {"locale": locale, "status": "canonical" if locale == "en-US" else "reviewed"},
                    values,
                ),
            )
        ]
    )
    catalog._function_records = lambda: [owner]
    return owner, entry, catalog


@pytest.mark.unit
@pytest.mark.parametrize(
    "symbol,role",
    [
        ("cue.primary", "activation"),
        ("cue.mode.increase", "increase"),
        ("cue.mode.decrease", "decrease"),
        ("cue.release", "release"),
        ("cue.cancel", "cancel"),
        ("cue.close", "close"),
        ("cue.retrieval", "retrieval"),
        ("cue.access_close", "access-close"),
        ("cue.id.OCF-CMD-COG-999-PRIMARY", "activation"),
    ],
)
def test_roles_and_ids_insert_complete_cue_without_prose_or_whitespace_drift(
    tmp_path, symbol, role
):
    owner, raw, catalog = fixture(tmp_path, symbol=symbol, role=role)
    entry, resolution = catalog.resource(raw.key, "en-US", domain="narration", fallback=False)
    assert entry.text == "Don't change  whitespace.\nThink Plus Example.\n"
    assert entry.render() == entry.text
    assert entry.raw_template == raw.text
    assert entry.cue_provenance[0]["provenance"]["command_id"] == owner.command_records[0].id
    assert raw.text.endswith("}}.\n")
    assert symbol in choices(owner)


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "{{ cue.unknown }}",
        "{{ cue.primary",
        "{{ cue.primary() }}",
        "{{ cue.primary }} }}",
        "{{ env.SECRET }}",
        "{{ cue.primary.__class__ }}",
        "{{ {{ cue.primary }} }}",
        "{{ cue.mode }}",
        "{cue.primary}",
        "{{ cue.primary }} {unapproved}",
    ],
)
def test_unknown_malformed_or_expression_syntax_is_rejected(text):
    with pytest.raises(CueTemplateError):
        scan(text)


@pytest.mark.unit
def test_documented_literal_brace_and_backslash_escapes_are_exact(tmp_path):
    owner, raw, catalog = fixture(tmp_path)
    raw = deepcopy(raw)
    from dataclasses import replace

    raw = replace(raw, text=r"Literal \{brace\}, slash \\, then {{ cue.primary }}.")
    text, _ = expand(raw, "en-US", catalog)
    assert text == r"Literal {brace}, slash \, then Plus Example."
    with pytest.raises(Exception, match="LocaleCatalog first"):
        raw.render()
    with pytest.raises(CueTemplateError, match="caller-supplied ICU"):
        expand(replace(raw, variables=("command",)), "en-US", catalog)


@pytest.mark.unit
def test_locale_cue_pronunciation_and_required_tokens_follow_expansion(tmp_path):
    from dataclasses import replace

    owner, entry, catalog = fixture(tmp_path)
    cue = catalog.canonical.entries["cue.example"]
    catalog.canonical.entries[cue.key] = replace(
        cue, pronunciation={"Example": {"piper": "Example"}}, required_pronunciation=("Example",)
    )
    resolved, _ = catalog.resource(entry.key, "en-US", domain="narration", fallback=False)
    assert resolved.pronunciation == {"Example": {"piper": "Example"}}
    assert resolved.required_pronunciation == ("Example",)
    assert resolved.text == "Don't change  whitespace.\nThink Plus Example.\n"
    catalog.canonical.entries[entry.key] = replace(
        entry, pronunciation={"Example": {"piper": "Conflicting"}}
    )
    with pytest.raises(CueTemplateError, match="conflicting pronunciation"):
        catalog.resource(entry.key, "en-US", domain="narration", fallback=False)


@pytest.mark.unit
def test_newline_and_icu_quote_characters_are_not_reformatted(tmp_path):
    from dataclasses import replace

    owner, entry, catalog = fixture(tmp_path)
    raw = "'Keep doubled apostrophes: '' exactly'\r\n\r\n{{ cue.primary }}.\r\n"
    entry = replace(entry, text=raw)
    catalog.canonical.entries[entry.key] = entry
    resolved, _ = catalog.resource(entry.key, "en-US", domain="narration", fallback=False)
    assert resolved.render().encode() == raw.replace("{{ cue.primary }}", "Plus Example").encode()


@pytest.mark.unit
@pytest.mark.parametrize(
    "change",
    [
        "missing-role",
        "ambiguous",
        "inactive",
        "cross-owner",
        "unauthorized",
        "undeclared",
        "extra-declaration",
        "unknown-owner",
        "missing-cue",
        "unreviewed",
        "conflicting-english",
        "nested",
    ],
)
def test_invalid_identity_authority_and_contracts_fail_closed(tmp_path, change):
    from dataclasses import replace

    owner, entry, catalog = fixture(tmp_path)
    if change == "missing-role":
        entry = replace(
            entry,
            text="{{ cue.release }}",
            cue_template={"function_id": owner.id, "allowed": ["cue.release"]},
        )
    elif change == "ambiguous":
        owner.data["commands"].append(deepcopy(owner.data["commands"][0]))
    elif change == "inactive":
        owner.data["commands"][0]["availability"] = "historical-lookup"
    elif change == "cross-owner":
        entry = replace(
            entry,
            text="{{ cue.id.OCF-CMD-FND-001-PRIMARY }}",
            cue_template={"function_id": owner.id, "allowed": ["cue.id.OCF-CMD-FND-001-PRIMARY"]},
        )
    elif change == "unauthorized":
        owner.data["narration"]["sequence"] = []
    elif change == "undeclared":
        entry = replace(entry, cue_template={"function_id": owner.id, "allowed": []})
    elif change == "extra-declaration":
        entry = replace(
            entry, cue_template={"function_id": owner.id, "allowed": ["cue.primary", "cue.close"]}
        )
    elif change == "unknown-owner":
        catalog._function_records = lambda: []
    elif change == "missing-cue":
        owner.data["commands"][0]["localization"] = {}
        owner.data["commands"][0]["spoken"] = None
    else:
        old = catalog.canonical.entries["cue.example"]
        if change == "unreviewed":
            catalog.canonical.entries[old.key] = replace(old, status="draft")
        elif change == "conflicting-english":
            catalog.canonical.entries[old.key] = replace(old, text="Plus Wrong")
        else:
            owner.data["commands"][0]["spoken"] = "{{ cue.primary }}"
            catalog.canonical.entries[old.key] = replace(old, text="{{ cue.primary }}")
    with pytest.raises(CueTemplateError, match="OCF-COG-999/en-US/fixture.body"):
        expand(entry, "en-US", catalog)


@pytest.mark.unit
@pytest.mark.parametrize("missing", [True, False])
def test_reviewed_locale_copy_cannot_authorize_missing_or_unresolved_english(tmp_path, missing):
    owner, entry, catalog = fixture(tmp_path)
    if missing:
        owner.data["commands"][0].pop("spoken")
        owner.data["commands"][0].pop("spoken_review")
    else:
        owner.data["commands"][0].update(spoken=None, spoken_review="unresolved")
    with pytest.raises(CueTemplateError, match="authoritative|conflicts"):
        expand(entry, "en-US", catalog)


@pytest.mark.unit
def test_display_and_ui_templates_cannot_form_a_recursive_resolution_cycle(tmp_path):
    from dataclasses import replace

    owner, entry, catalog = fixture(tmp_path)
    display = catalog.canonical.entries["cue.display"]
    catalog.canonical.entries[display.key] = replace(
        display, text="{{ cue.primary }}", cue_template=entry.cue_template
    )
    with pytest.raises(CueTemplateError, match="display cue must be literal"):
        expand(entry, "en-US", catalog)
    with pytest.raises(CueTemplateError, match="only for narration"):
        expand(replace(entry, domain="ui"), "en-US", catalog)


@pytest.mark.unit
@pytest.mark.parametrize(
    "locale,speech", [("ja", "見る"), ("ar", "تركيز"), ("es", "Enfocar"), ("zh-Hant", "專注")]
)
def test_locale_complete_realizations_preserve_unicode_and_translator_word_order(
    tmp_path, locale, speech
):
    owner, entry, catalog = fixture(tmp_path, locale=locale, speech=speech)
    from dataclasses import replace

    entry = replace(entry, text="{{ cue.primary }} — Surrounding grammar.")
    assert expand(entry, locale, catalog)[0] == speech + " — Surrounding grammar."


@pytest.mark.unit
def test_variants_require_review_and_same_stable_identity(tmp_path):
    from dataclasses import replace

    owner, entry, catalog = fixture(tmp_path, symbol="cue.primary.variant.object")
    owner.data["commands"][0]["spoken_variants"] = {
        "object": {"text": "the complete cue", "status": "reviewed"}
    }
    assert "cue.primary.variant.object" in choices(owner)
    assert expand(entry, "en-US", catalog)[0].endswith("Think the complete cue.\n")
    owner.data["commands"][0]["spoken_variants"]["object"]["status"] = "unresolved"
    with pytest.raises(CueTemplateError, match="unreviewed"):
        expand(entry, "en-US", catalog)
    owner, entry, catalog = fixture(
        tmp_path, locale="es", speech="Elegir", symbol="cue.primary.variant.object"
    )
    with pytest.raises(CueTemplateError, match="no localized binding"):
        expand(entry, "es", catalog)
    owner.data["commands"][0]["localization"]["spoken_variant_keys"] = {"object": "cue.example"}
    assert "Elegir" in expand(entry, "es", catalog)[0]
    catalog.packs["es"].entries["cue.example"] = replace(
        catalog.packs["es"].entries["cue.example"], status="draft"
    )
    with pytest.raises(CueTemplateError, match="needs review"):
        expand(entry, "es", catalog)


@pytest.mark.unit
def test_title_is_presentation_not_an_activation_and_regional_fallback_is_labeled(tmp_path):
    owner, entry, catalog = fixture(tmp_path, symbol="function.title")
    text, refs = expand(entry, "en-GB", catalog)
    assert text.endswith("Think Example.\n") and refs[0]["provenance"]["locale"] == "en-US"
    from dataclasses import replace

    catalog.canonical.entries["function.example"] = replace(
        catalog.canonical.entries["function.example"], text="Conflicting title"
    )
    with pytest.raises(CueTemplateError, match="title conflicts"):
        expand(entry, "en-US", catalog)
    del owner.data["documentation"]["title_key"]
    with pytest.raises(CueTemplateError, match="missing localized title"):
        expand(entry, "en-US", catalog)


@pytest.mark.unit
def test_translation_keeps_authorized_command_identity_but_may_use_reviewed_variant(tmp_path):
    from dataclasses import replace

    owner, source, catalog = fixture(tmp_path)
    translated = replace(
        source,
        locale="es",
        text="{{ cue.primary.variant.object }} ahora.",
        cue_template={"function_id": owner.id, "allowed": ["cue.primary.variant.object"]},
    )
    owner.data["commands"][0]["localization"]["spoken_variant_keys"] = {"object": "cue.object"}
    catalog.packs["es"] = LocalePack(
        {"locale": "es", "status": "reviewed"},
        {
            translated.key: translated,
            "cue.object": NarrationResource(
                "cue.object", "es", "narration", "Elegir", status="reviewed"
            ),
        },
    )
    assert expand(translated, "es", catalog)[0] == "Elegir ahora."
    cancel = deepcopy(owner.data["commands"][0])
    cancel.update(id="OCF-CMD-COG-999-CANCEL", role="cancel", designation="secondary")
    owner.data["commands"].append(cancel)
    translated = replace(
        translated,
        text="{{ cue.cancel }} ahora.",
        cue_template={"function_id": owner.id, "allowed": ["cue.cancel"]},
    )
    with pytest.raises(CueTemplateError, match="changed the authorized cue identities"):
        expand(translated, "es", catalog)


@pytest.mark.unit
def test_document_expansion_precedes_recording_fingerprints_and_release(tmp_path):
    from ocf_tools.narration_sources import SourceResolver
    from ocf_tools.release import transcript_from_render

    owner, entry, catalog = fixture(tmp_path)
    doc = {"locale": "en-US", "timeline": [{"id": "body", "at": 0, "narration_key": entry.key}]}
    resolved = resolve_document(doc, "en-US", catalog=catalog)
    text = resolved["timeline"][0]["text"]
    assert text.endswith("Think Plus Example.\n")
    assert "raw_template_sha256" in resolved["narration"]["resolved"][0]
    assert transcript_from_render({"narration_timing": {"cues": [{"spoken_text": text}]}}) == text
    for final in ("{{ cue.primary }}", "unfinished }}"):
        with pytest.raises(CueTemplateError):
            SourceResolver({"timeline": [{"id": "bad", "text": final}]}, {})
        with pytest.raises(CueTemplateError):
            transcript_from_render({"narration_timing": {"cues": [{"spoken_text": final}]}})
    from ocf_tools.voice import render_cue_wav

    with pytest.raises(CueTemplateError):
        render_cue_wav({}, "{{ cue.primary }}")


@pytest.mark.integration
def test_all_approved_resolved_bytes_and_four_passes_match_predecessor():
    from ocf_tools.narration_first import plan_narration
    from ocf_tools.paths import REPO_ROOT
    from ocf_tools.symbolic_integrity import verify
    from tools.check_hplus_narration_integrity import narration_texts

    data = json.loads(
        (REPO_ROOT / "function-content/editorial/symbolic-cues-001.json").read_text(
            encoding="utf-8"
        )
    )
    assert verify() == []
    assert len(data["entries"]) == 22
    assert {
        key: hashlib.sha256(text.encode()).hexdigest() for key, text in narration_texts().items()
    } == data["resolved_baseline"]
    for owner in sorted({row["function_id"] for row in data["entries"]}):
        view = preview(owner)
        assert not view["synthesis"]
        plan = plan_narration(owner, locale="en-US")
        for row in (item for item in data["entries"] if item["function_id"] == owner):
            repetitions = 4 if row["key"].endswith("function-body") else 1
            for playback in range(1, repetitions + 1):
                pieces = [
                    segment["canonical_text"]
                    for segment in plan["segments"]
                    if segment["resource_key"] == row["key"] and segment["playback"] == playback
                ]
                assert "\n\n".join(pieces).encode() == row["before_text"].encode()
        assert all("{{" not in resource["resolved_text"] for resource in view["resources"])
