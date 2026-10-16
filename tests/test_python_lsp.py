"""Optional real Pyright protocol in a contained, portable checkout fixture."""

import importlib.util
import json
import os
import shutil
import sys
import sysconfig
import venv
from urllib.parse import unquote

import pytest
from lsp_client import Client
from ocf_tools.authoring import position_at

if importlib.util.find_spec("pyright") is None or not shutil.which("node"):
    if os.environ.get("OCF_REQUIRE_PYTHON_LSP") == "1":
        raise RuntimeError("Python LSP job requires the pinned .[python-lsp] extra and Node")
    pytest.skip("optional .[python-lsp] extra and Node are not installed", allow_module_level=True)

pytestmark = [pytest.mark.integration, pytest.mark.external_tool]


@pytest.fixture
def python_client(repo_root, tmp_path):
    root = tmp_path / "Python checkout with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("ocf_launch.py", "start_ocf_python_lsp.py"):
        shutil.copy2(repo_root / "scripts" / name, scripts / name)
    environment = root / ".venv"
    venv.EnvBuilder(with_pip=False).create(environment)
    site_packages = environment / (
        "Lib/site-packages"
        if os.name == "nt"
        else f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    dependencies = sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
    (site_packages / "test-dependencies.pth").write_text(
        "\n".join(dependencies) + "\n", encoding="utf-8"
    )
    package = scripts / "fixture_package"
    package.mkdir()
    (package / "__init__.py").touch()
    definition = package / "sample.py"
    definition.write_text(
        'def greeting(name: str) -> str:\n    return f"Hi {name}"\n', encoding="utf-8"
    )
    usage = root / "usage.py"
    usage.write_text(
        'from fixture_package.sample import greeting\nimport yaml\n\nmessage = greeting("OCF")\n',
        encoding="utf-8",
    )
    (root / "unopened.py").write_text("wrong = missing_name\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[tool.pyright]\ninclude = ["scripts", "*.py"]\nextraPaths = ["scripts"]\n'
        'venvPath = "."\nvenv = ".venv"\npythonVersion = "3.11"\ntypeCheckingMode = "basic"\n',
        encoding="utf-8",
    )
    settings = json.loads((repo_root / ".opencode/opencode.json").read_text())["lsp"]["pyright"][
        "initialization"
    ]
    settings["python"]["analysis"]["logLevel"] = "Trace"
    rpc = Client(
        root,
        tmp_path / "pyright-stderr.log",
        command=[sys.executable, str(scripts / "start_ocf_python_lsp.py"), "--stdio"],
        settings=settings,
        cwd=root,
    )
    try:
        initialized = rpc.request(
            "initialize",
            {
                "processId": None,
                "rootUri": root.as_uri(),
                "workspaceFolders": [{"uri": root.as_uri(), "name": "fixture"}],
                "capabilities": {"workspace": {"configuration": True}},
                "initializationOptions": settings,
            },
        )
        assert "error" not in initialized, initialized
        rpc.send("initialized", {})
        rpc.send("workspace/didChangeConfiguration", {"settings": settings})
        yield rpc, root, definition, usage, initialized
    finally:
        rpc.close()
    assert rpc.process.returncode == 0


def open_python(rpc, path, version=1):
    rpc.send(
        "textDocument/didOpen",
        {
            "textDocument": {
                "uri": path.as_uri(),
                "languageId": "python",
                "version": version,
                "text": path.read_text(encoding="utf-8"),
            }
        },
    )


def test_python_symbols_hover_cross_file_navigation_and_environment(python_client):
    rpc, root, definition, usage, initialized = python_client
    assert initialized["result"]["capabilities"]["definitionProvider"]
    open_python(rpc, definition)
    open_python(rpc, usage)
    findings = rpc.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"]["uri"] == usage.as_uri()
        )
    )
    assert findings["params"]["diagnostics"] == []
    symbols = rpc.request(
        "textDocument/documentSymbol", {"textDocument": {"uri": definition.as_uri()}}
    )
    assert any(row["name"] == "greeting" for row in symbols["result"])
    text = usage.read_text()
    params = {
        "textDocument": {"uri": usage.as_uri()},
        "position": position_at(text, text.rindex("greeting")),
    }
    hover = rpc.request("textDocument/hover", params)
    assert "greeting" in json.dumps(hover["result"]) and "str" in json.dumps(hover["result"])
    target = rpc.request("textDocument/definition", params)
    assert any(row["uri"] == definition.as_uri() for row in target["result"])
    references = rpc.request(
        "textDocument/references", {**params, "context": {"includeDeclaration": True}}
    )
    assert any(row["uri"] == usage.as_uri() for row in references["result"])
    assert any(row["uri"] == definition.as_uri() for row in references["result"])
    assert any(request["method"] == "workspace/configuration" for request in rpc.server_requests)
    logs = "\n".join(
        message["params"]["message"]
        for message in rpc.notifications
        if message.get("method") == "window/logMessage"
    )
    assert str(root / ".venv").replace("\\", "/") in unquote(logs).replace("\\", "/")
    assert not any(
        message.get("method") == "textDocument/publishDiagnostics"
        and message["params"]["uri"] == (root / "unopened.py").as_uri()
        for message in rpc.notifications
    )


def test_python_unsaved_error_and_clearing(python_client):
    rpc, _root, _definition, usage, _initialized = python_client
    original = usage.read_text()
    open_python(rpc, usage)
    rpc.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"]["uri"] == usage.as_uri()
        )
    )
    rpc.send(
        "textDocument/didChange",
        {
            "textDocument": {"uri": usage.as_uri(), "version": 2},
            "contentChanges": [{"text": original + "broken = missing_name\n"}],
        },
    )
    findings = rpc.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"]["uri"] == usage.as_uri()
            and any(
                row.get("code") == "reportUndefinedVariable"
                for row in message["params"]["diagnostics"]
            )
        )
    )
    assert findings["params"]["diagnostics"]
    rpc.send(
        "textDocument/didChange",
        {
            "textDocument": {"uri": usage.as_uri(), "version": 3},
            "contentChanges": [{"text": original}],
        },
    )
    rpc.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"]["uri"] == usage.as_uri()
            and message["params"]["diagnostics"] == []
        )
    )
    assert usage.read_text() == original
