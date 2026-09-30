"""Wizard tests: keyboard-only navigation and schema-valid record building."""

from __future__ import annotations

import builtins

from ocf_tools import prompts
from ocf_tools.prompts import (
    BACK,
    QUIT,
    SKIP_CONST,
    ask,
    ask_yes_no,
    background_manifest_yaml,
    build_function_yaml,
    proposal_markdown,
)


def _answers(monkeypatch, sequence):
    queue = iter(sequence)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(queue))


def test_ask_returns_default_on_enter(monkeypatch):
    _answers(monkeypatch, [""])
    result = ask("Name?", default="fn")
    assert result.intent == "value"
    assert result.value == "fn"


def test_ask_help_then_value(monkeypatch, capsys):
    _answers(monkeypatch, ["?", ""])
    result = ask("Name?", default="fn", help_text="a name")
    out = capsys.readouterr().out
    assert "help: a name" in out
    assert result.value == "fn"


def test_ask_help_keeps_prompting(monkeypatch):
    _answers(monkeypatch, ["?", "? ", "x"])
    result = ask("Name?", help_text="a name")
    assert result.value == "x"


def test_ask_back_navigation(monkeypatch):
    _answers(monkeypatch, ["back"])
    result = ask("Name?")
    assert result.intent == "back"
    assert result.value == BACK


def test_ask_skip(monkeypatch):
    _answers(monkeypatch, ["skip"])
    result = ask("Name?")
    assert result.intent == "skip"
    assert result.value == SKIP_CONST


def test_ask_quit(monkeypatch):
    _answers(monkeypatch, ["quit"])
    result = ask("Name?")
    assert result.intent == "quit"
    assert result.value == QUIT


def test_ask_eof_counts_as_quit(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": (_ for _ in ()).throw(EOFError()))
    result = ask("Name?")
    assert result.intent == "quit"


def test_ask_pick_by_number(monkeypatch):
    _answers(monkeypatch, ["2"])
    result = prompts.ask_pick("Pick", ["alpha", "beta"])
    assert result.value == "beta"


def test_ask_yes_no_default(monkeypatch):
    _answers(monkeypatch, [""])
    assert str(ask_yes_no("Sure?", default=True).value) == "yes"


def test_function_wizard_quit_writes_nothing(monkeypatch, repo_root):
    funcs_dir = repo_root / "functions"
    before = sorted(p for p in funcs_dir.rglob("*.yaml"))
    _answers(monkeypatch, ["somebody", "", "quit"])
    prompts.run_function_wizard()
    after = sorted(p for p in funcs_dir.rglob("*.yaml"))
    assert after == before


def test_proposal_wizard_quit_writes_nothing(monkeypatch, repo_root):
    proposals_dir = repo_root / "proposals"
    before = sorted(p for p in proposals_dir.rglob("ocfp-*.md"))
    _answers(monkeypatch, ["quit"])
    prompts.run_proposal_wizard()
    after = sorted(p for p in proposals_dir.rglob("ocfp-*.md"))
    assert after == before


def test_build_function_yaml_is_schema_valid():
    import json

    data = build_function_yaml(
        function_id="OCF-FND-101",
        slug="wizard-test",
        name="Wizard Test",
        short_name="WT",
        primary_domain="foundation",
        secondary_domains=["cognition"],
        purpose="Test wizard output.",
        canonical_command="PLUS-WIZARD",
        modes=["PLUS-WIZARD MORE", "PLUS-WIZARD LESS"],
        legacy_name="",
        legacy_commands=[],
        command_status="unchanged",
        rationale="",
        compat_state="unchanged",
        source_availability="pending-source-review",
        reimplementation_status="planned",
        persistence="temporary",
        activation="manual",
        release_required=False,
        release_command=None,
        companions=[],
        incompatible=[],
        chains=[],
        safety_level="general",
        medical_relevance=False,
        safety_notes=[],
        evidence="unverified",
        applications=["demo"],
        contributor_name="Ada",
        contributor_contact="ada@example.com",
        source_files=["docs/x.pdf"],
        source_urls=["https://example.test"],
        community_notes=["reference one"],
        testing_status="informal",
        audio_status="not-started",
        background_status="optional",
        notes="first pass",
    )
    with open("schemas/function.schema.json", encoding="utf-8") as handle:
        from ocf_tools.validators import validate_against_schema

        errors = validate_against_schema(data, json.load(handle))
    assert errors == [], errors
    assert data["ocf"]["testing_status"] == "informal"
    source_types = [s["type"] for s in data["sources"]]
    assert "reference-file" in source_types
    assert "web" in source_types
    assert "community-notes" in source_types
    assert "first pass" in data["history"][0]["note"]


def test_proposal_markdown_shape():
    text = proposal_markdown(
        "OCFP-0001",
        "A newer focus",
        ["Bob"],
        "problem",
        "purpose",
        "Cool Focus",
        "PLUS-COOL",
        "one word",
        "manual",
        "",
        "temporary",
        "general",
        "preserved as aliases",
        "community-hypothesis",
        "none",
        "scripting",
        "informal",
        ["https://example.test"],
        "Apache-2.0",
    )
    assert text.startswith("# OCFP-0001: A newer focus")
    assert "## Proposed command" in text
    assert "`PLUS-COOL`" in text
    assert "## Compatibility" in text


def test_background_manifest_deterministic_id_prefixes():
    kwargs = dict(
        bg_id="OCF-BG-0003",
        name="A",
        author="B",
        engine="farfield",
        preset_file="audio/background/presets/a.yaml",
        provenance="original-ocf",
        notes="",
        intended="",
        functions=["OCF-FND-001"],
        seed="",
        fmt="wav",
        render_notes="",
        headphone=True,
        driving=True,
        safety_notes=[],
        license_="CC-BY-4.0",
    )
    data = background_manifest_yaml(**kwargs)
    assert data["id"].startswith("OCF-BG-")
    assert data["engine"] == "farfield"
    assert data["engine_source"]["repository"].endswith("txus/farfield")


def test_wizard_ask_back_not_allowed_passes_through(monkeypatch):
    _answers(monkeypatch, ["back"])
    result = ask("Path?", allow_back=False)
    assert result.intent == "value"
    assert result.value == "back"
