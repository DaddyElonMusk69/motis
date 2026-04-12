"""
Operator control-plane MCP tools.

These are contract-first stubs for the operator lifecycle boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

try:
    from mcp.types import TextContent, Tool
except ModuleNotFoundError:  # pragma: no cover - local smoke-test fallback
    @dataclass(slots=True)
    class TextContent:  # type: ignore[override]
        type: str
        text: str

    @dataclass(slots=True)
    class Tool:  # type: ignore[override]
        name: str
        description: str
        inputSchema: dict

OPERATOR_TOOLS: list[Tool] = [
    Tool(
        name="operator_create",
        description="Create a new operator in draft state.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "spec": {"type": "object"},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="operator_update",
        description="Update operator code, prompts, config, or risk settings.",
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "patch": {"type": "object"},
            },
            "required": ["operator_id", "patch"],
        },
    ),
    Tool(
        name="operator_delete",
        description="Archive or delete an operator.",
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    ),
    Tool(
        name="operator_invoke",
        description="Invoke an operator tick or run.",
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "mode": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    ),
    Tool(
        name="operator_status",
        description="Fetch operator runtime status.",
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    ),
    Tool(
        name="operator_pause",
        description="Pause a running operator.",
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    ),
    Tool(
        name="operator_resume",
        description="Resume a paused operator.",
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    ),
]


async def dispatch_operator(name: str, args: dict) -> list[TextContent]:
    known_tools = {tool.name for tool in OPERATOR_TOOLS}
    if name not in known_tools:
        raise ValueError(f"Unknown operator tool: {name}")

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "status": "not_implemented",
                    "service": "motis_operator_mcp",
                    "tool": name,
                    "args": args,
                }
            ),
        )
    ]
