from __future__ import annotations

import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from motis_data_mcp.tools import (
    ACTIVE_DATA_TOOLS,
    DATA_PROVIDER_ROUTING_PLAN,
    DATA_TOOLS,
    PLANNED_DATA_TOOLS,
)


def _tool_names(tools) -> list[str]:
    return [tool.name for tool in tools]


def test_live_data_tool_surface_stays_narrow():
    assert _tool_names(DATA_TOOLS) == _tool_names(ACTIVE_DATA_TOOLS)
    assert "web_search" in _tool_names(DATA_TOOLS)
    assert "market.resolve_symbol" in _tool_names(DATA_TOOLS)
    assert "market.get_ohlcv" in _tool_names(DATA_TOOLS)
    assert "market.get_funding_rate" in _tool_names(DATA_TOOLS)
    assert "market.get_open_interest" in _tool_names(DATA_TOOLS)
    assert "macro.get_series" in _tool_names(DATA_TOOLS)
    assert "equity.get_fundamentals" in _tool_names(DATA_TOOLS)
    assert "equity.get_earnings_calendar" in _tool_names(DATA_TOOLS)
    assert "flows.get_connect" in _tool_names(DATA_TOOLS)
    assert "china.get_moneyflow" in _tool_names(DATA_TOOLS)
    assert "macro.get_release_calendar" not in _tool_names(DATA_TOOLS)


def test_planned_catalog_covers_key_motis_domains():
    names = set(_tool_names(PLANNED_DATA_TOOLS))

    expected = {
        "market.list_instruments",
        "macro.get_release_calendar",
        "equity.get_filings",
        "flows.get_fund_flows",
        "china.get_margin_financing",
        "crypto.get_onchain_metrics",
        "credit.get_spreads",
        "commodity.get_inventory",
        "dataset.get_price_panel",
    }

    assert expected <= names


def test_data_tool_names_are_unique_across_active_and_planned_catalogs():
    all_names = _tool_names(ACTIVE_DATA_TOOLS) + _tool_names(PLANNED_DATA_TOOLS)
    assert len(all_names) == len(set(all_names))


def test_provider_routing_plan_keeps_structured_free_first_fallbacks():
    market_plan = DATA_PROVIDER_ROUTING_PLAN["structured_market_routing"]

    assert market_plan["a_share"] == ["tushare", "akshare"]
    assert market_plan["us_equity"] == ["yfinance", "akshare"]
    assert market_plan["crypto"] == ["okx", "ccxt"]
