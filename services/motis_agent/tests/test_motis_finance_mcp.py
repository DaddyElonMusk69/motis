from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

import tools.motis_finance_tool as finance_tools


def test_route_data_source_uses_market_mcp(monkeypatch) -> None:
    calls = []

    async def fake_call(tool_name: str, payload: dict, *, session_id: str | None = None) -> dict:
        calls.append((tool_name, payload, session_id))
        return {
            "status": "ok",
            "service": "motis_data_mcp",
            "tool": "market.get_ohlcv",
            "provider": "okx",
            "warnings": [],
            "error": None,
            "data": {
                "symbol": "BTC-USDT",
                "normalized_symbol": "BTC-USDT",
                "market": "crypto",
                "interval": "1h",
                "candles": [
                    {
                        "timestamp": "2026-04-11T00:00:00+00:00",
                        "open": 100.0,
                        "high": 104.0,
                        "low": 99.0,
                        "close": 103.0,
                        "volume": 10.0,
                    },
                    {
                        "timestamp": "2026-04-11T01:00:00+00:00",
                        "open": 103.0,
                        "high": 107.0,
                        "low": 102.0,
                        "close": 106.0,
                        "volume": 12.0,
                    },
                ],
            },
        }

    monkeypatch.setattr(finance_tools, "_call_data_mcp_async", fake_call)

    result = asyncio.run(
        finance_tools.route_data_source(
            symbol="BTC-USDT",
            interval="1h",
            limit=2,
            exchange="okx",
        )
    )

    assert calls == [
        (
            "market.get_ohlcv",
            {"symbol": "BTC-USDT", "interval": "1h", "limit": 2, "exchange": "okx"},
            None,
        )
    ]
    assert result["success"] is True
    assert result["source"] == "okx"
    assert result["count"] == 2
    assert result["candles"][1]["close"] == 106.0


def test_market_data_tools_route_through_market_mcp(monkeypatch) -> None:
    calls = []

    async def fake_call(tool_name: str, payload: dict, *, session_id: str | None = None) -> dict:
        calls.append((tool_name, payload, session_id))
        if tool_name == "market.resolve_symbol":
            data = {
                "input_symbol": payload["symbol"],
                "normalized_symbol": "BTC-USDT-SWAP",
                "market": "crypto",
                "instrument_type": "perpetual",
                "exchange": payload.get("exchange") or "okx",
            }
        elif tool_name == "market.get_ticker":
            data = {
                "symbol": payload["symbol"],
                "normalized_symbol": "BTC-USDT-SWAP",
                "last": 65000.0,
                "bid": 64999.5,
                "ask": 65000.5,
            }
        elif tool_name == "market.get_orderbook":
            data = {
                "symbol": payload["symbol"],
                "depth": payload["limit"],
                "bids": [[64999.5, 10.0]],
                "asks": [[65000.5, 9.5]],
            }
        elif tool_name == "market.get_funding_rate":
            data = {
                "symbol": payload["symbol"],
                "current": {"funding_rate": 0.0001},
                "history": [{"funding_rate": 0.00008}],
                "count": 1,
            }
        elif tool_name == "market.get_open_interest":
            data = {
                "symbol": payload["symbol"],
                "points": [{"open_interest": 123456.0}],
                "count": 1,
            }
        else:  # pragma: no cover - defensive guard for unexpected tool names
            raise AssertionError(f"Unexpected tool routed through fake MCP: {tool_name}")

        return {
            "status": "ok",
            "service": "motis_data_mcp",
            "tool": tool_name,
            "provider": "okx",
            "warnings": [],
            "error": None,
            "request_id": "mdmcp_test_123",
            "as_of": "2026-04-12T00:00:00Z",
            "data": data,
        }

    monkeypatch.setattr(finance_tools, "_call_data_mcp_async", fake_call)

    resolve_payload = json.loads(
        asyncio.run(finance_tools.data_resolve_symbol_tool({"symbol": "BTC/USDT:USDT", "exchange": "okx"}))
    )
    ticker_payload = json.loads(asyncio.run(finance_tools.data_ticker_tool({"symbol": "BTC-USDT-SWAP"})))
    orderbook_payload = json.loads(
        asyncio.run(finance_tools.data_orderbook_tool({"symbol": "BTC-USDT-SWAP", "limit": 5}))
    )
    funding_payload = json.loads(
        asyncio.run(finance_tools.data_funding_rate_tool({"symbol": "BTC-USDT-SWAP", "limit": 3}))
    )
    open_interest_payload = json.loads(
        asyncio.run(finance_tools.data_open_interest_tool({"symbol": "BTC-USDT-SWAP"}))
    )

    assert calls == [
        ("market.resolve_symbol", {"symbol": "BTC/USDT:USDT", "exchange": "okx"}, None),
        ("market.get_ticker", {"symbol": "BTC-USDT-SWAP"}, None),
        ("market.get_orderbook", {"symbol": "BTC-USDT-SWAP", "limit": 5}, None),
        ("market.get_funding_rate", {"symbol": "BTC-USDT-SWAP", "limit": 3}, None),
        ("market.get_open_interest", {"symbol": "BTC-USDT-SWAP", "limit": 50}, None),
    ]

    assert resolve_payload["success"] is True
    assert resolve_payload["normalized_symbol"] == "BTC-USDT-SWAP"
    assert resolve_payload["provider"] == "okx"

    assert ticker_payload["last"] == 65000.0
    assert orderbook_payload["depth"] == 5
    assert funding_payload["current"]["funding_rate"] == 0.0001
    assert open_interest_payload["points"][0]["open_interest"] == 123456.0


def test_structured_research_tools_route_through_data_mcp(monkeypatch) -> None:
    calls = []

    async def fake_call(tool_name: str, payload: dict, *, session_id: str | None = None) -> dict:
        calls.append((tool_name, payload, session_id))
        if tool_name == "macro.get_series":
            data = {
                "series": payload["series"],
                "country": payload.get("country") or "us",
                "points": [{"date": "2026-04-01", "value": 2.4}],
                "count": 1,
            }
        elif tool_name == "equity.get_fundamentals":
            data = {
                "symbols": payload["symbols"],
                "count": 1,
                "items": [{"symbol": payload["symbols"][0], "fundamentals": {"trailing_pe": 18.5}}],
            }
        elif tool_name == "equity.get_earnings_calendar":
            data = {
                "symbols": payload["symbols"],
                "count": 1,
                "events": [{"symbol": payload["symbols"][0], "event_date": "2026-05-02"}],
            }
        elif tool_name == "flows.get_connect":
            data = {
                "direction": payload["direction"],
                "count": 1,
                "daily_flows": [{"trade_date": "2026-04-11", "flow_mn": 321.0}],
            }
        elif tool_name == "china.get_moneyflow":
            data = {
                "symbols": payload["symbols"],
                "count": 1,
                "items": [{"symbol": payload["symbols"][0], "records": [{"trade_date": "2026-04-11", "net_mf_amount": 66.0}]}],
            }
        else:  # pragma: no cover - defensive guard
            raise AssertionError(f"Unexpected structured tool call: {tool_name}")

        return {
            "status": "ok",
            "service": "motis_data_mcp",
            "tool": tool_name,
            "provider": "fake_provider",
            "warnings": [],
            "error": None,
            "request_id": "mdmcp_test_456",
            "as_of": "2026-04-12T00:00:00Z",
            "data": data,
        }

    monkeypatch.setattr(finance_tools, "_call_data_mcp_async", fake_call)

    macro_payload = json.loads(asyncio.run(finance_tools.macro_get_series_tool({"series": "cpi", "country": "us"})))
    fundamentals_payload = json.loads(
        asyncio.run(finance_tools.equity_get_fundamentals_tool({"symbols": ["AAPL"], "fields": ["trailing_pe"]}))
    )
    earnings_payload = json.loads(
        asyncio.run(finance_tools.equity_get_earnings_calendar_tool({"symbols": ["AAPL"], "limit": 5}))
    )
    connect_payload = json.loads(asyncio.run(finance_tools.flows_get_connect_tool({"direction": "northbound"})))
    moneyflow_payload = json.loads(
        asyncio.run(finance_tools.china_get_moneyflow_tool({"symbols": ["600519.SH"], "start_date": "2026-04-01"}))
    )

    assert calls == [
        ("macro.get_series", {"series": "cpi", "country": "us"}, None),
        ("equity.get_fundamentals", {"symbols": ["AAPL"], "fields": ["trailing_pe"]}, None),
        ("equity.get_earnings_calendar", {"symbols": ["AAPL"], "limit": 5}, None),
        ("flows.get_connect", {"direction": "northbound"}, None),
        ("china.get_moneyflow", {"symbols": ["600519.SH"], "start_date": "2026-04-01"}, None),
    ]

    assert macro_payload["points"][0]["value"] == 2.4
    assert fundamentals_payload["items"][0]["fundamentals"]["trailing_pe"] == 18.5
    assert earnings_payload["events"][0]["event_date"] == "2026-05-02"
    assert connect_payload["daily_flows"][0]["flow_mn"] == 321.0
    assert moneyflow_payload["items"][0]["records"][0]["net_mf_amount"] == 66.0


def test_check_motis_data_mcp_uses_configured_url_only(monkeypatch) -> None:
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("MCP_URL", raising=False)
    assert finance_tools.check_motis_data_mcp() is False

    monkeypatch.setenv("MCP_URL", "http://localhost:8002/")
    assert finance_tools.check_motis_data_mcp() is True


def test_mcp_backed_finance_tools_hide_without_data_mcp(monkeypatch) -> None:
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("MCP_URL", raising=False)

    defs_without_mcp = finance_tools.registry.get_definitions(
        {"data.ticker", "options_pricing"},
        quiet=True,
    )
    names_without_mcp = {item["function"]["name"] for item in defs_without_mcp}

    monkeypatch.setenv("DATA_MCP_URL", "http://localhost:8002")
    defs_with_mcp = finance_tools.registry.get_definitions(
        {"data.ticker", "options_pricing"},
        quiet=True,
    )
    names_with_mcp = {item["function"]["name"] for item in defs_with_mcp}

    assert "options_pricing" in names_without_mcp
    assert "data.ticker" not in names_without_mcp
    assert {"data.ticker", "options_pricing"}.issubset(names_with_mcp)
