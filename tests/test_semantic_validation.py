"""Pre-render structural hygiene and function command ownership."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from ocf_tools.cli import main
from ocf_tools.session import compose, load_template
from ocf_tools.utils import OCFError
from ocf_tools.validators import validate_narration_usage
from ocf_tools.voice import render_narration


def command_doc(command="PLUS-FOCUS", function_id="OCF-FND-002"):
    return {"schema_version": "1.0", "title": "Owner", "function_id": function_id, "timeline": [
        {"id": "explain", "at": "00:00.000", "semantic": "function.command.explain",
         "narration_key": "function.activation.command", "variables": {"command": command}},
    ]}


def test_another_functions_valid_command_is_rejected():
    result = validate_narration_usage(command_doc("PLUS-THINK"), Path("owner.yaml"))
    assert "narration-command-owner" in [issue.code for issue in result.errors]


def test_command_explanation_requires_function_identity():
    doc = command_doc()
    doc.pop("function_id")
    result = validate_narration_usage(doc, Path("owner.yaml"))
    assert "narration-command-owner" in [issue.code for issue in result.errors]


def test_literal_wrong_command_cannot_bypass_owner_validation():
    doc = command_doc()
    doc["timeline"][0] = {"id": "explain", "at": "00:00.000", "semantic": "function.command.explain", "text": "Test PLUS-THINK."}
    assert "narration-command-owner" in [issue.code for issue in validate_narration_usage(doc, Path("owner.yaml")).errors]


def test_command_owner_matches_and_canonical_identity_survives_localization():
    from ocf_tools.locale import resolve_document

    doc = command_doc()
    resolved = resolve_document(doc, "es")
    assert resolved["timeline"][0]["variables"]["command"] == "PLUS-FOCUS"
    assert not validate_narration_usage(resolved, Path("owner.yaml")).errors


def test_bad_command_blocks_tts_before_any_synthesis(tmp_path):
    seen = []
    with pytest.raises(OCFError, match="command.*owner|command.*belong"):
        render_narration(command_doc("PLUS-THINK"), tmp_path / "out.wav",
                         backend={"backend": "espeak-ng"}, render_cue=lambda text: seen.append(text))
    assert not seen and not (tmp_path / "out.wav").exists()


def test_architecture_draft_missing_required_narration_blocks_tts(tmp_path):
    doc = compose(load_template("OCF-TPL-SESSION-PREP-ROUTINE-001"), {}, title="Draft")
    with pytest.raises(OCFError, match="required narration"):
        render_narration(doc, tmp_path / "out.wav", backend={"backend": "espeak-ng"}, render_cue=lambda text: b"")
    assert not (tmp_path / "out.wav").exists()


@pytest.mark.parametrize("change", [
    {"text": "TODO translate this placeholder"},
    {"text": "Unresolved {listener} variable."},
    {"text": ""},
    {"text": "A pause [pause: tomorrow]."},
    {"text": "Valid words.", "timing": {"pause_after": -2}},
])
def test_hygiene_errors_are_pre_render(change, tmp_path):
    event = {"id": "a", "at": "00:00.000", "semantic": "session.test", **change}
    with pytest.raises(OCFError):
        render_narration({"schema_version": "1.0", "title": "Hygiene", "timeline": [event]},
                         tmp_path / "out.wav", backend={"backend": "espeak-ng"},
                         render_cue=lambda text: pytest.fail("synthesis called before preflight"))
    assert not (tmp_path / "out.wav").exists()


def test_duplicate_auditory_signal_at_same_anchor_is_rejected(tmp_path):
    event = {"id": "a", "at": "00:00.000", "semantic": "focus.eleven.ready", "auditory_cue": "focus.eleven.ready"}
    doc = {"schema_version": "1.0", "title": "Duplicate", "timeline": [event, dict(event, id="b")]}
    with pytest.raises(OCFError, match="duplicate.*cue"):
        render_narration(doc, tmp_path / "out.wav", backend={"backend": "espeak-ng"})


def test_duplicate_narration_at_same_anchor_requires_explicit_repetition(tmp_path):
    doc = command_doc()
    doc["timeline"].append(dict(doc["timeline"][0], id="duplicate"))
    with pytest.raises(OCFError, match="duplicate.*narration"):
        render_narration(doc, tmp_path / "out.wav", backend={"backend": "espeak-ng"})


def test_intentional_repetition_and_later_state_reentry_are_valid():
    from ocf_tools.validators import validate_narration_hygiene

    event = {"id": "a", "at": "00:00.000", "semantic": "focus.ten.ready", "auditory_cue": "focus.ten.ready", "text": "Test wording."}
    doc = {"timeline": [event, dict(event, id="b", intentional_repeat=True), dict(event, id="c", at="00:20.000")]}
    assert not validate_narration_hygiene(doc).errors


def test_function_specific_stage_narration_overrides_do_not_change_semantics():
    template = deepcopy(load_template("OCF-TPL-SESSION-FUNCTION-INSTALL-001"))
    template["sections"][0]["narration"] = {"purpose": {"narration_key": "function.intro.name", "variables": {"function_name": "Attention"}}}
    doc = compose(template, {}, title="Custom")
    event = doc["sections"][0]["timeline"][0]
    assert event["semantic"] == "function.purpose"
    assert event["narration_key"] == "function.intro.name"


def test_live_compose_cli_binds_function_metadata_and_optional_stages(tmp_path, capsys):
    template = deepcopy(load_template("OCF-TPL-SESSION-FUNCTION-INSTALL-001"))
    template["sections"][2]["narration"] = {"explain": {"narration_key": "function.activation.command"}}
    source, output = tmp_path / "template.yaml", tmp_path / "composed.yaml"
    source.write_text(yaml.safe_dump(template))
    assert main(["session", "compose", "--template", str(source), "--function", "OCF-FND-002",
                 "--enable-stage", "examples", "--output", str(output)]) == 0
    doc = yaml.safe_load(output.read_text())
    assert doc["function_id"] == "OCF-FND-002"
    assert doc["sections"][1]["id"] == "examples"
    assert doc["sections"][2]["timeline"][0]["variables"] == {"command": "PLUS-FOCUS"}
    assert "Architecture draft" in capsys.readouterr().out


def test_locale_validation_rejects_uninstalled_language(capsys):
    assert main(["locale", "validate", "--locale", "de", "--json"]) == 1
    assert "locale-unavailable" in capsys.readouterr().out


def test_narration_override_cannot_change_dsp():
    template = deepcopy(load_template("OCF-TPL-SESSION-FUNCTION-INSTALL-001"))
    template["sections"][0]["narration"] = {"purpose": {"narration_key": "function.intro.name", "dsp": {"state": "wrong"}}}
    with pytest.raises(OCFError, match="cannot alter"):
        compose(template, {}, title="Invalid")


def test_required_pronunciation_fails_before_tts(tmp_path):
    from ocf_tools.locale import LocaleCatalog

    catalog = LocaleCatalog()
    key = "session.focus-cycle.opener"
    entry = catalog.canonical.entries[key]
    catalog.canonical.entries[key] = replace(entry, required_pronunciation=("OCF",))
    doc = {"schema_version": "1.0", "title": "Required", "timeline": [{"id": "a", "at": "00:00.000", "narration_key": key}]}
    with pytest.raises(OCFError, match="required pronunciation"):
        render_narration(doc, tmp_path / "out.wav", catalog=catalog,
                         backend={"backend": "espeak-ng"}, render_cue=lambda text: pytest.fail("TTS must not run"))


def test_malformed_resource_message_is_a_validation_issue_not_a_crash():
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.validators import validate_locale_packs

    catalog = LocaleCatalog()
    key = "session.focus-cycle.opener"
    catalog.canonical.entries[key] = replace(catalog.canonical.entries[key], text="Broken {name")
    assert "locale-message-syntax" in [issue.code for issue in validate_locale_packs(catalog).errors]


def test_narration_cannot_reference_an_absent_semantic_event(tmp_path):
    from ocf_tools.locale import LocaleCatalog

    catalog = LocaleCatalog()
    key = "session.focus-cycle.opener"
    catalog.canonical.entries[key] = replace(catalog.canonical.entries[key], requires_events=("focus.eleven.ready",))
    doc = {"schema_version": "1.0", "title": "Reference", "timeline": [{"id": "a", "at": "00:00.000", "narration_key": key}]}
    with pytest.raises(OCFError, match="absent semantic event"):
        render_narration(doc, tmp_path / "out.wav", catalog=catalog,
                         backend={"backend": "espeak-ng"}, render_cue=lambda text: pytest.fail("TTS must not run"))


def test_piper_uses_actual_model_locale_not_a_mislabelled_profile(tmp_path):
    from ocf_tools.locale import LocalizationError
    from ocf_tools.voice import resolve_backend

    model = tmp_path / "voice.onnx"
    Path(str(model) + ".json").write_text('{"language": {"code": "en_US"}}')
    with pytest.raises(LocalizationError, match="model.*es"):
        resolve_backend({"backend": "piper", "language": "es", "piper_model": str(model)}, [], locale="es")


def test_unsupported_language_switchable_voice_is_a_pre_synthesis_error(monkeypatch):
    from types import SimpleNamespace

    from ocf_tools import voice

    monkeypatch.setattr(voice.shutil, "which", lambda executable: "/fake/espeak-ng")
    monkeypatch.setattr(voice.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="Voice table header\n"))
    with pytest.raises(OCFError, match="does not support requested TTS locale"):
        voice.check_backend_locale({"name": "espeak-ng", "binary": "espeak-ng", "language": "unknown", "locale": "zz"})


def test_regional_resource_pronunciation_reaches_tts_without_changing_visible_text(tmp_path):
    from ocf_tools.locale import LocaleCatalog
    from test_localized_timing import pcm

    catalog = LocaleCatalog()
    key = "session.focus-cycle.opener"
    source = catalog.require("es").entries[key]
    catalog.require("es").entries[key] = replace(source, pronunciation={"Bienvenido": {"espeak-ng": "[[b j e n]]"}})
    doc = {"schema_version": "1.0", "title": "Regional", "timeline": [{"id": "a", "at": "00:00.000", "narration_key": key}]}
    seen = []

    def spy(text):
        seen.append(text)
        return pcm(.1)

    meta = render_narration(doc, tmp_path / "out.wav", locale="es-MX", catalog=catalog,
                            backend={"backend": "espeak-ng"}, render_cue=spy, sample_rate=100)
    assert seen[0].startswith("[[b j e n]]")
    assert meta["cue_stats"][0]["display_text"] == source.text
    assert meta["narration_resolution"]["resolved"][0]["locale"] == "es"
    assert "text" not in doc["timeline"][0]
