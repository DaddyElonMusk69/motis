"""Backtest runner — the SDK entry point for backtesting strategies.

Provides `run_backtest()` as an async function callable from operator nodes
or the master agent. Wraps the existing BaseEngine pipeline.

Usage:
    from motis_agent.core.backtest import run_backtest

    metrics = await run_backtest(
        signal_fn=my_signal_function,
        symbols=["BTC/USDT:USDT"],
        start_date="2024-01-01",
        end_date="2025-01-01",
        engine="crypto",
        config={"leverage": 3, "initial_cash": 100_000},
    )
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from motis_agent.core.backtest.engines.base import BaseEngine, _align, _load_optimizer
from motis_agent.core.backtest.metrics import calc_bars_per_year, calc_metrics, by_symbol_stats, by_exit_reason_stats
from motis_agent.core.backtest.models import TradeRecord

logger = logging.getLogger(__name__)

# Market detection patterns (from vibe trading runner.py)
_MARKET_TO_ENGINE = {
    "crypto": "crypto",
    "a_share": "china_a",
    "us_equity": "global_equity",
    "hk_equity": "global_equity",
}


def _create_engine(engine_type: str, config: dict) -> BaseEngine:
    """Create the appropriate market engine.

    Args:
        engine_type: One of 'crypto', 'china_a', 'global_equity'.
        config: Backtest configuration.

    Returns:
        Configured BaseEngine subclass.
    """
    if engine_type == "crypto":
        from motis_agent.core.backtest.engines.crypto import CryptoEngine
        return CryptoEngine(config)
    elif engine_type == "china_a":
        from motis_agent.core.backtest.engines.china_a import ChinaAEngine
        return ChinaAEngine(config)
    elif engine_type == "global_equity":
        from motis_agent.core.backtest.engines.global_equity import GlobalEquityEngine
        return GlobalEquityEngine(config)
    else:
        # Default to crypto
        from motis_agent.core.backtest.engines.crypto import CryptoEngine
        return CryptoEngine(config)


async def run_backtest(
    *,
    data_map: Dict[str, pd.DataFrame],
    signal_fn: Callable[[Dict[str, pd.DataFrame]], Dict[str, pd.Series]],
    engine: str = "crypto",
    config: Optional[Dict[str, Any]] = None,
    interval: str = "1D",
    source: str = "okx",
    artifacts_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run a bar-by-bar backtest and return performance metrics.

    This is the primary SDK function for backtesting. It wraps the BaseEngine
    pipeline in an async interface.

    Args:
        data_map: Mapping of symbol → OHLCV DataFrame. Each DataFrame must have
            columns: open, high, low, close, volume. Index must be DatetimeIndex.
        signal_fn: A function that takes data_map and returns signal_map.
            signal_map maps symbol → pd.Series of weights [-1.0, 1.0].
            This is the strategy logic.
        engine: Market engine type: 'crypto', 'china_a', 'global_equity'.
        config: Engine configuration. Common keys:
            - initial_cash (float): Starting capital. Default 1_000_000.
            - leverage (float): Default leverage. Default 1.0.
            - maker_rate (float): Maker fee rate (crypto). Default 0.0002.
            - taker_rate (float): Taker fee rate (crypto). Default 0.0005.
            - slippage (float): Slippage rate. Default 0.0005.
            - optimizer (str): Weight optimizer name (optional).
        interval: Bar interval for annualization ('1m', '5m', '1H', '4H', '1D').
        source: Data source for annualization ('okx', 'yfinance', 'tushare').
        artifacts_dir: Optional path to write CSV artifacts (equity.csv, trades.csv, etc.).

    Returns:
        Metrics dict with keys:
            - final_value, total_return, annual_return, max_drawdown
            - sharpe, calmar, sortino
            - win_rate, profit_loss_ratio, profit_factor
            - max_consecutive_loss, avg_holding_days, trade_count
            - benchmark_return, excess_return, information_ratio
            - by_symbol: per-symbol stats
            - by_exit_reason: per-exit-reason stats
            - trades: list of trade dicts (if artifacts_dir not set)
    """
    backtest_config = {
        "initial_cash": 1_000_000,
        "leverage": 1.0,
        **(config or {}),
    }

    # Run signal generation (may be CPU-bound, run in thread)
    signal_map = await asyncio.to_thread(signal_fn, data_map)

    valid_codes = sorted(c for c in signal_map if c in data_map)
    if not valid_codes:
        logger.warning("No valid signals generated — no symbols overlap")
        return _empty_result(backtest_config.get("initial_cash", 1_000_000))

    # Create engine
    market_engine = _create_engine(engine, backtest_config)

    # Align data + signals, compute target weights
    opt_fn = _load_optimizer(backtest_config)
    dates, close_df, target_pos, ret_df = _align(
        data_map, signal_map, valid_codes, optimizer=opt_fn,
    )

    # Execute bar-by-bar (CPU-bound)
    await asyncio.to_thread(
        market_engine._execute_bars,
        dates, data_map, close_df, target_pos, valid_codes,
    )

    # Build equity series
    equity_series = pd.Series(
        [s.equity for s in market_engine.equity_snapshots],
        index=[s.timestamp for s in market_engine.equity_snapshots],
    )

    # Benchmark
    bench_ret = ret_df.mean(axis=1) if ret_df.shape[1] > 0 else pd.Series(0.0, index=dates)

    # Calculate metrics
    bars_per_year = calc_bars_per_year(interval, source)
    initial_cash = backtest_config.get("initial_cash", 1_000_000)
    metrics = calc_metrics(equity_series, market_engine.trades, initial_cash, bars_per_year, bench_ret)
    metrics["by_symbol"] = by_symbol_stats(market_engine.trades)
    metrics["by_exit_reason"] = by_exit_reason_stats(market_engine.trades)

    # Include trade list for programmatic access
    metrics["trades"] = [
        {
            "symbol": t.symbol,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "entry_time": str(t.entry_time),
            "exit_time": str(t.exit_time),
            "size": t.size,
            "pnl": round(t.pnl, 2),
            "pnl_pct": round(t.pnl_pct, 2),
            "exit_reason": t.exit_reason,
            "holding_bars": t.holding_bars,
        }
        for t in market_engine.trades
    ]

    # Write artifacts if requested
    if artifacts_dir is not None:
        bench_equity = initial_cash * (1 + bench_ret).cumprod()
        await asyncio.to_thread(
            market_engine._write_artifacts,
            artifacts_dir, data_map, dates, equity_series,
            bench_equity, bench_ret, target_pos, metrics, valid_codes,
        )
        logger.info("Backtest artifacts written to %s", artifacts_dir)

    return metrics


def _empty_result(initial_cash: float) -> Dict[str, Any]:
    """Return zero-valued metrics when no data or signals available."""
    return {
        "final_value": initial_cash,
        "total_return": 0, "annual_return": 0, "max_drawdown": 0,
        "sharpe": 0, "calmar": 0, "sortino": 0,
        "win_rate": 0, "profit_loss_ratio": 0, "profit_factor": 0,
        "max_consecutive_loss": 0, "avg_holding_days": 0, "trade_count": 0,
        "benchmark_return": 0, "excess_return": 0, "information_ratio": 0,
        "by_symbol": {}, "by_exit_reason": {}, "trades": [],
    }
