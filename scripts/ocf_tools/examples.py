"""Discover and check public interface examples without executing operator actions."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import inspect
import io
import json

from . import agent_api, cli, validators
from .lsp_server import FEATURES
from .paths import REPO_ROOT, SCHEMAS_DIR
from .utils import OCFError, write_text_atomic, yaml_safe_load

MANIFEST = REPO_ROOT / "examples/interfaces.json"
SCHEMA_FILES = {
    "audio-implementation": "audio/manifests/OCF-AUDIO-0001.yaml",
    "background-audio": "tests/fixtures/background-sample.yaml",
    "brand": "brand/identity.json",
    "brand-import": "brand/versions/0.3.0/identity.json",
    "brand-refinement": "brand/versions/0.2.0/identity.json",
    "command-procedure": "function-content/command-procedures.yaml",
    "community-voice": "templates/community-voice.yaml",
    "corpus-inventory": "docs/research/humanplus-corpus-inventory.json",
    "cue-profile": "audio/cues/profiles/OCF-CUE-PROFILE-DEFAULT.yaml",
    "function": "tests/fixtures/function-sample.yaml",
    "function-binding": "function-content/bindings/OCF-FND-002.yaml",
    "function-decisions": "function-content/decisions/OCF-FND-002.yaml",
    "function-evidence": "function-content/evidence/OCF-FND-002.yaml",
    "function-specification": "function-content/specifications/OCF-FND-002.yaml",
    "locale-manifest": "locales/en-US/manifest.yaml",
    "locale-resource": "locales/en-US/ui.yaml",
    "semantic-dsp-profile": "audio/background/state-profiles/OCF-DSP-DEFAULT-001.yaml",
    "session-pacing": "audio/templates/pacing/OCF-PACING-HPLUS-STANDARD-001.yaml",
    "session-plan": "audio/session-plans/en-US/OCF-FND-002.json",
    "session-stage": "audio/templates/stages/OCF-TPL-STAGE-ORIENTATION-001.yaml",
    "session-template": "audio/templates/sessions/OCF-TPL-SESSION-LEARN-001.yaml",
    "theme": "brand/themes/ocf-dark.json",
    "timed-transcript": "templates/timed-transcript.yaml",
    "voice-profile": "audio/voices/profiles/espeak-en.yaml",
}
RUNTIME_SCHEMAS = {
    "capabilities.schema.json": ["capabilities", "--json"],
    "doctor.schema.json": ["doctor", "--json"],
    "function-discovery.schema.json": ["functions", "describe", "OCF-FND-002", "--rich", "--json"],
}
SAFE_COMMANDS = [
    ["capabilities", "--json"],
    ["functions", "list", "--json"],
    ["functions", "describe", "OCF-FND-002", "--rich", "--json"],
    ["locale", "list"],
    ["audio", "defaults"],
    ["audio", "eligibility", "OCF-FND-002"],
    ["audio", "plan", "OCF-FND-002", "--expand"],
    ["narration", "sources", "OCF-SLP-005", "--locale", "en-US"],
    ["voice", "capabilities", "--json"],
    ["lsp", "--capabilities"],
    ["dev", "ocf_project_overview"],
]


def _value(action):
    if action.choices:
        return str(next(iter(action.choices)))
    if action.type is int:
        return "1"
    if action.type is float:
        return "1.0"
    return {
        "function_id": "OCF-FND-002",
        "query": "OCF-FND-002",
        "operation": "ocf_project_overview",
        "locale": "en-US",
        "voice": "espeak-en",
        "voice_id": "espeak-en",
        "template": "OCF-TPL-SESSION-LEARN-001",
        "output": ".ocf-work/examples/YOUR_OUTPUT",
    }.get(action.dest, "YOUR_" + action.dest.upper())


def parser_examples(parser):
    rows = []

    def walk(node, prefix):
        sub = next(
            (item for item in node._actions if isinstance(item, argparse._SubParsersAction)), None
        )
        if sub:
            for name, child in sub.choices.items():
                walk(child, [*prefix, name])
            return
        arguments = []
        required_group_actions = {
            group._group_actions[0] for group in node._mutually_exclusive_groups if group.required
        }
        for action in node._actions:
            if action.dest in {"help", argparse.SUPPRESS}:
                continue
            if action.option_strings:
                if not action.required and action not in required_group_actions:
                    continue
                arguments.append(action.option_strings[-1])
                if action.nargs == 0:
                    continue
            elif action.nargs in ("?", "*"):
                continue
            count = action.nargs if isinstance(action.nargs, int) else 1
            arguments.extend([_value(action)] * count)
        argv = [*prefix, *arguments]
        parser.parse_args(argv)
        rows.append(
            {
                "path": prefix,
                "argv": argv,
                "verification": "parser-only; placeholders are not dispatched",
                "usage": node.format_usage().strip(),
            }
        )

    walk(parser, [])
    return rows


def mcp_examples():
    rows = []
    for name, function in sorted(agent_api.TOOLS.items()):
        arguments = {}
        for key, parameter in inspect.signature(function).parameters.items():
            if parameter.default is not inspect.Parameter.empty:
                continue
            arguments[key] = {
                "function_id": "OCF-FND-002",
                "voice": "espeak-en",
                "voices": ["espeak-en"],
                "changed_files": ["scripts/ocf_tools/cli.py"],
                "theme": "ocf-cosmic-dark",
                "name": "add-function" if name == "ocf_get_workflow" else "function.schema.json",
            }.get(key, "YOUR_" + key.upper())
        agent_api.validate_tool_arguments(name, arguments)
        rows.append(
            {
                "name": name,
                "arguments": arguments,
                "read_only_hint": name in agent_api.READ_ONLY,
                "verification": "signature/type checked only; no job, render, deletion or packaging dispatched",
            }
        )
    return rows


def mcp_declarations():
    tree = ast.parse((REPO_ROOT / "scripts/ocf_tools/mcp_server.py").read_text(encoding="utf-8"))
    resources, prompts = [], []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr == "resource":
                resources.append(
                    {
                        "uri": ast.literal_eval(decorator.args[0]),
                        "verification": "registered resource declaration; protocol tests cover reads",
                    }
                )
            if decorator.func.attr == "prompt":
                prompts.append(
                    {
                        "name": node.name,
                        "arguments": {"name": "add-function"},
                        "verification": "registered prompt declaration; workflow selectors checked separately",
                    }
                )
    return sorted(resources, key=lambda row: row["uri"]), sorted(
        prompts, key=lambda row: row["name"]
    )


def schema_examples():
    bundle = json.loads((REPO_ROOT / "examples/contracts.json").read_text(encoding="utf-8"))
    rows = []
    for path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        schema = validators._load_schema(path.name)
        stem = path.name.removesuffix(".schema.json")
        if stem in SCHEMA_FILES:
            source = SCHEMA_FILES[stem]
            data = yaml_safe_load((REPO_ROOT / source).read_text(encoding="utf-8"))
        elif path.name in bundle:
            source = "examples/contracts.json#/" + path.name
            data = bundle[path.name]
        elif path.name in RUNTIME_SCHEMAS:
            rows.append(
                {
                    "schema": path.name,
                    "argv": RUNTIME_SCHEMAS[path.name],
                    "verification": "runtime JSON schema checked by --execute-read-only",
                }
            )
            continue
        else:
            raise OCFError("missing schema example: " + path.name)
        errors = validators.validate_against_schema(data, schema)
        if errors:
            raise OCFError(f"{path.name}: {source}: " + "; ".join(errors[:3]))
        rows.append(
            {
                "schema": path.name,
                "source": source,
                "example_sha256": hashlib.sha256(
                    json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest(),
                "verification": "structural schema only; not semantic, asset, rights or release approval",
            }
        )
    if set(bundle) - {path.name for path in SCHEMAS_DIR.glob("*.schema.json")}:
        raise OCFError("example bundle references removed schemas")
    return rows


def build():
    parser = cli._build_parser()
    resources, prompts = mcp_declarations()
    workflows = json.loads((REPO_ROOT / "docs/workflows.json").read_text(encoding="utf-8"))
    return {
        "schema_version": "1.0",
        "generator": "ocf_tools.examples",
        "policy": "Discovery/contract checks are not operation execution. YOUR_* and zero hashes are documentation placeholders. No public HTTP API exists.",
        "cli": parser_examples(parser),
        "mcp_tools": mcp_examples(),
        "mcp_resources": resources,
        "mcp_prompts": prompts,
        "workflows": workflows,
        "schemas": schema_examples(),
        "lsp": [
            {
                "method": name,
                "purpose": purpose,
                "example_guide": "docs/LSP.md",
                "verification": "actual protocol coverage is reported by test_lsp_protocol.py, not inferred from discovery",
            }
            for name, purpose in FEATURES.items()
        ],
        "safe_cli_examples": SAFE_COMMANDS,
        "source_hashes": {
            path.relative_to(REPO_ROOT).as_posix(): hashlib.sha256(
                path.read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest()
            for path in [
                REPO_ROOT / "scripts/ocf_tools" / name
                for name in (
                    "cli.py",
                    "prompts.py",
                    "narration_cli.py",
                    "voice_engine_cli.py",
                    "agent_api.py",
                    "mcp_server.py",
                    "lsp_server.py",
                )
            ]
            + sorted(SCHEMAS_DIR.glob("*.schema.json"))
        },
    }


def execute_read_only():
    """Run an explicit fixed allowlist; never dispatch generated placeholder examples."""
    results = []
    for argv in SAFE_COMMANDS + [RUNTIME_SCHEMAS["doctor.schema.json"]]:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = cli.main(argv)
        # doctor may report unavailable optional/native tooling on a clean host.
        if code and argv[0] != "doctor":
            raise OCFError(f"read-only example failed ({code}): {argv}")
        for name, command in RUNTIME_SCHEMAS.items():
            if argv == command:
                errors = validators.validate_against_schema(
                    json.loads(stream.getvalue()), validators._load_schema(name)
                )
                if errors:
                    raise OCFError(f"{name} runtime example: {errors}")
        results.append(
            {
                "argv": argv,
                "exit_code": code,
                "output_bytes": len(stream.getvalue().encode("utf-8")),
            }
        )
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--execute-read-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = build()
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        fresh = MANIFEST.is_file() and MANIFEST.read_text(encoding="utf-8") == text
        if not args.check:
            write_text_atomic(MANIFEST, text)
            fresh = True
        result = {
            "fresh": fresh,
            **{
                key: len(data[key])
                for key in ("cli", "mcp_tools", "mcp_resources", "mcp_prompts", "schemas", "lsp")
            },
        }
        if args.execute_read_only:
            result["executed_read_only"] = execute_read_only()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if fresh else 1
    except (OCFError, OSError, ValueError) as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
