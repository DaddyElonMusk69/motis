"""
Motis Execution MCP server.

All state-changing exchange actions should terminate here.
"""

from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server

from motis_execution_mcp.tools import EXECUTION_TOOLS, dispatch_execution

server = Server("motis-execution-mcp")


@server.list_tools()
async def list_tools():
    return EXECUTION_TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    return await dispatch_execution(name, arguments)


async def serve() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
