"""Real launcher and protocol checks without changing canonical documents."""

import json
import os
import shutil
import subprocess
import sys
import sysconfig
import venv

import pytest
from lsp_client import Client
from ocf_tools.authoring import position_at
from ocf_tools.paths import workspace_environment

pytest.importorskip("pygls")
pytestmark = [pytest.mark.integration, pytest.mark.external_tool]


@pytest.fixture
def checkout_launcher(repo_root, tmp_path):
    """Exercise a real checkout venv without depending on a developer's .venv."""
    root = tmp_path / "checkout with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("ocf_launch.py", "start_ocf_lsp.py"):
        shutil.copy2(repo_root / "scripts" / name, scripts / name)
    environment = root / ".venv"
    venv.EnvBuilder(with_pip=False).create(environment)
    site_packages = environment / (
        "Lib/site-packages"
        if os.name == "nt"
        else f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    # Reuse the test runner's already installed optional dependencies, without
    # installing packages or changing its environment. Source stays explicit on
    # PYTHONPATH because editable-install .pth hooks are not recursively loaded.
    dependencies = sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
    (site_packages / "ocf-test-dependencies.pth").write_text(
        "\n".join(dependencies) + "\n", encoding="utf-8"
    )
    return scripts / "start_ocf_lsp.py"


def test_launcher_symbols_cross_file_definition_unsaved_error_and_clean_shutdown(
    repo_root, tmp_path, checkout_launcher
):
    path = repo_root / "functions/sleep/sleep-easy.yaml"
    original = path.read_text(encoding="utf-8")
    command = [sys.executable, str(checkout_launcher), "--stdio"]
    rpc = Client(repo_root, tmp_path / "launcher-stderr.log", command=command)
    try:
        response = rpc.request(
            "initialize",
            {
                "processId": None,
                "rootUri": repo_root.as_uri(),
                "capabilities": {},
                "initializationOptions": {"diagnosticsDebounceMs": 150},
            },
        )
        assert "error" not in response and response["result"]["serverInfo"]["name"] == "OCF"
        rpc.send("initialized", {})
        rpc.send(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": original,
                }
            },
        )
        symbols = rpc.request(
            "textDocument/documentSymbol", {"textDocument": {"uri": path.as_uri()}}
        )
        assert any(row["name"] == "OCF-SLP-005" for row in symbols["result"])
        position = position_at(original, original.index("hplus.function.ocf-slp-005.function-body"))
        definition = rpc.request(
            "textDocument/definition",
            {
                "textDocument": {"uri": path.as_uri()},
                "position": position,
            },
        )
        assert any(
            row["uri"] == (repo_root / "locales/en-US/hplus-OCF-SLP-005.yaml").as_uri()
            for row in definition["result"]
        )
        rpc.send(
            "textDocument/didChange",
            {
                "textDocument": {"uri": path.as_uri(), "version": 2},
                "contentChanges": [{"text": "schema_version: ["}],
            },
        )
        diagnostic = rpc.receive(
            lambda message: (
                message.get("method") == "textDocument/publishDiagnostics"
                and message["params"].get("version") == 2
            )
        )
        assert any(row["code"] == "ocf.parse" for row in diagnostic["params"]["diagnostics"])
        assert path.read_text(encoding="utf-8") == original
    finally:
        rpc.close()
    assert rpc.process.returncode == 0


def test_launcher_propagates_parser_exit_status_and_streams(repo_root, checkout_launcher):
    env = workspace_environment({"PYTHONPATH": str(repo_root / "scripts")})
    result = subprocess.run(
        [sys.executable, str(checkout_launcher), "--not-a-valid-argument"],
        env=env,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 2 and not result.stdout
    assert b"unrecognized arguments" in result.stderr
    result = subprocess.run(
        [sys.executable, str(checkout_launcher), "--capabilities"],
        env=env,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout)["transport"] == "stdio"


def test_project_configuration_retains_mcp_watchers_and_read_only_agents(repo_root):
    import tomllib

    import yaml

    config = json.loads((repo_root / ".opencode/opencode.json").read_text(encoding="utf-8"))
    assert config["mcp"]["ocf"] == {
        "type": "local",
        "command": ["python3", "scripts/start_ocf_mcp.py"],
        "enabled": True,
    }
    assert "audio/rendered/**" in config["watcher"]["ignore"]
    assert config["lsp"]["ocf"]["extensions"] == [".yaml", ".yml", ".json"]
    assert config["lsp"]["ocf"]["initialization"] == {"diagnosticsDebounceMs": 150}
    assert config["lsp"]["pyright"]["extensions"] == [".py", ".pyi"]
    assert (
        config["lsp"]["pyright"]["initialization"]["python"]["analysis"]["diagnosticMode"]
        == "openFilesOnly"
    )
    assert config["lsp"]["yaml-ls"] == config["lsp"]["biome"] == {"disabled": True}
    assert config["permission"] == {"lsp": "allow"}
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["optional-dependencies"]["python-lsp"] == ["pyright==1.1.408"]
    policy = project["tool"]["pyright"]
    assert policy["typeCheckingMode"] == "basic" and policy["pythonVersion"] == "3.11"
    assert policy["extraPaths"] == ["scripts", "tests"]
    assert policy["venvPath"] == "." and policy["venv"] == ".venv"
    assert not (repo_root / "pyrightconfig.json").exists()
    for name in ("ocf-investigator", "ocf-test-reviewer"):
        text = (repo_root / f".opencode/agents/{name}.md").read_text(encoding="utf-8")
        permissions = yaml.safe_load(text.split("---", 2)[1])["permission"]
        assert permissions["lsp"] == "allow"
        assert all(
            permissions[key] == "deny" for key in ("edit", "bash", "task", "webfetch", "websearch")
        )
