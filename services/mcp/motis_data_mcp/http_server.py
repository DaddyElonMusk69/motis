"""
HTTP transport for Motis Data MCP.

The live Motis agent currently dispatches remote tools over HTTP. This app
bridges that transport to the Motis-owned data tool contracts implemented in
``dispatch_data()`` while we keep the stdio MCP server for direct MCP clients.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, status

from motis_data_mcp.providers.market import get_market_provider_diagnostics
from motis_data_mcp.providers.research import get_research_provider_diagnostics
from motis_data_mcp.providers.router import get_networking_router
from motis_data_mcp.settings import settings
from motis_data_mcp.tools import DATA_TOOLS, dispatch_data

app = FastAPI(
    title="Motis Data MCP HTTP",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)


def _tool_to_dict(tool: Any) -> dict[str, Any]:
    if hasattr(tool, "model_dump"):
        return tool.model_dump()
    if is_dataclass(tool):
        return asdict(tool)
    return {
        "name": getattr(tool, "name", ""),
        "description": getattr(tool, "description", ""),
        "inputSchema": getattr(tool, "inputSchema", {}),
    }


def _decode_tool_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result

    if isinstance(result, list):
        for item in result:
            text = getattr(item, "text", None)
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
            return {"status": "ok", "data": payload}

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Motis data MCP returned an unsupported response payload",
    )


def _verify_agent_token(x_agent_token: str | None) -> None:
    expected = settings.agent_mcp_secret
    if expected and x_agent_token == expected:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid X-Agent-Token",
    )


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, Any]:
    router = get_networking_router()
    return {
        "status": "ok",
        "service": "motis_data_mcp",
        "transport": "http",
        "tool_count": len(DATA_TOOLS),
        "routing": {
            "search_provider": getattr(router.search_provider, "name", type(router.search_provider).__name__),
            "extract_provider": getattr(router.extract_provider, "name", type(router.extract_provider).__name__),
            "crawl_provider": getattr(router.crawl_provider, "name", type(router.crawl_provider).__name__),
        },
        "providers": {
            "market": get_market_provider_diagnostics(),
            "research": get_research_provider_diagnostics(),
        },
    }


@app.get("/tools")
async def list_tools(x_agent_token: str | None = Header(default=None, alias="X-Agent-Token")) -> dict[str, Any]:
    _verify_agent_token(x_agent_token)
    return {
        "service": "motis_data_mcp",
        "tools": [_tool_to_dict(tool) for tool in DATA_TOOLS],
    }


@app.post("/tools/{tool_name}")
async def call_tool(
    tool_name: str,
    payload: dict[str, Any] | None = None,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_conversation_id: str | None = Header(default=None, alias="X-Conversation-Id"),
) -> dict[str, Any]:
    _verify_agent_token(x_agent_token)

    del x_user_id, x_conversation_id  # Reserved for future per-user policy wiring.

    try:
        result = await dispatch_data(tool_name, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _decode_tool_result(result)


def main() -> None:
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
