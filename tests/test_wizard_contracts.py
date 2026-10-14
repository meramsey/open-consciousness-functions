"""Wizard collection/review contracts with prompt, discovery and write boundaries injected."""

from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from ocf_tools import prompts, utils

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "wizard",
    [
        prompts.run_function_wizard,
        prompts.run_proposal_wizard,
        prompts.run_audio_wizard,
        prompts.run_background_wizard,
        prompts.run_test_report_wizard,
    ],
)
@pytest.mark.parametrize("cancel", ["quit", "eof", "interrupt"])
def test_quit_at_first_field_stops_before_discovery_and_writes(monkeypatch, wizard, cancel, capsys):
    def input_value(prompt):
        if cancel == "eof":
            raise EOFError()
        if cancel == "interrupt":
            raise KeyboardInterrupt()
        return "quit"

    monkeypatch.setattr("builtins.input", input_value)
    monkeypatch.setattr(
        prompts, "write_text_atomic", lambda *a, **kw: pytest.fail("must not write")
    )
    monkeypatch.setattr(
        prompts,
        "load_all_functions",
        lambda: (
            [NS(id="OCF-FND-999")]
            if wizard is prompts.run_audio_wizard
            else pytest.fail("must not discover after quit")
        ),
    )
    wizard()
    assert "nothing written" in capsys.readouterr().out
    assert prompts._WIZARD_ACTIVE.get() is False
    assert prompts.ask("standalone").intent == "quit"


def test_quit_after_an_optional_field_is_not_serialized(monkeypatch, capsys):
    responses = iter(["Contributor", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))
    monkeypatch.setattr(
        prompts,
        "build_function_yaml",
        lambda **kw: pytest.fail("must not assemble cancelled fields"),
    )
    prompts.run_function_wizard()
    assert "nothing written" in capsys.readouterr().out


@pytest.fixture
def authoring_boundary(monkeypatch, tmp_path):
    writes = []
    monkeypatch.setattr(prompts, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prompts, "FUNCTIONS_DIR", tmp_path / "functions")
    monkeypatch.setattr(prompts, "PROPOSALS_DIR", tmp_path / "proposals")
    monkeypatch.setattr(prompts, "AUDIO_MANIFESTS_DIR", tmp_path / "audio/manifests")
    monkeypatch.setattr(prompts, "load_all_functions", lambda: [])
    monkeypatch.setattr(prompts, "current_date", lambda: "2026-10-04")
    monkeypatch.setattr(
        prompts, "write_text_atomic", lambda path, text, **kw: writes.append((path, text))
    )
    monkeypatch.setattr(prompts, "validate_function_file", lambda path: NS(ok=True))
    monkeypatch.setattr(prompts, "validate_background_manifests", lambda: NS(ok=True))
    monkeypatch.setattr(prompts, "print_result", lambda result: 0)
    monkeypatch.setattr(prompts, "multi_ask", lambda *a, **kw: [])
    monkeypatch.setattr(
        prompts,
        "ask_pick",
        lambda p, choices, **kw: prompts.PromptResult(kw.get("default") or choices[0]),
    )
    monkeypatch.setattr(
        prompts,
        "ask_yes_no",
        lambda p, **kw: prompts.PromptResult("yes" if kw.get("default") else "no"),
    )
    return tmp_path, writes


@pytest.mark.parametrize(
    "status,release,confirm",
    [("unchanged", False, True), ("normalized", True, True), ("proposed", False, False)],
)
def test_function_collection_compatibility_release_and_final_review(
    monkeypatch, authoring_boundary, status, release, confirm
):
    root, writes = authoring_boundary

    def ask(prompt, **kwargs):
        if prompt == "Canonical command":
            return prompts.PromptResult("PLUS-TEST")
        return prompts.PromptResult(kwargs.get("default") or "Fixture")

    monkeypatch.setattr(prompts, "ask", ask)

    def pick(prompt, choices, **kw):
        return prompts.PromptResult(
            status if prompt == "Command status" else kw.get("default") or choices[0]
        )

    monkeypatch.setattr(prompts, "ask_pick", pick)

    def yes_no(prompt, **kw):
        if prompt == "Requires release command?":
            return prompts.PromptResult("yes" if release else "no")
        return prompts.PromptResult("yes" if confirm else "no")

    monkeypatch.setattr(prompts, "ask_yes_no", yes_no)
    records = []
    monkeypatch.setattr(
        prompts, "build_function_yaml", lambda **kw: records.append(kw) or {"fixture": status}
    )
    prompts.run_function_wizard()
    assert bool(writes) is confirm
    assert (
        records[0]["compat_state"]
        == {"unchanged": "unchanged", "normalized": "alias-listed", "proposed": "bridge-trainable"}[
            status
        ]
    )
    assert records[0]["release_required"] is release
    assert bool(records[0]["release_command"]) is release
    assert records[0]["canonical_command"] == "PLUS-TEST"
    if confirm:
        assert writes[0][0] == root / "functions/foundation/fixture.yaml"


def test_function_overwrite_decline_and_list_prompt_quit_do_not_write(
    monkeypatch, authoring_boundary, capsys
):
    _, writes = authoring_boundary
    monkeypatch.setattr(
        prompts, "ask", lambda *a, **kw: prompts.PromptResult(kw.get("default") or "Fixture")
    )
    monkeypatch.setattr(prompts, "_confirm_write", lambda path: False)
    prompts.run_function_wizard()
    assert not writes and "Overwrite declined" in capsys.readouterr().out

    def quit_list(*a, **kw):
        raise prompts.WizardQuit()

    monkeypatch.setattr(prompts, "multi_ask", quit_list)
    prompts.run_function_wizard()
    assert not writes and "nothing written" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["quit", "skip", "back", "yes", "no"])
def test_source_import_copy_requires_explicit_choice(monkeypatch, tmp_path, capsys, answer):
    source = tmp_path / "input/source.txt"
    source.parent.mkdir()
    source.write_text("synthetic source")
    root = tmp_path / "repo"
    monkeypatch.setattr(prompts, "REPO_ROOT", root)
    responses = iter([str(source), answer])
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))
    prompts.run_import_source()
    assert (root / "references/uploads/source.txt").exists() is (answer == "no")
    assert source.read_text() == "synthetic source"
    if answer != "no":
        assert "Copied to" not in capsys.readouterr().out


def test_source_import_missing_input_existing_copy_decline_and_media_warning(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(prompts, "REPO_ROOT", tmp_path)
    responses = iter([str(tmp_path / "missing")])
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))
    prompts.run_import_source()
    assert "no such file" in capsys.readouterr().out
    source = tmp_path / "fixture.wav"
    source.write_bytes(b"synthetic input, not audio")
    existing = tmp_path / "references/uploads/fixture.wav"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"old")
    responses = iter([str(source), "no", "no"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))
    prompts.run_import_source()
    assert existing.read_bytes() == b"old"
    responses = iter([str(source), "no", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))
    prompts.run_import_source()
    assert existing.read_bytes() == source.read_bytes()
    assert "redistribute" in capsys.readouterr().out


@pytest.mark.parametrize(
    "wizard", [prompts.run_proposal_wizard, prompts.run_audio_wizard, prompts.run_background_wizard]
)
@pytest.mark.parametrize("decision", ["write", "decline", "overwrite-decline"])
def test_other_authoring_wizards_only_write_after_explicit_review(
    monkeypatch, authoring_boundary, wizard, decision, capsys
):
    root, writes = authoring_boundary

    def ask(prompt, **kw):
        if prompt in (
            "Duration (minutes, optional)",
            "Sample rate (optional)",
            "Channels (optional)",
        ):
            return prompts.PromptResult("")
        return prompts.PromptResult(kw.get("default", "Fixture"))

    monkeypatch.setattr(prompts, "ask", ask)
    monkeypatch.setattr(prompts, "load_all_functions", lambda: [NS(id="OCF-FND-999")])
    monkeypatch.setattr(prompts, "validate_audio_output", lambda path: None)
    monkeypatch.setattr(
        prompts,
        "ask_yes_no",
        lambda p, **kw: prompts.PromptResult(
            "no" if decision == "decline" and p.startswith("Write") else "yes"
        ),
    )
    monkeypatch.setattr(prompts, "_confirm_write", lambda path: decision != "overwrite-decline")
    wizard()
    assert bool(writes) is (decision == "write")
    if writes:
        assert writes[0][0].is_relative_to(root)
        assert "Fixture" in writes[0][1]
    else:
        assert "nothing written" in capsys.readouterr().out


def test_audio_wizard_empty_discovery_and_report_template_substitution(
    monkeypatch, authoring_boundary, capsys
):
    root, writes = authoring_boundary
    prompts.run_audio_wizard()
    assert not writes and "No functions yet" in capsys.readouterr().out
    monkeypatch.setattr(
        prompts, "ask", lambda p, **kw: prompts.PromptResult(kw.get("default") or "Fixture")
    )
    monkeypatch.setattr(
        prompts,
        "read_text",
        lambda path: (
            "__TARGET__|__TESTER__|__DATE__|__CONTEXT__|__RESULTS__|__ISSUES__|__VERDICT__"
        ),
    )
    prompts.run_test_report_wizard()
    assert len(writes) == 1
    assert writes[0][0].is_relative_to(root / "audio/testing-reports")
    assert "__TARGET__" not in writes[0][1] and "None recorded" in writes[0][1]


def test_editor_planning_errors_do_not_claim_validation(monkeypatch, tmp_path, capsys):
    from ocf_tools import indexes

    prompts.run_edit_function(None)
    assert "usage:" in capsys.readouterr().out
    monkeypatch.setattr(indexes, "load_function_by_slug_or_id", lambda q: None)
    prompts.run_edit_function("unknown")
    assert "no function matches" in capsys.readouterr().out
    path = Path(tmp_path / "fixture.yaml")
    monkeypatch.setattr(indexes, "load_function_by_slug_or_id", lambda q: NS(path=path))
    calls = []
    monkeypatch.setenv("EDITOR", "fixture-editor")
    monkeypatch.setattr(
        prompts,
        "workspace_run",
        lambda argv: calls.append(argv) or NS(returncode=0),
    )
    monkeypatch.setattr(prompts, "validate_function_file", lambda p: calls.append(p) or "validated")
    monkeypatch.setattr(prompts, "print_result", lambda result: calls.append(result))
    prompts.run_edit_function("fixture")
    assert calls == [["fixture-editor", str(path)], path, "validated"]
    monkeypatch.delenv("EDITOR")
    prompts.run_edit_function("fixture")
    assert calls[-3][0] in ("vi", "notepad")
    monkeypatch.setattr(prompts, "workspace_run", lambda argv: NS(returncode=7))
    with pytest.raises(utils.OCFError, match="exit 7"):
        prompts.run_edit_function("fixture")

    def missing(argv):
        raise OSError("missing executable")

    monkeypatch.setattr(prompts, "workspace_run", missing)
    with pytest.raises(utils.OCFError, match="cannot start editor"):
        prompts.run_edit_function("fixture")


def test_temporary_editor_document_preserves_unicode_and_is_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    path = prompts.tmp_dump("Café\n")
    assert path.is_relative_to(tmp_path / "ocf-work" / "tmp")
    assert path.read_text(encoding="utf-8") == "Café\n"


def test_manifest_id_allocation_reads_metadata_not_filename(monkeypatch, tmp_path):
    directory = tmp_path / "manifests"
    directory.mkdir()
    monkeypatch.setattr(prompts, "AUDIO_MANIFESTS_DIR", directory)
    (directory / "ocf-audio-0001.yaml").write_text("id: OCF-AUDIO-0099")
    (directory / "named.yml").write_text("id: OCF-AUDIO-0100")
    (directory / "notes.txt").write_text("ignored")
    (directory / "subdirectory.yaml").mkdir()
    (directory / "other.yaml").write_text("id: unrelated")
    assert prompts.next_audio_id() == "OCF-AUDIO-0101"


def test_audio_validation_adapter_delegates_without_schema_read(monkeypatch, tmp_path, capsys):
    from ocf_tools import validators

    monkeypatch.setattr(prompts, "REPO_ROOT", tmp_path)
    result = object()
    monkeypatch.setattr(validators, "validate_audio_manifests", lambda: result)
    received = []
    monkeypatch.setattr(prompts, "print_result", lambda data: received.append(data))
    prompts.validate_audio_output(tmp_path / "audio/manifests/fixture.yaml")
    assert received == [result]
    assert "Created:" in capsys.readouterr().out


def test_optional_contributor_fields_can_remain_empty(monkeypatch, authoring_boundary):
    _, writes = authoring_boundary

    def ask(prompt, **kw):
        if prompt in ("Contributor name (for attribution)", "Optional contact handle/email"):
            return prompts.PromptResult("")
        return prompts.PromptResult(kw.get("default") or "Fixture")

    monkeypatch.setattr(prompts, "ask", ask)
    collected = []
    monkeypatch.setattr(
        prompts, "build_function_yaml", lambda **kw: collected.append(kw) or {"fixture": True}
    )
    prompts.run_function_wizard()
    assert writes
    assert collected[0]["contributor_name"] is None and collected[0]["contributor_contact"] is None
