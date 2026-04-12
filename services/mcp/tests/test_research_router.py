from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from motis_data_mcp.contracts import build_tool_envelope
from motis_data_mcp import tools as data_tools


def test_dispatch_data_routes_structured_research_tools(monkeypatch):
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeRouter:
        async def macro_get_series(self, **kwargs):
            calls.append(("macro.get_series", kwargs))
            return build_tool_envelope(
                tool="macro.get_series",
                provider="fake_macro",
                data={"series": kwargs["series"], "country": kwargs.get("country") or "us", "points": [{"date": "2026-04-01", "value": 1.0}]},
            )

        async def equity_get_fundamentals(self, **kwargs):
            calls.append(("equity.get_fundamentals", kwargs))
            return build_tool_envelope(
                tool="equity.get_fundamentals",
                provider="fake_fundamentals",
                data={"symbols": kwargs["symbols"], "count": 1, "items": [{"symbol": kwargs["symbols"][0], "fundamentals": {"trailing_pe": 20.0}}]},
            )

        async def equity_get_earnings_calendar(self, **kwargs):
            calls.append(("equity.get_earnings_calendar", kwargs))
            return build_tool_envelope(
                tool="equity.get_earnings_calendar",
                provider="fake_earnings",
                data={"symbols": kwargs["symbols"], "count": 1, "events": [{"symbol": kwargs["symbols"][0], "event_date": "2026-05-01"}]},
            )

        async def flows_get_connect(self, **kwargs):
            calls.append(("flows.get_connect", kwargs))
            return build_tool_envelope(
                tool="flows.get_connect",
                provider="fake_connect",
                data={"direction": kwargs["direction"], "count": 1, "daily_flows": [{"trade_date": "2026-04-10", "flow_mn": 123.0}]},
            )

        async def china_get_moneyflow(self, **kwargs):
            calls.append(("china.get_moneyflow", kwargs))
            return build_tool_envelope(
                tool="china.get_moneyflow",
                provider="fake_moneyflow",
                data={"symbols": kwargs["symbols"], "count": 1, "items": [{"symbol": kwargs["symbols"][0], "records": [{"trade_date": "2026-04-10", "net_mf_amount": 88.0}]}]},
            )

    monkeypatch.setattr(data_tools, "get_networking_router", lambda: FakeRouter())

    macro_payload = asyncio.run(data_tools.dispatch_data("macro.get_series", {"series": "cpi", "country": "us"}))
    fundamentals_payload = asyncio.run(
        data_tools.dispatch_data("equity.get_fundamentals", {"symbols": ["AAPL"], "fields": ["trailing_pe"]})
    )
    earnings_payload = asyncio.run(
        data_tools.dispatch_data("equity.get_earnings_calendar", {"symbols": ["AAPL"], "limit": 5})
    )
    connect_payload = asyncio.run(data_tools.dispatch_data("flows.get_connect", {"direction": "northbound"}))
    moneyflow_payload = asyncio.run(
        data_tools.dispatch_data("china.get_moneyflow", {"symbols": ["600519.SH"], "start_date": "2026-04-01"})
    )

    decoded_macro = json.loads(macro_payload[0].text)
    decoded_fundamentals = json.loads(fundamentals_payload[0].text)
    decoded_earnings = json.loads(earnings_payload[0].text)
    decoded_connect = json.loads(connect_payload[0].text)
    decoded_moneyflow = json.loads(moneyflow_payload[0].text)

    assert calls == [
        ("macro.get_series", {"series": "cpi", "country": "us", "start_date": None, "end_date": None, "frequency": None}),
        ("equity.get_fundamentals", {"symbols": ["AAPL"], "fields": ["trailing_pe"], "as_of": None, "frequency": None}),
        ("equity.get_earnings_calendar", {"symbols": ["AAPL"], "start_date": None, "end_date": None, "limit": 5}),
        ("flows.get_connect", {"direction": "northbound", "symbols": [], "start_date": None, "end_date": None}),
        ("china.get_moneyflow", {"symbols": ["600519.SH"], "start_date": "2026-04-01", "end_date": None, "granularity": None}),
    ]
    assert decoded_macro["provider"] == "fake_macro"
    assert decoded_fundamentals["data"]["items"][0]["fundamentals"]["trailing_pe"] == 20.0
    assert decoded_earnings["data"]["events"][0]["event_date"] == "2026-05-01"
    assert decoded_connect["data"]["daily_flows"][0]["flow_mn"] == 123.0
    assert decoded_moneyflow["data"]["items"][0]["records"][0]["net_mf_amount"] == 88.0


def test_dispatch_data_validates_structured_research_requests():
    macro_payload = asyncio.run(data_tools.dispatch_data("macro.get_series", {}))
    fundamentals_payload = asyncio.run(data_tools.dispatch_data("equity.get_fundamentals", {"symbols": []}))
    moneyflow_payload = asyncio.run(data_tools.dispatch_data("china.get_moneyflow", {}))

    decoded_macro = json.loads(macro_payload[0].text)
    decoded_fundamentals = json.loads(fundamentals_payload[0].text)
    decoded_moneyflow = json.loads(moneyflow_payload[0].text)

    assert decoded_macro["error"]["code"] == "validation_error"
    assert decoded_fundamentals["error"]["code"] == "validation_error"
    assert decoded_moneyflow["error"]["code"] == "validation_error"
