"""
Execution MCP tools.

Security choke point:
  - Platform risk guard runs here before any exchange call
  - User API keys should be decrypted here, never in operator code
  - All fills should eventually be written to the immutable trade log here
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

from motis_execution_mcp.paper import PaperTradeExecutor
from motis_execution_mcp.risk_guard import PlatformRiskGuard

EXECUTION_TOOLS: list[Tool] = [
    Tool(
        name="execute_paper_trade",
        description=(
            "Execute a paper trade (simulated, no real capital). "
            "Records to trade log with is_paper=True once persistence is wired."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "symbol": {"type": "string"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "order_type": {"type": "string", "enum": ["market", "limit"]},
                "size": {"type": "number"},
                "price": {"type": "number"},
                "reduce_only": {"type": "boolean", "default": False},
            },
            "required": ["operator_id", "symbol", "side", "order_type", "size"],
        },
    ),
    Tool(
        name="execute_live_trade",
        description=(
            "Execute a live trade on a connected exchange. "
            "Platform risk guard is enforced before submission."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "symbol": {"type": "string"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "order_type": {"type": "string", "enum": ["market", "limit", "stop_market"]},
                "size": {"type": "number"},
                "price": {"type": "number"},
                "stop_price": {"type": "number"},
                "reduce_only": {"type": "boolean", "default": False},
            },
            "required": ["operator_id", "symbol", "side", "order_type", "size"],
        },
    ),
    Tool(
        name="get_positions",
        description="Get current open positions for an operator.",
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    ),
    Tool(
        name="get_account_balance",
        description="Get current account balance/equity for an operator's exchange account.",
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    ),
]


async def dispatch_execution(name: str, args: dict) -> list[TextContent]:
    guard = PlatformRiskGuard()

    if name == "execute_paper_trade":
        check = await guard.check(args["operator_id"], args)
        if not check.approved:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": "Risk guard rejected", "reasons": check.reasons}
                    ),
                )
            ]

        executor = PaperTradeExecutor()
        result = await executor.execute(args)
        return [TextContent(type="text", text=json.dumps(result))]

    if name == "execute_live_trade":
        check = await guard.check(args["operator_id"], args)
        if not check.approved:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": "Risk guard rejected", "reasons": check.reasons}
                    ),
                )
            ]

        return [
            TextContent(
                type="text",
                text=json.dumps({"status": "not_implemented", "tool": name}),
            )
        ]

    if name == "get_positions":
        return [TextContent(type="text", text=json.dumps({"positions": []}))]

    if name == "get_account_balance":
        return [TextContent(type="text", text=json.dumps({"balance": 0}))]

    raise ValueError(f"Unknown execution tool: {name}")
