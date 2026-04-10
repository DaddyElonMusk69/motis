"""
Motis MCP Server — the platform's chokepoint for all trading execution.

ALL exchange interactions go through here. This is where:
  1. Platform-level risk guard is enforced (cannot be bypassed by operator code)
  2. User API keys are decrypted and injected (operator code never sees keys)
  3. Paper trade / live trade routing happens
  4. Trade log entries are written (source of truth for Arena + Marketplace)
"""
from __future__ import annotations

import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from motis_mcp.market_data.tools import MARKET_DATA_TOOLS, dispatch_market_data
from motis_mcp.execution.tools import EXECUTION_TOOLS, dispatch_execution
from motis_mcp.operator_tools.tools import OPERATOR_TOOLS, dispatch_operator

server = Server("motis-mcp")

ALL_TOOLS: list[Tool] = [
    *MARKET_DATA_TOOLS,
    *EXECUTION_TOOLS,
    *OPERATOR_TOOLS,
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return ALL_TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name in {t.name for t in MARKET_DATA_TOOLS}:
        return await dispatch_market_data(name, arguments)
    elif name in {t.name for t in EXECUTION_TOOLS}:
        return await dispatch_execution(name, arguments)
    elif name in {t.name for t in OPERATOR_TOOLS}:
        return await dispatch_operator(name, arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
