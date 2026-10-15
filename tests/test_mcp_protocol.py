import asyncio
import json
import os
import sys

import pytest
from ocf_tools.paths import REPO_ROOT


def test_official_stdio_protocol_registration_resources_arguments_and_parity(monkeypatch, tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from ocf_tools import agent_api as api

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    (tmp_path / "sources.json").write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "id": "protocol-test",
                "locale": "en-US",
                "mode": "tts",
            }
        )
    )

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(REPO_ROOT / "scripts/ocf.py"), "mcp"],
            cwd=str(REPO_ROOT),
            env=dict(os.environ),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {t.name for t in tools.tools}
                assert {"ocf_get_function", "ocf_start_audio_render", "ocf_cancel_job"} <= names
                assert names == set(api.TOOLS)
                registered = {t.name: t for t in tools.tools}
                for name in ("ocf_inspect_narration_sources", "ocf_inspect_voice_capabilities"):
                    assert registered[name].annotations.readOnlyHint
                for name in ("ocf_validate_recordings", "ocf_start_narration_render"):
                    assert not registered[name].annotations.readOnlyHint
                assert "dataset" in registered["ocf_plan_voice_training"].inputSchema["properties"]
                assert (
                    "idempotency_key"
                    in registered["ocf_start_narration_render"].inputSchema["properties"]
                )
                resources = await session.list_resources()
                assert len(resources.resources) == 7
                prompts = await session.list_prompts()
                assert "workflow" in {p.name for p in prompts.prompts}
                response = await session.call_tool(
                    "ocf_get_function", {"function_id": "OCF-FND-002", "fields": ["commands"]}
                )
                data = response.structuredContent or json.loads(response.content[0].text)
                assert data["data"]["commands"]["primary"] == "PLUS-FOCUS"
                assert len(json.dumps(data)) < 1000
                response = await session.call_tool(
                    "ocf_inspect_narration_sources",
                    {
                        "function_id": "OCF-FND-002",
                        "manifest": "sources.json",
                        "limit": 2,
                    },
                )
                sources = response.structuredContent or json.loads(response.content[0].text)
                assert sources == api.inspect_narration_sources(
                    "OCF-FND-002", "sources.json", limit=2
                )
                assert sources["events"]["next_offset"] == 2
                response = await session.call_tool("ocf_inspect_voice_capabilities", {})
                capabilities = response.structuredContent or json.loads(response.content[0].text)
                assert capabilities == api.inspect_voice_capabilities()
                response = await session.call_tool(
                    "ocf_validate_recordings",
                    {
                        "function_id": "OCF-FND-002",
                        "manifest": "sources.json",
                    },
                )
                job = response.structuredContent or json.loads(response.content[0].text)
                for _ in range(300):
                    response = await session.call_tool(
                        "ocf_get_job_result", {"job_id": job["job_id"]}
                    )
                    result = response.structuredContent or json.loads(response.content[0].text)
                    if "data" in result:
                        break
                    await asyncio.sleep(0.1)
                assert result["state"] == "completed" and result["data"]["errors"] == 0
                invalid = await session.call_tool("ocf_list_functions", {"limit": "not-a-number"})
                assert invalid.isError
                prompt = await session.get_prompt("workflow", {"name": "plan-all"})
                assert "audio plan" in str(prompt)

    asyncio.run(exercise())
