import asyncio
import json
import os
import sys

import pytest
from ocf_tools.paths import REPO_ROOT


def test_official_stdio_protocol_registration_resources_arguments_and_parity():
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

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
                invalid = await session.call_tool("ocf_list_functions", {"limit": "not-a-number"})
                assert invalid.isError
                prompt = await session.get_prompt("workflow", {"name": "plan-all"})
                assert "audio plan" in str(prompt)

    asyncio.run(exercise())
