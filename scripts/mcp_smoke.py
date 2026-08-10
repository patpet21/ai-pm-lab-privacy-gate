from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


REQUIRED_TOOLS = {
    "privacy_gate_status",
    "list_protected_documents",
    "search_protected_documents",
    "get_protected_document",
}


async def run(command: str, args: list[str], data_dir: str | None) -> None:
    environment = dict(os.environ)
    if data_dir:
        environment["PRIVACY_GATE_DATA_DIR"] = data_dir
    parameters = StdioServerParameters(command=command, args=args, env=environment)
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            missing = REQUIRED_TOOLS - names
            if missing:
                raise RuntimeError(f"Missing MCP tools: {sorted(missing)}")
            status = await session.call_tool("privacy_gate_status")
            if status.is_error:
                raise RuntimeError("privacy_gate_status returned an MCP error")
            print(json.dumps({"tools": sorted(names), "status": "ok"}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the Privacy Gate MCP stdio server")
    parser.add_argument("command")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parser.add_argument("--data-dir")
    options = parser.parse_args()
    asyncio.run(run(options.command, options.args, options.data_dir))


if __name__ == "__main__":
    main()
