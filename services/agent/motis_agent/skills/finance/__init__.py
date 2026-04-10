"""
Finance skill index — all skills absorbed from Vibe-Trading + Motis originals.

Skills are organised by category and exposed to the master agent via:
  - FINANCE_SKILL_DEFINITIONS: OpenAI tool schemas (read by MotisAgentLoop)
  - run_finance_skill(): async dispatcher (called by MotisToolRouter)

Categories (matching Vibe-Trading's 7 categories, extended):
    data        — market data fetching (OHLCV, orderbook, fundamentals)
    analysis    — technical analysis, pattern recognition, quantitative
    research    — macro, fundamental, on-chain, news
    reporting   — report generation, Pine Script export
    execution   — order management helpers (not the actual MCP execution layer)

NOTE: SwarmRunner is NO LONGER exported from here.
Research swarms are run via ResearchOperator (services/platform), not inline.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motis_agent.context import UserContext

logger = logging.getLogger(__name__)

# ── Data skills ──────────────────────────────────────────────────────────────
from motis_agent.skills.finance.data.routing import route_data_source

# ── Analysis skills ───────────────────────────────────────────────────────────
from motis_agent.skills.finance.analysis.smc import (
    detect_bos,
    detect_choch,
    detect_liquidity_sweep,
    detect_order_blocks,
    detect_fvg,
)


# ── Tool schema definitions ──────────────────────────────────────────────────
# These are the OpenAI function-calling schemas for finance skills.
# The master agent sees these as callable tools (e.g. "data.ohlcv", "smc.bos").

FINANCE_SKILL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "data.ohlcv",
            "description": (
                "Fetch OHLCV (Open/High/Low/Close/Volume) market data. "
                "Auto-routes across 5 data sources: ccxt, yfinance, akshare, tushare, okx. "
                "Supports crypto, US equities, HK equities, A-shares, forex, futures."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Ticker symbol (e.g. BTC/USDT, AAPL, 600519.SH)"},
                    "interval": {"type": "string", "description": "Timeframe: 1m, 5m, 15m, 1h, 4h, 1d, 1w"},
                    "limit": {"type": "integer", "default": 200, "description": "Number of candles"},
                    "exchange": {"type": "string", "description": "Preferred exchange/source (optional)"},
                },
                "required": ["symbol", "interval"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "smc.structure",
            "description": (
                "Analyse market structure using Smart Money Concepts (SMC/ICT): "
                "Break of Structure (BOS), Change of Character (CHoCH), liquidity sweeps, "
                "order blocks, and Fair Value Gaps (FVG). "
                "Returns a structured market context object."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "interval": {"type": "string"},
                    "htf_interval": {"type": "string", "description": "Higher timeframe for bias (optional)"},
                    "limit": {"type": "integer", "default": 200},
                },
                "required": ["symbol", "interval"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "technical.indicators",
            "description": (
                "Calculate technical indicators: RSI, MACD, Bollinger Bands, ATR, "
                "EMA/SMA, VWAP, volume profile. Returns indicator values for the specified symbol."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "interval": {"type": "string"},
                    "indicators": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["rsi", "macd", "bb", "atr", "ema", "sma", "vwap"]},
                        "description": "List of indicators to calculate",
                    },
                },
                "required": ["symbol", "interval", "indicators"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research.macro",
            "description": (
                "Analyse the macro environment: economic calendar, interest rates, CPI, PMI, "
                "DXY, global equity flows, risk-on/risk-off regime."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "Optional focus area (e.g. 'rates', 'liquidity', 'earnings')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research.onchain",
            "description": (
                "Fetch on-chain metrics for crypto assets: exchange netflow, "
                "whale wallet tracking, MVRV, NVT, funding rates, open interest."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "asset": {"type": "string", "description": "e.g. BTC, ETH"},
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific metrics (optional, returns all if omitted)",
                    },
                },
                "required": ["asset"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "research.fundamentals",
            "description": (
                "Fetch fundamental data for equities: income statement, balance sheet, "
                "cash flow, earnings estimates, analyst ratings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Equity ticker (e.g. AAPL, TSLA)"},
                    "period": {"type": "string", "enum": ["annual", "quarterly"], "default": "quarterly"},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report.generate",
            "description": (
                "Generate a formatted strategy research report with equity curve, "
                "drawdown chart, trade statistics, and markdown summary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "data": {"type": "object", "description": "Backtest results or operator trade log"},
                    "format": {"type": "string", "enum": ["markdown", "html", "pdf"], "default": "markdown"},
                },
                "required": ["title", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report.pine_script",
            "description": (
                "Export a strategy as TradingView Pine Script v6. "
                "Returns the script as a string the user can paste into TradingView."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_spec": {"type": "object", "description": "Operator strategy specification"},
                },
                "required": ["strategy_spec"],
            },
        },
    },
]


# ── Skill dispatcher ───────────────────────────────────────────────────────────

# Map tool names to their handler functions
_SKILL_HANDLERS: dict[str, Any] = {
    "data.ohlcv": route_data_source,
    "smc.structure": detect_bos,        # aggregates BOS, CHoCH, OB, FVG
    # Full handler map populated as skills are implemented
}


async def run_finance_skill(
    tool_name: str,
    args: dict,
    ctx: "UserContext",
) -> Any:
    """
    Dispatch a finance skill call by tool name.
    Called by MotisToolRouter for all finance.* / smc.* / data.* / technical.* tools.
    """
    handler = _SKILL_HANDLERS.get(tool_name)
    if handler is None:
        # Graceful stub: return an informative error rather than crashing
        logger.warning("Finance skill %r not yet implemented", tool_name)
        return {
            "error": f"Skill '{tool_name}' is not yet implemented.",
            "available": list(_SKILL_HANDLERS.keys()),
        }

    try:
        if callable(handler):
            import inspect
            if inspect.iscoroutinefunction(handler):
                return await handler(**args)
            return handler(**args)
        return {"error": f"Handler for {tool_name!r} is not callable"}
    except Exception as exc:
        logger.error("Finance skill %r failed: %s", tool_name, exc, exc_info=True)
        return {"error": str(exc)}


__all__ = [
    "FINANCE_SKILL_DEFINITIONS",
    "run_finance_skill",
    # Data
    "route_data_source",
    # Analysis
    "detect_bos", "detect_choch", "detect_liquidity_sweep",
    "detect_order_blocks", "detect_fvg",
]
