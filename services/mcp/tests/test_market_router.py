from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from motis_data_mcp.contracts import build_tool_envelope
from motis_data_mcp.providers import market as market_module
from motis_data_mcp.providers.market import MarketDataNotSupported, MarketDataRouter, resolve_instrument
from motis_data_mcp import tools as data_tools


def test_resolve_instrument_covers_core_motis_markets():
    us_equity = resolve_instrument("AAPL")
    hk_equity = resolve_instrument("700.hk")
    a_share = resolve_instrument("000001.SZ")
    crypto_spot = resolve_instrument("BTCUSDT")
    crypto_perp = resolve_instrument("BTC/USDT:USDT")

    assert us_equity.market == "us_equity"
    assert us_equity.normalized_symbol == "AAPL.US"
    assert us_equity.provider_symbols["yfinance"] == "AAPL"

    assert hk_equity.market == "hk_equity"
    assert hk_equity.normalized_symbol == "0700.HK"

    assert a_share.market == "a_share"
    assert a_share.provider_symbols["tushare"] == "000001.SZ"

    assert crypto_spot.market == "crypto"
    assert crypto_spot.normalized_symbol == "BTC-USDT"
    assert crypto_spot.instrument_type == "spot"

    assert crypto_perp.market == "crypto"
    assert crypto_perp.normalized_symbol == "BTC-USDT-SWAP"
    assert crypto_perp.instrument_type == "perpetual"


def test_market_router_uses_provider_chain(monkeypatch):
    class FakeOKXProvider:
        name = "okx"

        def is_available(self) -> bool:
            return True

        async def get_ohlcv(self, resolved, *, interval: str, limit: int):
            assert resolved.normalized_symbol == "BTC-USDT"
            assert interval == "1h"
            assert limit == 2
            return {
                "symbol": resolved.input_symbol,
                "normalized_symbol": resolved.normalized_symbol,
                "market": resolved.market,
                "interval": interval,
                "count": 2,
                "candles": [
                    {
                        "timestamp": "2026-04-11T00:00:00+00:00",
                        "open": 100.0,
                        "high": 105.0,
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
            }

        async def get_ticker(self, resolved):
            raise MarketDataNotSupported("not needed for this test")

        async def get_orderbook(self, resolved, *, limit: int):
            raise MarketDataNotSupported("not needed for this test")

        async def get_funding_rate(self, resolved, *, limit: int):
            raise MarketDataNotSupported("not needed for this test")

        async def get_open_interest(self, resolved, *, limit: int):
            raise MarketDataNotSupported("not needed for this test")

    monkeypatch.setitem(market_module._MARKET_PROVIDER_FACTORIES, "okx", FakeOKXProvider)

    envelope = asyncio.run(MarketDataRouter().get_ohlcv("BTC-USDT", "1h", limit=2))

    assert envelope.status == "ok"
    assert envelope.provider == "okx"
    assert envelope.data["count"] == 2
    assert envelope.data["candles"][0]["close"] == 103.0


def test_dispatch_data_routes_market_tools(monkeypatch):
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeRouter:
        def market_resolve_symbol(self, symbol: str, *, exchange: str | None = None):
            calls.append(("market.resolve_symbol", {"symbol": symbol, "exchange": exchange}))
            return build_tool_envelope(
                tool="market.resolve_symbol",
                provider="fake_market_router",
                data={"normalized_symbol": "AAPL.US", "exchange": exchange},
            )

        async def market_get_ohlcv(
            self,
            symbol: str,
            *,
            interval: str,
            limit: int = 200,
            exchange: str | None = None,
        ):
            calls.append(
                (
                    "market.get_ohlcv",
                    {"symbol": symbol, "interval": interval, "limit": limit, "exchange": exchange},
                )
            )
            return build_tool_envelope(
                tool="market.get_ohlcv",
                provider="fake_market_router",
                data={
                    "symbol": symbol,
                    "interval": interval,
                    "count": 1,
                    "candles": [
                        {
                            "timestamp": "2026-04-11T00:00:00+00:00",
                            "open": 1.0,
                            "high": 2.0,
                            "low": 0.5,
                            "close": 1.5,
                            "volume": 3.0,
                        }
                    ],
                },
            )

    monkeypatch.setattr(data_tools, "get_networking_router", lambda: FakeRouter())

    resolve_payload = asyncio.run(data_tools.dispatch_data("market.resolve_symbol", {"symbol": "AAPL"}))
    ohlcv_payload = asyncio.run(
        data_tools.dispatch_data("market.get_ohlcv", {"symbol": "BTC-USDT", "interval": "1h", "limit": 1})
    )

    decoded_resolve = json.loads(resolve_payload[0].text)
    decoded_ohlcv = json.loads(ohlcv_payload[0].text)

    assert calls == [
        ("market.resolve_symbol", {"symbol": "AAPL", "exchange": None}),
        ("market.get_ohlcv", {"symbol": "BTC-USDT", "interval": "1h", "limit": 1, "exchange": None}),
    ]
    assert decoded_resolve["provider"] == "fake_market_router"
    assert decoded_resolve["data"]["normalized_symbol"] == "AAPL.US"
    assert decoded_ohlcv["provider"] == "fake_market_router"
    assert decoded_ohlcv["data"]["candles"][0]["close"] == 1.5


def test_dispatch_data_validates_market_requests():
    payload = asyncio.run(data_tools.dispatch_data("market.get_ohlcv", {"symbol": "BTC-USDT"}))
    decoded = json.loads(payload[0].text)

    assert decoded["status"] == "error"
    assert decoded["error"]["code"] == "validation_error"
    assert "interval" in decoded["error"]["message"]
