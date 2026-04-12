"""Structured market-data routing for Motis Data MCP."""

from __future__ import annotations

import asyncio
import importlib.util
import math
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from motis_data_mcp.contracts import ToolEnvelope, build_not_implemented_envelope, build_tool_envelope

_CRYPTO_PERP_RE = re.compile(r"^(?P<base>[A-Z0-9]+)[/-](?P<quote>[A-Z0-9]+)(?::(?P<settle>[A-Z0-9]+))$")
_CRYPTO_SPOT_RE = re.compile(r"^(?P<base>[A-Z0-9]+)[/-](?P<quote>[A-Z0-9]+)$")
_CRYPTO_SWAP_RE = re.compile(r"^(?P<base>[A-Z0-9]+)-(?P<quote>[A-Z0-9]+)-SWAP$")
_A_SHARE_RE = re.compile(r"^\d{6}\.(SZ|SH|BJ)$")
_HK_RE = re.compile(r"^\d{1,5}\.HK$")
_US_EXPLICIT_RE = re.compile(r"^[A-Z][A-Z0-9.\-]*\.US$")
_US_PLAIN_RE = re.compile(r"^[A-Z][A-Z0-9.\-]*$")
_COMPACT_CRYPTO_QUOTES = ("USDT", "USDC", "USD", "BTC", "ETH")


class MarketDataNotSupported(RuntimeError):
    """Raised when a provider cannot serve the requested operation."""


@dataclass(slots=True, frozen=True)
class ResolvedInstrument:
    input_symbol: str
    normalized_symbol: str
    market: str
    instrument_type: str
    exchange: str | None
    base_asset: str | None
    quote_asset: str | None
    provider_symbols: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_symbol": self.input_symbol,
            "normalized_symbol": self.normalized_symbol,
            "market": self.market,
            "instrument_type": self.instrument_type,
            "exchange": self.exchange,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "provider_symbols": dict(self.provider_symbols),
        }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _provider_symbol(symbols: dict[str, str], provider_name: str) -> str:
    symbol = symbols.get(provider_name)
    if not symbol:
        raise MarketDataNotSupported(f"{provider_name} symbol mapping is unavailable for this instrument")
    return symbol


def _normalize_interval(interval: str) -> str:
    value = str(interval or "").strip().lower()
    aliases = {
        "1min": "1m",
        "3min": "3m",
        "5min": "5m",
        "15min": "15m",
        "30min": "30m",
        "60m": "1h",
        "60min": "1h",
        "1hr": "1h",
        "1hour": "1h",
        "240m": "4h",
        "4hr": "4h",
        "4hour": "4h",
        "1day": "1d",
        "1week": "1w",
    }
    normalized = aliases.get(value, value)
    if normalized not in {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1mo"}:
        raise ValueError(f"Unsupported interval: {interval}")
    return normalized


def _compact_crypto_split(symbol: str) -> tuple[str, str] | None:
    upper = symbol.upper()
    for quote in _COMPACT_CRYPTO_QUOTES:
        if upper.endswith(quote) and len(upper) > len(quote):
            return upper[: -len(quote)], quote
    return None


def resolve_instrument(symbol: str, exchange: str | None = None) -> ResolvedInstrument:
    raw = str(symbol or "").strip()
    if not raw:
        raise ValueError("symbol is required")

    upper = raw.upper().replace(" ", "")
    exchange_value = str(exchange or "").strip().lower() or None

    if match := _CRYPTO_SWAP_RE.match(upper):
        base = match.group("base")
        quote = match.group("quote")
        normalized = f"{base}-{quote}-SWAP"
        return ResolvedInstrument(
            input_symbol=raw,
            normalized_symbol=normalized,
            market="crypto",
            instrument_type="perpetual",
            exchange=exchange_value or "okx",
            base_asset=base,
            quote_asset=quote,
            provider_symbols={
                "okx": normalized,
                "ccxt": f"{base}/{quote}:{quote}",
            },
        )

    if match := _CRYPTO_PERP_RE.match(upper):
        base = match.group("base")
        quote = match.group("quote")
        settle = match.group("settle") or quote
        normalized = f"{base}-{quote}-SWAP"
        return ResolvedInstrument(
            input_symbol=raw,
            normalized_symbol=normalized,
            market="crypto",
            instrument_type="perpetual",
            exchange=exchange_value or "okx",
            base_asset=base,
            quote_asset=quote,
            provider_symbols={
                "okx": normalized,
                "ccxt": f"{base}/{quote}:{settle}",
            },
        )

    if match := _CRYPTO_SPOT_RE.match(upper):
        base = match.group("base")
        quote = match.group("quote")
        normalized = f"{base}-{quote}"
        return ResolvedInstrument(
            input_symbol=raw,
            normalized_symbol=normalized,
            market="crypto",
            instrument_type="spot",
            exchange=exchange_value or "okx",
            base_asset=base,
            quote_asset=quote,
            provider_symbols={
                "okx": normalized,
                "ccxt": f"{base}/{quote}",
            },
        )

    compact = _compact_crypto_split(upper)
    if compact:
        base, quote = compact
        normalized = f"{base}-{quote}"
        return ResolvedInstrument(
            input_symbol=raw,
            normalized_symbol=normalized,
            market="crypto",
            instrument_type="spot",
            exchange=exchange_value or "okx",
            base_asset=base,
            quote_asset=quote,
            provider_symbols={
                "okx": normalized,
                "ccxt": f"{base}/{quote}",
            },
        )

    if _A_SHARE_RE.match(upper):
        return ResolvedInstrument(
            input_symbol=raw,
            normalized_symbol=upper,
            market="a_share",
            instrument_type="equity",
            exchange=exchange_value or upper.rsplit(".", 1)[-1].lower(),
            base_asset=None,
            quote_asset=None,
            provider_symbols={
                "tushare": upper,
                "akshare": upper,
            },
        )

    if _HK_RE.match(upper):
        digits = upper.split(".", 1)[0]
        normalized = f"{digits.zfill(max(4, len(digits)))}.HK"
        return ResolvedInstrument(
            input_symbol=raw,
            normalized_symbol=normalized,
            market="hk_equity",
            instrument_type="equity",
            exchange=exchange_value or "hk",
            base_asset=None,
            quote_asset=None,
            provider_symbols={
                "yfinance": normalized,
                "akshare": normalized,
            },
        )

    if _US_EXPLICIT_RE.match(upper):
        ticker = upper[:-3]
        normalized = f"{ticker}.US"
        return ResolvedInstrument(
            input_symbol=raw,
            normalized_symbol=normalized,
            market="us_equity",
            instrument_type="equity",
            exchange=exchange_value or "us",
            base_asset=None,
            quote_asset=None,
            provider_symbols={
                "yfinance": ticker,
                "akshare": normalized,
            },
        )

    if _US_PLAIN_RE.match(upper):
        normalized = f"{upper}.US"
        return ResolvedInstrument(
            input_symbol=raw,
            normalized_symbol=normalized,
            market="us_equity",
            instrument_type="equity",
            exchange=exchange_value or "us",
            base_asset=None,
            quote_asset=None,
            provider_symbols={
                "yfinance": upper,
                "akshare": normalized,
            },
        )

    raise ValueError(
        f"Unable to resolve symbol '{raw}'. Use forms like AAPL, 0700.HK, 000001.SZ, BTC-USDT, or BTC/USDT:USDT."
    )


def ensure_derivatives_symbol(resolved: ResolvedInstrument) -> ResolvedInstrument:
    if resolved.market != "crypto":
        raise MarketDataNotSupported("Funding rates and open interest are only supported for crypto instruments")
    if resolved.instrument_type == "perpetual":
        return resolved
    if not resolved.base_asset or not resolved.quote_asset:
        raise MarketDataNotSupported("Unable to derive a perpetual symbol for this crypto instrument")
    normalized = f"{resolved.base_asset}-{resolved.quote_asset}-SWAP"
    return ResolvedInstrument(
        input_symbol=resolved.input_symbol,
        normalized_symbol=normalized,
        market=resolved.market,
        instrument_type="perpetual",
        exchange=resolved.exchange,
        base_asset=resolved.base_asset,
        quote_asset=resolved.quote_asset,
        provider_symbols={
            "okx": normalized,
            "ccxt": f"{resolved.base_asset}/{resolved.quote_asset}:{resolved.quote_asset}",
        },
    )


def _lookback_dates(limit: int, interval: str) -> tuple[str, str]:
    interval_days = {
        "1m": max(2, math.ceil(limit / 1440) + 2),
        "3m": max(2, math.ceil(limit / 480) + 2),
        "5m": max(2, math.ceil(limit / 288) + 2),
        "15m": max(4, math.ceil(limit / 96) + 4),
        "30m": max(8, math.ceil(limit / 48) + 8),
        "1h": max(16, math.ceil(limit / 24) + 16),
        "4h": max(32, math.ceil(limit / 6) + 32),
        "1d": max(365, limit * 3),
        "1w": max(365, limit * 14),
        "1mo": max(365 * 5, limit * 45),
    }
    end_dt = _utc_now()
    start_dt = end_dt - timedelta(days=interval_days.get(interval, 365))
    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def _records_from_frame(frame: Any) -> list[dict[str, Any]]:
    import pandas as pd

    normalized = frame.copy()
    normalized = normalized.rename(
        columns={
            "Datetime": "timestamp",
            "Date": "timestamp",
            "trade_date": "timestamp",
            "trade_time": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }
    )

    if "timestamp" not in normalized.columns:
        if getattr(normalized.index, "name", None):
            normalized = normalized.reset_index().rename(columns={normalized.index.name: "timestamp"})
        else:
            normalized = normalized.reset_index().rename(columns={"index": "timestamp"})

    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True, errors="coerce")
    normalized = normalized.dropna(subset=["timestamp"])

    for column in ("open", "high", "low", "close", "volume"):
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if "volume" not in normalized.columns:
        normalized["volume"] = 0.0

    normalized = normalized.dropna(subset=["open", "high", "low", "close"])
    records = normalized.to_dict(orient="records")
    cleaned: list[dict[str, Any]] = []
    for record in records:
        cleaned.append(
            {
                "timestamp": _iso(record["timestamp"]),
                "open": _to_float(record.get("open")),
                "high": _to_float(record.get("high")),
                "low": _to_float(record.get("low")),
                "close": _to_float(record.get("close")),
                "volume": _to_float(record.get("volume")) or 0.0,
            }
        )
    return cleaned


class YFinanceMarketProvider:
    name = "yfinance"
    markets = {"us_equity", "hk_equity"}

    def is_available(self) -> bool:
        return importlib.util.find_spec("yfinance") is not None

    async def get_ohlcv(self, resolved: ResolvedInstrument, *, interval: str, limit: int) -> dict[str, Any]:
        if resolved.market not in self.markets:
            raise MarketDataNotSupported("yfinance only supports US and HK equities")
        return await asyncio.to_thread(self._get_ohlcv_sync, resolved, interval, limit)

    def _get_ohlcv_sync(self, resolved: ResolvedInstrument, interval: str, limit: int) -> dict[str, Any]:
        import pandas as pd
        import yfinance as yf

        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "1h",
            "1d": "1d",
            "1w": "1wk",
            "1mo": "1mo",
        }
        period_map = {
            "1m": "7d",
            "5m": "60d",
            "15m": "60d",
            "30m": "60d",
            "1h": "730d",
            "4h": "730d",
            "1d": "max",
            "1w": "max",
            "1mo": "max",
        }
        ticker = yf.Ticker(_provider_symbol(resolved.provider_symbols, self.name))
        frame = ticker.history(period=period_map[interval], interval=interval_map[interval], auto_adjust=False)
        if frame is None or frame.empty:
            raise ValueError(f"yfinance returned no OHLCV data for {resolved.normalized_symbol}")
        if interval == "4h":
            frame = frame.resample("4h").agg(
                {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
            )
            frame = frame.dropna(subset=["Open", "High", "Low", "Close"])
        records = _records_from_frame(frame.tail(limit))
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "interval": interval,
            "count": len(records),
            "candles": records,
        }

    async def get_ticker(self, resolved: ResolvedInstrument) -> dict[str, Any]:
        if resolved.market not in self.markets:
            raise MarketDataNotSupported("yfinance only supports US and HK equities")
        return await asyncio.to_thread(self._get_ticker_sync, resolved)

    def _get_ticker_sync(self, resolved: ResolvedInstrument) -> dict[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(_provider_symbol(resolved.provider_symbols, self.name))
        last_timestamp = None
        history = ticker.history(period="5d", interval="1d", auto_adjust=False)
        if history is not None and not history.empty:
            latest = history.iloc[-1]
            last_timestamp = history.index[-1]
            fallback = {
                "last": _to_float(latest.get("Close")),
                "open": _to_float(latest.get("Open")),
                "high": _to_float(latest.get("High")),
                "low": _to_float(latest.get("Low")),
                "volume": _to_float(latest.get("Volume")),
            }
        else:
            fallback = {"last": None, "open": None, "high": None, "low": None, "volume": None}

        fast_info = getattr(ticker, "fast_info", None) or {}
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "timestamp": _iso(last_timestamp) if last_timestamp is not None else None,
            "last": _to_float(fast_info.get("lastPrice")) or fallback["last"],
            "bid": _to_float(fast_info.get("bid")),
            "ask": _to_float(fast_info.get("ask")),
            "open": _to_float(fast_info.get("open")) or fallback["open"],
            "high": _to_float(fast_info.get("dayHigh")) or fallback["high"],
            "low": _to_float(fast_info.get("dayLow")) or fallback["low"],
            "previous_close": _to_float(fast_info.get("previousClose")),
            "volume": _to_float(fast_info.get("lastVolume")) or fallback["volume"],
            "currency": fast_info.get("currency"),
        }

    async def get_orderbook(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("yfinance does not expose public order book depth")

    async def get_funding_rate(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("Funding rates are only supported for crypto derivatives")

    async def get_open_interest(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("Open interest is only supported for crypto derivatives")


class AkshareMarketProvider:
    name = "akshare"
    markets = {"a_share", "us_equity", "hk_equity"}

    def is_available(self) -> bool:
        return importlib.util.find_spec("akshare") is not None

    async def get_ohlcv(self, resolved: ResolvedInstrument, *, interval: str, limit: int) -> dict[str, Any]:
        if resolved.market not in self.markets:
            raise MarketDataNotSupported("akshare only supports equity-style markets in this runtime")
        return await asyncio.to_thread(self._get_ohlcv_sync, resolved, interval, limit)

    def _get_ohlcv_sync(self, resolved: ResolvedInstrument, interval: str, limit: int) -> dict[str, Any]:
        import akshare as ak
        import pandas as pd

        if interval not in {"1d", "1w", "1mo"}:
            raise MarketDataNotSupported("akshare fallback currently supports daily, weekly, and monthly OHLCV only")

        start_date, end_date = _lookback_dates(limit, interval)
        period = {"1d": "daily", "1w": "weekly", "1mo": "monthly"}[interval]

        if resolved.market == "a_share":
            symbol = resolved.normalized_symbol.split(".", 1)[0]
            frame = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq",
            )
        elif resolved.market == "us_equity":
            symbol = resolved.normalized_symbol[:-3]
            frame = None
            for prefix in ("105.", "106.", ""):
                try:
                    candidate = ak.stock_us_hist(
                        symbol=f"{prefix}{symbol}",
                        period="daily",
                        start_date=start_date.replace("-", ""),
                        end_date=end_date.replace("-", ""),
                        adjust="qfq",
                    )
                except Exception:
                    continue
                if candidate is not None and not candidate.empty:
                    frame = candidate
                    break
        else:
            symbol = resolved.normalized_symbol.replace(".HK", "")
            frame = ak.stock_hk_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq",
            )

        if frame is None or frame.empty:
            raise ValueError(f"akshare returned no OHLCV data for {resolved.normalized_symbol}")

        frame = frame.rename(columns={"日期": "trade_date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"})
        if "trade_date" not in frame.columns and "date" in frame.columns:
            frame = frame.rename(columns={"date": "trade_date"})
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        frame = frame.set_index("trade_date").sort_index()
        records = _records_from_frame(frame.tail(limit))
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "interval": interval,
            "count": len(records),
            "candles": records,
        }

    async def get_ticker(self, resolved: ResolvedInstrument) -> dict[str, Any]:
        payload = await self.get_ohlcv(resolved, interval="1d", limit=2)
        candles = payload["candles"]
        latest = candles[-1] if candles else {}
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "timestamp": latest.get("timestamp"),
            "last": latest.get("close"),
            "open": latest.get("open"),
            "high": latest.get("high"),
            "low": latest.get("low"),
            "volume": latest.get("volume"),
            "bid": None,
            "ask": None,
            "previous_close": candles[-2]["close"] if len(candles) > 1 else None,
        }

    async def get_orderbook(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("akshare order book support is not wired in this runtime")

    async def get_funding_rate(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("Funding rates are only supported for crypto derivatives")

    async def get_open_interest(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("Open interest is only supported for crypto derivatives")


class TushareMarketProvider:
    name = "tushare"
    markets = {"a_share"}

    def is_available(self) -> bool:
        return bool(os.getenv("TUSHARE_TOKEN")) and importlib.util.find_spec("tushare") is not None

    async def get_ohlcv(self, resolved: ResolvedInstrument, *, interval: str, limit: int) -> dict[str, Any]:
        if resolved.market not in self.markets:
            raise MarketDataNotSupported("tushare is only used for A-share instruments in this runtime")
        return await asyncio.to_thread(self._get_ohlcv_sync, resolved, interval, limit)

    def _get_client(self):
        import tushare as ts

        token = os.getenv("TUSHARE_TOKEN", "").strip()
        if not token:
            raise ValueError("TUSHARE_TOKEN is not configured")
        return ts.pro_api(token)

    def _get_ohlcv_sync(self, resolved: ResolvedInstrument, interval: str, limit: int) -> dict[str, Any]:
        import pandas as pd

        api = self._get_client()
        start_date, end_date = _lookback_dates(limit, interval)

        if interval == "1d":
            frame = api.daily(
                ts_code=resolved.normalized_symbol,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            if frame is None or frame.empty:
                raise ValueError(f"tushare returned no OHLCV data for {resolved.normalized_symbol}")
            frame = frame.sort_values("trade_date")
            frame["trade_date"] = pd.to_datetime(frame["trade_date"])
            frame = frame.rename(columns={"vol": "volume"}).set_index("trade_date")
        else:
            freq_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "60min"}
            freq = freq_map.get(interval)
            if not freq:
                raise MarketDataNotSupported("tushare intraday support is limited to 1m/5m/15m/30m/1h")
            frame = api.stk_mins(
                ts_code=resolved.normalized_symbol,
                freq=freq,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            if frame is None or frame.empty:
                raise ValueError(f"tushare returned no intraday data for {resolved.normalized_symbol}")
            frame = frame.sort_values("trade_time")
            frame["trade_time"] = pd.to_datetime(frame["trade_time"])
            frame = frame.rename(columns={"trade_time": "timestamp", "vol": "volume"}).set_index("timestamp")

        records = _records_from_frame(frame.tail(limit))
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "interval": interval,
            "count": len(records),
            "candles": records,
        }

    async def get_ticker(self, resolved: ResolvedInstrument) -> dict[str, Any]:
        payload = await self.get_ohlcv(resolved, interval="1d", limit=2)
        candles = payload["candles"]
        latest = candles[-1] if candles else {}
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "timestamp": latest.get("timestamp"),
            "last": latest.get("close"),
            "open": latest.get("open"),
            "high": latest.get("high"),
            "low": latest.get("low"),
            "volume": latest.get("volume"),
            "bid": None,
            "ask": None,
            "previous_close": candles[-2]["close"] if len(candles) > 1 else None,
        }

    async def get_orderbook(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("tushare order book support is not wired in this runtime")

    async def get_funding_rate(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("Funding rates are only supported for crypto derivatives")

    async def get_open_interest(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("Open interest is only supported for crypto derivatives")


class OKXMarketProvider:
    name = "okx"
    markets = {"crypto"}
    _base_url = "https://www.okx.com/api/v5"

    def is_available(self) -> bool:
        return True

    async def _request(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]] | list[list[str]]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, trust_env=False) as client:
            response = await client.get(f"{self._base_url}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") != "0":
            raise ValueError(payload.get("msg") or f"OKX request failed for {path}")
        return payload.get("data") or []

    async def get_ohlcv(self, resolved: ResolvedInstrument, *, interval: str, limit: int) -> dict[str, Any]:
        if resolved.market != "crypto":
            raise MarketDataNotSupported("OKX only supports crypto instruments")
        bar_map = {
            "1m": "1m",
            "3m": "3m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
            "1w": "1W",
            "1mo": "1M",
        }
        inst_id = _provider_symbol(resolved.provider_symbols, self.name)
        rows: list[list[str]] = []
        cursor: str | None = None
        remaining = max(1, min(int(limit), 1200))
        while remaining > 0:
            page_size = min(remaining, 300)
            params = {"instId": inst_id, "bar": bar_map[interval], "limit": str(page_size)}
            if cursor:
                params["after"] = cursor
            page = await self._request("/market/candles", params)
            if not page:
                break
            typed_page = [row for row in page if isinstance(row, list)]
            rows.extend(typed_page)
            remaining -= len(typed_page)
            if len(typed_page) < page_size:
                break
            cursor = typed_page[-1][0]
        if not rows:
            raise ValueError(f"OKX returned no OHLCV data for {inst_id}")
        records = [
            {
                "timestamp": datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC).isoformat(),
                "open": _to_float(row[1]),
                "high": _to_float(row[2]),
                "low": _to_float(row[3]),
                "close": _to_float(row[4]),
                "volume": _to_float(row[5]) or 0.0,
            }
            for row in reversed(rows[:limit])
        ]
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "interval": interval,
            "count": len(records),
            "candles": records,
        }

    async def get_ticker(self, resolved: ResolvedInstrument) -> dict[str, Any]:
        if resolved.market != "crypto":
            raise MarketDataNotSupported("OKX only supports crypto instruments")
        inst_id = _provider_symbol(resolved.provider_symbols, self.name)
        data = await self._request("/market/ticker", {"instId": inst_id})
        if not data:
            raise ValueError(f"OKX returned no ticker data for {inst_id}")
        row = data[0]
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "timestamp": datetime.fromtimestamp(int(row["ts"]) / 1000, tz=UTC).isoformat() if row.get("ts") else None,
            "last": _to_float(row.get("last")),
            "bid": _to_float(row.get("bidPx")),
            "ask": _to_float(row.get("askPx")),
            "open": _to_float(row.get("open24h")),
            "high": _to_float(row.get("high24h")),
            "low": _to_float(row.get("low24h")),
            "volume": _to_float(row.get("vol24h")),
            "previous_close": None,
        }

    async def get_orderbook(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        if resolved.market != "crypto":
            raise MarketDataNotSupported("OKX order books are only supported for crypto instruments")
        inst_id = _provider_symbol(resolved.provider_symbols, self.name)
        depth = max(1, min(int(limit), 400))
        data = await self._request("/market/books", {"instId": inst_id, "sz": str(depth)})
        if not data:
            raise ValueError(f"OKX returned no order book for {inst_id}")
        row = data[0]
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "timestamp": datetime.fromtimestamp(int(row["ts"]) / 1000, tz=UTC).isoformat() if row.get("ts") else None,
            "depth": depth,
            "bids": [[_to_float(price), _to_float(size)] for price, size, *_ in row.get("bids", [])[:depth]],
            "asks": [[_to_float(price), _to_float(size)] for price, size, *_ in row.get("asks", [])[:depth]],
        }

    async def get_funding_rate(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        derivatives = ensure_derivatives_symbol(resolved)
        inst_id = _provider_symbol(derivatives.provider_symbols, self.name)
        current = await self._request("/public/funding-rate", {"instId": inst_id})
        history = await self._request("/public/funding-rate-history", {"instId": inst_id, "limit": str(min(int(limit), 100))})
        current_row = current[0] if current else {}
        history_rows = [
            {
                "timestamp": datetime.fromtimestamp(int(row["fundingTime"]) / 1000, tz=UTC).isoformat()
                if row.get("fundingTime")
                else None,
                "funding_rate": _to_float(row.get("fundingRate")),
                "realized_rate": _to_float(row.get("realizedRate")),
            }
            for row in reversed(history)
        ]
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": derivatives.normalized_symbol,
            "market": resolved.market,
            "current": {
                "timestamp": datetime.fromtimestamp(int(current_row["fundingTime"]) / 1000, tz=UTC).isoformat()
                if current_row.get("fundingTime")
                else None,
                "funding_rate": _to_float(current_row.get("fundingRate")),
                "next_funding_time": datetime.fromtimestamp(int(current_row["nextFundingTime"]) / 1000, tz=UTC).isoformat()
                if current_row.get("nextFundingTime")
                else None,
            },
            "history": history_rows,
            "count": len(history_rows),
        }

    async def get_open_interest(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        del limit
        derivatives = ensure_derivatives_symbol(resolved)
        inst_id = _provider_symbol(derivatives.provider_symbols, self.name)
        data = await self._request("/public/open-interest", {"instType": "SWAP", "instId": inst_id})
        if not data:
            raise ValueError(f"OKX returned no open-interest data for {inst_id}")
        row = data[0]
        point = {
            "timestamp": datetime.fromtimestamp(int(row["ts"]) / 1000, tz=UTC).isoformat() if row.get("ts") else None,
            "open_interest": _to_float(row.get("oi")),
            "open_interest_ccy": _to_float(row.get("oiCcy")),
            "open_interest_usd": _to_float(row.get("oiUsd")),
        }
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": derivatives.normalized_symbol,
            "market": resolved.market,
            "points": [point],
            "count": 1,
        }


class CCXTMarketProvider:
    name = "ccxt"
    markets = {"crypto"}

    def is_available(self) -> bool:
        return importlib.util.find_spec("ccxt") is not None

    def _exchange_id(self, exchange: str | None = None) -> str:
        return str(exchange or os.getenv("CCXT_EXCHANGE", "binance")).strip().lower()

    def _exchange(self, exchange: str | None = None):
        import ccxt

        exchange_id = self._exchange_id(exchange)
        exchange_cls = getattr(ccxt, exchange_id, None)
        if exchange_cls is None:
            raise ValueError(f"Unknown CCXT exchange: {exchange_id}")
        return exchange_cls({"enableRateLimit": True})

    async def get_ohlcv(self, resolved: ResolvedInstrument, *, interval: str, limit: int) -> dict[str, Any]:
        if resolved.market != "crypto":
            raise MarketDataNotSupported("CCXT only supports crypto instruments")
        return await asyncio.to_thread(self._get_ohlcv_sync, resolved, interval, limit)

    def _get_ohlcv_sync(self, resolved: ResolvedInstrument, interval: str, limit: int) -> dict[str, Any]:
        exchange = self._exchange(resolved.exchange)
        timeframe_map = {
            "1m": "1m",
            "3m": "3m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
            "1w": "1w",
            "1mo": "1M",
        }
        symbol = _provider_symbol(resolved.provider_symbols, self.name)
        rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe_map[interval], limit=max(1, min(int(limit), 1000)))
        if not rows:
            raise ValueError(f"CCXT returned no OHLCV data for {symbol}")
        records = [
            {
                "timestamp": datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC).isoformat(),
                "open": _to_float(row[1]),
                "high": _to_float(row[2]),
                "low": _to_float(row[3]),
                "close": _to_float(row[4]),
                "volume": _to_float(row[5]) or 0.0,
            }
            for row in rows[-limit:]
        ]
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "interval": interval,
            "count": len(records),
            "candles": records,
        }

    async def get_ticker(self, resolved: ResolvedInstrument) -> dict[str, Any]:
        if resolved.market != "crypto":
            raise MarketDataNotSupported("CCXT only supports crypto instruments")
        return await asyncio.to_thread(self._get_ticker_sync, resolved)

    def _get_ticker_sync(self, resolved: ResolvedInstrument) -> dict[str, Any]:
        exchange = self._exchange(resolved.exchange)
        symbol = _provider_symbol(resolved.provider_symbols, self.name)
        row = exchange.fetch_ticker(symbol)
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "timestamp": datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=UTC).isoformat()
            if row.get("timestamp")
            else None,
            "last": _to_float(row.get("last")),
            "bid": _to_float(row.get("bid")),
            "ask": _to_float(row.get("ask")),
            "open": _to_float(row.get("open")),
            "high": _to_float(row.get("high")),
            "low": _to_float(row.get("low")),
            "volume": _to_float(row.get("baseVolume")) or _to_float(row.get("quoteVolume")),
            "previous_close": _to_float(row.get("previousClose")),
        }

    async def get_orderbook(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        if resolved.market != "crypto":
            raise MarketDataNotSupported("CCXT only supports crypto order books")
        return await asyncio.to_thread(self._get_orderbook_sync, resolved, limit)

    def _get_orderbook_sync(self, resolved: ResolvedInstrument, limit: int) -> dict[str, Any]:
        exchange = self._exchange(resolved.exchange)
        symbol = _provider_symbol(resolved.provider_symbols, self.name)
        depth = max(1, min(int(limit), 200))
        row = exchange.fetch_order_book(symbol, depth)
        timestamp = row.get("timestamp")
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "timestamp": datetime.fromtimestamp(int(timestamp) / 1000, tz=UTC).isoformat() if timestamp else None,
            "depth": depth,
            "bids": [[_to_float(price), _to_float(size)] for price, size in row.get("bids", [])[:depth]],
            "asks": [[_to_float(price), _to_float(size)] for price, size in row.get("asks", [])[:depth]],
        }

    async def get_funding_rate(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("CCXT funding-rate fallback is not wired in this runtime")

    async def get_open_interest(self, resolved: ResolvedInstrument, *, limit: int) -> dict[str, Any]:
        raise MarketDataNotSupported("CCXT open-interest fallback is not wired in this runtime")


_MARKET_PROVIDER_FACTORIES = {
    "tushare": TushareMarketProvider,
    "akshare": AkshareMarketProvider,
    "yfinance": YFinanceMarketProvider,
    "okx": OKXMarketProvider,
    "ccxt": CCXTMarketProvider,
}

_MARKET_FALLBACK_CHAINS = {
    "a_share": ["tushare", "akshare"],
    "us_equity": ["yfinance", "akshare"],
    "hk_equity": ["yfinance", "akshare"],
    "crypto": ["okx", "ccxt"],
}


class MarketDataRouter:
    """Provider-backed market router with market-level fallback chains."""

    def resolve_symbol(self, symbol: str, exchange: str | None = None) -> ToolEnvelope:
        resolved = resolve_instrument(symbol, exchange=exchange)
        return build_tool_envelope(
            tool="market.resolve_symbol",
            provider="motis_router",
            data=resolved.to_dict(),
        )

    async def get_ohlcv(self, symbol: str, interval: str, limit: int = 200, exchange: str | None = None) -> ToolEnvelope:
        resolved = resolve_instrument(symbol, exchange=exchange)
        return await self._dispatch_chain(
            tool="market.get_ohlcv",
            resolved=resolved,
            request={"symbol": symbol, "interval": interval, "limit": limit, "exchange": exchange},
            operation="get_ohlcv",
            interval=_normalize_interval(interval),
            limit=max(1, min(int(limit), 2000)),
        )

    async def get_ticker(self, symbol: str, exchange: str | None = None) -> ToolEnvelope:
        resolved = resolve_instrument(symbol, exchange=exchange)
        return await self._dispatch_chain(
            tool="market.get_ticker",
            resolved=resolved,
            request={"symbol": symbol, "exchange": exchange},
            operation="get_ticker",
        )

    async def get_orderbook(self, symbol: str, limit: int = 20, exchange: str | None = None) -> ToolEnvelope:
        resolved = resolve_instrument(symbol, exchange=exchange)
        return await self._dispatch_chain(
            tool="market.get_orderbook",
            resolved=resolved,
            request={"symbol": symbol, "limit": limit, "exchange": exchange},
            operation="get_orderbook",
            limit=max(1, min(int(limit), 400)),
        )

    async def get_funding_rate(self, symbol: str, limit: int = 50, exchange: str | None = None) -> ToolEnvelope:
        resolved = resolve_instrument(symbol, exchange=exchange)
        return await self._dispatch_chain(
            tool="market.get_funding_rate",
            resolved=resolved,
            request={"symbol": symbol, "limit": limit, "exchange": exchange},
            operation="get_funding_rate",
            limit=max(1, min(int(limit), 100)),
        )

    async def get_open_interest(self, symbol: str, limit: int = 50, exchange: str | None = None) -> ToolEnvelope:
        resolved = resolve_instrument(symbol, exchange=exchange)
        return await self._dispatch_chain(
            tool="market.get_open_interest",
            resolved=resolved,
            request={"symbol": symbol, "limit": limit, "exchange": exchange},
            operation="get_open_interest",
            limit=max(1, min(int(limit), 100)),
        )

    async def _dispatch_chain(
        self,
        *,
        tool: str,
        resolved: ResolvedInstrument,
        request: dict[str, Any],
        operation: str,
        **kwargs: Any,
    ) -> ToolEnvelope:
        chain = _MARKET_FALLBACK_CHAINS.get(resolved.market, [])
        warnings: list[str] = []
        unsupported = 0

        for provider_name in chain:
            factory = _MARKET_PROVIDER_FACTORIES.get(provider_name)
            if factory is None:
                warnings.append(f"{provider_name}: provider is not registered")
                continue
            provider = factory()
            if not provider.is_available():
                warnings.append(f"{provider_name}: provider is unavailable in this runtime")
                continue
            try:
                handler = getattr(provider, operation)
                payload = await handler(resolved, **kwargs)
                return build_tool_envelope(
                    tool=tool,
                    provider=provider.name,
                    data={**payload, "resolved": resolved.to_dict()},
                    warnings=warnings,
                )
            except MarketDataNotSupported as exc:
                unsupported += 1
                warnings.append(f"{provider_name}: {exc}")
            except Exception as exc:
                warnings.append(f"{provider_name}: {exc}")

        if chain and unsupported == len(chain):
            return build_not_implemented_envelope(
                tool=tool,
                provider="motis_router",
                request={**request, "resolved": resolved.to_dict()},
                message=f"No provider in the {resolved.market} fallback chain supports {tool} yet.",
            )

        return build_tool_envelope(
            tool=tool,
            provider="motis_router",
            status="error",
            data={"request": request, "resolved": resolved.to_dict()},
            warnings=warnings,
            error={
                "code": "no_provider_available",
                "message": f"Motis could not satisfy {tool} for {resolved.normalized_symbol} from the current provider chain.",
            },
        )
