"""Structured research-data routing for Motis Data MCP."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from typing import Any

import httpx

from motis_data_mcp.contracts import ToolEnvelope, build_not_implemented_envelope, build_tool_envelope
from motis_data_mcp.providers.market import ResolvedInstrument, resolve_instrument


class ResearchDataNotSupported(RuntimeError):
    """Raised when a research provider cannot serve the requested operation."""


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _clean_date(value: Any) -> str | None:
    text = _clean_str(value)
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _ymd(value: Any) -> str | None:
    cleaned = _clean_date(value)
    return cleaned.replace("-", "") if cleaned else None


def _to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_of_date(value: Any) -> str | None:
    cleaned = _clean_date(value)
    if cleaned:
        return cleaned
    return None


def _safe_date_string(value: Any) -> str | None:
    try:
        import pandas as pd

        timestamp = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if getattr(timestamp, "isna", lambda: False)():
        return None
    if hasattr(timestamp, "strftime"):
        return timestamp.strftime("%Y-%m-%d")
    return _clean_date(timestamp)


def _normalize_country(country: str | None) -> str:
    normalized = _clean_str(country).lower()
    aliases = {
        "cn": "china",
        "china": "china",
        "prc": "china",
        "us": "us",
        "usa": "us",
        "united_states": "us",
        "united states": "us",
    }
    return aliases.get(normalized, normalized or "us")


def _normalize_fields(fields: list[str] | None) -> list[str]:
    return [field for field in (_clean_str(item) for item in (fields or [])) if field]


def _default_fundamental_fields() -> list[str]:
    return [
        "market_cap",
        "trailing_pe",
        "forward_pe",
        "price_to_book",
        "dividend_yield",
        "roe",
        "roa",
        "revenue_growth",
        "earnings_growth",
        "gross_margin",
        "operating_margin",
        "profit_margin",
        "current_ratio",
        "debt_to_equity",
    ]


def _pick_first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in {None, ""}:
            return record[key]
    return None


def _slice_by_date(records: list[dict[str, Any]], key: str, *, start_date: str | None, end_date: str | None) -> list[dict[str, Any]]:
    if not start_date and not end_date:
        return records

    start = _clean_date(start_date)
    end = _clean_date(end_date)
    filtered: list[dict[str, Any]] = []
    for record in records:
        value = _clean_date(record.get(key))
        if not value:
            continue
        if start and value < start:
            continue
        if end and value > end:
            continue
        filtered.append(record)
    return filtered


class FredMacroProvider:
    name = "fred"
    _series_ids = {
        ("us", "cpi"): "CPIAUCSL",
        ("us", "gdp"): "GDP",
        ("us", "unemployment"): "UNRATE",
        ("us", "fed_funds"): "FEDFUNDS",
        ("us", "ppi"): "PPIACO",
    }

    def is_available(self) -> bool:
        return True

    def supports(self, country: str, series: str) -> bool:
        return (country, series) in self._series_ids

    async def get_series(
        self,
        *,
        series: str,
        country: str,
        start_date: str | None,
        end_date: str | None,
        frequency: str | None,
    ) -> dict[str, Any]:
        del frequency
        series_id = self._series_ids.get((country, series))
        if not series_id:
            raise ResearchDataNotSupported(f"FRED does not map series '{series}' for country '{country}'")

        url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, trust_env=False) as client:
            response = await client.get(url, params={"id": series_id})
            response.raise_for_status()

        import pandas as pd

        frame = pd.read_csv(StringIO(response.text))
        if frame.empty or "DATE" not in frame.columns:
            raise ValueError(f"FRED returned no rows for {series_id}")
        frame = frame.rename(columns={"DATE": "date", series_id: "value"})
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        frame = frame.dropna(subset=["date", "value"])

        records = [
            {"date": row["date"], "value": _to_float(row["value"])}
            for _, row in frame.iterrows()
        ]
        records = _slice_by_date(records, "date", start_date=start_date, end_date=end_date)

        return {
            "series": series,
            "country": country,
            "source_series_id": series_id,
            "frequency": "unknown",
            "points": records,
            "count": len(records),
        }


class AkshareMacroProvider:
    name = "akshare"
    _series_map = {
        ("china", "cpi"): "macro_china_cpi",
        ("china", "gdp"): "macro_china_gdp",
    }

    def is_available(self) -> bool:
        return importlib.util.find_spec("akshare") is not None

    def supports(self, country: str, series: str) -> bool:
        return (country, series) in self._series_map

    async def get_series(
        self,
        *,
        series: str,
        country: str,
        start_date: str | None,
        end_date: str | None,
        frequency: str | None,
    ) -> dict[str, Any]:
        del frequency
        fn_name = self._series_map.get((country, series))
        if not fn_name:
            raise ResearchDataNotSupported(f"Akshare does not map series '{series}' for country '{country}'")
        return await asyncio.to_thread(self._get_series_sync, fn_name, series, country, start_date, end_date)

    def _get_series_sync(
        self,
        fn_name: str,
        series: str,
        country: str,
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, Any]:
        import akshare as ak
        import pandas as pd

        frame = getattr(ak, fn_name)()
        if frame is None or frame.empty:
            raise ValueError(f"Akshare returned no rows for {country}:{series}")

        date_col = None
        for candidate in ("日期", "date", "Date", "月份", "季度"):
            if candidate in frame.columns:
                date_col = candidate
                break
        if date_col is None:
            date_col = frame.columns[0]

        value_col = None
        for column in frame.columns:
            if column == date_col:
                continue
            numeric = pd.to_numeric(frame[column], errors="coerce")
            if numeric.notna().sum() > 0:
                value_col = column
                break
        if value_col is None:
            raise ValueError(f"Akshare did not expose a numeric value column for {country}:{series}")

        normalized = frame[[date_col, value_col]].copy()
        normalized["date"] = pd.to_datetime(normalized[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
        normalized["value"] = pd.to_numeric(normalized[value_col], errors="coerce")
        normalized = normalized.dropna(subset=["date", "value"])

        records = [
            {"date": row["date"], "value": _to_float(row["value"])}
            for _, row in normalized.iterrows()
        ]
        records = _slice_by_date(records, "date", start_date=start_date, end_date=end_date)

        return {
            "series": series,
            "country": country,
            "source_series_id": fn_name,
            "frequency": "unknown",
            "points": records,
            "count": len(records),
        }


class YFinanceResearchProvider:
    name = "yfinance"

    def is_available(self) -> bool:
        return importlib.util.find_spec("yfinance") is not None

    async def get_fundamentals(
        self,
        resolved: ResolvedInstrument,
        *,
        fields: list[str],
        as_of: str | None,
        frequency: str | None,
    ) -> dict[str, Any]:
        if resolved.market not in {"us_equity", "hk_equity"}:
            raise ResearchDataNotSupported("yfinance fundamentals are only used for US and HK equities")
        return await asyncio.to_thread(self._get_fundamentals_sync, resolved, fields, as_of, frequency)

    def _get_fundamentals_sync(
        self,
        resolved: ResolvedInstrument,
        fields: list[str],
        as_of: str | None,
        frequency: str | None,
    ) -> dict[str, Any]:
        import yfinance as yf

        ticker = yf.Ticker(resolved.provider_symbols["yfinance"])
        info = getattr(ticker, "info", None) or {}
        fast_info = getattr(ticker, "fast_info", None) or {}
        selected_fields = fields or _default_fundamental_fields()
        field_map = {
            "market_cap": info.get("marketCap") or fast_info.get("marketCap"),
            "currency": info.get("currency") or fast_info.get("currency"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "current_ratio": info.get("currentRatio"),
            "debt_to_equity": info.get("debtToEquity"),
        }
        fundamentals = {field: _to_float(field_map.get(field)) if field not in {"currency", "sector", "industry"} else field_map.get(field) for field in selected_fields}
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "exchange": resolved.exchange,
            "as_of": as_of,
            "frequency": frequency,
            "fundamentals": fundamentals,
        }

    async def get_earnings_calendar(
        self,
        resolved: ResolvedInstrument,
        *,
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if resolved.market not in {"us_equity", "hk_equity"}:
            raise ResearchDataNotSupported("yfinance earnings calendar is only used for US and HK equities")
        return await asyncio.to_thread(self._get_earnings_calendar_sync, resolved, start_date, end_date, limit)

    def _get_earnings_calendar_sync(
        self,
        resolved: ResolvedInstrument,
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> dict[str, Any]:
        import pandas as pd
        import yfinance as yf

        ticker = yf.Ticker(resolved.provider_symbols["yfinance"])
        rows: list[dict[str, Any]] = []

        earnings_dates = getattr(ticker, "earnings_dates", None)
        if isinstance(earnings_dates, pd.DataFrame) and not earnings_dates.empty:
            frame = earnings_dates.reset_index()
            frame.columns = [str(column) for column in frame.columns]
            date_col = frame.columns[0]
            eps_estimate_col = next((column for column in frame.columns if "EPS Estimate" in column), None)
            reported_col = next((column for column in frame.columns if "Reported EPS" in column), None)
            surprise_col = next((column for column in frame.columns if "Surprise(%)" in column), None)
            for _, row in frame.iterrows():
                rows.append(
                    {
                        "symbol": resolved.input_symbol,
                        "normalized_symbol": resolved.normalized_symbol,
                        "market": resolved.market,
                        "event_date": _safe_date_string(row[date_col]),
                        "eps_estimate": _to_float(row.get(eps_estimate_col)) if eps_estimate_col else None,
                        "reported_eps": _to_float(row.get(reported_col)) if reported_col else None,
                        "surprise_pct": _to_float(row.get(surprise_col)) if surprise_col else None,
                        "source": self.name,
                    }
                )
        else:
            calendar = getattr(ticker, "calendar", None)
            if calendar is not None and hasattr(calendar, "to_dict"):
                calendar_dict = calendar.to_dict()
                event_date = calendar_dict.get("Earnings Date")
                if isinstance(event_date, list) and event_date:
                    event_date = event_date[0]
                rows.append(
                    {
                        "symbol": resolved.input_symbol,
                        "normalized_symbol": resolved.normalized_symbol,
                        "market": resolved.market,
                        "event_date": _safe_date_string(event_date),
                        "eps_estimate": _to_float(calendar_dict.get("EPS Estimate")),
                        "reported_eps": _to_float(calendar_dict.get("Reported EPS")),
                        "surprise_pct": None,
                        "source": self.name,
                    }
                )

        rows = [row for row in rows if row.get("event_date")]
        rows = _slice_by_date(rows, "event_date", start_date=start_date, end_date=end_date)
        rows = rows[: max(1, limit)]
        return {
            "symbols": [resolved.input_symbol],
            "count": len(rows),
            "events": rows,
        }


class TushareResearchProvider:
    name = "tushare"

    def is_available(self) -> bool:
        return importlib.util.find_spec("tushare") is not None and bool(os.getenv("TUSHARE_TOKEN"))

    def _client(self):
        import tushare as ts

        token = os.getenv("TUSHARE_TOKEN", "").strip()
        if not token:
            raise ResearchDataNotSupported("TUSHARE_TOKEN is not configured")
        return ts.pro_api(token)

    async def get_fundamentals(
        self,
        resolved: ResolvedInstrument,
        *,
        fields: list[str],
        as_of: str | None,
        frequency: str | None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_fundamentals_sync, resolved, fields, as_of, frequency)

    def _get_fundamentals_sync(
        self,
        resolved: ResolvedInstrument,
        fields: list[str],
        as_of: str | None,
        frequency: str | None,
    ) -> dict[str, Any]:
        import pandas as pd

        api = self._client()
        kwargs: dict[str, Any] = {"ts_code": resolved.normalized_symbol}
        if as_of:
            kwargs["period"] = _ymd(as_of)
        if frequency and str(frequency).upper().startswith("Q"):
            kwargs["report_type"] = str(frequency).upper()

        if resolved.market == "a_share":
            frame = api.fina_indicator(**kwargs)
        elif resolved.market == "hk_equity":
            frame = api.hk_fina_indicator(**kwargs)
        elif resolved.market == "us_equity":
            kwargs["ts_code"] = resolved.normalized_symbol[:-3]
            frame = api.us_fina_indicator(**kwargs)
        else:
            raise ResearchDataNotSupported(f"Tushare fundamentals do not support market '{resolved.market}'")

        if frame is None or frame.empty:
            raise ValueError(f"Tushare returned no fundamentals for {resolved.normalized_symbol}")

        latest = frame.iloc[0].to_dict()
        selected_fields = fields or _default_fundamental_fields()
        normalized = {
            "market_cap": _pick_first(latest, "total_market_cap", "market_cap"),
            "trailing_pe": _pick_first(latest, "pe_ttm"),
            "forward_pe": None,
            "price_to_book": _pick_first(latest, "pb_ttm"),
            "dividend_yield": _pick_first(latest, "dividend_rate"),
            "roe": _pick_first(latest, "roe", "roe_avg", "roe_waa"),
            "roa": _pick_first(latest, "roa"),
            "revenue_growth": _pick_first(latest, "operate_income_yoy"),
            "earnings_growth": _pick_first(latest, "parent_holder_netprofit_yoy", "holder_profit_yoy", "basic_eps_yoy"),
            "gross_margin": _pick_first(latest, "gross_profit_ratio", "gross_margin", "grossprofit_margin"),
            "operating_margin": _pick_first(latest, "operate_profit", "op_of_gr"),
            "profit_margin": _pick_first(latest, "net_profit_ratio", "netprofit_margin"),
            "current_ratio": _pick_first(latest, "current_ratio"),
            "debt_to_equity": _pick_first(latest, "debt_to_eqt", "debt_asset_ratio", "equity_ratio"),
            "currency": _pick_first(latest, "currency", "currency_abbr"),
        }
        fundamentals = {
            field: _to_float(normalized[field]) if field not in {"currency"} else normalized[field]
            for field in selected_fields
            if field in normalized
        }
        report_end = _as_of_date(_pick_first(latest, "end_date", "std_report_date"))
        return {
            "symbol": resolved.input_symbol,
            "normalized_symbol": resolved.normalized_symbol,
            "market": resolved.market,
            "exchange": resolved.exchange,
            "as_of": report_end or as_of,
            "frequency": frequency,
            "fundamentals": fundamentals,
        }

    async def get_earnings_calendar(
        self,
        resolved: ResolvedInstrument,
        *,
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_earnings_calendar_sync, resolved, start_date, end_date, limit)

    def _get_earnings_calendar_sync(
        self,
        resolved: ResolvedInstrument,
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> dict[str, Any]:
        api = self._client()

        if resolved.market == "a_share":
            frame = api.disclosure_date(ts_code=resolved.normalized_symbol)
            if frame is None or frame.empty:
                raise ValueError(f"Tushare returned no disclosure dates for {resolved.normalized_symbol}")
            events = [
                {
                    "symbol": resolved.input_symbol,
                    "normalized_symbol": resolved.normalized_symbol,
                    "market": resolved.market,
                    "event_date": _clean_date(_pick_first(row, "actual_date", "pre_date")),
                    "ann_date": _clean_date(row.get("ann_date")),
                    "report_period": _clean_date(row.get("end_date")),
                    "source": self.name,
                }
                for row in frame.to_dict(orient="records")
            ]
        else:
            raise ResearchDataNotSupported("Tushare earnings calendar is only wired for A-share disclosure dates")

        events = [event for event in events if event.get("event_date")]
        events = _slice_by_date(events, "event_date", start_date=start_date, end_date=end_date)
        events = events[: max(1, limit)]
        return {
            "symbols": [resolved.input_symbol],
            "count": len(events),
            "events": events,
        }

    async def get_connect(
        self,
        *,
        direction: str,
        symbols: list[str],
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_connect_sync, direction, symbols, start_date, end_date)

    def _get_connect_sync(
        self,
        direction: str,
        symbols: list[str],
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, Any]:
        api = self._client()

        daily = api.moneyflow_hsgt(
            start_date=_ymd(start_date) or _ymd(end_date) or datetime.now(UTC).strftime("%Y%m%d"),
            end_date=_ymd(end_date) or _ymd(start_date) or datetime.now(UTC).strftime("%Y%m%d"),
        )
        daily_records = []
        if daily is not None and not daily.empty:
            for row in daily.to_dict(orient="records"):
                daily_records.append(
                    {
                        "trade_date": _clean_date(row.get("trade_date")),
                        "northbound_flow_mn": _to_float(row.get("north_money")),
                        "southbound_flow_mn": _to_float(row.get("south_money")),
                        "hgt_mn": _to_float(row.get("hgt")),
                        "sgt_mn": _to_float(row.get("sgt")),
                        "ggt_ss_mn": _to_float(row.get("ggt_ss")),
                        "ggt_sz_mn": _to_float(row.get("ggt_sz")),
                    }
                )
        daily_records = _slice_by_date(daily_records, "trade_date", start_date=start_date, end_date=end_date)

        top_holdings: list[dict[str, Any]] = []
        if symbols:
            requested = {symbol.upper() for symbol in symbols}
            for market_type in ("1", "3"):
                frame = api.hsgt_top10(
                    start_date=_ymd(start_date) or _ymd(end_date) or datetime.now(UTC).strftime("%Y%m%d"),
                    end_date=_ymd(end_date) or _ymd(start_date) or datetime.now(UTC).strftime("%Y%m%d"),
                    market_type=market_type,
                )
                if frame is None or frame.empty:
                    continue
                for row in frame.to_dict(orient="records"):
                    symbol = _clean_str(row.get("ts_code")).upper()
                    if symbol not in requested:
                        continue
                    top_holdings.append(
                        {
                            "trade_date": _clean_date(row.get("trade_date")),
                            "symbol": symbol,
                            "name": row.get("name"),
                            "market_type": row.get("market_type"),
                            "rank": _to_int(row.get("rank")),
                            "amount": _to_float(row.get("amount")),
                            "net_amount": _to_float(row.get("net_amount")),
                            "buy": _to_float(row.get("buy")),
                            "sell": _to_float(row.get("sell")),
                        }
                    )
            top_holdings = _slice_by_date(top_holdings, "trade_date", start_date=start_date, end_date=end_date)

        if direction == "northbound":
            daily_records = [
                {
                    "trade_date": row["trade_date"],
                    "flow_mn": row["northbound_flow_mn"],
                    "hgt_mn": row["hgt_mn"],
                    "sgt_mn": row["sgt_mn"],
                }
                for row in daily_records
            ]
        elif direction == "southbound":
            daily_records = [
                {
                    "trade_date": row["trade_date"],
                    "flow_mn": row["southbound_flow_mn"],
                    "ggt_ss_mn": row["ggt_ss_mn"],
                    "ggt_sz_mn": row["ggt_sz_mn"],
                }
                for row in daily_records
            ]

        return {
            "direction": direction,
            "symbols": symbols,
            "count": len(daily_records),
            "daily_flows": daily_records,
            "security_details": top_holdings,
        }

    async def get_china_moneyflow(
        self,
        *,
        symbols: list[str],
        start_date: str | None,
        end_date: str | None,
        granularity: str | None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_china_moneyflow_sync, symbols, start_date, end_date, granularity)

    def _get_china_moneyflow_sync(
        self,
        symbols: list[str],
        start_date: str | None,
        end_date: str | None,
        granularity: str | None,
    ) -> dict[str, Any]:
        if not symbols:
            raise ResearchDataNotSupported("china.get_moneyflow currently requires explicit symbols")

        api = self._client()
        items: list[dict[str, Any]] = []
        for symbol in symbols:
            resolved = resolve_instrument(symbol)
            if resolved.market != "a_share":
                raise ResearchDataNotSupported("china.get_moneyflow only supports A-share symbols in this runtime")
            frame = api.moneyflow(
                ts_code=resolved.normalized_symbol,
                start_date=_ymd(start_date),
                end_date=_ymd(end_date),
            )
            if frame is None or frame.empty:
                continue
            records = []
            for row in frame.to_dict(orient="records"):
                records.append(
                    {
                        "trade_date": _clean_date(row.get("trade_date")),
                        "net_mf_amount": _to_float(row.get("net_mf_amount")),
                        "buy_sm_amount": _to_float(row.get("buy_sm_amount")),
                        "sell_sm_amount": _to_float(row.get("sell_sm_amount")),
                        "buy_md_amount": _to_float(row.get("buy_md_amount")),
                        "sell_md_amount": _to_float(row.get("sell_md_amount")),
                        "buy_lg_amount": _to_float(row.get("buy_lg_amount")),
                        "sell_lg_amount": _to_float(row.get("sell_lg_amount")),
                        "buy_elg_amount": _to_float(row.get("buy_elg_amount")),
                        "sell_elg_amount": _to_float(row.get("sell_elg_amount")),
                    }
                )
            records = _slice_by_date(records, "trade_date", start_date=start_date, end_date=end_date)
            items.append(
                {
                    "symbol": symbol,
                    "normalized_symbol": resolved.normalized_symbol,
                    "market": resolved.market,
                    "granularity": granularity or "stock",
                    "count": len(records),
                    "records": records,
                }
            )

        return {
            "symbols": symbols,
            "granularity": granularity or "stock",
            "count": len(items),
            "items": items,
        }


@dataclass(slots=True)
class ResearchDataRouter:
    """Provider-backed router for structured non-market research data."""

    async def get_macro_series(
        self,
        *,
        series: str,
        country: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        frequency: str | None = None,
    ) -> ToolEnvelope:
        normalized_country = _normalize_country(country)
        normalized_series = _clean_str(series).lower()
        chain = []
        if normalized_country == "us":
            chain = [FredMacroProvider(), AkshareMacroProvider()]
        elif normalized_country == "china":
            chain = [AkshareMacroProvider()]
        else:
            return build_not_implemented_envelope(
                tool="macro.get_series",
                provider="motis_router",
                request={"series": series, "country": country, "start_date": start_date, "end_date": end_date, "frequency": frequency},
                message=f"Motis has not wired structured macro providers for country '{normalized_country}' yet.",
            )

        warnings: list[str] = []
        for provider in chain:
            if not provider.is_available():
                warnings.append(f"{provider.name}: provider is unavailable in this runtime")
                continue
            if not provider.supports(normalized_country, normalized_series):
                warnings.append(f"{provider.name}: series '{normalized_series}' is not mapped for country '{normalized_country}'")
                continue
            try:
                payload = await provider.get_series(
                    series=normalized_series,
                    country=normalized_country,
                    start_date=start_date,
                    end_date=end_date,
                    frequency=frequency,
                )
                return build_tool_envelope(
                    tool="macro.get_series",
                    provider=provider.name,
                    data=payload,
                    warnings=warnings,
                )
            except Exception as exc:
                warnings.append(f"{provider.name}: {exc}")

        return build_tool_envelope(
            tool="macro.get_series",
            provider="motis_router",
            status="error",
            data={"series": normalized_series, "country": normalized_country},
            warnings=warnings,
            error={
                "code": "no_provider_available",
                "message": f"Motis could not satisfy macro.get_series for {normalized_country}:{normalized_series}.",
            },
        )

    async def get_equity_fundamentals(
        self,
        *,
        symbols: list[str],
        fields: list[str] | None = None,
        as_of: str | None = None,
        frequency: str | None = None,
    ) -> ToolEnvelope:
        warnings: list[str] = []
        items: list[dict[str, Any]] = []
        for symbol in symbols:
            resolved = resolve_instrument(symbol)
            provider_chain = self._equity_provider_chain(resolved)
            payload, provider_name, provider_warnings = await self._dispatch_equity_chain(
                operation="get_fundamentals",
                resolved=resolved,
                fields=_normalize_fields(fields),
                as_of=as_of,
                frequency=frequency,
                chain=provider_chain,
            )
            warnings.extend(provider_warnings)
            if payload is not None:
                items.append({**payload, "provider": provider_name})
        status = "ok" if items else "error"
        error = None if items else {"code": "no_provider_available", "message": "Motis could not fetch fundamentals for the requested symbols."}
        return build_tool_envelope(
            tool="equity.get_fundamentals",
            provider="motis_router",
            status=status,
            data={"symbols": symbols, "count": len(items), "items": items},
            warnings=warnings,
            error=error,
        )

    async def get_equity_earnings_calendar(
        self,
        *,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
    ) -> ToolEnvelope:
        warnings: list[str] = []
        events: list[dict[str, Any]] = []
        for symbol in symbols:
            resolved = resolve_instrument(symbol)
            provider_chain = self._equity_provider_chain(resolved)
            payload, provider_name, provider_warnings = await self._dispatch_equity_chain(
                operation="get_earnings_calendar",
                resolved=resolved,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                chain=provider_chain,
            )
            warnings.extend(provider_warnings)
            if payload is None:
                continue
            for event in payload.get("events") or []:
                events.append({**event, "provider": provider_name})
        events = sorted(events, key=lambda item: (item.get("event_date") or "", item.get("symbol") or ""))
        return build_tool_envelope(
            tool="equity.get_earnings_calendar",
            provider="motis_router",
            status="ok" if events else "error",
            data={"symbols": symbols, "count": len(events), "events": events[: max(1, limit)]},
            warnings=warnings,
            error=None if events else {"code": "no_provider_available", "message": "Motis could not fetch earnings calendars for the requested symbols."},
        )

    async def get_connect(
        self,
        *,
        direction: str,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ToolEnvelope:
        provider = TushareResearchProvider()
        if not provider.is_available():
            return build_not_implemented_envelope(
                tool="flows.get_connect",
                provider="motis_router",
                request={"direction": direction, "symbols": symbols or [], "start_date": start_date, "end_date": end_date},
                message="flows.get_connect currently requires Tushare connectivity in this runtime.",
            )
        payload = await provider.get_connect(
            direction=direction,
            symbols=list(symbols or []),
            start_date=start_date,
            end_date=end_date,
        )
        return build_tool_envelope(
            tool="flows.get_connect",
            provider=provider.name,
            data=payload,
        )

    async def get_china_moneyflow(
        self,
        *,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        granularity: str | None = None,
    ) -> ToolEnvelope:
        provider = TushareResearchProvider()
        if not provider.is_available():
            return build_not_implemented_envelope(
                tool="china.get_moneyflow",
                provider="motis_router",
                request={"symbols": symbols, "start_date": start_date, "end_date": end_date, "granularity": granularity},
                message="china.get_moneyflow currently requires Tushare connectivity in this runtime.",
            )
        payload = await provider.get_china_moneyflow(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )
        return build_tool_envelope(
            tool="china.get_moneyflow",
            provider=provider.name,
            data=payload,
        )

    def _equity_provider_chain(self, resolved: ResolvedInstrument) -> list[Any]:
        chain: list[Any] = []
        if resolved.market in {"us_equity", "hk_equity"}:
            chain.append(YFinanceResearchProvider())
        chain.append(TushareResearchProvider())
        return chain

    async def _dispatch_equity_chain(
        self,
        *,
        operation: str,
        resolved: ResolvedInstrument,
        chain: list[Any],
        **kwargs: Any,
    ) -> tuple[dict[str, Any] | None, str | None, list[str]]:
        warnings: list[str] = []
        for provider in chain:
            if not provider.is_available():
                warnings.append(f"{provider.name}: provider is unavailable in this runtime")
                continue
            try:
                handler = getattr(provider, operation)
                payload = await handler(resolved, **kwargs)
                return payload, provider.name, warnings
            except ResearchDataNotSupported as exc:
                warnings.append(f"{provider.name}: {exc}")
            except Exception as exc:
                warnings.append(f"{provider.name}: {exc}")
        return None, None, warnings
