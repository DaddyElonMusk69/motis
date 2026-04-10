"""Backtest infrastructure for operators.

Provides the bar-by-bar simulation engine, market-specific engines,
performance metrics, and the `run_backtest()` SDK function.

Ported from vibe_trading/agent/backtest/ — adapted as Motis infrastructure.
"""

from motis_agent.core.backtest.runner import run_backtest

__all__ = ["run_backtest"]
