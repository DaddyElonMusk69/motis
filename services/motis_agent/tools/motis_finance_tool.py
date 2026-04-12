"""Motis finance tools for the Motis runtime."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

import httpx
import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

_DATA_MCP_TIMEOUT = 30.0
_LOCAL_DATA_DISPATCH = None


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
    return aliases.get(value, value)


def _infer_market_type(symbol: str) -> str:
    normalized = str(symbol or "").upper()
    if (
        "/" in normalized
        or ":" in normalized
        or normalized.endswith(("USDT", "USDC", "PERP", "-SWAP"))
        or (
            "-" in normalized
            and normalized.split("-")[-1] in {"USDT", "USDC", "USD", "BTC", "ETH", "SWAP"}
        )
    ):
        return "crypto"
    return "equity"


def _get_data_mcp_url() -> str:
    explicit_url = os.getenv("DATA_MCP_URL", "").strip().rstrip("/")
    if explicit_url:
        return explicit_url
    return os.getenv("MCP_URL", "").strip().rstrip("/")


def _get_data_mcp_secret() -> str:
    return os.getenv("AGENT_MCP_SECRET", "dev-secret-change-in-prod").strip()


def _build_data_mcp_headers(*, session_id: str | None = None) -> dict[str, str]:
    headers = {"X-Agent-Token": _get_data_mcp_secret()}
    if session_id:
        headers["X-Conversation-Id"] = str(session_id)
    return headers


def _decode_data_mcp_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result

    if isinstance(result, list):
        for item in result:
            text = getattr(item, "text", None)
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload

    raise ValueError("Motis Data MCP returned an unsupported payload shape")


def _resolve_local_data_dispatch():
    global _LOCAL_DATA_DISPATCH
    if _LOCAL_DATA_DISPATCH is not None:
        return _LOCAL_DATA_DISPATCH

    try:
        from motis_data_mcp.tools import dispatch_data as local_dispatch_data
    except ModuleNotFoundError:
        service_root = Path(__file__).resolve().parents[2] / "mcp"
        if str(service_root) not in sys.path:
            sys.path.insert(0, str(service_root))
        from motis_data_mcp.tools import dispatch_data as local_dispatch_data

    _LOCAL_DATA_DISPATCH = local_dispatch_data
    return _LOCAL_DATA_DISPATCH


async def _call_data_mcp_async(
    tool_name: str,
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    base_url = _get_data_mcp_url()
    if base_url:
        async with httpx.AsyncClient(
            timeout=_DATA_MCP_TIMEOUT,
            follow_redirects=True,
            trust_env=False,
        ) as client:
            response = await client.post(
                f"{base_url}/tools/{tool_name}",
                json=payload,
                headers=_build_data_mcp_headers(session_id=session_id),
            )
            response.raise_for_status()
            return response.json()

    dispatch_data = _resolve_local_data_dispatch()
    return _decode_data_mcp_payload(await dispatch_data(tool_name, payload))


def _extract_data_mcp_data(response: dict[str, Any], *, tool_name: str) -> dict[str, Any]:
    if response.get("status") != "ok":
        error = response.get("error") or {}
        raise RuntimeError(
            error.get("message")
            or f"Motis Data MCP returned status '{response.get('status', 'error')}' for {tool_name}"
        )

    payload = dict(response.get("data") or {})
    return {
        "success": True,
        "service": response.get("service") or "motis_data_mcp",
        "provider": response.get("provider") or "motis_data_mcp",
        "request_id": response.get("request_id"),
        "as_of": response.get("as_of"),
        "warnings": response.get("warnings") or [],
        **_jsonify(payload),
    }


async def _call_structured_data_mcp(
    tool_name: str,
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    response = await _call_data_mcp_async(tool_name, payload, session_id=session_id)
    return _extract_data_mcp_data(response, tool_name=tool_name)


async def _mcp_market_ohlcv_source(
    *,
    symbol: str,
    timeframe: str,
    limit: int,
    exchange: str | None = None,
) -> dict[str, Any]:
    request = {
        "symbol": symbol,
        "interval": timeframe,
        "limit": int(limit),
    }
    if exchange:
        request["exchange"] = exchange

    data = await _call_structured_data_mcp("market.get_ohlcv", request)
    candles = data.get("candles")
    if not isinstance(candles, list) or not candles:
        raise ValueError("Motis Data MCP returned no candles for market.get_ohlcv")

    return {
        "candles": candles,
        "source": data.get("provider") or data.get("service") or "motis_data_mcp",
        "normalized_symbol": data.get("normalized_symbol"),
        "market": data.get("market"),
        "resolved": data.get("resolved"),
        "warnings": data.get("warnings") or [],
    }


def _get_source_priority(market_type: str, exchange: str | None) -> list[Callable[..., Any]]:
    del market_type, exchange
    return [_mcp_market_ohlcv_source]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _jsonify(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _records_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    normalized = frame.copy()
    normalized = normalized.rename(
        columns={
            "Datetime": "timestamp",
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    if "timestamp" not in normalized.columns:
        if normalized.index.name:
            normalized = normalized.reset_index().rename(columns={normalized.index.name: "timestamp"})
        else:
            normalized = normalized.reset_index().rename(columns={"index": "timestamp"})

    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True, errors="coerce")
    normalized = normalized.dropna(subset=["timestamp"])

    for column in ("open", "high", "low", "close", "volume"):
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    return [_jsonify(record) for record in normalized.to_dict(orient="records")]


def _records_to_ohlcv_frame(ohlcv: list[dict[str, Any]]) -> pd.DataFrame:
    if not isinstance(ohlcv, list) or not ohlcv:
        raise ValueError(
            "smc.structure requires non-empty 'ohlcv' data, or 'symbol' plus 'interval'."
        )

    frame = pd.DataFrame(ohlcv).copy()
    frame = frame.rename(
        columns={
            "Datetime": "timestamp",
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    required = ["timestamp", "open", "high", "low", "close"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"OHLCV payload is missing columns: {', '.join(missing)}")

    if "volume" not in frame.columns:
        frame["volume"] = 0.0

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"])

    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["open", "high", "low", "close"]).sort_values("timestamp")
    if frame.empty:
        raise ValueError("OHLCV payload did not contain any valid candles")

    return frame.set_index("timestamp")[["open", "high", "low", "close", "volume"]]


def _ts(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return pd.Timestamp(value, tz=UTC).isoformat()


def _detect_bos(frame: pd.DataFrame) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for idx in range(1, len(frame)):
        current = frame.iloc[idx]
        previous = frame.iloc[idx - 1]
        timestamp = _ts(frame.index[idx])
        if float(current["close"]) > float(previous["high"]):
            events.append({"timestamp": timestamp, "direction": "bullish", "level": float(previous["high"])})
        elif float(current["close"]) < float(previous["low"]):
            events.append({"timestamp": timestamp, "direction": "bearish", "level": float(previous["low"])})
    return events[-20:]


def _detect_choch(frame: pd.DataFrame) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    close_diff = frame["close"].diff()
    for idx in range(2, len(frame)):
        prev_diff = close_diff.iloc[idx - 1]
        curr_diff = close_diff.iloc[idx]
        if pd.isna(prev_diff) or pd.isna(curr_diff) or prev_diff == 0 or curr_diff == 0:
            continue
        if (prev_diff > 0 and curr_diff < 0) or (prev_diff < 0 and curr_diff > 0):
            events.append(
                {
                    "timestamp": _ts(frame.index[idx]),
                    "direction": "bullish_to_bearish" if prev_diff > 0 else "bearish_to_bullish",
                }
            )
    return events[-20:]


def _detect_liquidity_sweep(frame: pd.DataFrame) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for idx in range(1, len(frame)):
        current = frame.iloc[idx]
        previous = frame.iloc[idx - 1]
        if float(current["high"]) > float(previous["high"]) and float(current["close"]) < float(previous["high"]):
            events.append({"timestamp": _ts(frame.index[idx]), "direction": "bearish", "swept_level": float(previous["high"])})
        elif float(current["low"]) < float(previous["low"]) and float(current["close"]) > float(previous["low"]):
            events.append({"timestamp": _ts(frame.index[idx]), "direction": "bullish", "swept_level": float(previous["low"])})
    return events[-20:]


def _detect_fvg(frame: pd.DataFrame) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for idx in range(2, len(frame)):
        left = frame.iloc[idx - 2]
        current = frame.iloc[idx]
        timestamp = _ts(frame.index[idx])
        if float(current["low"]) > float(left["high"]):
            events.append({"timestamp": timestamp, "direction": "bullish", "gap_low": float(left["high"]), "gap_high": float(current["low"])})
        elif float(current["high"]) < float(left["low"]):
            events.append({"timestamp": timestamp, "direction": "bearish", "gap_low": float(current["high"]), "gap_high": float(left["low"])})
    return events[-20:]


async def route_data_source(
    symbol: str,
    interval: str = "1d",
    limit: int = 200,
    exchange: str | None = None,
) -> dict[str, Any]:
    timeframe = _normalize_interval(interval or "1d")
    market_type = _infer_market_type(symbol)
    source_errors: list[str] = []

    for source in _get_source_priority(market_type, exchange):
        source_name = getattr(source, "__name__", source.__class__.__name__)
        try:
            result = source(symbol=symbol, timeframe=timeframe, limit=int(limit), exchange=exchange)
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                raise ValueError("backend returned no data")
            if isinstance(result, pd.DataFrame):
                candles = _records_from_frame(result)
            elif isinstance(result, list):
                candles = [_jsonify(item) for item in result]
            elif isinstance(result, dict):
                source_name = str(result.get("source") or source_name)
                payload = result.get("candles")
                if isinstance(payload, pd.DataFrame):
                    candles = _records_from_frame(payload)
                elif isinstance(payload, list):
                    candles = [_jsonify(item) for item in payload]
                else:
                    raise TypeError("backend payload dict must include a 'candles' list or DataFrame")
            else:
                raise TypeError(f"unsupported backend result type: {type(result).__name__}")
            return {
                "success": True,
                "symbol": symbol,
                "interval": timeframe,
                "exchange": exchange,
                "market_type": market_type,
                "candles": candles[: int(limit)],
                "count": min(len(candles), int(limit)),
                "source": source_name,
            }
        except Exception as exc:
            source_errors.append(f"{source_name}: {exc}")

    raise ValueError(
        "Unable to fetch OHLCV data from available sources. " + "; ".join(source_errors)
    )


async def analyze_smc_structure(
    *,
    symbol: str | None = None,
    interval: str = "4h",
    htf_interval: str = "1d",
    limit: int = 200,
    exchange: str | None = None,
    ohlcv: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if ohlcv is None:
        if not symbol or not interval:
            raise ValueError("smc.structure requires either 'ohlcv' or both 'symbol' and 'interval'.")
        fetched = await route_data_source(symbol=symbol, interval=interval, limit=limit, exchange=exchange)
        ohlcv = fetched["candles"]

    frame = _records_to_ohlcv_frame(ohlcv)
    result = {
        "success": True,
        "symbol": symbol,
        "interval": _normalize_interval(interval),
        "htf_interval": _normalize_interval(htf_interval),
        "bos": _detect_bos(frame),
        "choch": _detect_choch(frame),
        "liquidity_sweeps": _detect_liquidity_sweep(frame),
        "fair_value_gaps": _detect_fvg(frame),
        "order_blocks": [],
        "latest_close": float(frame["close"].iloc[-1]),
        "latest_timestamp": _ts(frame.index[-1]),
        "candle_count": int(len(frame)),
    }
    return result


async def data_ohlcv_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        result = await route_data_source(
            symbol=args.get("symbol", ""),
            interval=args.get("interval", "1d"),
            limit=args.get("limit", 200),
            exchange=args.get("exchange"),
        )
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def data_resolve_symbol_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        symbol = str(args.get("symbol") or "").strip()
        if not symbol:
            raise ValueError("symbol is required")

        payload = {"symbol": symbol}
        exchange = str(args.get("exchange") or "").strip()
        if exchange:
            payload["exchange"] = exchange

        result = await _call_structured_data_mcp("market.resolve_symbol", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def data_ticker_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        symbol = str(args.get("symbol") or "").strip()
        if not symbol:
            raise ValueError("symbol is required")

        payload = {"symbol": symbol}
        exchange = str(args.get("exchange") or "").strip()
        if exchange:
            payload["exchange"] = exchange

        result = await _call_structured_data_mcp("market.get_ticker", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def data_orderbook_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        symbol = str(args.get("symbol") or "").strip()
        if not symbol:
            raise ValueError("symbol is required")

        payload = {
            "symbol": symbol,
            "limit": int(args.get("limit", 20) or 20),
        }
        exchange = str(args.get("exchange") or "").strip()
        if exchange:
            payload["exchange"] = exchange

        result = await _call_structured_data_mcp("market.get_orderbook", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def data_funding_rate_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        symbol = str(args.get("symbol") or "").strip()
        if not symbol:
            raise ValueError("symbol is required")

        payload = {
            "symbol": symbol,
            "limit": int(args.get("limit", 50) or 50),
        }
        exchange = str(args.get("exchange") or "").strip()
        if exchange:
            payload["exchange"] = exchange

        result = await _call_structured_data_mcp("market.get_funding_rate", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def data_open_interest_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        symbol = str(args.get("symbol") or "").strip()
        if not symbol:
            raise ValueError("symbol is required")

        payload = {
            "symbol": symbol,
            "limit": int(args.get("limit", 50) or 50),
        }
        exchange = str(args.get("exchange") or "").strip()
        if exchange:
            payload["exchange"] = exchange

        result = await _call_structured_data_mcp("market.get_open_interest", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def macro_get_series_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        series = str(args.get("series") or "").strip()
        if not series:
            raise ValueError("series is required")

        payload = {"series": series}
        for key in ("country", "start_date", "end_date", "frequency"):
            value = str(args.get(key) or "").strip()
            if value:
                payload[key] = value

        result = await _call_structured_data_mcp("macro.get_series", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def equity_get_fundamentals_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        symbols = _string_list(args.get("symbols"))
        if not symbols:
            raise ValueError("symbols is required")

        payload: dict[str, Any] = {"symbols": symbols}
        fields = _string_list(args.get("fields"))
        if fields:
            payload["fields"] = fields
        for key in ("as_of", "frequency"):
            value = str(args.get(key) or "").strip()
            if value:
                payload[key] = value

        result = await _call_structured_data_mcp("equity.get_fundamentals", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def equity_get_earnings_calendar_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        symbols = _string_list(args.get("symbols"))
        if not symbols:
            raise ValueError("symbols is required")

        payload: dict[str, Any] = {
            "symbols": symbols,
            "limit": int(args.get("limit", 50) or 50),
        }
        for key in ("start_date", "end_date"):
            value = str(args.get(key) or "").strip()
            if value:
                payload[key] = value

        result = await _call_structured_data_mcp("equity.get_earnings_calendar", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def flows_get_connect_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        direction = str(args.get("direction") or "both").strip() or "both"
        payload: dict[str, Any] = {"direction": direction}
        symbols = _string_list(args.get("symbols"))
        if symbols:
            payload["symbols"] = symbols
        for key in ("start_date", "end_date"):
            value = str(args.get(key) or "").strip()
            if value:
                payload[key] = value

        result = await _call_structured_data_mcp("flows.get_connect", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def china_get_moneyflow_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        symbols = _string_list(args.get("symbols"))
        if not symbols:
            raise ValueError("symbols is required")

        payload: dict[str, Any] = {"symbols": symbols}
        for key in ("start_date", "end_date", "granularity"):
            value = str(args.get(key) or "").strip()
            if value:
                payload[key] = value

        result = await _call_structured_data_mcp("china.get_moneyflow", payload)
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


async def smc_structure_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        result = await analyze_smc_structure(
            symbol=args.get("symbol"),
            interval=args.get("interval", "4h"),
            htf_interval=args.get("htf_interval", "1d"),
            limit=args.get("limit", 200),
            exchange=args.get("exchange"),
            ohlcv=args.get("ohlcv"),
        )
        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), success=False)


def _load_csv(path_value: str) -> pd.DataFrame:
    csv_path = Path(path_value).expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    return pd.read_csv(csv_path, index_col=0)


def _compute_ic_series(factor_df: pd.DataFrame, return_df: pd.DataFrame) -> pd.Series:
    common_dates = factor_df.index.intersection(return_df.index)
    common_codes = factor_df.columns.intersection(return_df.columns)
    if len(common_dates) == 0 or len(common_codes) == 0:
        return pd.Series(dtype=float)

    factor_df = factor_df.loc[common_dates, common_codes]
    return_df = return_df.loc[common_dates, common_codes]

    ic_values: dict[Any, float] = {}
    for current_date in common_dates:
        f = factor_df.loc[current_date].dropna()
        r = return_df.loc[current_date].dropna()
        shared = f.index.intersection(r.index)
        if len(shared) < 5:
            continue
        corr, _ = spearmanr(f[shared], r[shared])
        if not np.isnan(corr):
            ic_values[current_date] = float(corr)

    return pd.Series(ic_values, dtype=float)


def _compute_group_equity(
    factor_df: pd.DataFrame, return_df: pd.DataFrame, n_groups: int
) -> pd.DataFrame:
    common_dates = sorted(factor_df.index.intersection(return_df.index))
    common_codes = factor_df.columns.intersection(return_df.columns)
    if len(common_dates) == 0 or len(common_codes) == 0:
        return pd.DataFrame()

    factor_df = factor_df.loc[common_dates, common_codes]
    return_df = return_df.loc[common_dates, common_codes]
    group_returns: dict[str, list[float]] = {f"Group_{idx+1}": [] for idx in range(n_groups)}
    valid_dates: list[Any] = []

    for current_date in common_dates:
        f = factor_df.loc[current_date].dropna()
        r = return_df.loc[current_date].dropna()
        shared = f.index.intersection(r.index)
        if len(shared) < n_groups:
            continue
        valid_dates.append(current_date)
        ranked = f[shared].rank(method="first")
        bins = pd.qcut(ranked, n_groups, labels=False, duplicates="drop")
        if bins.nunique() < n_groups:
            bins = pd.cut(ranked, n_groups, labels=False)
        for group_idx in range(n_groups):
            members = bins[bins == group_idx].index
            group_returns[f"Group_{group_idx+1}"].append(float(r[members].mean()) if len(members) else 0.0)

    if not valid_dates:
        return pd.DataFrame()

    ret_df = pd.DataFrame(group_returns, index=valid_dates)
    return (1 + ret_df).cumprod()


def factor_analysis_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        factor_df = _load_csv(args.get("factor_csv", ""))
        return_df = _load_csv(args.get("return_csv", ""))
        n_groups = int(args.get("n_groups", 5) or 5)
        output_dir = args.get("output_dir")

        ic_series = _compute_ic_series(factor_df, return_df)
        if ic_series.empty:
            return tool_error("IC computation failed: insufficient shared dates/assets (need at least 5 per day)", status="error")

        ic_mean = float(ic_series.mean())
        ic_std = float(ic_series.std())
        ir = ic_mean / ic_std if ic_std > 0 else 0.0
        equity_df = _compute_group_equity(factor_df, return_df, n_groups)
        if equity_df.empty:
            return tool_error("Layered backtest failed: insufficient valid cross-section dates", status="error")

        result: dict[str, Any] = {
            "status": "ok",
            "ic_mean": round(ic_mean, 6),
            "ic_std": round(ic_std, 6),
            "ir": round(ir, 4),
            "ic_positive_ratio": round(float((ic_series > 0).mean()), 4),
            "ic_count": len(ic_series),
            "n_groups": n_groups,
            "long_short_spread": round(float(equity_df.iloc[-1, -1] - equity_df.iloc[-1, 0]), 4),
            "group_final_equity": {
                col: round(float(equity_df[col].iloc[-1]), 4) for col in equity_df.columns
            },
        }

        if output_dir:
            out_path = Path(output_dir).expanduser().resolve()
            out_path.mkdir(parents=True, exist_ok=True)
            ic_series.to_csv(out_path / "ic_series.csv", header=["IC"])
            (out_path / "ic_summary.json").write_text(
                json.dumps(
                    {
                        "ic_mean": result["ic_mean"],
                        "ic_std": result["ic_std"],
                        "ir": result["ir"],
                        "ic_positive_ratio": result["ic_positive_ratio"],
                        "ic_count": result["ic_count"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            equity_df.to_csv(out_path / "group_equity.csv")
            result["output_dir"] = str(out_path)
            result["files"] = ["ic_series.csv", "ic_summary.json", "group_equity.csv"]

        return tool_result(result)
    except Exception as exc:
        return tool_error(str(exc), status="error")


def options_pricing_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        spot = float(args.get("spot"))
        strike = float(args.get("strike"))
        expiry_days = float(args.get("expiry_days"))
        risk_free_rate = float(args.get("risk_free_rate", 0.05))
        volatility = float(args.get("volatility"))
        option_type = str(args.get("option_type", "call")).lower().strip()

        if option_type not in {"call", "put"}:
            return tool_error("option_type must be 'call' or 'put'", status="error")

        T = max(expiry_days, 0.0) / 365.0
        if T <= 0 or volatility <= 0:
            if option_type == "call":
                price = max(spot - strike, 0.0)
                delta = 1.0 if spot > strike else 0.0
            else:
                price = max(strike - spot, 0.0)
                delta = -1.0 if spot < strike else 0.0
            greeks = {"price": price, "delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
            return tool_result({k: round(float(v), 6) for k, v in greeks.items()})

        sqrt_T = np.sqrt(T)
        d1 = (np.log(spot / strike) + (risk_free_rate + volatility**2 / 2) * T) / (volatility * sqrt_T)
        d2 = d1 - volatility * sqrt_T
        nd1_pdf = float(norm.pdf(d1))

        if option_type == "call":
            price = float(spot * norm.cdf(d1) - strike * np.exp(-risk_free_rate * T) * norm.cdf(d2))
            delta = float(norm.cdf(d1))
        else:
            price = float(strike * np.exp(-risk_free_rate * T) * norm.cdf(-d2) - spot * norm.cdf(-d1))
            delta = float(norm.cdf(d1) - 1.0)

        gamma = float(nd1_pdf / (spot * volatility * sqrt_T))
        theta_common = -(spot * nd1_pdf * volatility) / (2 * sqrt_T)
        if option_type == "call":
            theta = theta_common - risk_free_rate * strike * np.exp(-risk_free_rate * T) * norm.cdf(d2)
        else:
            theta = theta_common + risk_free_rate * strike * np.exp(-risk_free_rate * T) * norm.cdf(-d2)

        return tool_result(
            {
                "price": round(price, 6),
                "delta": round(delta, 6),
                "gamma": round(gamma, 6),
                "theta": round(float(theta / 365.0), 6),
                "vega": round(float(spot * nd1_pdf * sqrt_T / 100.0), 6),
            }
        )
    except Exception as exc:
        return tool_error(str(exc), status="error")


async def _load_pattern_frame_async(args: dict[str, Any]) -> pd.DataFrame:
    if isinstance(args.get("ohlcv"), list) and args.get("ohlcv"):
        return _records_to_ohlcv_frame(args["ohlcv"]).reset_index()

    if args.get("ohlcv_csv"):
        csv_path = Path(args["ohlcv_csv"]).expanduser().resolve()
        if not csv_path.exists():
            raise FileNotFoundError(f"OHLCV CSV not found: {csv_path}")
        frame = pd.read_csv(csv_path)
        return frame.rename(
            columns={
                "Datetime": "timestamp",
                "Date": "timestamp",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )

    symbol = args.get("symbol")
    timeframe = args.get("timeframe") or args.get("interval")
    if symbol and timeframe:
        fetched = await route_data_source(
            symbol=symbol,
            interval=str(timeframe),
            limit=int(args.get("limit", 500) or 500),
            exchange=args.get("exchange"),
        )
        return _records_to_ohlcv_frame(fetched["candles"]).reset_index()

    raise ValueError("pattern requires either ohlcv, ohlcv_csv, or both symbol and timeframe.")


def _find_peaks_valleys(close: pd.Series, window: int = 5) -> dict[str, list[int]]:
    n = len(close)
    if n < 2 * window + 1:
        return {"peaks": [], "valleys": []}
    values = close.values.astype(float)
    peaks, valleys = [], []
    for idx in range(window, n - window):
        seg = values[idx - window : idx + window + 1]
        if np.isnan(values[idx]):
            continue
        seg = seg[~np.isnan(seg)]
        if len(seg) == 0:
            continue
        if values[idx] == np.max(seg):
            peaks.append(idx)
        if values[idx] == np.min(seg):
            valleys.append(idx)
    return {"peaks": peaks, "valleys": valleys}


def _candlestick_patterns(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    body = (close - open_).abs()
    total_range = high - low
    upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low
    result = pd.Series(0, index=close.index, dtype=int)
    safe_range = total_range.replace(0, np.nan)
    is_doji = body / safe_range < 0.10
    is_hammer = (lower_shadow > 2 * body) & (upper_shadow < body) & ~is_doji
    result = result.where(~is_hammer, 1)
    prev_bearish = close.shift(1) < open_.shift(1)
    curr_bullish = close > open_
    engulf_bull = prev_bearish & curr_bullish & (open_ <= close.shift(1)) & (close >= open_.shift(1)) & (body > body.shift(1))
    result = result.where(~engulf_bull, 1)
    prev_bullish = close.shift(1) > open_.shift(1)
    curr_bearish = close < open_
    engulf_bear = prev_bullish & curr_bearish & (open_ >= close.shift(1)) & (close <= open_.shift(1)) & (body > body.shift(1))
    return result.where(~engulf_bear, -1)


def _support_resistance(close: pd.Series, window: int = 20, num_levels: int = 3) -> dict[str, list[float]]:
    pv = _find_peaks_valleys(close, window=window)
    values = close.values.astype(float)
    peak_prices = [float(values[idx]) for idx in pv["peaks"] if not np.isnan(values[idx])]
    valley_prices = [float(values[idx]) for idx in pv["valleys"] if not np.isnan(values[idx])]

    def _cluster(prices: list[float], n: int) -> list[float]:
        if not prices:
            return []
        sorted_prices = sorted(prices)
        if len(sorted_prices) <= n:
            return sorted_prices
        clusters: list[list[float]] = [[sorted_prices[0]]]
        price_range = sorted_prices[-1] - sorted_prices[0]
        threshold = price_range * 0.05 if price_range > 0 else 1.0
        for price in sorted_prices[1:]:
            if abs(price - np.mean(clusters[-1])) <= threshold:
                clusters[-1].append(price)
            else:
                clusters.append([price])
        centers = [(len(cluster), float(np.mean(cluster))) for cluster in clusters]
        centers.sort(reverse=True)
        return [center for _, center in centers[:n]]

    return {"support": _cluster(valley_prices, num_levels), "resistance": _cluster(peak_prices, num_levels)}


def _trend_line_slope(close: pd.Series, window: int = 20) -> pd.Series:
    n = len(close)
    slopes = np.full(n, np.nan)
    values = close.values.astype(float)
    x = np.arange(window, dtype=float)
    for idx in range(window - 1, n):
        seg = values[idx - window + 1 : idx + 1]
        if np.any(np.isnan(seg)):
            continue
        slopes[idx] = np.polyfit(x, seg, 1)[0]
    return pd.Series(slopes, index=close.index)


def _head_and_shoulders(close: pd.Series, window: int = 10) -> pd.Series:
    result = pd.Series(0, index=close.index, dtype=int)
    pv = _find_peaks_valleys(close, window=window)
    values = close.values.astype(float)
    peaks = pv["peaks"]
    for idx in range(len(peaks) - 2):
        lv, hv, rv = values[peaks[idx]], values[peaks[idx + 1]], values[peaks[idx + 2]]
        if any(np.isnan(x) for x in (lv, hv, rv)) or hv <= lv or hv <= rv:
            continue
        avg = (lv + rv) / 2
        if avg != 0 and abs(lv - rv) / avg <= 0.05:
            result.iloc[peaks[idx + 1]] = 1
    return result


def _double_top_bottom(close: pd.Series, window: int = 10) -> pd.Series:
    result = pd.Series(0, index=close.index, dtype=int)
    pv = _find_peaks_valleys(close, window=window)
    values = close.values.astype(float)
    for idx in range(len(pv["peaks"]) - 1):
        v1, v2 = values[pv["peaks"][idx]], values[pv["peaks"][idx + 1]]
        if not np.isnan(v1) and not np.isnan(v2):
            avg = (v1 + v2) / 2
            if avg != 0 and abs(v1 - v2) / avg < 0.03:
                result.iloc[pv["peaks"][idx + 1]] = 1
    for idx in range(len(pv["valleys"]) - 1):
        v1, v2 = values[pv["valleys"][idx]], values[pv["valleys"][idx + 1]]
        if not np.isnan(v1) and not np.isnan(v2):
            avg = (v1 + v2) / 2
            if avg != 0 and abs(v1 - v2) / abs(avg) < 0.03 and result.iloc[pv["valleys"][idx + 1]] == 0:
                result.iloc[pv["valleys"][idx + 1]] = -1
    return result


def _triangle(close: pd.Series, window: int = 20) -> pd.Series:
    n = len(close)
    result = pd.Series(0, index=close.index, dtype=int)
    values = close.values.astype(float)
    for idx in range(window, n):
        seg = pd.Series(values[idx - window : idx + 1])
        pv = _find_peaks_valleys(seg, window=max(2, window // 5))
        if len(pv["peaks"]) < 2 or len(pv["valleys"]) < 2:
            continue
        pvals = [float(seg.iloc[p]) for p in pv["peaks"]]
        vvals = [float(seg.iloc[v]) for v in pv["valleys"]]
        ps = np.polyfit(np.arange(len(pvals), dtype=float), pvals, 1)[0] if len(pvals) >= 2 else 0.0
        vs = np.polyfit(np.arange(len(vvals), dtype=float), vvals, 1)[0] if len(vvals) >= 2 else 0.0
        price_range = max(pvals) - min(vvals)
        if price_range == 0:
            continue
        flat = price_range * 0.02
        if vs > flat and abs(ps) < flat:
            result.iloc[idx] = 1
        elif ps < -flat and abs(vs) < flat:
            result.iloc[idx] = -1
    return result


def _broadening(close: pd.Series, window: int = 20) -> pd.Series:
    n = len(close)
    result = pd.Series(0, index=close.index, dtype=int)
    values = close.values.astype(float)
    for idx in range(window, n):
        seg = pd.Series(values[idx - window : idx + 1])
        pv = _find_peaks_valleys(seg, window=max(2, window // 5))
        if len(pv["peaks"]) < 2 or len(pv["valleys"]) < 2:
            continue
        pvals = [float(seg.iloc[p]) for p in pv["peaks"]]
        vvals = [float(seg.iloc[v]) for v in pv["valleys"]]
        if all(pvals[j + 1] > pvals[j] for j in range(len(pvals) - 1)) and all(vvals[j + 1] < vvals[j] for j in range(len(vvals) - 1)):
            result.iloc[idx] = 1
    return result


_PATTERN_FUNCS = {
    "peaks_valleys": lambda df, w: _find_peaks_valleys(df["close"], window=w),
    "candlestick": lambda df, w: _candlestick_patterns(df["open"], df["high"], df["low"], df["close"]).value_counts().to_dict(),
    "support_resistance": lambda df, w: _support_resistance(df["close"], window=w),
    "trend_slope": lambda df, w: {"mean_slope": float(_trend_line_slope(df["close"], window=w).dropna().mean())} if len(df) > w else {"mean_slope": 0.0},
    "head_and_shoulders": lambda df, w: {"count": int(_head_and_shoulders(df["close"], window=w).sum())},
    "double_top_bottom": lambda df, w: {
        "double_top": int((_double_top_bottom(df["close"], window=w) == 1).sum()),
        "double_bottom": int((_double_top_bottom(df["close"], window=w) == -1).sum()),
    },
    "triangle": lambda df, w: {
        "ascending": int((_triangle(df["close"], window=w) == 1).sum()),
        "descending": int((_triangle(df["close"], window=w) == -1).sum()),
    },
    "broadening": lambda df, w: {"count": int(_broadening(df["close"], window=w).sum())},
}


async def pattern_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        df = await _load_pattern_frame_async(args)
        if df.empty:
            return tool_error("Empty OHLCV data", status="error")

        selected = str(args.get("patterns", "all") or "all")
        window = int(args.get("window", 10) or 10)
        if selected == "all":
            pattern_names = list(_PATTERN_FUNCS.keys())
        else:
            pattern_names = [name.strip() for name in selected.split(",") if name.strip() in _PATTERN_FUNCS]
            if not pattern_names:
                return tool_error(
                    f"Invalid pattern name(s). Available: {', '.join(_PATTERN_FUNCS.keys())}",
                    status="error",
                )

        results = {name: _PATTERN_FUNCS[name](df, window) for name in pattern_names}
        return tool_result(status="ok", results=_jsonify(results), patterns=pattern_names, window=window)
    except Exception as exc:
        return tool_error(str(exc), status="error")


DATA_OHLCV_SCHEMA = {
    "name": "data.ohlcv",
    "description": "Fetch OHLCV candle data from the configured market-data backends.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Trading symbol such as BTC/USDT:USDT or AAPL"},
            "interval": {"type": "string", "description": "Candle interval such as 1h, 4h, or 1d", "default": "1d"},
            "limit": {"type": "integer", "description": "Maximum number of candles to return", "default": 200},
            "exchange": {"type": "string", "description": "Optional exchange hint"},
        },
        "required": ["symbol"],
    },
}

DATA_RESOLVE_SYMBOL_SCHEMA = {
    "name": "data.resolve_symbol",
    "description": "Resolve a user-facing symbol into Motis-normalized market identity fields.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol such as BTC-USDT, BTC/USDT:USDT, AAPL, 0700.HK, or 000001.SZ"},
            "exchange": {"type": "string", "description": "Optional exchange hint"},
        },
        "required": ["symbol"],
    },
}

DATA_TICKER_SCHEMA = {
    "name": "data.ticker",
    "description": "Fetch the latest normalized ticker snapshot for a symbol through Motis market-data adapters.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Trading symbol such as BTC-USDT, BTC/USDT:USDT, or AAPL"},
            "exchange": {"type": "string", "description": "Optional exchange hint"},
        },
        "required": ["symbol"],
    },
}

DATA_ORDERBOOK_SCHEMA = {
    "name": "data.orderbook",
    "description": "Fetch the latest normalized order book depth for a symbol through Motis market-data adapters.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Trading symbol such as BTC-USDT or BTC/USDT:USDT"},
            "exchange": {"type": "string", "description": "Optional exchange hint"},
            "limit": {"type": "integer", "description": "Maximum depth levels per side", "default": 20},
        },
        "required": ["symbol"],
    },
}

DATA_FUNDING_RATE_SCHEMA = {
    "name": "data.funding_rate",
    "description": "Fetch current and recent perpetual funding-rate data through Motis market-data adapters.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Perpetual symbol such as BTC-USDT-SWAP or BTC/USDT:USDT"},
            "exchange": {"type": "string", "description": "Optional exchange hint"},
            "limit": {"type": "integer", "description": "Maximum historical points to return", "default": 50},
        },
        "required": ["symbol"],
    },
}

DATA_OPEN_INTEREST_SCHEMA = {
    "name": "data.open_interest",
    "description": "Fetch the latest normalized open-interest snapshot for a derivatives symbol.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Perpetual symbol such as BTC-USDT-SWAP or BTC/USDT:USDT"},
            "exchange": {"type": "string", "description": "Optional exchange hint"},
            "limit": {"type": "integer", "description": "Reserved for provider-specific history windows", "default": 50},
        },
        "required": ["symbol"],
    },
}

MACRO_GET_SERIES_SCHEMA = {
    "name": "macro.get_series",
    "description": "Fetch a normalized macroeconomic time series through the Motis data MCP.",
    "parameters": {
        "type": "object",
        "properties": {
            "series": {"type": "string", "description": "Series alias such as cpi, gdp, unemployment, or fed_funds"},
            "country": {"type": "string", "description": "Country code or label such as US or China"},
            "start_date": {"type": "string", "description": "Optional YYYY-MM-DD start date"},
            "end_date": {"type": "string", "description": "Optional YYYY-MM-DD end date"},
            "frequency": {"type": "string", "description": "Optional target frequency hint"},
        },
        "required": ["series"],
    },
}

EQUITY_GET_FUNDAMENTALS_SCHEMA = {
    "name": "equity.get_fundamentals",
    "description": "Fetch normalized valuation and quality fields for one or more equities.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "fields": {"type": "array", "items": {"type": "string"}},
            "as_of": {"type": "string", "description": "Optional YYYY-MM-DD report date"},
            "frequency": {"type": "string", "description": "Optional report-type hint such as Q4"},
        },
        "required": ["symbols"],
    },
}

EQUITY_GET_EARNINGS_CALENDAR_SCHEMA = {
    "name": "equity.get_earnings_calendar",
    "description": "Fetch structured earnings-calendar events for one or more equities.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "start_date": {"type": "string", "description": "Optional YYYY-MM-DD start date"},
            "end_date": {"type": "string", "description": "Optional YYYY-MM-DD end date"},
            "limit": {"type": "integer", "description": "Maximum number of events to return", "default": 50},
        },
        "required": ["symbols"],
    },
}

FLOWS_GET_CONNECT_SCHEMA = {
    "name": "flows.get_connect",
    "description": "Fetch Northbound and Southbound connect flows and optional symbol-level details.",
    "parameters": {
        "type": "object",
        "properties": {
            "direction": {"type": "string", "enum": ["northbound", "southbound", "both"], "default": "both"},
            "symbols": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "Optional YYYY-MM-DD start date"},
            "end_date": {"type": "string", "description": "Optional YYYY-MM-DD end date"},
        },
    },
}

CHINA_GET_MONEYFLOW_SCHEMA = {
    "name": "china.get_moneyflow",
    "description": "Fetch structured A-share moneyflow records for one or more symbols.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "start_date": {"type": "string", "description": "Optional YYYY-MM-DD start date"},
            "end_date": {"type": "string", "description": "Optional YYYY-MM-DD end date"},
            "granularity": {"type": "string", "description": "Optional granularity hint, default stock"},
        },
        "required": ["symbols"],
    },
}

SMC_STRUCTURE_SCHEMA = {
    "name": "smc.structure",
    "description": "Analyze Smart Money Concepts structure from OHLCV data or by fetching candles for a symbol.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Trading symbol such as BTC/USDT:USDT or AAPL"},
            "interval": {"type": "string", "description": "Primary timeframe", "default": "4h"},
            "htf_interval": {"type": "string", "description": "Higher timeframe reference", "default": "1d"},
            "limit": {"type": "integer", "default": 200},
            "exchange": {"type": "string", "description": "Optional exchange hint"},
            "ohlcv": {
                "type": "array",
                "description": "Optional direct OHLCV payload. Each candle should contain timestamp/open/high/low/close/volume.",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string"},
                        "open": {"type": "number"},
                        "high": {"type": "number"},
                        "low": {"type": "number"},
                        "close": {"type": "number"},
                        "volume": {"type": "number"},
                    },
                },
            },
        },
    },
}

FACTOR_ANALYSIS_SCHEMA = {
    "name": "factor_analysis",
    "description": "Analyze alpha factors by computing IC/IR statistics and a layered backtest from CSV inputs.",
    "parameters": {
        "type": "object",
        "properties": {
            "factor_csv": {"type": "string", "description": "Path to factor values CSV"},
            "return_csv": {"type": "string", "description": "Path to returns CSV"},
            "n_groups": {"type": "integer", "description": "Number of quantile groups", "default": 5},
            "output_dir": {"type": "string", "description": "Optional output directory for CSV/JSON artifacts"},
        },
        "required": ["factor_csv", "return_csv"],
    },
}

OPTIONS_PRICING_SCHEMA = {
    "name": "options_pricing",
    "description": "Compute Black-Scholes theoretical option price and Greeks.",
    "parameters": {
        "type": "object",
        "properties": {
            "spot": {"type": "number", "description": "Current underlying price"},
            "strike": {"type": "number", "description": "Strike price"},
            "expiry_days": {"type": "number", "description": "Days to expiry"},
            "risk_free_rate": {"type": "number", "description": "Annualized risk-free rate", "default": 0.05},
            "volatility": {"type": "number", "description": "Annualized volatility, e.g. 0.25"},
            "option_type": {"type": "string", "enum": ["call", "put"]},
        },
        "required": ["spot", "strike", "expiry_days", "volatility", "option_type"],
    },
}

PATTERN_RECOGNITION_SCHEMA = {
    "name": "pattern_recognition",
    "description": "Detect chart patterns in OHLCV data from a direct payload, CSV, or fetched candles.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Trading symbol if the tool should fetch candles itself"},
            "timeframe": {"type": "string", "description": "Timeframe used when fetching candles"},
            "interval": {"type": "string", "description": "Alias for timeframe"},
            "exchange": {"type": "string", "description": "Optional exchange hint"},
            "patterns": {"type": "string", "description": "Comma-separated pattern names or 'all'", "default": "all"},
            "window": {"type": "integer", "description": "Detection window size", "default": 10},
            "limit": {"type": "integer", "description": "Candle limit when fetching data", "default": 500},
            "ohlcv_csv": {"type": "string", "description": "Optional CSV path with OHLCV columns"},
            "ohlcv": {
                "type": "array",
                "description": "Optional direct OHLCV payload",
                "items": {"type": "object"},
            },
        },
    },
}


registry.register(
    name="data.resolve_symbol",
    toolset="motis-finance",
    schema=DATA_RESOLVE_SYMBOL_SCHEMA,
    handler=data_resolve_symbol_tool,
    is_async=True,
    emoji="🧩",
)

registry.register(
    name="data.ohlcv",
    toolset="motis-finance",
    schema=DATA_OHLCV_SCHEMA,
    handler=data_ohlcv_tool,
    is_async=True,
    emoji="📈",
    max_result_size_chars=100_000,
)

registry.register(
    name="data.ticker",
    toolset="motis-finance",
    schema=DATA_TICKER_SCHEMA,
    handler=data_ticker_tool,
    is_async=True,
    emoji="💹",
)

registry.register(
    name="data.orderbook",
    toolset="motis-finance",
    schema=DATA_ORDERBOOK_SCHEMA,
    handler=data_orderbook_tool,
    is_async=True,
    emoji="📚",
    max_result_size_chars=100_000,
)

registry.register(
    name="data.funding_rate",
    toolset="motis-finance",
    schema=DATA_FUNDING_RATE_SCHEMA,
    handler=data_funding_rate_tool,
    is_async=True,
    emoji="🪙",
    max_result_size_chars=100_000,
)

registry.register(
    name="data.open_interest",
    toolset="motis-finance",
    schema=DATA_OPEN_INTEREST_SCHEMA,
    handler=data_open_interest_tool,
    is_async=True,
    emoji="🏦",
    max_result_size_chars=100_000,
)

registry.register(
    name="macro.get_series",
    toolset="motis-finance",
    schema=MACRO_GET_SERIES_SCHEMA,
    handler=macro_get_series_tool,
    is_async=True,
    emoji="🌐",
    max_result_size_chars=100_000,
)

registry.register(
    name="equity.get_fundamentals",
    toolset="motis-finance",
    schema=EQUITY_GET_FUNDAMENTALS_SCHEMA,
    handler=equity_get_fundamentals_tool,
    is_async=True,
    emoji="🏛",
    max_result_size_chars=100_000,
)

registry.register(
    name="equity.get_earnings_calendar",
    toolset="motis-finance",
    schema=EQUITY_GET_EARNINGS_CALENDAR_SCHEMA,
    handler=equity_get_earnings_calendar_tool,
    is_async=True,
    emoji="🗓",
    max_result_size_chars=100_000,
)

registry.register(
    name="flows.get_connect",
    toolset="motis-finance",
    schema=FLOWS_GET_CONNECT_SCHEMA,
    handler=flows_get_connect_tool,
    is_async=True,
    emoji="🔁",
    max_result_size_chars=100_000,
)

registry.register(
    name="china.get_moneyflow",
    toolset="motis-finance",
    schema=CHINA_GET_MONEYFLOW_SCHEMA,
    handler=china_get_moneyflow_tool,
    is_async=True,
    emoji="🏮",
    max_result_size_chars=100_000,
)

registry.register(
    name="smc.structure",
    toolset="motis-finance",
    schema=SMC_STRUCTURE_SCHEMA,
    handler=smc_structure_tool,
    is_async=True,
    emoji="🧭",
    max_result_size_chars=100_000,
)

registry.register(
    name="factor_analysis",
    toolset="motis-finance",
    schema=FACTOR_ANALYSIS_SCHEMA,
    handler=factor_analysis_tool,
    emoji="📊",
    max_result_size_chars=100_000,
)

registry.register(
    name="options_pricing",
    toolset="motis-finance",
    schema=OPTIONS_PRICING_SCHEMA,
    handler=options_pricing_tool,
    emoji="🧮",
)

registry.register(
    name="pattern_recognition",
    toolset="motis-finance",
    schema=PATTERN_RECOGNITION_SCHEMA,
    handler=pattern_tool,
    is_async=True,
    emoji="📐",
    max_result_size_chars=100_000,
)

registry.register(
    name="pattern",
    toolset="motis-finance",
    schema={**PATTERN_RECOGNITION_SCHEMA, "name": "pattern", "description": "Compatibility alias for pattern_recognition."},
    handler=pattern_tool,
    is_async=True,
    emoji="📐",
    max_result_size_chars=100_000,
)
