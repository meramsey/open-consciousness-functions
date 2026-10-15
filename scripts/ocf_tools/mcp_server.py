"""Optional local stdio MCP adapter using the official SDK, never a network listener."""

from __future__ import annotations

import asyncio
import json
from functools import wraps


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError(
            "Optional MCP dependency missing; install with python -m pip install -e '.[mcp]'. CLI remains available."
        ) from exc
    from . import agent_api as api

    server = FastMCP(
        "OCF",
        instructions="Use compact discovery first, then focused validation. CLI/services are authoritative. Audio and full tests require explicit start tools; poll returned job IDs. Never infer release approval from renderability. See ocf://overview and ocf_get_workflow. This server is local stdio only.",
    )

    def threaded(function):
        @wraps(function)
        async def invoke(*args, **kwargs):
            return await asyncio.to_thread(function, *args, **kwargs)

        return invoke

    for name, function in api.TOOLS.items():
        server.add_tool(
            threaded(function),
            name=name,
            description=(function.__doc__ or name.replace("_", " ")),
            annotations=ToolAnnotations(
                readOnlyHint=name in api.READ_ONLY,
                destructiveHint=name == "ocf_cache_clean",
                openWorldHint=False,
            ),
        )

    @server.resource("ocf://overview")
    def overview() -> str:
        return json.dumps(api.project_overview(), ensure_ascii=False)

    @server.resource("ocf://schemas")
    def schemas() -> str:
        from .paths import SCHEMAS_DIR

        return json.dumps({"schemas": sorted(p.name for p in SCHEMAS_DIR.glob("*.schema.json"))})

    @server.resource("ocf://audio-defaults")
    def defaults() -> str:
        return json.dumps(api.get_audio_defaults())

    @server.resource("ocf://documentation")
    def documentation() -> str:
        return json.dumps(
            {
                "index": "docs/documentation-index.json",
                "navigation": "docs/README.md",
                "workflows": "docs/workflows.json",
            }
        )

    @server.resource("ocf://functions")
    def functions() -> str:
        return json.dumps(api.list_functions())

    @server.resource("ocf://validation")
    def validation() -> str:
        return json.dumps(
            {
                "status": "not-run",
                "instruction": "Use targeted validators or explicit final_validation; no stale success is inferred.",
            }
        )

    @server.resource("ocf://artifacts")
    def artifacts() -> str:
        return json.dumps(
            {
                "source_plans": "audio/session-plans",
                "local_auditions": ".ocf-work/renders",
                "jobs": ".ocf-work/logs/jobs",
            }
        )

    @server.prompt()
    def workflow(name: str) -> str:
        """Select add-function, review-narration, add-locale, plan-all, render-audition, debug-render, package-release or validate-pr."""
        return json.dumps(api.get_workflow(name), ensure_ascii=False)

    return server


def main():
    try:
        create_server().run(transport="stdio")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
