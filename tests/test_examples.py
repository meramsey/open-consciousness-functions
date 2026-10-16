"""Example freshness and no-dispatch boundaries, not operation success by inference."""

import argparse
import json

import pytest
from ocf_tools import agent_api, examples
from ocf_tools.utils import OCFError


@pytest.mark.integration
def test_all_public_examples_are_fresh_without_dispatching_operations(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("inventory building must never dispatch an operation")

    monkeypatch.setattr(examples.cli, "main", forbidden)
    monkeypatch.setattr(agent_api, "dispatch", forbidden)
    assert examples.build() == json.loads(examples.MANIFEST.read_text(encoding="utf-8"))


@pytest.mark.unit
def test_required_mutually_exclusive_flags_and_typed_positionals_parse():
    parser = argparse.ArgumentParser()
    child = parser.add_subparsers(dest="command").add_parser("example")
    child.add_argument("count", type=int)
    group = child.add_mutually_exclusive_group(required=True)
    group.add_argument("--file")
    group.add_argument("--event")
    child.add_argument("--kind", choices=["safe", "other"], required=True)
    rows = examples.parser_examples(parser)
    parsed = parser.parse_args(rows[0]["argv"])
    assert parsed.count == 1 and parsed.file and parsed.event is None and parsed.kind == "safe"


@pytest.mark.unit
def test_tool_argument_preflight_does_not_run_tool_and_rejects_wrong_types(monkeypatch):
    called = []

    def operation(function_id: str, full: bool = False) -> dict:
        called.append(function_id)
        return {}

    monkeypatch.setitem(agent_api.TOOLS, "ocf_example", operation)
    agent_api.validate_tool_arguments("ocf_example", {"function_id": "OCF-TST-999"})
    assert called == []
    with pytest.raises(OCFError, match="invalid argument type"):
        agent_api.validate_tool_arguments("ocf_example", {"function_id": "OCF-TST-999", "full": 1})
    with pytest.raises(OCFError):
        agent_api.validate_tool_arguments("ocf_example", {"undeclared": "value"})


@pytest.mark.unit
def test_read_only_runner_fails_when_a_supported_example_fails(monkeypatch):
    monkeypatch.setattr(examples.cli, "main", lambda argv: 1)
    with pytest.raises(OCFError, match="read-only example failed"):
        examples.execute_read_only()
