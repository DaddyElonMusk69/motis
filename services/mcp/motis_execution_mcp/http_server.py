"""
HTTP transport for Motis Execution MCP.

This keeps execution MCP deployable as a separately hosted service while the
current Motis platform still uses a simple HTTP tool-dispatch pattern in some
paths.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, status

from motis_execution_mcp.settings import settings
from motis_execution_mcp.tools import EXECUTION_TOOLS, dispatch_execution

app = FastAPI(
    title="Motis Execution MCP HTTP",
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
        detail="Motis execution MCP returned an unsupported response payload",
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
    return {
        "status": "ok",
        "service": "motis_execution_mcp",
        "transport": "http",
        "tool_count": len(EXECUTION_TOOLS),
    }


@app.get("/tools")
async def list_tools(x_agent_token: str | None = Header(default=None, alias="X-Agent-Token")) -> dict[str, Any]:
    _verify_agent_token(x_agent_token)
    return {
        "service": "motis_execution_mcp",
        "tools": [_tool_to_dict(tool) for tool in EXECUTION_TOOLS],
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

    del x_user_id, x_conversation_id  # Reserved for future user-scoped execution policy.

    try:
        result = await dispatch_execution(tool_name, payload or {})
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
