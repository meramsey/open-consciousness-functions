"""CLI-only routing/output contracts; every repository/process collaborator is stubbed."""

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from ocf_tools import (
    audio_build,
    cli,
    content,
    corpus,
    diagnostics,
    editorial,
    generators,
    indexes,
    locale,
    planning,
    recordings,
    semantic_dsp,
    session,
    transcript,
    utils,
    validators,
    voice_registry,
)
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def test_help_parse_failure_argv_default_and_interrupt(monkeypatch, capsys):
    assert cli.main([]) == 0
    assert cli.main(["help"]) == 0
    assert cli.main(["--quiet"]) == 0
    assert cli.main(["bogus"]) == 2
    assert cli.main(["voice", "--help"]) == 0
    monkeypatch.setattr(cli.sys, "argv", ["ocf", "help"])
    assert cli.main() == 0
    assert "ocf new function" in capsys.readouterr().out

    def interrupted():
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli.audio_mod, "check_engine", interrupted)
    assert cli.main(["audio", "check-engine"]) == 130
    assert "interrupted" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv,target",
    [
        (["new", "function"], "run_function_wizard"),
        (["new", "proposal"], "run_proposal_wizard"),
        (["new", "audio"], "run_audio_wizard"),
        (["new", "background"], "run_background_wizard"),
        (["new", "test-report"], "run_test_report_wizard"),
        (["import", "source"], "run_import_source"),
    ],
)
def test_wizard_dispatch_never_performs_authoring_in_unit_tests(monkeypatch, argv, target):
    calls = []
    monkeypatch.setattr(cli, target, lambda: calls.append(target))
    assert cli.main(argv) == 0 and calls == [target]


@pytest.mark.parametrize(
    "argv",
    [["new"], ["audio"], ["voice"], ["session"], ["import"], ["review"], ["edit"], ["corpus"]],
)
def test_incomplete_groups_keep_documented_help_behavior(argv, capsys):
    assert cli.main(argv) == 0
    assert "ocf new function" in capsys.readouterr().out


def test_edit_validate_and_index_dispatch(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(cli, "run_edit_function", lambda query: seen.append(query))
    assert cli.main(["edit", "function", "fixture"]) == 0
    assert cli.main(["edit", "function"]) == 0
    assert seen == ["fixture", None]
    marker = object()
    monkeypatch.setattr(cli, "validate_all", lambda: marker)
    monkeypatch.setattr(cli, "validate_function_file", lambda path: seen.append(path) or marker)
    monkeypatch.setattr(cli, "print_result", lambda result: 7 if result is marker else 0)
    assert cli.main(["validate"]) == cli.main(["validate", "--all"]) == 7
    assert cli.main(["validate", "fixture.yaml"]) == 7 and seen[-1] == Path("fixture.yaml")
    monkeypatch.setattr(generators, "indexes_are_fresh", lambda: True)
    assert cli.main(["build-index", "--check"]) == 0
    monkeypatch.setattr(generators, "indexes_are_fresh", lambda: False)
    assert cli.main(["build-index", "--check"]) == 1
    monkeypatch.setattr(generators, "refresh_indexes", lambda: seen.append("refresh"))
    assert cli.main(["build-index"]) == 0 and seen[-1] == "refresh"
    assert "STALE" in capsys.readouterr().out


def test_plan_success_and_structured_error_translation(monkeypatch, capsys):
    document = {"template": "fixture"}
    monkeypatch.setattr(indexes, "load_yaml_file", lambda path: document)
    calls = []
    monkeypatch.setattr(
        planning,
        "plan",
        lambda d, root: (
            calls.append((d, root))
            or {"template_id": "fixture", "locale": "fr", "content_status": "draft"}
        ),
    )
    assert cli.main(["plan", "request.yaml"]) == 0
    assert "Valid dry-run plan" in capsys.readouterr().out
    assert calls[0] == (document, Path("request.yaml").resolve().parent)
    assert cli.main(["plan", "request.yaml", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["locale"] == "fr"

    def invalid(*args):
        raise OCFError("invalid fixture")

    monkeypatch.setattr(planning, "plan", invalid)
    assert cli.main(["plan", "request.yaml", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["errors"] == ["invalid fixture"]
    assert cli.main(["plan", "request.yaml"]) == 1
    assert "invalid fixture" in capsys.readouterr().err


@pytest.mark.parametrize(
    "rich,json_output,describe",
    [(r, j, d) for r in (False, True) for j in (False, True) for d in (False, True)],
)
def test_function_listing_output_contract_and_identity(
    monkeypatch, capsys, rich, json_output, describe
):
    raw = {
        "id": "OCF-FND-999",
        "canonical": {"name": "Café", "command": {"primary": "PLUS-FOCUS"}},
        "purpose": {"summary": "Fixture"},
    }
    record = NS(data=raw)
    detailed = {
        "function_id": raw["id"],
        "title": "Café",
        "activation": {"primary": "PLUS-FOCUS"},
        "extraction_status": "complete",
        "human_review": "required",
    }
    monkeypatch.setattr(cli, "load_all_functions", lambda: [record])
    monkeypatch.setattr(indexes, "load_function_by_slug_or_id", lambda q: record)
    monkeypatch.setattr(content, "discover", lambda r: detailed)
    argv = ["functions", "describe", raw["id"]] if describe else ["functions", "list"]
    argv += (["--rich"] if rich else []) + (["--json"] if json_output else [])
    assert cli.main(argv) == 0
    text = capsys.readouterr().out
    if json_output:
        assert json.loads(text)["functions"] == [detailed if rich else raw]
    else:
        assert "Café" in text and "PLUS-FOCUS" in text
    monkeypatch.setattr(indexes, "load_function_by_slug_or_id", lambda q: None)
    assert cli.main(["functions", "describe", "unknown"]) == 1


def test_corpus_output_schema_and_reference_write_boundaries(monkeypatch, tmp_path, capsys):
    data = {"fixture": True}
    monkeypatch.setattr(corpus, "inventory", lambda root: data)
    monkeypatch.setattr(corpus, "markdown", lambda doc: "Fixture markdown\n")
    monkeypatch.setattr(validators, "_load_schema", lambda name: {})
    monkeypatch.setattr(validators, "validate_against_schema", lambda doc, schema: [])
    writes = []
    monkeypatch.setattr(utils, "write_text_atomic", lambda *a, **kw: writes.append(a))
    root = tmp_path / "references"
    assert cli.main(["corpus", "inventory", "--root", str(root)]) == 0
    assert json.loads(capsys.readouterr().out) == data
    output = tmp_path / "report.md"
    assert (
        cli.main(
            ["corpus", "inventory", "--root", str(root), "--format", "md", "--output", str(output)]
        )
        == 0
    )
    assert writes == [(output, "Fixture markdown\n")]
    assert (
        cli.main(["corpus", "inventory", "--root", str(root), "--output", str(root / "bad.json")])
        == 1
    )
    assert "read-only" in capsys.readouterr().err
    monkeypatch.setattr(validators, "validate_against_schema", lambda doc, schema: ["invalid"])
    assert cli.main(["corpus", "inventory", "--root", str(root)]) == 1


@pytest.mark.parametrize(
    "kind,symbol", [("check-engine", "check_engine"), ("list-background", "list_background")]
)
def test_audio_status_dispatch_returns_callee_exit_code(monkeypatch, kind, symbol):
    monkeypatch.setattr(cli.audio_mod, symbol, lambda: 9)
    assert cli.main(["audio", kind]) == 9


def test_background_mix_inspect_and_state_renderer_forwarding(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli.audio_mod, "describe_background", lambda *a: calls.append(a) or 8)
    assert cli.main(["audio", "describe-background", "preset", "--engine", "sbagenx"]) == 8
    assert calls[-1] == ("preset", "sbagenx")
    monkeypatch.setattr(cli.audio_mod, "render_background", lambda *a: calls.append(a) or 7)
    assert (
        cli.main(
            ["audio", "render-background", "preset", "--output", "bed.wav", "--engine", "sbagenx"]
        )
        == 7
    )
    assert calls[-1] == ("preset", "bed.wav", "sbagenx")
    monkeypatch.setattr(audio_build, "mix", lambda *a, **kw: calls.append((a, kw)))
    assert (
        cli.main(
            [
                "audio",
                "mix",
                "--speech",
                "speech.wav",
                "--output",
                "out.wav",
                "--background",
                "bed.wav",
                "--background-gain",
                ".1",
                "--force",
            ]
        )
        == 0
    )
    assert calls[-1] == (
        ("speech.wav", "bed.wav", "out.wav"),
        {"background_gain": 0.1, "overwrite": True},
    )
    monkeypatch.setattr(audio_build, "inspect", lambda file: {"inspected": file})
    assert cli.main(["audio", "inspect", "out.wav"]) == 0
    assert "inspected: out.wav" in capsys.readouterr().out
    monkeypatch.setattr(semantic_dsp, "run_render_program", lambda args: calls.append(args) or 6)
    assert (
        cli.main(
            [
                "audio",
                "render-state-program",
                "semantic.yaml",
                "--render-manifest",
                "ledger.yaml",
                "--dsp-profile",
                "profile",
                "--output",
                "bed.wav",
            ]
        )
        == 6
    )
    assert calls[-1].dsp_profile == "profile" and calls[-1].render_manifest == "ledger.yaml"


@pytest.mark.parametrize("group", ["audio", "voice"])
def test_speech_cli_forwards_locale_recordings_and_explicit_output(monkeypatch, group):
    calls = []
    monkeypatch.setattr(audio_build, "default_narration_output", lambda path: "default.wav")
    monkeypatch.setattr(cli.voice_mod, "render_script", lambda *a, **kw: calls.append((a, kw)) or 4)
    kind = "render-speech" if group == "audio" else "render"
    assert cli.main([group, kind, "source.yaml"]) == 4
    assert calls[-1][0] == ("source.yaml", "default.wav") and calls[-1][1]["strict"] is True
    argv = [
        group,
        kind,
        "source.yaml",
        "--output",
        "chosen.wav",
        "--voice",
        "profile",
        "--recordings",
        "recordings.yaml",
        "--locale",
        "fr",
        "--allow-fallback",
        "--rate",
        "22050",
        "--force",
    ]
    if group == "voice":
        argv += ["--fit", "--flow", "--even-counts"]
    assert cli.main(argv) == 4
    positional, kw = calls[-1]
    assert positional == ("source.yaml", "chosen.wav")
    assert kw["backend"] == "profile" and kw["sample_rate"] == 22050
    assert kw["recordings"] == "recordings.yaml" and kw["locale"] == "fr" and kw["strict"] is False
    assert kw["force"] is True
    if group == "voice":
        assert kw["fit"] and kw["flow"] and kw["even_counts"]


@pytest.mark.parametrize(
    "formats,expected",
    [
        ([], ["wav", "flac", "mp3"]),
        (["--format", "wav"], ["wav"]),
        (["--format", "flac", "--format", "mp3"], ["flac", "mp3"]),
    ],
)
def test_build_explicit_formats_override_defaults_and_tags_preserve_equals(
    monkeypatch, formats, expected
):
    calls = []
    monkeypatch.setattr(audio_build, "build", lambda *a, **kw: calls.append((a, kw)))
    argv = [
        "audio",
        "build",
        "manifest",
        *formats,
        "--tag",
        "comment=a=b",
        "--voice",
        "profile",
        "--locale",
        "fr",
        "--allow-fallback",
        "--recordings",
        "recordings.yaml",
        "--dsp-profile",
        "dsp",
        "--fit",
        "--flow",
        "--even-counts",
    ]
    assert cli.main(argv) == 0
    assert calls[-1][1]["formats"] == expected
    assert calls[-1][1]["tag_overrides"] == {"comment": "a=b"}
    assert calls[-1][1]["locale"] == "fr" and calls[-1][1]["strict"] is False
    assert calls[-1][1]["dsp_profile"] == "dsp" and calls[-1][1]["fit"]
    assert cli.main(["audio", "build", "manifest", "--tag", "invalid"]) == 1


@pytest.mark.parametrize(
    "kind,symbol",
    [
        ("list-backends", "list_backends_cmd"),
        ("doctor", "voice_doctor"),
        ("list", "list_profiles_cmd"),
    ],
)
def test_voice_status_routes(monkeypatch, kind, symbol):
    monkeypatch.setattr(cli.voice_mod, symbol, lambda: 5)
    assert cli.main(["voice", kind]) == 5


def test_voice_registry_output_and_no_downloads(monkeypatch, capsys):
    monkeypatch.setattr(voice_registry, "load_registry", lambda: [])
    assert cli.main(["voice", "packs"]) == 0
    assert "No community" in capsys.readouterr().out
    entries = [{"id": "fixture", "display_name": "Café", "install_status": "metadata-only"}]
    monkeypatch.setattr(voice_registry, "load_registry", lambda: entries)
    assert cli.main(["voice", "packs", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["voices"] == entries
    assert cli.main(["voice", "packs"]) == 0
    assert "metadata-only" in capsys.readouterr().out


def test_recording_import_json_errors_and_forwarding(monkeypatch, tmp_path, capsys):
    mapping = tmp_path / "map.json"
    argv = [
        "voice",
        "import-recordings",
        "semantic.yaml",
        "--directory",
        "inputs",
        "--mapping",
        str(mapping),
        "--locale",
        "fr",
        "--author",
        "Editor",
        "--license",
        "unknown",
        "--speaker",
        "Speaker",
        "--output",
        "package.yaml",
    ]
    calls = []
    monkeypatch.setattr(transcript, "load_timed_doc", lambda path: {"id": "session"})
    monkeypatch.setattr(
        recordings,
        "import_directory",
        lambda *a, **kw: calls.append((a, kw)) or {"recordings": ["one"]},
    )
    assert cli.main(argv) == 1
    mapping.write_text("{broken")
    assert cli.main(argv) == 1 and "invalid recording mapping JSON" in capsys.readouterr().err
    mapping.write_text('{"a":"one.wav","a":"two.wav"}')
    assert cli.main(argv) == 1 and not calls
    mapping.write_text('{"a":"one.wav"}')
    assert cli.main(argv) == 0
    assert calls[-1] == (
        ({"id": "session"}, Path("inputs"), {"a": "one.wav"}, Path("package.yaml")),
        {"locale": "fr", "author": "Editor", "license": "unknown", "speaker": "Speaker"},
    )


def test_session_transcript_editorial_and_locale_dispatch_are_boundaries(monkeypatch):
    calls = []
    monkeypatch.setattr(session, "run_list_templates", lambda: 8)
    monkeypatch.setattr(session, "run_compose", lambda args: calls.append(args) or 7)
    monkeypatch.setattr(transcript, "run_transcript", lambda args: calls.append(args) or 6)
    monkeypatch.setattr(editorial, "run", lambda args: calls.append(args) or 5)
    assert cli.main(["session", "list-templates"]) == 8
    assert cli.main(["session", "compose", "--template", "fixture", "--locale", "fr"]) == 7
    assert calls[-1].template == "fixture"
    assert cli.main(["transcript", "analyze", "file.yaml"]) == 6
    assert cli.main(["content", "diff", "OCF-FND-999"]) == 5
    for kind, name, tail in [
        ("list", "cmd_locale_list", []),
        ("coverage", "cmd_locale_coverage", []),
        ("validate", "cmd_locale_validate", []),
        ("resolve", "cmd_locale_resolve", ["--locale", "fr"]),
        ("pseudo", "cmd_locale_pseudo", []),
    ]:
        monkeypatch.setattr(cli, name, lambda *a: 9)
        assert cli.main(["locale", kind, *tail]) == 9
    assert cli.main(["locale"]) == 9


def test_doctor_text_json_and_status_are_derived_from_diagnostics(monkeypatch, capsys):
    health = {
        "ok": False,
        "workflow": "core",
        "checks": [
            {"status": "missing", "id": "python", "requirement": "core", "detail": "fixture"}
        ],
    }
    monkeypatch.setattr(diagnostics, "diagnose", lambda workflow: health)
    assert cli.main(["doctor"]) == 1 and "python" in capsys.readouterr().out
    assert cli.main(["doctor", "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == health


class Catalog:
    canonical_locale = "en-US"

    def __init__(self, root):
        self.root, self.problems = root, []

    def resource(self, key, target):
        entry = NS(
            variables={
                "locale",
                "covered",
                "total",
                "percent",
                "path",
                "keys",
                "source",
                "version",
                "count",
            }
        )
        entry.render = lambda values, **kw: key + " " + json.dumps(values, ensure_ascii=False)
        return entry, None

    def plural_rules_for(self, target):
        return {}

    def locales(self):
        return ["en-US", "fr"]

    def require(self, tag):
        return NS(
            path=self.root / tag,
            locale=tag,
            semantic_version="1.0.0",
            direction="ltr",
            translation={"source_locale": "en-US", "translator": "Editor"} if tag == "fr" else {},
            describe=lambda: tag,
        )

    def coverage(self, tag, domain=None):
        return {"covered": 1, "total": 2, "percent": 50}

    def missing_keys(self, tag, domain=None):
        return ["missing.key"]

    def spoken_chain(self, wanted):
        if wanted == "unknown":
            raise locale.LocalizationError("pack unavailable")
        return [wanted]


def test_locale_operator_messages_filter_variables_and_keep_fallback(monkeypatch, tmp_path, capsys):
    catalog = Catalog(tmp_path)
    monkeypatch.setattr(cli, "_locale_catalog", lambda: catalog)
    assert cli.cmd_locale_list() == 0
    assert "translator Editor" in capsys.readouterr().out
    catalog.problems = ["fixture failure"]
    assert cli.cmd_locale_list() == 1 and "fixture failure" in capsys.readouterr().out
    assert "ignored" not in cli._locale_ui(catalog, "fixture", locale="fr", ignored="extra")
    assert cli.cmd_locale_coverage(NS(locale=None, domain=None)) == 0
    assert "missing.key" in capsys.readouterr().out
    assert cli.cmd_locale_coverage(NS(locale="fr", domain="narration")) == 0
    assert "locale.coverage.narration" in capsys.readouterr().out

    def missing(*args):
        raise locale.LocalizationError("missing UI resource")

    monkeypatch.setattr(catalog, "resource", missing)
    assert cli._locale_ui(catalog, "missing", count=2) == "count=2"


def test_locale_validation_selected_pack_excludes_prefix_lookalikes(monkeypatch, tmp_path, capsys):
    catalog = Catalog(tmp_path)
    monkeypatch.setattr(cli, "_locale_catalog", lambda: catalog)
    full = validators.ValidationResult()
    full.add("info", "locale-count", "fixture count")
    full.add("warning", "selected", "fr warning", str(tmp_path / "fr/narration.yaml"))
    full.add("error", "other", "fr-CA issue", str(tmp_path / "fr-CA/narration.yaml"))
    monkeypatch.setattr(validators, "validate_locale_packs", lambda cat: full)
    assert cli.cmd_locale_validate(NS(locale="fr", file=None, json=True)) == 0
    assert {item["code"] for item in json.loads(capsys.readouterr().out)["issues"]} == {
        "locale-count",
        "selected",
    }
    assert cli.cmd_locale_validate(NS(locale="unknown", file=None, json=True)) == 1
    assert json.loads(capsys.readouterr().out)["issues"][0]["code"] == "locale-unavailable"
    monkeypatch.setattr(indexes, "load_yaml_file", lambda path: {"id": "document"})
    monkeypatch.setattr(
        validators, "validate_narration_usage", lambda *a: validators.ValidationResult()
    )
    monkeypatch.setattr(
        validators, "validate_narration_hygiene", lambda *a: validators.ValidationResult()
    )
    monkeypatch.setattr(locale, "resolve_document", lambda doc, *a, **kw: doc)
    assert cli.cmd_locale_validate(NS(locale=None, file="source.yaml", json=True)) == 1
    capsys.readouterr()

    def missing(*a, **kw):
        raise locale.LocalizationError("missing spoken words")

    monkeypatch.setattr(locale, "resolve_document", missing)
    assert cli.cmd_locale_validate(NS(locale="fr", file="source.yaml", json=True)) == 1
    assert "narration-strict-missing" in {
        item["code"] for item in json.loads(capsys.readouterr().out)["issues"]
    }
    monkeypatch.setattr(cli, "print_result", lambda result: 0)
    assert cli.cmd_locale_validate(NS(locale="fr", file=None, json=False)) == 0


def test_locale_resolution_file_template_output_and_invalid_combinations(
    monkeypatch, tmp_path, capsys
):
    catalog = Catalog(tmp_path)
    monkeypatch.setattr(cli, "_locale_catalog", lambda: catalog)
    monkeypatch.setattr(indexes, "load_yaml_file", lambda path: {"kind": "file"})
    monkeypatch.setattr(session, "load_template", lambda name: {"id": "fixture", "name": "Fixture"})
    composed = []
    monkeypatch.setattr(
        session, "compose", lambda *a, **kw: composed.append(kw) or {"kind": "template"}
    )
    resolved = []
    monkeypatch.setattr(
        locale,
        "resolve_document",
        lambda doc, target, **kw: resolved.append((doc, target, kw)) or doc,
    )
    writes = []
    monkeypatch.setattr(utils, "write_text_atomic", lambda *a, **kw: writes.append((a, kw)))
    common = dict(file=None, session=None, locale="fr", no_strict=False, output=None, force=False)
    for overrides, match in [({}, "pass --file"), ({"file": "a", "session": "b"}, "not both")]:
        with pytest.raises(OCFError, match=match):
            cli.cmd_locale_resolve(NS(**{**common, **overrides}))
    assert cli.cmd_locale_resolve(NS(**{**common, "file": "source.yaml"})) == 0
    assert "kind: file" in capsys.readouterr().out and resolved[-1][2]["strict"] is True
    assert (
        cli.cmd_locale_resolve(
            NS(
                **{
                    **common,
                    "session": "fixture",
                    "output": "new.yaml",
                    "force": True,
                    "no_strict": True,
                }
            )
        )
        == 0
    )
    assert composed[-1]["document_id"] == "fixture-fr"
    assert writes[-1][1] == {"overwrite": True} and resolved[-1][2]["strict"] is False


def test_pseudo_locale_serialization_uses_pack_metadata_not_engine_calls(
    monkeypatch, tmp_path, capsys
):
    catalog = Catalog(tmp_path)
    monkeypatch.setattr(cli, "_locale_catalog", lambda: catalog)

    def entry(file, domain, text):
        return NS(
            file=file,
            domain=domain,
            text=text,
            variables={"count"},
            status="draft",
            version="1.0.0",
            pronunciation={},
            requires_events=[],
            required_pronunciation=[],
        )

    pack = NS(
        locale="en-XA",
        manifest={"locale": "en-XA"},
        entries={
            "narration.fixture": entry("narration.yaml", "narration", "Café"),
            "ui.fixture": entry("ui.yaml", "ui", "Label"),
            "inline.fixture": entry("", "narration", "No file"),
        },
        keys=lambda domain: ["narration.fixture"],
    )
    monkeypatch.setattr(locale, "build_pseudo_pack", lambda *a, **kw: pack)
    assert cli.cmd_locale_pseudo(NS(source_locale=None, locale=None, output=None)) == 0
    assert "Café" in capsys.readouterr().out
    target = tmp_path / "pseudo"
    assert cli.cmd_locale_pseudo(NS(source_locale="en-US", locale="en-XA", output=str(target))) == 0
    import yaml

    assert (
        yaml.safe_load((target / "narration.yaml").read_text(encoding="utf-8"))["entries"]["narration.fixture"][
            "text"
        ]
        == "Café"
    )
    assert yaml.safe_load((target / "ui.yaml").read_text(encoding="utf-8"))["domain"] == "ui"


def test_review_commands_and_capabilities_delegate_to_injected_data(monkeypatch, tmp_path, capsys):
    from ocf_tools import paths

    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(generators, "command_review_markdown", lambda: "Generated fixture")
    writes = []
    monkeypatch.setattr(utils, "write_text_atomic", lambda *a: writes.append(a))
    assert cli.main(["review", "commands"]) == 0
    assert writes == [(tmp_path / "docs/COMMAND_REVIEW.md", "Generated fixture")]
    monkeypatch.setattr(cli, "SCHEMAS_DIR", tmp_path)
    assert cli.main(["capabilities"]) == 0
    assert "ocf content diff" in capsys.readouterr().out
    assert cli.main(["capabilities", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["schemas"] == []
    catalog = Catalog(tmp_path)
    monkeypatch.setattr(locale, "LocaleCatalog", lambda: catalog)
    assert cli._locale_catalog() is catalog


def test_module_entrypoint_isolated_in_process(monkeypatch, capsys):
    import runpy

    monkeypatch.setattr(cli.sys, "argv", ["ocf_tools.cli", "help"])
    with pytest.warns(RuntimeWarning, match="found in sys.modules"):
        with pytest.raises(SystemExit) as exit_status:
            runpy.run_module("ocf_tools.cli", run_name="__main__")
    assert exit_status.value.code == 0
    assert "ocf new function" in capsys.readouterr().out


def test_unknown_locale_kind_cannot_fall_through_to_pseudo(monkeypatch):
    monkeypatch.setattr(
        cli, "cmd_locale_pseudo", lambda args: pytest.fail("unknown command must be rejected")
    )
    assert cli.main(["locale", "unknown-kind"]) == 2
