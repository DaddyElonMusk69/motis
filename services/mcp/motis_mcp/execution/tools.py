"""
Execution MCP tools — paper and live trade routing.

SECURITY CHOKEPOINT:
  - Platform-level risk guard runs here BEFORE any exchange call
  - User API keys are decrypted here and NEVER exposed to operator code
  - All fills are written to the immutable trade_log table here
"""
from __future__ import annotations

import json
from mcp.types import Tool, TextContent
from pydantic import BaseModel

from motis_mcp.execution.risk_guard import PlatformRiskGuard
from motis_mcp.execution.paper import PaperTradeExecutor

EXECUTION_TOOLS: list[Tool] = [
    Tool(
        name="execute_paper_trade",
        description=(
            "Execute a paper trade (simulated, no real capital). "
            "Fills at mid-price + configurable slippage. "
            "Records to trade_log with is_paper=True."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "symbol": {"type": "string"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "order_type": {"type": "string", "enum": ["market", "limit"]},
                "size": {"type": "number"},
                "price": {"type": "number", "description": "Required for limit orders"},
                "reduce_only": {"type": "boolean", "default": False},
            },
            "required": ["operator_id", "symbol", "side", "order_type", "size"],
        },
    ),
    Tool(
        name="execute_live_trade",
        description=(
            "Execute a live trade on a connected exchange. "
            "Requires operator to have an active exchange_connection. "
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
        # Risk check first
        check = await guard.check(args["operator_id"], args)
        if not check.approved:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "Risk guard rejected", "reasons": check.reasons})
            )]
        executor = PaperTradeExecutor()
        result = await executor.execute(args)
        return [TextContent(type="text", text=json.dumps(result))]

    elif name == "execute_live_trade":
        check = await guard.check(args["operator_id"], args)
        if not check.approved:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "Risk guard rejected", "reasons": check.reasons})
            )]
        # TODO: resolve exchange connection → decrypt keys → route to exchange
        return [TextContent(type="text", text=json.dumps({"status": "not_implemented"}))]

    elif name == "get_positions":
        # TODO: fetch from positions table
        return [TextContent(type="text", text=json.dumps({"positions": []}))]

    elif name == "get_account_balance":
        # TODO: fetch from exchange via decrypted keys
        return [TextContent(type="text", text=json.dumps({"balance": 0}))]

    raise ValueError(f"Unknown execution tool: {name}")
