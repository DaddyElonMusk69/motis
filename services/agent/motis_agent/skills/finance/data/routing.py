"""
Data source routing — auto-fallback across 5 sources.
Adapted from Vibe-Trading's data-routing meta-skill.

Priority order per market:
  Crypto:      ccxt → okx → yfinance
  US/HK:       yfinance → akshare
  A-shares:    tushare → akshare
  Forex:       ccxt → akshare
  Futures:     ccxt → akshare
"""
from __future__ import annotations

import logging
from typing import Optional
import pandas as pd

log = logging.getLogger(__name__)


async def route_data_source(
    symbol: str,
    timeframe: str,
    limit: int = 500,
    exchange: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV data with automatic source fallback.

    Args:
        symbol: Unified symbol e.g. "BTC/USDT", "AAPL", "600519.SH"
        timeframe: e.g. "1m", "5m", "1h", "1d"
        limit: Number of candles
        exchange: Optional exchange hint for crypto

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    market_type = _infer_market_type(symbol)

    sources = _get_source_priority(market_type, exchange)

    for source_fn in sources:
        try:
            df = await source_fn(symbol=symbol, timeframe=timeframe, limit=limit)
            if df is not None and not df.empty:
                log.info(f"Fetched {symbol} from {source_fn.__name__}")
                return df
        except Exception as e:
            log.warning(f"{source_fn.__name__} failed for {symbol}: {e}")
            continue

    raise RuntimeError(
        f"All data sources failed for {symbol}. "
        "Check your API keys and network connectivity."
    )


def _infer_market_type(symbol: str) -> str:
    """Infer market type from symbol format."""
    if "/" in symbol:
        return "crypto"
    if symbol.endswith(".SH") or symbol.endswith(".SZ"):
        return "a_share"
    if symbol.endswith(".HK"):
        return "hk_equity"
    if "=" in symbol or len(symbol) == 6 and symbol.isalpha():
        return "forex"
    return "us_equity"


def _get_source_priority(market_type: str, exchange: Optional[str]):
    from motis_agent.skills.finance.data.ccxt_ohlcv import get_ohlcv_ccxt
    from motis_agent.skills.finance.data.yfinance_data import get_ohlcv_yfinance
    from motis_agent.skills.finance.data.akshare_data import get_ohlcv_akshare
    from motis_agent.skills.finance.data.okx_market import get_okx_market_data

    priorities = {
        "crypto":     [get_ohlcv_ccxt, get_okx_market_data, get_ohlcv_yfinance],
        "us_equity":  [get_ohlcv_yfinance, get_ohlcv_akshare],
        "hk_equity":  [get_ohlcv_yfinance, get_ohlcv_akshare],
        "a_share":    [get_ohlcv_akshare],  # tushare added if token set
        "forex":      [get_ohlcv_ccxt, get_ohlcv_akshare],
    }
    return priorities.get(market_type, [get_ohlcv_yfinance, get_ohlcv_akshare])
