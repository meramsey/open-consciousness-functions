import json

import pytest
from ocf_tools import agent_api as api
from ocf_tools import cli, dev_jobs
from ocf_tools.utils import OCFError, _parsed_yaml, yaml_safe_load


def test_compact_lookup_fields_changed_only_and_cli_parity(capsys):
    summary = api.get_function("OCF-FND-002", fields=["commands", "human_review"])
    assert summary["data"]["commands"]["primary"] == "PLUS-FOCUS"
    assert len(json.dumps(summary)) < 1000
    assert (
        api.get_function("OCF-FND-002", ["commands", "human_review"], summary["sha256"])["status"]
        == "unchanged"
    )
    assert (
        cli.main(
            [
                "dev",
                "ocf_get_function",
                "--arguments",
                '{"function_id":"OCF-FND-002","fields":["commands","human_review"]}',
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == summary
    assert api.get_function("../../secret")["status"] == "failed"
    assert api.get_schema("../function.schema.json")["status"] == "failed"


def test_compact_lookup_exposes_lifecycle_scopes_and_resolved_command_effects():
    data = api.get_function("OCF-COG-004", fields=["purpose", "lifecycle", "command_metadata"])[
        "data"
    ]
    assert data["lifecycle"]["persistence"] == "permanent"
    assert data["lifecycle"]["scopes"]["baseline"]["persistence"] == "permanent"
    commands = {row["id"]: row for row in data["command_metadata"]}
    imprint = commands["OCF-CMD-COG-004-PRIMARY"]
    recall = commands["OCF-CMD-COG-004-RECALL"]
    assert imprint["effect_scope"] == "permanent"
    assert imprint["invocation_scope"]["persistence"] == "temporary"
    assert recall["effect_scope"] == "temporary"
    assert recall["invocation_scope"]["activation"] == "manual"


def test_pagination_schema_summary_and_workflow_commands():
    first = api.list_functions(limit=2)
    second = api.list_functions(offset=2, limit=2)
    assert first["total"] == 58 and first["next_offset"] == 2
    assert not set(r["id"] for r in first["items"]) & set(r["id"] for r in second["items"])
    assert api.list_functions(limit=500)["status"] == "failed"
    assert "canonical" in api.get_schema("function.schema.json")["fields"]
    workflows = json.loads((api.REPO_ROOT / "docs/workflows.json").read_text())["workflows"]
    import shlex

    for row in workflows.values():
        assert (api.REPO_ROOT / row["guide"]).is_file()
        for command in row["commands"]:
            try:
                cli._build_parser().parse_args(shlex.split(command))
            except SystemExit as exc:
                assert exc.code == 0


@pytest.mark.unit
def test_plan_audio_diagnoses_explicit_background_profile_not_voice_default(monkeypatch, tmp_path):
    from ocf_tools import audio_build, complete_session, diagnostics

    work = tmp_path / "work"
    work.mkdir()
    profile_path = work / "ref-profile.yaml"
    profile_path.write_text("fixture")
    monkeypatch.setenv("OCF_WORK_DIR", str(work))
    selected_profiles = []
    workflows = []

    def render(function_id, *, voice, dsp_profile, **_kwargs):
        selected_profiles.append(dsp_profile)
        return {
            "session_plan": {
                "voice": {
                    "id": voice,
                    "backend": "piper" if "PIPER" in voice else "chatterbox-nano",
                },
                "stages": [{"id": "one"}],
                "tts_plan": {"estimated_duration_seconds": 3},
                "resolved_dsp_profile": {
                    "id": "REFERENCE-F10-F11-V4",
                    "states": {"focus-10": {"mode": "preset", "preset": "reference"}},
                },
            }
        }

    monkeypatch.setattr(complete_session, "render_complete_session", render)
    monkeypatch.setattr(
        audio_build, "_resolve_background_manifest", lambda _preset: {"engine": "reference-master"}
    )
    monkeypatch.setattr(
        diagnostics,
        "diagnose",
        lambda workflow: workflows.append(workflow) or {"ok": True, "failures": [], "checks": []},
    )
    first = api.plan_audio("OCF-SEN-001", "OCF-VOICE-PIPER", dsp_profile="ref-profile.yaml")
    second = api.plan_audio("OCF-SEN-001", "OCF-VOICE-CLONE", dsp_profile="ref-profile.yaml")
    assert first["status"] == second["status"] == "ready"
    assert first["resolved_dsp_profile"] == second["resolved_dsp_profile"] == "REFERENCE-F10-F11-V4"
    assert first["background_engines"] == second["background_engines"] == ["reference-master"]
    assert selected_profiles == [str(profile_path.resolve())] * 2
    assert workflows == ["encode", "encode"]


@pytest.mark.unit
def test_plan_audio_keeps_standard_farfield_requirement(monkeypatch):
    from ocf_tools import audio_build, complete_session, diagnostics

    monkeypatch.setattr(
        complete_session,
        "render_complete_session",
        lambda *_args, **_kwargs: {
            "session_plan": {
                "voice": {"id": "OCF-VOICE-9100", "backend": "chatterbox-nano"},
                "stages": [],
                "tts_plan": {"estimated_duration_seconds": 1},
                "resolved_dsp_profile": {
                    "id": "OCF-DSP-HPLUS-LOCKED-003",
                    "states": {"focus-10": {"mode": "preset", "preset": "hplus"}},
                },
            }
        },
    )
    monkeypatch.setattr(
        audio_build, "_resolve_background_manifest", lambda _preset: {"engine": "farfield"}
    )
    monkeypatch.setattr(
        diagnostics,
        "diagnose",
        lambda workflow: {"ok": False, "failures": ["farfield"], "checks": []},
    )
    result = api.plan_audio("OCF-SEN-001", "OCF-VOICE-9100")
    assert result["status"] == "blocked"
    assert result["missing_dependencies"] == ["farfield"]
    assert result["background_engines"] == ["farfield"]


def test_targeted_validation_and_source_plan_summary():
    validation = api.validate_function("OCF-FND-002", limit=1)
    assert validation["errors"] == 0
    assert validation["diagnostics"]["limit"] == 1
    summary = api.get_session_plan("OCF-SLP-005", stages=True)
    assert summary["timing"]["body_repetitions"] == {"programming": 2, "sleep": 2}
    assert not summary["approval"]["release_ready"]
    assert "spoken_text" not in json.dumps(summary)
    assert api.select_tests(["schemas/function.schema.json"])["full_suite_required"]
    assert api.select_tests(["scripts/ocf_tools/speech_cache.py"])["tests"] == [
        "tests/test_bulk_render.py"
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "value", ["../secret", "/etc/passwd", "C:/private/file", "C:\\private\\file", "\\\\host\\file"]
)
def test_path_boundaries(value, tmp_path):
    with pytest.raises(OCFError):
        api.safe_path(value, tmp_path, exists=False)


@pytest.mark.unit
def test_typed_dispatch_and_job_allowlist():
    with pytest.raises(OCFError):
        api.dispatch("ocf_run_tests", {"full": "false"})
    for request in (
        {"paths": ["--pyargs=malicious"], "full": False},
        {"paths": ["tests/../setup.py"], "full": False},
        {"paths": [], "full": True, "workers": 50},
    ):
        with pytest.raises(OCFError):
            dev_jobs.validate_request("tests", request)
    with pytest.raises(OCFError):
        dev_jobs.validate_request("shell", {"command": "echo bad"})


@pytest.mark.unit
def test_content_cache_invalidates_without_mtime_assumptions_and_is_bounded(tmp_path):
    path = tmp_path / "data.yaml"
    _parsed_yaml.cache_clear()
    path.write_text("key: [one]\n")
    first = yaml_safe_load(path.read_text())
    first["key"].append("changed")
    assert yaml_safe_load(path.read_text()) == {"key": ["one"]}
    assert _parsed_yaml.cache_info().hits == 1
    path.write_text("key: [two]\n")
    assert yaml_safe_load(path.read_text()) == {"key": ["two"]}
    for i in range(140):
        yaml_safe_load(f"index: {i}")
    assert _parsed_yaml.cache_info().currsize == 128


@pytest.mark.unit
def test_referenced_schema_cache_invalidates_by_content(monkeypatch, tmp_path):
    from ocf_tools import validators

    monkeypatch.setattr(validators, "schema_path", lambda name: tmp_path / name)
    target = tmp_path / "target.schema.json"
    target.write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "https://fixture/target",
                "type": "integer",
            }
        )
    )
    reference = {"$ref": "https://fixture/target"}
    assert validators.validate_against_schema(3, reference) == []
    target.write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": "https://fixture/target",
                "type": "string",
            }
        )
    )
    assert validators.validate_against_schema(3, reference)


@pytest.mark.unit
def test_schema_absence_does_not_require_mcp(monkeypatch):
    import builtins

    from ocf_tools.mcp_server import create_server

    original = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "mcp.server.fastmcp":
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    with pytest.raises(RuntimeError, match="Optional MCP dependency"):
        create_server()


@pytest.mark.unit
def test_symlink_escape_and_cache_cleanup_protect_unowned_data(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    from ocf_tools.paths import work_path

    unowned = work_path("cache", "tts", "user-data")
    unowned.mkdir(parents=True)
    (unowned / "manifest.json").write_text("{}")
    assert api.cache_clean(0, dry_run=False, confirmed=True)["selected_count"] == 0
    assert unowned.exists()
    assert api.cache_clean(0, dry_run=False)["status"] == "failed"


def test_voice_capability_cli_parity_and_dynamic_discovery(capsys):
    summary = api.inspect_voice_capabilities()
    assert cli.main(["dev", "ocf_inspect_voice_capabilities"]) == 0
    assert json.loads(capsys.readouterr().out) == summary
    assert api.project_overview()["operations"] == sorted(api.TOOLS)
    assert {"ocf_inspect_narration_sources", "ocf_inspect_voice_capabilities"} <= api.READ_ONLY
    assert not {"ocf_validate_recordings", "ocf_start_narration_render"} & api.READ_ONLY
    for name, args in (
        ("ocf_inspect_voice_capabilities", {"probe_gpu": "true"}),
        ("ocf_plan_voice_training", {"dataset": 123}),
        ("ocf_validate_recordings", {"function_id": "OCF-FND-002", "manifest": []}),
        (
            "ocf_start_narration_render",
            {"function_id": "OCF-FND-002", "manifest": "a.json", "voice": False},
        ),
    ):
        with pytest.raises(OCFError, match="invalid argument type"):
            api.dispatch(name, args)
