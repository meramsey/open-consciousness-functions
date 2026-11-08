"""CLI entry-point, help, doctor, and validation routing tests."""

from __future__ import annotations

import subprocess
import sys

from conftest import REPO_ROOT


def test_no_args_prints_help(capsys):
    from ocf_tools.cli import main

    assert main([]) == 0
    assert "ocf new function" in capsys.readouterr().out


def test_help_command(capsys):
    from ocf_tools.cli import main

    assert main(["help"]) == 0
    out = capsys.readouterr().out
    assert "ocf audio check-engine" in out
    assert "ocf build-index" in out


def test_doctor_reports_environment(capsys):
    from ocf_tools.cli import main

    code = main(["doctor"])
    out = capsys.readouterr().out
    assert "core/workflow health" in out
    assert "farfield (optional)" in out
    import sys

    assert code == (0 if sys.version_info >= (3, 11) else 1)


def test_validate_all_returns_success(capsys):
    from ocf_tools.cli import main

    assert main(["validate", "--all"]) == 0
    out = capsys.readouterr().out
    assert "0 errors" in out


def test_validate_single_file(sample_function_path, capsys):
    from ocf_tools.cli import main

    assert main(["validate", str(sample_function_path)]) == 0
    assert "0 errors" in capsys.readouterr().out


def test_build_index_check_fresh(capsys):
    from ocf_tools.cli import main

    assert main(["build-index", "--check"]) == 0
    assert "fresh" in capsys.readouterr().out


def test_review_commands_does_not_crash(capsys):
    from ocf_tools.cli import main

    assert main(["review", "commands"]) == 0
    assert "Command review report" in capsys.readouterr().out


def test_unknown_audio_subcommand_prints_help(capsys):
    from ocf_tools.cli import main

    assert main(["audio", "bogus"]) == 2
    assert "ocf new function" in capsys.readouterr().out


def test_functions_list_uses_canonical_registry_and_json_projection(capsys):
    import json

    from ocf_tools.cli import main

    assert main(["functions", "list", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["schema_version"] == "1.0"
    assert len(result["functions"]) == 58
    assert all("canonical" in row and "function_id" not in row for row in result["functions"])


def test_functions_list_search_is_localized_and_rich_projection_is_explicit(capsys):
    import json

    from ocf_tools.cli import main

    assert main(["functions", "list", "--json", "--rich", "--search", "Focus"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["functions"]
    assert all("function_id" in row and "extraction_status" in row for row in result["functions"])


def test_cli_describe_preview_lookup_and_command_list_use_canonical_resources(capsys):
    import json

    from ocf_tools.cli import main

    assert main(["functions", "describe", "OCF-FND-004", "--json"]) == 0
    described = json.loads(capsys.readouterr().out)["functions"][0]
    assert described["id"] == "OCF-FND-004"
    assert described["canonical"]["name"] == "Relax"

    assert main(["functions", "preview", "OCF-FND-004"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["function_id"] == "OCF-FND-004" and not preview["synthesis"]

    assert main(["functions", "lookup", "Relax", "--json"]) == 0
    lookup = json.loads(capsys.readouterr().out)
    assert lookup["activation_selected"] is False
    assert any(row["function_id"] == "OCF-FND-004" for row in lookup["matches"])

    assert main(["commands", "list", "--json"]) == 0
    commands = json.loads(capsys.readouterr().out)
    assert {row["function_id"] for row in commands["functions"]} >= {"OCF-FND-004"}


def test_cli_dev_defaults_eligibility_and_workspace_status_routes(capsys, tmp_path):
    import json

    from ocf_tools.cli import main

    assert (
        main(
            [
                "dev",
                "ocf_get_function",
                "--arguments",
                '{"function_id":"OCF-FND-004","fields":["lifecycle","provenance"]}',
            ]
        )
        == 0
    )
    function = json.loads(capsys.readouterr().out)
    assert function["data"]["id"] == "OCF-FND-004"

    assert main(["audio", "defaults"]) == 0
    defaults = json.loads(capsys.readouterr().out)
    assert defaults["id"] == "OCF-AUDIO-DEFAULTS-HPLUS-016"
    assert defaults["human_listening_approval"] is None

    eligibility_path = tmp_path / "eligibility.json"
    assert (
        main(
            [
                "audio",
                "eligibility",
                "OCF-FND-004",
                "--locale",
                "en-US",
                "--output",
                str(eligibility_path),
            ]
        )
        == 0
    )
    report = json.loads(eligibility_path.read_text(encoding="utf-8"))
    capsys.readouterr()
    assert report["function_id"] == "OCF-FND-004"
    assert report["release_ready"] is False

    assert main(["workspace", "status", "--json"]) == 0
    workspace = json.loads(capsys.readouterr().out)
    assert workspace["checkout"]


def test_cli_bad_dev_json_and_clean_docs_inventory_fail_or_pass_explicitly(capsys):
    from ocf_tools.cli import main

    assert main(["dev", "ocf_get_function", "--arguments", "not-json"]) == 1
    assert "valid JSON" in capsys.readouterr().err
    assert main(["docs-inventory", "--check"]) == 0
    assert '"fresh": true' in capsys.readouterr().out


def test_cli_audio_defaults_plan_and_eligibility_are_read_only(capsys, tmp_path):
    import json

    from ocf_tools.cli import main

    assert main(["audio", "defaults"]) == 0
    defaults = json.loads(capsys.readouterr().out)
    assert defaults["id"] == "OCF-AUDIO-DEFAULTS-HPLUS-016"
    assert defaults["human_listening_approval"] is None

    assert main(["audio", "plan", "OCF-FND-004", "--expand"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["function_id"] == "OCF-FND-004"
    assert plan["locale"] == "en-US"

    output = tmp_path / "eligibility.json"
    assert (
        main(["audio", "eligibility", "OCF-FND-004", "--locale", "en-US", "--output", str(output)])
        == 0
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["function_id"] == "OCF-FND-004"
    assert report["release_ready"] is False
    capsys.readouterr()


def test_cli_canonical_function_lookup_and_preview_never_select_activation(capsys):
    import json

    from ocf_tools.cli import main

    assert main(["functions", "lookup", "Relax", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["activation_selected"] is False
    assert any(row["function_id"] == "OCF-FND-004" for row in result["matches"])

    assert main(["functions", "preview", "OCF-FND-004"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["function_id"] == "OCF-FND-004" and not preview["synthesis"]


def test_cli_command_export_and_workspace_status_json(capsys):
    import json

    from ocf_tools.cli import main

    assert main(["commands", "list", "--json"]) == 0
    commands = json.loads(capsys.readouterr().out)
    assert any(row["function_id"] == "OCF-FND-004" for row in commands["functions"])

    assert main(["workspace", "status", "--json"]) == 0
    workspace = json.loads(capsys.readouterr().out)
    assert workspace["checkout"]


def test_narration_sources_lists_canonical_events_without_selecting_recordings(capsys):
    import json

    from ocf_tools.cli import main

    assert main(["narration", "sources", "OCF-FND-004", "--locale", "en-US"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["function_id"] == "OCF-FND-004"
    assert report["recordings_selected"] is False
    assert report["events"]
    assert all(event["source"] in {"unselected", "silence"} for event in report["events"])


def test_artwork_themes_and_capabilities_cli_are_read_only(capsys):
    import json

    from ocf_tools.cli import main

    assert main(["artwork", "themes"]) == 0
    themes = json.loads(capsys.readouterr().out)
    assert themes["themes"] and themes["brand"]["id"]

    assert main(["capabilities", "--json"]) == 0
    capabilities = json.loads(capsys.readouterr().out)
    assert any(row["path"][:2] == ["functions", "list"] for row in capabilities["commands"])


def test_artwork_cli_dispatches_review_gallery_brand_theme_and_cover_without_rendering(
    capsys, monkeypatch, tmp_path
):
    import json

    from ocf_tools import artwork, brand_refinement
    from ocf_tools.cli import main

    calls = []

    def record(kind):
        return lambda *args, **kwargs: calls.append((kind, args, kwargs)) or {"kind": kind}

    monkeypatch.setattr(brand_refinement, "comparison_gallery", record("refine"))
    monkeypatch.setattr(artwork, "gallery", record("gallery"))
    monkeypatch.setattr(artwork, "export_brand", record("brand"))
    monkeypatch.setattr(artwork, "theme_tokens", record("theme"))
    monkeypatch.setattr(artwork, "generate_cover", record("generate"))

    for args in (
        ["artwork", "refine", "--output", str(tmp_path / "refine"), "--vector-only"],
        ["artwork", "gallery", "--output", str(tmp_path / "gallery")],
        ["artwork", "brand", "--variant", "icon", "--output", str(tmp_path / "icon.svg")],
        ["artwork", "theme", "--surface", "documentation", "--theme", "ocf-dark"],
        [
            "artwork",
            "generate",
            "OCF-FND-004",
            "--format",
            "jpeg",
            "--font",
            "fixture.ttf",
            "--no-cue",
            "--lyrics",
        ],
    ):
        assert main(args) == 0
        assert json.loads(capsys.readouterr().out)["kind"] == args[1]

    assert [kind for kind, _args, _kwargs in calls] == [
        "refine",
        "gallery",
        "brand",
        "theme",
        "generate",
    ]
    assert calls[-1][2]["overrides"] == {"font": "fixture.ttf"}
    assert calls[-1][2]["show_cue"] is False
    assert calls[-1][2]["lyrics"] is True


def test_workspace_clean_json_dry_run_never_removes_unmarked_data(capsys, monkeypatch, tmp_path):
    import json

    from ocf_tools.cli import main

    work = tmp_path / "work"
    scratch = work / "tmp/ocf-unmarked" / "unmarked.txt"
    scratch.parent.mkdir(parents=True)
    scratch.write_text("keep", encoding="utf-8")
    monkeypatch.setenv("OCF_WORK_DIR", str(work))

    assert main(["workspace", "clean", "--older-than-hours", "0", "--dry-run", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["dry_run"] is True
    assert scratch.read_text(encoding="utf-8") == "keep"


def test_narration_source_coverage_cli_reports_canonical_events(capsys):
    import json

    from ocf_tools.cli import main

    assert main(["narration", "sources", "OCF-FND-004", "--locale", "en-US"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["function_id"] == "OCF-FND-004"
    assert report["recordings_selected"] is False
    assert report["events"]
    assert all(event["source"] in {"unselected", "silence"} for event in report["events"])


def test_cli_dev_reports_canonical_function_metadata_and_invalid_arguments(capsys):
    import json

    from ocf_tools.cli import main

    assert (
        main(
            [
                "dev",
                "ocf_get_function",
                "--arguments",
                '{"function_id":"OCF-FND-004","fields":["lifecycle","provenance"]}',
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok"
    assert result["data"]["id"] == "OCF-FND-004"
    assert result["data"]["provenance"]["canonical_resource"].startswith("locales/en-US/")

    assert main(["dev", "ocf_get_function", "--arguments", "not-json"]) == 1
    assert "valid JSON" in capsys.readouterr().err


def test_workspace_clean_rejects_nonfinite_age_before_filesystem_changes(capsys):
    from ocf_tools.cli import main

    assert main(["workspace", "clean", "--older-than-hours", "nan", "--json"]) == 1
    assert "finite and nonnegative" in capsys.readouterr().err


def test_audio_defaults_expanded_plan_and_eligibility_cli_routes(capsys, tmp_path):
    import json

    from ocf_tools.cli import main

    assert main(["audio", "defaults"]) == 0
    defaults = json.loads(capsys.readouterr().out)
    assert defaults["id"] == "OCF-AUDIO-DEFAULTS-HPLUS-016"
    assert defaults["human_listening_approval"] is None

    assert main(["audio", "plan", "OCF-FND-004", "--expand"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["function_id"] == "OCF-FND-004" and plan["locale"] == "en-US"

    output = tmp_path / "eligibility.json"
    assert (
        main(["audio", "eligibility", "OCF-FND-004", "--locale", "en-US", "--output", str(output)])
        == 0
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["function_id"] == "OCF-FND-004" and not result["release_ready"]
    capsys.readouterr()


def test_ocf_py_entrypoint_via_subprocess():
    result = subprocess.run(
        [sys.executable, "scripts/ocf.py", "help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "ocf new proposal" in result.stdout
